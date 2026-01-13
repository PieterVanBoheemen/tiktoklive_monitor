"""
Main stream monitoring coordinator for TikTok Live Stream Monitor
Orchestrates all monitoring activities with graceful shutdown support
"""

import asyncio
import logging
import platform
from datetime import datetime
from typing import Dict, List, TYPE_CHECKING

from config.signal_handler import GracefulShutdownHandler
from .stream_checker import StreamChecker
from .stability_tracker import StabilityTracker
from recording.stream_recorder import StreamRecorder
from utils.session_logger import SessionLogger
from utils.status_manager import StatusManager
from utils.system_utils import check_system_limits, get_open_file_count

# TODO: Is this needed? Commenting it out and using ConfigManager without quotes works fine.
# There are no circular imports here.
if TYPE_CHECKING:
    from config.config_manager import ConfigManager


class StreamMonitor:
    """Main stream monitoring coordinator"""

    def __init__(self, config_manager: 'ConfigManager'):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.monitoring = True

        # Initialize components
        self.session_logger = SessionLogger()
        self.status_manager = StatusManager()
        self.stream_checker = StreamChecker(config_manager)
        self.stability_tracker = StabilityTracker(config_manager)
        self.recorder = StreamRecorder(config_manager, self.session_logger)

        # Initialize graceful shutdown handler
        self.shutdown_handler = GracefulShutdownHandler(self)

        # Platform detection
        self.is_windows = platform.system() == "Windows"

        # Log initialization
        self._log_initialization_info()

        # Check system limits
        self._check_system_resources()

        # Initial status update
        self.status_manager.update_status_file("starting")

    def _log_initialization_info(self):
        """Log initialization information"""
        if self.config_manager.session_id_override:
            self.logger.info("🔑 Using session ID from command line argument")
        elif self.config_manager.config['settings'].get('session_id'):
            self.logger.info("🔑 Using session ID from config file")
        else:
            self.logger.info("ℹ️  No session ID provided - only public streams accessible")

        # Log stability settings
        stability_threshold = self.config_manager.config['settings'].get('stability_threshold', 3)
        min_action_cooldown = self.config_manager.config['settings'].get('min_action_cooldown_seconds', 90)
        disconnect_delay = self.config_manager.config['settings'].get('disconnect_confirmation_delay_seconds', 30)

        self.logger.info(f"📊 Stability settings: threshold={stability_threshold}, cooldown={min_action_cooldown}s")
        self.logger.info(f"🔌 Disconnect confirmation delay: {disconnect_delay}s")

    def _check_system_resources(self):
        """Check and log system resource information"""
        max_concurrent = self.config_manager.config['settings']['max_concurrent_recordings']
        limits_info = check_system_limits(max_concurrent)

        if 'warning' in limits_info:
            self.logger.warning(f"⚠️  {limits_info['warning']}")

    async def monitor_streamers(self):
        """Main monitoring loop with enhanced stability tracking"""
        self.logger.info("🔍 Starting TikTok streamer monitor...")
        self.logger.info(f"🖥️  Platform: {platform.system()} {platform.release()}")

        enabled_streamers = self.config_manager.get_enabled_streamers()
        self.logger.info(f"📋 Monitoring {len(enabled_streamers)} streamers")

        self.logger.info("📄 Control files:")
        self.logger.info("   • Create 'stop_monitor.txt' to stop monitoring gracefully")
        self.logger.info("   • Create 'pause_monitor.txt' to pause monitoring temporarily")
        self.logger.info("   • Check 'monitor_status.txt' for current status")
        self.logger.info(f"   • Edit '{self.config_manager.config_file}' to modify streamers list (auto-reloads)")

        check_count = 0
        self.status_manager.update_status_file("monitoring", "Started monitoring loop")

        while self.monitoring:
            try:
                # Check for config file changes first
                config_changed = self.config_manager.check_config_changes()
                if config_changed:
                    # Update components with new config
                    self.stability_tracker.update_config(self.config_manager)
                    enabled_streamers = self.config_manager.get_enabled_streamers()

                # Check for control signals
                control_signal = self.shutdown_handler.check_control_signals()

                if control_signal.startswith("stop:"):
                    reason = control_signal.split(":", 1)[1]
                    self.logger.info(f"🛑 Received stop signal: {reason}")

                    # If it's a signal-based stop, we need to be extra graceful
                    if reason.startswith("signal_"):
                        self.logger.info("📹 Signal-based shutdown detected - ensuring video files are properly closed")

                    self.monitoring = False
                    self.status_manager.update_status_file("stopping", f"Stop signal received: {reason}")
                    break

                elif control_signal.startswith("pause:"):
                    duration = int(control_signal.split(":", 1)[1])
                    await self.shutdown_handler.handle_pause_signal(duration)
                    continue

                check_count += 1
                start_time = asyncio.get_event_loop().time()

                self.logger.debug(f"🔄 Check cycle #{check_count} - Checking {len(enabled_streamers)} streamers in parallel...")

                # Check all streamers in parallel
                live_status = await self.stream_checker.check_all_streamers_parallel(enabled_streamers)

                # Process results with stability checking
                actions_taken = []
                for username, is_live in live_status.items():
                    current_recording = self.recorder.is_recording(username)

                    # Use stability tracking to determine if action should be taken
                    should_act = self.stability_tracker.track_stream_stability(username, is_live, current_recording)

                    if should_act and is_live and not current_recording:
                        # Start recording
                        self.logger.info(f"🟢 {username} went LIVE! (stability confirmed)")
                        asyncio.create_task(self.recorder.start_recording(username))
                        actions_taken.append(f"{username}:LIVE")

                # Get current state for status updates
                currently_live = [username for username, is_live in live_status.items() if is_live]
                currently_recording = list(self.recorder.active_recordings.keys())
                pending_disconnects = list(self.recorder.pending_disconnects.keys())

                # Calculate check duration
                check_duration = asyncio.get_event_loop().time() - start_time

                # Update status file
                status_info = f"Check #{check_count}, duration: {check_duration:.1f}s"
                if pending_disconnects:
                    status_info += f", pending disconnects: {len(pending_disconnects)}"

                self.status_manager.update_status_file(
                    "monitoring",
                    status_info,
                    currently_recording,
                    pending_disconnects
                )

                # Status logging with cleaner output
                self._log_monitoring_status(
                    check_count, len(enabled_streamers), currently_live,
                    currently_recording, pending_disconnects, check_duration,
                    actions_taken, config_changed
                )

                # Check if we should continue
                if not self.monitoring:
                    break

                # Dynamic sleep with interrupt checking
                await self._sleep_with_monitoring_check(check_duration)

                # Periodic cleanup
                if check_count % 50 == 0:  # Every 50 cycles
                    await self._periodic_cleanup()

            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                self.status_manager.update_status_file("error", f"Error in monitoring loop: {e}")

                # Even on error, check if we should continue
                if not self.monitoring:
                    break

                await asyncio.sleep(30)

    def _log_monitoring_status(self, check_count: int, total_streamers: int,
                             currently_live: List[str], currently_recording: List[str],
                             pending_disconnects: List[str], check_duration: float,
                             actions_taken: List[str], config_changed: bool):
        """Log monitoring status with appropriate verbosity"""
        status_msg_parts = [f"📊 Checked {total_streamers} streamers"]

        if config_changed:
            status_msg_parts.append("🔄 Config reloaded")
        if currently_live:
            status_msg_parts.append(f"📺 Live: {', '.join(currently_live)}")
        else:
            status_msg_parts.append("💤 None live")
        if currently_recording:
            status_msg_parts.append(f"🎥 Recording: {', '.join(currently_recording)}")
        if pending_disconnects:
            status_msg_parts.append(f"🔌 Pending disconnects: {', '.join(pending_disconnects)}")
        status_msg_parts.append(f"⏱️ {check_duration:.1f}s")

        # Show status based on activity
        if actions_taken or config_changed or pending_disconnects or check_count % 5 == 0:
            self.logger.info(" | ".join(status_msg_parts))
            if actions_taken:
                self.logger.info(f"🎬 Actions: {', '.join(actions_taken)}")
        elif check_count % 20 == 0:  # Minimal status every 20 cycles
            self.logger.info(f"📊 Check #{check_count} | {total_streamers} streamers | {len(currently_live)} live | {len(currently_recording)} recording | ⏱️ {check_duration:.1f}s")

        # Performance warnings
        base_interval = self.config_manager.config['settings']['check_interval_seconds']
        if check_duration > base_interval * 0.8:  # If check takes more than 80% of interval
            self.logger.warning(f"⚠️  Check cycle took {check_duration:.1f}s (target: {base_interval}s)")

    async def _sleep_with_monitoring_check(self, check_duration: float):
        """Sleep between checks while remaining responsive to shutdown signals"""
        base_interval = self.config_manager.config['settings']['check_interval_seconds']
        adjusted_interval = max(10, base_interval - check_duration)  # Minimum 10 seconds

        # Sleep in smaller chunks to be more responsive to shutdown signals
        # TODO: check logic as adjusted_interval is always >=10 here and therefore the max is redundant
        sleep_chunks = max(1, int(adjusted_interval))
        for _ in range(sleep_chunks):
            if not self.monitoring:
                break
            await asyncio.sleep(min(1, adjusted_interval / sleep_chunks))

    async def _periodic_cleanup(self):
        """Perform periodic cleanup tasks"""
        try:
            # Clean up old stability data
            self.stability_tracker.cleanup_old_data()

            # Check for stale recordings
            await self.recorder.cleanup_stale_recordings()

            # Log file descriptor usage
            open_files = get_open_file_count()
            if open_files > 0:
                self.logger.debug(f"Current open file descriptors: {open_files}")
                if open_files > 200:  # Warning threshold
                    self.logger.warning(f"⚠️  High number of open files ({open_files})")

        except Exception as e:
            self.logger.debug(f"Error in periodic cleanup: {e}")

    async def run(self):
        """Run the monitor with enhanced graceful shutdown"""
        try:
            await self.monitor_streamers()
        except KeyboardInterrupt:
            self.logger.info("👋 Keyboard interrupt received - initiating graceful shutdown...")
            self.monitoring = False
        finally:
            # Enhanced cleanup process
            self.status_manager.update_status_file("shutting_down", "Cleaning up active recordings")

            # Perform graceful shutdown
            await self.shutdown_handler.graceful_shutdown()

            # Final cleanup
            self.status_manager.update_status_file("stopped", "Monitor shutdown complete")
            self.logger.info("🏁 Monitor shutdown complete")

    # Properties for backward compatibility and easy access
    @property
    def active_recordings(self) -> Dict[str, any]:
        """Get active recordings"""
        return self.recorder.active_recordings

    @property
    def pending_disconnects(self) -> Dict[str, any]:
        """Get pending disconnects"""
        return self.recorder.pending_disconnects

    def update_status_file(self, status: str, extra_info: str = ""):
        """Update status file (for backward compatibility)"""
        self.status_manager.update_status_file(
            status,
            extra_info,
            list(self.recorder.active_recordings.keys()),
            list(self.recorder.pending_disconnects.keys())
        )

    def get_monitoring_statistics(self) -> Dict[str, any]:
        """Get comprehensive monitoring statistics"""
        return {
            'platform': platform.system(),
            'monitoring': self.monitoring,
            'recordings': self.recorder.get_all_recording_stats(),
            'stability': self.stability_tracker.get_statistics(),
            'config': {
                'total_streamers': len(self.config_manager.config.get('streamers', {})),
                'enabled_streamers': len(self.config_manager.get_enabled_streamers()),
                'max_concurrent': self.config_manager.config['settings']['max_concurrent_recordings']
            },
            'system': {
                'open_files': get_open_file_count(),
                'platform': platform.system()
            }
        }
