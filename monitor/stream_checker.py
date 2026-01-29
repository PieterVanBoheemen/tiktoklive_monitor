"""
Stream status checking for TikTok Live Stream Monitor
Handles checking if streamers are live with retries and parallel processing
"""

import asyncio
import logging
import os
import random
from typing import Dict, TYPE_CHECKING

import httpx
from TikTokLive.client.client import TikTokLiveClient
from TikTokLive.client.web.routes.fetch_room_id_live_html import FailedParseRoomIdError
from TikTokLive.client.errors import UserNotFoundError


from utils.system_utils import debug_breakpoint
from utils.patches import patch_TikTokLiveClient

# if TYPE_CHECKING:
from config.config_manager import ConfigManager


class StreamChecker:
    """Handles checking stream status for multiple streamers"""

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.clients = {}

    async def check_streamer_status(self, username: str) -> bool:
        """Check if a streamer is currently live with enhanced error handling"""
        max_retries = self.config_manager.config['settings'].get('max_retries', 2)
        timeout = self.config_manager.config['settings'].get('individual_check_timeout', 20)

        for attempt in range(max_retries + 1):
            try:
                # Ensure environment variable is set for authenticated sessions
                whitelist_host = self.config_manager.config['settings'].get(
                    'whitelist_sign_server', 'tiktok.eulerstream.com'
                )
                os.environ['WHITELIST_AUTHENTICATED_SESSION_ID_HOST'] = whitelist_host

                # Reuse existing client if available
                if username in self.clients:
                    client = self.clients[username]['client']
                else:
                    client = TikTokLiveClient(unique_id=username)
                    patch_TikTokLiveClient(client)
                    self.clients[username] = {'client': client, 'failed': False}
                # Set session ID if available
                session_id = self.config_manager.get_session_id_for_streamer(username)
                tt_target_idc = self.config_manager.get_target_idc_for_streamer(username)

                if session_id:
                    client.web.set_session(session_id, tt_target_idc)

                # Check with timeout
                is_live = await asyncio.wait_for(client.is_live(), timeout=timeout)

                if attempt > 0:  # Log successful retry
                    self.logger.debug(f"✅ Status check succeeded for {username} on attempt {attempt + 1}")

                self.clients[username]['failed'] = False
                return is_live

            except asyncio.TimeoutError:
                if attempt < max_retries:
                    self.logger.warning(f"⚠️  Async timeout checking {username}, retrying... (attempt {attempt + 1}/{max_retries + 1})")
                    await asyncio.sleep(random.uniform(0.5,1))  # Minimal delay for retry
                    continue
                else:
                    self.logger.error(f"❌ Final asynch timeout checking {username} after {max_retries + 1} attempts")
                    self.clients[username]['failed'] = True
                    return False
            except httpx.ReadTimeout:
                if attempt < max_retries:
                    self.logger.warning(f"⚠️  Network timeout checking {username}, retrying... (attempt {attempt + 1}/{max_retries + 1})")
                    await asyncio.sleep(random.uniform(0.5,1))  # Minimal delay for retry
                    continue
                else:
                    self.logger.error(f"❌ Final network timeout checking {username} after {max_retries + 1} attempts")
                    self.clients[username]['failed'] = True
                    return False
            except httpx.ConnectError:
                if attempt < max_retries:
                    self.logger.warning(f"⚠️  Network connect error checking {username}, retrying... (attempt {attempt + 1}/{max_retries + 1})")
                    await asyncio.sleep(random.uniform(0.5,1))  # Minimal delay for retry
                    continue
                else:
                    self.logger.error(f"❌ Final network connect error checking {username} after {max_retries + 1} attempts")
                    self.clients[username]['failed'] = True
                    return False
            except httpx.ConnectTimeout:
                if attempt < max_retries:
                    self.logger.warning(f"⚠️  Network connect timeout checking {username}, retrying... (attempt {attempt + 1}/{max_retries + 1})")
                    await asyncio.sleep(random.uniform(0.5,1))  # Minimal delay for retry
                    continue
                else:
                    self.logger.error(f"❌ Final network connect timeout checking {username} after {max_retries + 1} attempts")
                    self.clients[username]['failed'] = True
                    return False
            except FailedParseRoomIdError as e:
                if attempt < max_retries:
                    self.logger.warning(f"⚠️  Failed to parse room ID for {username}: {e}, retrying... (attempt {attempt + 1}/{max_retries + 1})")
                    await asyncio.sleep(random.uniform(0.5,1))  # Minimal delay for retry
                    continue
                else:
                    self.logger.error(f"❌ Final failed to parse room ID for {username} after {max_retries + 1} attempts")
                    self.clients[username]['failed'] = True
                    return False
            except UserNotFoundError as e:
                if attempt < max_retries:
                    self.logger.warning(f"⚠️  User not found for {username}: {e}, retrying... (attempt {attempt + 1}/{max_retries + 1})")
                    await asyncio.sleep(random.uniform(0.5,1))  # Minimal delay for retry
                    continue
                else:
                    self.logger.error(f"❌ Final user not found for {username} after {max_retries + 1} attempts")
                    self.clients[username]['failed'] = True
                    return False
            except Exception as e:
                debug_breakpoint()
                if attempt < max_retries:
                    self.logger.warning(f"⚠️  Unknown error checking {username}: {e}, retrying... (attempt {attempt + 1}/{max_retries + 1})")
                    await asyncio.sleep(random.uniform(0.5,1))  # Minimal delay for retry
                    continue
                else:
                    self.logger.error(f"❌ Final unknown error checking {username}: {e}")
                    self.clients[username]['failed'] = True
                    return False

        return False

    async def check_all_streamers_parallel(self, enabled_streamers: Dict[str, dict]) -> Dict[str, bool]:
        """Check all streamers in parallel with batch processing for improved performance"""
        timeout = self.config_manager.config['settings'].get('individual_check_timeout', 20)
        batch_size = self.config_manager.config['settings'].get('batch_size', 50)

        async def check_single_streamer_with_timeout(username: str):
            try:
                # Use individual timeout per streamer
                is_live = await asyncio.wait_for(
                    self.check_streamer_status(username),
                    timeout=timeout + 5  # Add buffer to individual timeout
                )
                return username, is_live
            except asyncio.TimeoutError:
                self.logger.warning(f"Individual timeout for {username}")
                return username, False
            except Exception as e:
                # Catch-all for any unexpected errors, should not happen because check_streamer_status handles its own errors
                self.logger.warning(f"Error in parallel check for {username}: {e}")
                return username, False

        # Split streamers into batches
        streamers = [key for key in enabled_streamers.keys()]
        total_streamers = len(streamers)
        live_status = {}

        self.logger.info(f"🔄 Processing {total_streamers} streamers in batches of {batch_size}")

        total_batches = (total_streamers + batch_size - 1) // batch_size
        for i in range(0, total_streamers, batch_size):
            batch = streamers[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            
            self.logger.info(f"📦 Processing batch {batch_num}/{total_batches} ({len(batch)} streamers)")

            # Create tasks for current batch
            tasks = [
                check_single_streamer_with_timeout(username)
                for username in batch
            ]

            try:
                # Run batch tasks in parallel
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process batch results
                for result in results:
                    if isinstance(result, tuple):
                        username, is_live = result
                        live_status[username] = is_live
                        if not is_live:
                            self.logger.debug(f"🔴 {username} is offline")
                            if username in self.clients:
                                del self.clients[username]  # Remove client to avoid accumulating TikTokLiveClient instances
                    elif isinstance(result, Exception):
                        self.logger.warning(f"Task exception: {result}")

                # Brief pause between batches to avoid overwhelming the API
                if i + batch_size < total_streamers:
                    await asyncio.sleep(random.uniform(0.5,2))

            except Exception as e:
                self.logger.warning(f"⚠️  Error in batch {batch_num}: {e}")
                # Mark failed batch streamers as offline
                for username in batch:
                    live_status[username] = False

        # Check if all streamers failed and in case inform monitoring
        if len(self.clients) > 0 and not any(not self.clients[username]['failed'] for username in self.clients):
            live_status['_all_failed'] = True
        else:
            live_status['_all_failed'] = False

        return live_status

    def get_check_statistics(self, results: Dict[str, bool], duration: float) -> Dict[str, any]:
        """Get statistics about the check operation"""
        total_checked = len(results)
        currently_live = [username for username, is_live in results.items() if is_live]

        return {
            'total_checked': total_checked,
            'live_count': len(currently_live),
            'currently_live': currently_live,
            'duration_seconds': duration,
            'avg_time_per_check': duration / max(1, total_checked)
        }
