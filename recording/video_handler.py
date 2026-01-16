"""
Video recording management for TikTok Live Stream Monitor
Handles starting, stopping, and graceful termination of video recordings
"""

import asyncio
import os
import logging
import subprocess
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from utils.system_utils import debug_breakpoint




class VideoHandler:
    """Manages video recording operations with graceful shutdown support"""

    def __init__(self, output_directory: str):
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self.active_video_processes: Dict[str, Dict[str, Any]] = {}

    def get_video_file_path(self, username: str, start_time: datetime) -> Path:
        """Generate video file path for a streamer"""
        timestamp = start_time.strftime("%Y%m%d_%H%M%S")
        username_clean = username.replace("@", "")
        return self.output_directory / f"{username_clean}_{timestamp}.mp4"

    def get_video_quality(self, room_info):
        """Determine video quality from room info"""
        from TikTokLive.client.web.routes.fetch_video_data import VideoFetchQuality

        record_data: dict = json.loads(room_info['stream_url']['live_core_sdk_data']['pull_data']['stream_data'])
        record_url_data: dict = record_data['data']
        if 'ld' in record_url_data.keys():
            quality : VideoFetchQuality = VideoFetchQuality.LD
        elif 'origin' in record_url_data.keys():
            quality : VideoFetchQuality = VideoFetchQuality.ORIGIN
        else:
            self.logger.error(f"Unable to set quality from {record_url_data.keys()}")
            raise ValueError("Unknown video quality in room info: {record_url_data.keys()}")
        return quality

    async def start_video_recording(self, client, username: str, start_time: datetime) -> Optional[Path]:
        """Start video recording for a streamer"""
        video_file = self.get_video_file_path(username, start_time)

        try:
            if hasattr(client.web, 'fetch_video_data'):
                # Get quality as sometimes the default quality is not available
                quality = self.get_video_quality(client.room_info)
                client.web.fetch_video_data.start(
                    output_fp=str(video_file),
                    room_info=client.room_info,
                    quality=quality,
                    output_format="mp4"
                )
                
                # Store video recording info
                self.active_video_processes[username] = {
                    'file_path': video_file,
                    'start_time': start_time,
                    'client': client,
                    'fetch_video_data': client.web.fetch_video_data
                }

                self.logger.info(f"🎥 Started video recording: {video_file}")
                return video_file
            else:
                self.logger.warning(f"⚠️  Video recording not available for {username}")
                return None

        except Exception as e:
            self.logger.error(f"Failed to start video recording for {username}: {e}")
            debug_breakpoint()
            return None

    async def stop_video_recording(self, username: str, graceful: bool = True) -> bool:
        """Stop video recording for a streamer with enhanced graceful shutdown"""
        if username not in self.active_video_processes:
            self.logger.debug(f"No active video recording found for {username}")
            return True

        video_info = self.active_video_processes[username]
        video_file = video_info['file_path']
        fetch_video_data = video_info['fetch_video_data']

        try:
            if hasattr(fetch_video_data, 'is_recording') and fetch_video_data.is_recording:
                if graceful:
                    self.logger.info(f"🎬 Gracefully stopping video recording for {username}...")
                    success = await self._graceful_video_stop(username, fetch_video_data, video_file)
                else:
                    self.logger.info(f"🎬 Force stopping video recording for {username}...")
                    success = await self._force_video_stop(username, fetch_video_data, video_file)

                # Check final video file status
                await self._check_video_file_status(video_file, username)

                return success
            else:
                self.logger.debug(f"Video recording for {username} was not active")
                return True

        except Exception as e:
            self.logger.error(f"Error stopping video recording for {username}: {e}")
            return False
        finally:
            # Clean up from active processes
            if username in self.active_video_processes:
                del self.active_video_processes[username]

    async def _graceful_video_stop(self, username: str, fetch_video_data, video_file: Path) -> bool:
        """Gracefully stop video recording with proper finalization time"""
        try:
            
            fetch_video_data.stop()

            # Wait for initial finalization
            self.logger.info(f"⏳ Waiting for video finalization for {username}...")
            await asyncio.sleep(5)  # Initial wait time

            # Check if the video process needs more time
            # TODO: where is this coming from? I cannot find _process attribute in fetch_video_data
            if hasattr(fetch_video_data, '_process') and fetch_video_data._process:
                process = fetch_video_data._process
                if process.poll() is None:  # Process still running
                    self.logger.info(f"📹 Video process still finalizing for {username}, waiting additional time...")

                    # Wait up to 20 more seconds for graceful termination
                    for i in range(20):
                        if process.poll() is not None:
                            self.logger.debug(f"Video process completed after {i+1} additional seconds")
                            break
                        await asyncio.sleep(1)

                    # If still running, send SIGTERM (not SIGKILL)
                    if process.poll() is None:
                        self.logger.warning(f"⚠️  Sending SIGTERM to video process for {username}")
                        try:
                            process.terminate()  # Graceful termination
                            await asyncio.sleep(5)  # Give time to clean up

                            # Final check - if still running, something is wrong
                            if process.poll() is None:
                                self.logger.error(f"❌ Video process for {username} not responding to SIGTERM")
                                return False
                        except Exception as e:
                            self.logger.error(f"Error terminating video process for {username}: {e}")
                            return False

            return True

        except Exception as e:
            self.logger.error(f"Error in graceful video stop for {username}: {e}")
            return False

    async def _force_video_stop(self, username: str, fetch_video_data, video_file: Path) -> bool:
        """Force stop video recording (used as fallback)"""
        try:
            fetch_video_data.stop()

            # Shorter wait time for force stop
            await asyncio.sleep(2)

            # If process exists, kill it immediately
            if hasattr(fetch_video_data, '_process') and fetch_video_data._process:
                process = fetch_video_data._process
                if process.poll() is None:
                    try:
                        process.kill()  # Immediate termination
                        self.logger.warning(f"⚠️  Force killed video process for {username}")
                    except:
                        pass

            return True

        except Exception as e:
            self.logger.error(f"Error in force video stop for {username}: {e}")
            return False

    async def _check_video_file_status(self, video_file: Path, username: str):
        """Check and log video file status after recording stops"""
        try:
            if video_file.exists():
                file_size = video_file.stat().st_size / (1024 * 1024)  # MB
                self.logger.info(f"📁 Video file size for {username}: {file_size:.1f} MB")

                if file_size < 0.1:  # Less than 100KB might indicate corruption
                    self.logger.warning(f"⚠️  Video file for {username} seems very small, might be corrupted")
                elif file_size < 1.0:  # Less than 1MB is suspicious for a stream
                    self.logger.warning(f"⚠️  Video file for {username} is quite small ({file_size:.1f} MB)")
                else:
                    self.logger.info(f"✅ Video file for {username} appears to be valid")
            else:
                self.logger.warning(f"⚠️  Video file not found for {username}: {video_file}")
        except Exception as e:
            self.logger.debug(f"Error checking video file status for {username}: {e}")

    async def stop_all_recordings(self, graceful: bool = True) -> bool:
        """Stop all active video recordings"""
        if not self.active_video_processes:
            return True

        self.logger.info(f"🎬 Stopping {len(self.active_video_processes)} video recording(s)...")

        success = True
        stop_tasks = []

        # Create tasks for stopping all recordings
        for username in list(self.active_video_processes.keys()):
            task = asyncio.create_task(self.stop_video_recording(username, graceful))
            stop_tasks.append(task)

        # Wait for all stops to complete
        if stop_tasks:
            try:
                timeout = 60.0 if graceful else 15.0
                results = await asyncio.wait_for(
                    asyncio.gather(*stop_tasks, return_exceptions=True),
                    timeout=timeout
                )

                # Check results
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        self.logger.error(f"Error stopping video recording {i}: {result}")
                        success = False
                    elif not result:
                        success = False

            except asyncio.TimeoutError:
                self.logger.warning("⚠️  Timeout stopping video recordings")
                success = False

        return success

    def get_active_recording_count(self) -> int:
        """Get the number of active video recordings"""
        return len(self.active_video_processes)

    def get_active_recordings(self) -> Dict[str, Dict[str, Any]]:
        """Get information about active video recordings"""
        return self.active_video_processes.copy()

    def is_recording(self, username: str) -> bool:
        """Check if a specific user is being recorded"""
        return username in self.active_video_processes

    async def cleanup_stale_processes(self):
        """Clean up any stale video processes"""
        stale_users = []

        for username, video_info in self.active_video_processes.items():
            try:
                fetch_video_data = video_info['fetch_video_data']
                if hasattr(fetch_video_data, '_process') and fetch_video_data._process:
                    process = fetch_video_data._process
                    if process.poll() is not None:  # Process has finished
                        self.logger.info(f"🧹 Cleaning up finished video process for {username}")
                        stale_users.append(username)
                elif not hasattr(fetch_video_data, 'is_recording') or not fetch_video_data.is_recording:
                    self.logger.info(f"🧹 Cleaning up inactive video recording for {username}")
                    stale_users.append(username)
            except Exception as e:
                self.logger.debug(f"Error checking video process for {username}: {e}")
                stale_users.append(username)

        # Remove stale processes
        for username in stale_users:
            if username in self.active_video_processes:
                del self.active_video_processes[username]

    def get_video_statistics(self) -> Dict[str, Any]:
        """Get statistics about video recordings"""
        stats = {
            'active_count': len(self.active_video_processes),
            'recordings': {}
        }

        for username, video_info in self.active_video_processes.items():
            duration = (datetime.now() - video_info['start_time']).total_seconds()
            stats['recordings'][username] = {
                'duration_seconds': duration,
                'file_path': str(video_info['file_path']),
                'start_time': video_info['start_time'].isoformat()
            }

        return stats
