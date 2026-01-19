"""
Stream stability tracking for TikTok Live Stream Monitor
Prevents rapid cycling by requiring consistent status before taking action
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, TYPE_CHECKING

# if TYPE_CHECKING:
from config.config_manager import ConfigManager


class StabilityTracker:
    """Tracks stream status stability to prevent rapid cycling"""

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.stream_stability: Dict[str, Dict[str, Any]] = {}

        # Get stability settings from config
        self.stability_threshold = self.config_manager.config['settings'].get('stability_threshold', 3)
        self.min_action_cooldown = self.config_manager.config['settings'].get('min_action_cooldown_seconds', 90)

    def track_stream_stability(self, username: str, is_live: bool, current_recording: bool) -> bool:
        """Enhanced stream status stability tracking to prevent rapid cycling"""
        # now for all the checks
        now = datetime.now()

        if username not in self.stream_stability:
            self.stream_stability[username] = {
                'recent_checks': [],
                'last_action_time': now - timedelta(minutes=10),  # Allow immediate first action
                'consecutive_live': 0,
                'consecutive_offline': 0,
                'last_status': None
            }

        stability_info = self.stream_stability[username]
        

        # Keep only recent checks (last 10 minutes for better historical context)
        stability_info['recent_checks'] = [
            (timestamp, status) for timestamp, status in stability_info['recent_checks']
            if now - timestamp < timedelta(minutes=10)
        ]

        # Add current check
        stability_info['recent_checks'].append((now, is_live))

        # Update consecutive counters
        if is_live:
            stability_info['consecutive_offline'] = 0
            if stability_info['last_status'] == True:
                stability_info['consecutive_live'] += 1
            else:
                stability_info['consecutive_live'] = 1
        else:
            stability_info['consecutive_live'] = 0
            if stability_info['last_status'] == False:
                stability_info['consecutive_offline'] += 1
            else:
                stability_info['consecutive_offline'] = 1

        stability_info['last_status'] = is_live

        # For going live: need consecutive live checks
        if is_live and not current_recording:
            if stability_info['consecutive_live'] >= self.stability_threshold:
                # Check cooldown period
                time_since_action = now - stability_info['last_action_time']
                if time_since_action.total_seconds() >= self.min_action_cooldown:
                    stability_info['last_action_time'] = now
                    self.logger.debug(f"✅ {username} stability confirmed for LIVE after {stability_info['consecutive_live']} checks")
                    return True
                else:
                    remaining_cooldown = self.min_action_cooldown - time_since_action.total_seconds()
                    self.logger.debug(f"⏳ {username} stability confirmed but in cooldown ({remaining_cooldown:.0f}s remaining)")
                    return False
            else:
                self.logger.debug(f"📊 {username} LIVE tracking: {stability_info['consecutive_live']}/{self.stability_threshold}")
                return False

        # For going offline via polling: REMOVED - no longer use polling for termination
        # Only event-based termination (LiveEndEvent/DisconnectEvent) will stop recordings

        return False

    def update_config(self, config_manager: 'ConfigManager'):
        """Update stability settings when config changes"""
        self.config_manager = config_manager
        old_threshold = self.stability_threshold
        old_cooldown = self.min_action_cooldown

        self.stability_threshold = self.config_manager.config['settings'].get('stability_threshold', 3)
        self.min_action_cooldown = self.config_manager.config['settings'].get('min_action_cooldown_seconds', 90)

        if old_threshold != self.stability_threshold or old_cooldown != self.min_action_cooldown:
            self.logger.info(f"📊 Updated stability settings: threshold={self.stability_threshold}, cooldown={self.min_action_cooldown}s")

    def get_stability_info(self, username: str) -> Dict[str, Any]:
        """Get stability information for a streamer"""
        if username not in self.stream_stability:
            return {}

        stability_info = self.stream_stability[username]
        now = datetime.now()
        time_since_action = now - stability_info['last_action_time']

        return {
            'consecutive_live': stability_info['consecutive_live'],
            'consecutive_offline': stability_info['consecutive_offline'],
            'last_status': stability_info['last_status'],
            'recent_checks_count': len(stability_info['recent_checks']),
            'time_since_last_action_seconds': time_since_action.total_seconds(),
            'in_cooldown': time_since_action.total_seconds() < self.min_action_cooldown,
            'remaining_cooldown_seconds': max(0, self.min_action_cooldown - time_since_action.total_seconds())
        }

    def get_all_stability_info(self) -> Dict[str, Dict[str, Any]]:
        """Get stability information for all tracked streamers"""
        return {
            username: self.get_stability_info(username)
            for username in self.stream_stability.keys()
        }

    def reset_stability_for_user(self, username: str):
        """Reset stability tracking for a specific user"""
        if username in self.stream_stability:
            del self.stream_stability[username]
            self.logger.debug(f"Reset stability tracking for {username}")

    def cleanup_old_data(self):
        """Clean up old stability data"""
        now = datetime.now()
        cutoff_time = now - timedelta(hours=24)  # Keep data for 24 hours

        users_to_remove = []
        for username, stability_info in self.stream_stability.items():
            # Remove if no recent checks
            if not stability_info['recent_checks']:
                users_to_remove.append(username)
                continue

            # Remove if all checks are too old
            recent_checks = [
                (timestamp, status) for timestamp, status in stability_info['recent_checks']
                if timestamp > cutoff_time
            ]

            if not recent_checks:
                users_to_remove.append(username)
            else:
                # Update with only recent checks
                stability_info['recent_checks'] = recent_checks

        # Remove old users
        for username in users_to_remove:
            del self.stream_stability[username]
            self.logger.debug(f"Cleaned up old stability data for {username}")

        if users_to_remove:
            self.logger.debug(f"Cleaned up stability data for {len(users_to_remove)} users")

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about stability tracking"""
        total_tracked = len(self.stream_stability)
        currently_stable_live = 0
        in_cooldown = 0

        for username in self.stream_stability:
            info = self.get_stability_info(username)
            if info.get('consecutive_live', 0) >= self.stability_threshold:
                currently_stable_live += 1
            if info.get('in_cooldown', False):
                in_cooldown += 1

        return {
            'total_tracked_streamers': total_tracked,
            'currently_stable_live': currently_stable_live,
            'streamers_in_cooldown': in_cooldown,
            'stability_threshold': self.stability_threshold,
            'min_action_cooldown_seconds': self.min_action_cooldown
        }
