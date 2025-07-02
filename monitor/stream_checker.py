"""
Stream status checking for TikTok Live Stream Monitor
Handles checking if streamers are live with retries and parallel processing
"""

import asyncio
import logging
import os
from typing import Dict, TYPE_CHECKING

from TikTokLive.client.client import TikTokLiveClient

if TYPE_CHECKING:
    from config.config_manager import ConfigManager


class StreamChecker:
    """Handles checking stream status for multiple streamers"""

    def __init__(self, config_manager: 'ConfigManager'):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)

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

                client = TikTokLiveClient(unique_id=username)

                # Set session ID if available
                session_id = self.config_manager.get_session_id_for_streamer(username)
                tt_target_idc = self.config_manager.get_target_idc_for_streamer(username)

                if session_id:
                    client.web.set_session(session_id, tt_target_idc)

                # Check with timeout
                is_live = await asyncio.wait_for(client.is_live(), timeout=timeout)

                if attempt > 0:  # Log successful retry
                    self.logger.debug(f"✅ Status check succeeded for {username} on attempt {attempt + 1}")

                return is_live

            except asyncio.TimeoutError:
                if attempt < max_retries:
                    self.logger.debug(f"⏱️ Timeout checking {username}, retrying... (attempt {attempt + 1}/{max_retries + 1})")
                    await asyncio.sleep(3 + attempt)  # Progressive backoff
                    continue
                else:
                    self.logger.debug(f"⏱️ Final timeout checking {username} after {max_retries + 1} attempts")
                    return False
            except Exception as e:
                if attempt < max_retries:
                    self.logger.debug(f"⚠️ Error checking {username}: {e}, retrying... (attempt {attempt + 1}/{max_retries + 1})")
                    await asyncio.sleep(3 + attempt)  # Progressive backoff
                    continue
                else:
                    self.logger.debug(f"❌ Final error checking {username}: {e}")
                    return False

        return False

    async def check_all_streamers_parallel(self, enabled_streamers: Dict[str, dict]) -> Dict[str, bool]:
        """Check all streamers in parallel with improved error handling"""
        timeout = self.config_manager.config['settings'].get('individual_check_timeout', 20)

        async def check_single_streamer_with_timeout(streamer_key: str, streamer_config: dict):
            username = streamer_config['username']
            try:
                # Use individual timeout per streamer
                is_live = await asyncio.wait_for(
                    self.check_streamer_status(username),
                    timeout=timeout + 5  # Add buffer to individual timeout
                )
                return username, is_live
            except asyncio.TimeoutError:
                self.logger.debug(f"Individual timeout for {username}")
                return username, False
            except Exception as e:
                self.logger.debug(f"Error in parallel check for {username}: {e}")
                return username, False

        # Create tasks for all streamers
        tasks = [
            check_single_streamer_with_timeout(streamer_key, streamer_config)
            for streamer_key, streamer_config in enabled_streamers.items()
        ]

        live_status = {}

        try:
            # Run all tasks in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for result in results:
                if isinstance(result, tuple):
                    username, is_live = result
                    live_status[username] = is_live
                elif isinstance(result, Exception):
                    self.logger.debug(f"Task exception: {result}")

            return live_status

        except Exception as e:
            self.logger.warning(f"⚠️ Error in parallel checking: {e}")
            # Return False for any streamers we couldn't check
            return {config['username']: False for config in enabled_streamers.values()}

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
