"""
Stream recording coordinator for TikTok Live Stream Monitor
Coordinates video recording, CSV writing, and event handling
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
import random
from typing import Dict, Optional, Any

from TikTokLive.client.client import TikTokLiveClient
from TikTokLive.events import ConnectEvent, DisconnectEvent, CommentEvent, GiftEvent
from TikTokLive.events.custom_events import FollowEvent, ShareEvent, LiveEndEvent
from TikTokLive.events.proto_events import JoinEvent, LikeEvent

from .csv_writer import CSVWriter
from .video_handler import VideoHandler
from utils.patches import patch_TikTokLiveClient
from utils.system_utils import debug_breakpoint


class StreamRecorder:
    """Coordinates all aspects of stream recording"""

    def __init__(self, config_manager, session_logger):
        self.config_manager = config_manager
        self.session_logger = session_logger
        self.logger = logging.getLogger(__name__)

        # Initialize components
        output_dir = self.config_manager.config['settings']['output_directory']
        self.csv_writer = CSVWriter(output_dir)
        self.video_handler = VideoHandler(output_dir)

        # Track active recordings
        self.active_recordings: Dict[str, Dict[str, Any]] = {}
        self.pending_disconnects: Dict[str, Dict[str, Any]] = {}

    async def start_recording(self, username: str) -> bool:
        """Start recording a streamer"""
        if username in self.active_recordings:
            self.logger.warning(f"⚠️  Already recording {username}")
            return False

        max_concurrent = self.config_manager.config['settings']['max_concurrent_recordings']
        if len(self.active_recordings) >= max_concurrent:
            self.logger.info(f"Max concurrent recordings reached ({max_concurrent}). Skipping {username}")
            self.session_logger.log_session_event(
                username, 'recording_attempt', 'failed',
                error_message='Max concurrent recordings reached'
            )
            return False

        try:
            # Avoid too many simultaneous recordings since dict is not incremented until after await
            if username not in self.active_recordings:
                self.active_recordings[username] = {}
            else:
                self.logger.error(f"❌ Race condition detected: already recording {username}")
                return False
            self.logger.info(f"🔴 Starting recording for {username}")
            start_time = datetime.now()

            # Setup environment for authenticated sessions
            self._setup_authentication_environment()

            # Create TikTok client
            client = TikTokLiveClient(unique_id=username)
            # Override some methods for better error handling
            patch_TikTokLiveClient(client)
            self._configure_client_session(client, username)

            # Create CSV files
            csv_files = self.csv_writer.create_csv_files(username, start_time)

            # Initialize CSV writers
            if not self.csv_writer.initialize_csv_writers(username, csv_files):
                raise Exception("Failed to initialize CSV writers")

            # Store recording info
            recording_info = {
                'client': client,
                'start_time': start_time,
                'csv_files': csv_files,
                'stats': {'comments': 0, 'gifts': 0, 'follows': 0, 'shares': 0, 'joins': 0, 'likes': 0},
                'is_recording': True,
                'video_file': None
            }

            # Set up event handlers
            self._setup_event_handlers(client, username, recording_info)

            # Start the client
            await client.start(fetch_room_info=True)

            # Store in active recordings
            self.active_recordings[username] = recording_info

            self.session_logger.log_session_event(username, 'recording_started', 'success')
            self.logger.info(f"✅ Successfully started recording {username}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to start recording {username}: {e}")

            # Cleanup on failure
            # Remove from active recordings
            if username in self.active_recordings:
                # username should not be present in active_recordings, in case this happens there might be some cleanup
                # to be performed, but this case does not seem possible at the current state of the software
                self.logger.warning(f"⚠️  Deleting {username} from active recordings without cleanup (this should not happen)")
                del self.active_recordings[username]

            if self.csv_writer.is_writing(username):
                self.csv_writer.close_csv_writers(username)

            self.session_logger.log_session_event(
                username, 'recording_started', 'failed', error_message=str(e)
            )
            return False

    async def stop_recording(self, username: str, reason: str = "manual") -> bool:
        """Stop recording a streamer with enhanced graceful shutdown"""
        if username not in self.active_recordings:
            self.logger.warning(f"⚠️  No active recording found for {username}")
            return False

        # Cancel any pending disconnect confirmations
        if username in self.pending_disconnects:
            try:
                self.pending_disconnects[username]['task'].cancel()
                del self.pending_disconnects[username]
                self.logger.debug(f"Cancelled pending disconnect confirmation for {username}")
            except Exception as e:
                self.logger.debug(f"Error cancelling disconnect confirmation: {e}")

        recording_info = self.active_recordings[username]
        duration = (datetime.now() - recording_info['start_time']).total_seconds() / 60

        try:
            client = recording_info['client']

            # Mark recording as stopped to prevent new events from writing
            recording_info['is_recording'] = False
            self.logger.debug(f"Marked recording as stopped for {username}")

            # Stop video recording gracefully
            video_success = await self.video_handler.stop_video_recording(username, graceful=True)
            if not video_success:
                self.logger.warning(f"⚠️  Video recording stop had issues for {username}")

            # Disconnect client gracefully
            if hasattr(client, 'connected') and client.connected:
                self.logger.debug(f"Disconnecting client for {username}")
                try:
                    await asyncio.wait_for(client.disconnect(), timeout=15.0)
                except asyncio.TimeoutError:
                    self.logger.warning(f"⚠️  Disconnect timeout for {username}")
                except Exception as e:
                    self.logger.debug(f"Disconnect error for {username}: {e}")

                # Give time for events to finish processing
                await asyncio.sleep(random.uniform(3, 5))

            # Close CSV files
            csv_success = self.csv_writer.close_csv_writers(username)
            if not csv_success:
                self.logger.warning(f"⚠️  CSV closing had issues for {username}")

            # Log session info
            self.session_logger.log_session_event(
                username, f'recording_stopped_{reason}', 'success',
                duration, recording_info['stats']
            )

            self.logger.info(f"⏹️  Stopped recording {username} ({reason}) - Duration: {duration:.1f}m")
            self.logger.info(f"📊 Stats: {recording_info['stats']}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error stopping recording for {username}: {e}")
            return False
        finally:
            # Ensure recording is removed from active list
            if username in self.active_recordings:
                del self.active_recordings[username]

    async def force_stop_recording(self, username: str) -> bool:
        """Force stop recording (used during emergency shutdown)"""
        if username not in self.active_recordings:
            return True

        try:
            recording_info = self.active_recordings[username]
            recording_info['is_recording'] = False

            # Force stop video
            await self.video_handler.stop_video_recording(username, graceful=False)

            # Force close CSV files
            self.csv_writer.close_csv_writers(username)

            # Force disconnect client
            try:
                client = recording_info['client']
                if hasattr(client, 'disconnect'):
                    await asyncio.wait_for(client.disconnect(), timeout=5.0)
            except:
                pass

            return True
        except Exception as e:
            self.logger.error(f"❌ Error force stopping {username}: {e}")
            return False
        finally:
            if username in self.active_recordings:
                del self.active_recordings[username]

    def _setup_authentication_environment(self):
        """Setup authentication environment variables"""
        whitelist_host = self.config_manager.config['settings'].get(
            'whitelist_sign_server', 'tiktok.eulerstream.com'
        )
        os.environ['WHITELIST_AUTHENTICATED_SESSION_ID_HOST'] = whitelist_host

    def _configure_client_session(self, client: TikTokLiveClient, username: str):
        """Configure client with session ID if available"""
        session_id = self.config_manager.get_session_id_for_streamer(username)
        tt_target_idc = self.config_manager.get_target_idc_for_streamer(username)

        if session_id:
            client.web.set_session(session_id, tt_target_idc)
            self.logger.debug(f"🔑 Session ID configured for {username}")

    def _setup_event_handlers(self, client: TikTokLiveClient, username: str, recording_info: Dict[str, Any]):
        """Set up event handlers for the TikTok client"""

        @client.on(ConnectEvent)
        async def on_connect(event: ConnectEvent):
            self.logger.info(f"📡 Connected to {username}'s stream (Room: {client.room_id})")

            # Start video recording
            video_file = await self.video_handler.start_video_recording(
                client, username, recording_info['start_time']
            )
            if video_file:
                recording_info['video_file'] = video_file

        @client.on(LiveEndEvent)
        async def on_live_end(event: LiveEndEvent):
            self.logger.info(f"🔴 {username} stream ended (LiveEndEvent received)")
            # Cancel any pending disconnect confirmations
            if username in self.pending_disconnects:
                del self.pending_disconnects[username]
                self.logger.debug(f"Cancelled pending disconnect confirmation for {username}")
            # Immediately stop recording when we get the official stream end event
            await self.stop_recording(username, "live_end_event")

        @client.on(DisconnectEvent)
        async def on_disconnect(event: DisconnectEvent):
            disconnect_delay = self.config_manager.config['settings'].get(
                'disconnect_confirmation_delay_seconds', 30
            )
            self.logger.info(f"🔌 Disconnect event received for {username} - confirming in {disconnect_delay}s")

            # Don't immediately stop recording, but start confirmation process
            if username not in self.pending_disconnects:
                self.pending_disconnects[username] = {
                    'timestamp': datetime.now(),
                    'task': asyncio.create_task(self._handle_disconnect_confirmation(username))
                }

        @client.on(CommentEvent)
        async def on_comment(event: CommentEvent):
            if recording_info.get('is_recording', False):
                try:
                    self.csv_writer.write_comment(username, event)
                    recording_info['stats']['comments'] += 1
                except Exception as e:
                    self.logger.error(f"❌ Error writing comment from {event} for {username}: {e}")
                    debug_breakpoint()

        @client.on(GiftEvent)
        async def on_gift(event: GiftEvent):
            if recording_info.get('is_recording', False):
                try:
                    self.csv_writer.write_gift(username, event)
                    recording_info['stats']['gifts'] += 1
                except Exception as e:
                    self.logger.error(f"❌ Error writing gift from {event} for {username}: {e}")
                    debug_breakpoint()

        @client.on(FollowEvent)
        async def on_follow(event: FollowEvent):
            if recording_info.get('is_recording', False):
                try:
                    self.csv_writer.write_follow(username, event)
                    recording_info['stats']['follows'] += 1
                except Exception as e:
                    self.logger.error(f"❌ Error writing follow from {event} for {username}: {e}")  
                    debug_breakpoint()   

        @client.on(ShareEvent)
        async def on_share(event: ShareEvent):
            if recording_info.get('is_recording', False):
                try:
                    self.csv_writer.write_share(username, event)
                    recording_info['stats']['shares'] += 1
                except Exception as e:
                    self.logger.error(f"❌ Error writing share from {event} for {username}: {e}")
                    debug_breakpoint()

        @client.on(JoinEvent)
        async def on_join(event: JoinEvent):
            if recording_info.get('is_recording', False):
                try:
                    self.csv_writer.write_join(username, event)
                    recording_info['stats']['joins'] += 1
                except Exception as e:
                    self.logger.error(f"❌ Error writing join from {event} for {username}: {e}")
                    debug_breakpoint()

        @client.on(LikeEvent)
        async def on_like(event: LikeEvent):
            if recording_info.get('is_recording', False):
                try:
                    self.csv_writer.write_like(username, event)
                    recording_info['stats']['likes'] += 1
                except Exception as e:
                    self.logger.error(f"❌ Error writing like from {event} for {username}: {e}")
                    debug_breakpoint()

    async def _handle_disconnect_confirmation(self, username: str):
        """Handle disconnect confirmation after delay"""
        disconnect_delay = self.config_manager.config['settings'].get(
            'disconnect_confirmation_delay_seconds', 30
        )

        await asyncio.sleep(random.uniform(disconnect_delay, disconnect_delay*(1+1/5)))

        # Check if still in pending disconnects and still recording
        if username in self.pending_disconnects and username in self.active_recordings:
            try:
                # Double-check if actually offline by checking stream status
                from monitor.stream_checker import StreamChecker
                checker = StreamChecker(self.config_manager)
                is_live = await checker.check_streamer_status(username)

                if not is_live:
                    self.logger.info(f"🔴 {username} disconnect confirmed after {disconnect_delay}s - stopping recording")
                    await self.stop_recording(username, "disconnect_confirmed")
                else:
                    self.logger.info(f"🟢 {username} back online after disconnect - continuing recording")
            except Exception as e:
                self.logger.warning(f"⚠️  Error confirming disconnect for {username}: {e}")
                # Assume disconnect is real and stop recording
                await self.stop_recording(username, "disconnect_error")

        # Clean up pending disconnect
        if username in self.pending_disconnects:
            del self.pending_disconnects[username]

    async def stop_all_recordings(self, graceful: bool = True) -> bool:
        """Stop all active recordings"""
        if not self.active_recordings:
            return True

        self.logger.info(f"🎬 Stopping {len(self.active_recordings)} active recording(s)...")

        # Cancel all pending disconnect confirmations first
        for username, pending_info in list(self.pending_disconnects.items()):
            try:
                pending_info['task'].cancel()
                self.logger.debug(f"Cancelled pending disconnect for {username}")
            except:
                pass
        self.pending_disconnects.clear()

        # Stop all recordings
        stop_tasks = []
        for username in list(self.active_recordings.keys()):
            if graceful:
                task = asyncio.create_task(self.stop_recording(username, "shutdown"))
            else:
                task = asyncio.create_task(self.force_stop_recording(username))
            stop_tasks.append(task)

        # Wait for all recordings to stop
        success = True
        if stop_tasks:
            try:
                timeout = 45.0 if graceful else 15.0
                results = await asyncio.wait_for(
                    asyncio.gather(*stop_tasks, return_exceptions=True),
                    timeout=timeout
                )

                # Check results
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        self.logger.error(f"❌ Error stopping recording {i}: {result}")
                        success = False
                    elif not result:
                        success = False

            except asyncio.TimeoutError:
                self.logger.warning("⚠️  Timeout stopping recordings")
                success = False

        return success

    def get_active_recordings(self) -> Dict[str, Dict[str, Any]]:
        """Get information about active recordings"""
        return self.active_recordings.copy()

    def get_recording_stats(self, username: str) -> Optional[Dict[str, Any]]:
        """Get recording statistics for a specific user"""
        if username not in self.active_recordings:
            return None

        recording_info = self.active_recordings[username]
        duration = (datetime.now() - recording_info['start_time']).total_seconds()

        return {
            'username': username,
            'start_time': recording_info['start_time'].isoformat(),
            'duration_seconds': duration,
            'stats': recording_info['stats'].copy(),
            'video_file': str(recording_info.get('video_file', '')),
            'is_recording': recording_info.get('is_recording', False)
        }

    def get_all_recording_stats(self) -> Dict[str, Any]:
        """Get statistics for all active recordings"""
        stats = {
            'active_count': len(self.active_recordings),
            'pending_disconnects': len(self.pending_disconnects),
            'recordings': {}
        }

        for username in self.active_recordings:
            recording_stats = self.get_recording_stats(username)
            if recording_stats:
                stats['recordings'][username] = recording_stats

        return stats

    def is_recording(self, username: str) -> bool:
        """Check if a user is currently being recorded"""
        return username in self.active_recordings

    def get_active_count(self) -> int:
        """Get the number of active recordings"""
        return len(self.active_recordings)

    async def cleanup_stale_recordings(self):
        """Clean up any stale recordings"""
        stale_users = []

        for username, recording_info in self.active_recordings.items():
            try:
                client = recording_info['client']
                # Check if client is still connected
                if hasattr(client, 'connected') and not client.connected:
                    # Check how long it's been disconnected
                    if not recording_info.get('is_recording', True):
                        stale_users.append(username)
            except Exception as e:
                self.logger.debug(f"Error checking recording status for {username}: {e}")
                stale_users.append(username)

        # Clean up stale recordings
        for username in stale_users:
            self.logger.info(f"🧹 Cleaning up stale recording for {username}")
            await self.force_stop_recording(username)

    def update_recording_config(self, new_config: Dict[str, Any]):
        """Update recording configuration"""
        # Update any configuration-dependent settings
        # This method can be called when config is reloaded
        pass
