"""
Signal handling and graceful shutdown for TikTok Live Stream Monitor
Ensures recordings are properly finalized when the application is terminated
"""

import asyncio
import logging
import os
import platform
import random
import signal
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from monitor.stream_monitor import StreamMonitor


class GracefulShutdownHandler:
    """Handles graceful shutdown of the stream monitor"""

    def __init__(self, monitor: 'StreamMonitor'):
        self.monitor = monitor
        self.logger = logging.getLogger(__name__)
        self.is_windows = platform.system() == "Windows"
        self.stop_file = Path("stop_monitor.txt")
        self.pause_file = Path("pause_monitor.txt")
        self.shutdown_initiated = False

        self.setup_signal_handlers()
        self.cleanup_control_files()

    def setup_signal_handlers(self):
        """Set up signal handlers compatible with Windows"""
        try:
            if self.is_windows:
                # Windows supports limited signals
                signal.signal(signal.SIGINT, self.signal_handler)
                signal.signal(signal.SIGTERM, self.signal_handler)
                # SIGBREAK is Windows-specific
                if hasattr(signal, 'SIGBREAK'):
                    signal.signal(signal.SIGBREAK, self.signal_handler)
            else:
                # Unix-like systems support more signals
                signal.signal(signal.SIGINT, self.signal_handler)
                signal.signal(signal.SIGTERM, self.signal_handler)
                signal.signal(signal.SIGHUP, self.signal_handler)
        except Exception as e:
            self.logger.warning(f"⚠️  Could not set up all signal handlers: {e}")

    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        if self.shutdown_initiated:
            self.logger.info("🚨 Multiple shutdown signals received - forcing immediate exit")
            os._exit(1)

        self.shutdown_initiated = True
        signal_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
        self.logger.info(f"🛑 Received signal {signal_name} ({signum}). Initiating graceful shutdown...")

        # Create stop file to signal graceful shutdown
        try:
            with open(self.stop_file, 'w', encoding='utf-8') as f:
                f.write(f"signal_{signal_name}")
            self.logger.info("📄 Created stop file for graceful shutdown")
        except Exception as e:
            self.logger.error(f"❌ Could not create stop file: {e}")

        # Don't immediately stop monitoring - let the monitoring loop handle it gracefully
        self.monitor.monitoring = False

    def cleanup_control_files(self):
        """Remove any existing control files from previous runs"""
        for file_path in [self.stop_file, self.pause_file]:
            if file_path.exists():
                try:
                    file_path.unlink()
                    self.logger.debug(f"Removed existing control file: {file_path}")
                except Exception as e:
                    self.logger.warning(f"⚠️  Could not remove {file_path}: {e}")

    def check_control_signals(self) -> str:
        """Check for file-based control signals"""
        # Check for stop signal
        if self.stop_file.exists():
            try:
                with open(self.stop_file, 'r', encoding='utf-8') as f:
                    reason = f.read().strip() or "file_signal"
                return f"stop:{reason}"
            except Exception:
                return "stop:file_signal"

        # Check for pause signal
        if self.pause_file.exists():
            try:
                with open(self.pause_file, 'r', encoding='utf-8') as f:
                    duration = f.read().strip()
                    if duration.isdigit():
                        return f"pause:{duration}"
                    return "pause:60"  # Default 60 seconds
            except Exception:
                return "pause:60"

        return "continue"

    async def graceful_shutdown(self):
        """Perform graceful shutdown of all recordings"""
        self.logger.info("🏁 Starting graceful shutdown process...")

        # Cancel all pending disconnect confirmations first
        if hasattr(self.monitor, 'pending_disconnects'):
            for username, pending_info in list(self.monitor.pending_disconnects.items()):
                try:
                    pending_info['task'].cancel()
                    self.logger.debug(f"Cancelled pending disconnect for {username}")
                except Exception as e:
                    self.logger.debug(f"Error cancelling disconnect for {username}: {e}")
            self.monitor.pending_disconnects.clear()

        # Stop all active recordings gracefully
        if hasattr(self.monitor, 'active_recordings') and self.monitor.active_recordings:
            self.logger.info(f"🎬 Gracefully stopping {len(self.monitor.active_recordings)} active recording(s)...")

            # Stop all recordings in parallel with timeout
            shutdown_tasks = []
            for username in list(self.monitor.active_recordings.keys()):
                if hasattr(self.monitor, 'recorder'):
                    task = asyncio.create_task(
                        self.monitor.recorder.stop_recording(username, "graceful_shutdown")
                    )
                    shutdown_tasks.append(task)

            # Wait for all recordings to stop gracefully
            if shutdown_tasks:
                self.logger.info("⏳ Waiting for all recordings to stop gracefully...")
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*shutdown_tasks, return_exceptions=True),
                        timeout=45.0  # Generous timeout for video finalization
                    )
                    self.logger.info("✅ All recordings stopped gracefully")
                except asyncio.TimeoutError:
                    self.logger.warning("⚠️  Some recordings took longer than expected to stop")
                    # Force cleanup any remaining recordings
                    for username in list(self.monitor.active_recordings.keys()):
                        try:
                            if hasattr(self.monitor, 'recorder'):
                                await asyncio.wait_for(
                                    self.monitor.recorder.force_stop_recording(username),
                                    timeout=5.0
                                )
                        except Exception as e:
                            self.logger.error(f"❌ Error force-stopping {username}: {e}")
                except Exception as e:
                    self.logger.error(f"❌ Error during graceful shutdown: {e}")

        # Clean up control files
        self.cleanup_control_files()

        # Clean up any remaining video processes
        self._cleanup_video_processes()

        self.logger.info("🏁 Graceful shutdown complete")

    def _cleanup_video_processes(self):
        """Clean up any remaining video processes"""
        try:
            import psutil
            current_process = psutil.Process()
            children = current_process.children(recursive=True)

            for child in children:
                if 'ffmpeg' in child.name().lower():
                    self.logger.info(f"🧹 Cleaning up FFmpeg process: {child.pid}")
                    try:
                        child.terminate()  # Graceful termination
                        child.wait(timeout=5)
                        self.logger.debug(f"FFmpeg process {child.pid} terminated gracefully")
                    except psutil.TimeoutExpired:
                        self.logger.warning(f"⚠️  Force killing FFmpeg process: {child.pid}")
                        try:
                            child.kill()
                        except:
                            pass
                    except Exception as e:
                        self.logger.debug(f"Error terminating FFmpeg process {child.pid}: {e}")
        except ImportError:
            # psutil not available, skip cleanup
            self.logger.debug("psutil not available for process cleanup")
        except Exception as e:
            self.logger.debug(f"Error cleaning up video processes: {e}")

    async def handle_pause_signal(self, duration: int):
        """Handle pause signal"""
        self.logger.info(f"⏸️  Pausing monitoring for about {duration} seconds...")

        # Update status if monitor has status update capability
        if hasattr(self.monitor, 'update_status_file'):
            self.monitor.update_status_file("paused", f"Paused for {duration} seconds")

        # Remove pause file and wait
        if self.pause_file.exists():
            try:
                self.pause_file.unlink()
            except Exception as e:
                self.logger.warning(f"⚠️  Could not remove pause file: {e}")

        await asyncio.sleep(random.uniform(duration*(1-1/5), duration*(1+1/5)))
        self.logger.info("▶️  Resuming monitoring...")

        # Update status
        if hasattr(self.monitor, 'update_status_file'):
            self.monitor.update_status_file("monitoring", "Resumed after pause")
