"""
CSV data recording for TikTok Live Stream Monitor
Handles creation and management of CSV files for different event types
"""

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any, TextIO


class CSVWriter:
    """Manages CSV file creation and writing for stream events"""

    def __init__(self, output_directory: str):
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self.active_writers: Dict[str, Dict[str, Any]] = {}

    def get_csv_headers(self) -> Dict[str, list]:
        """Get CSV headers for different event types"""
        return {
            'comments': ['timestamp', 'user_id', 'nickname', 'comment', 'follower_count'],
            'gifts': ['timestamp', 'user_id', 'nickname', 'gift_name', 'repeat_count', 'streakable', 'streaking'],
            'follows': ['timestamp', 'user_id', 'nickname', 'follow_count', 'share_type', 'action'],
            'shares': ['timestamp', 'user_id', 'nickname', 'share_type', 'share_target', 'share_count', 'users_joined', 'action'],
            'joins': ['timestamp', 'user_id', 'nickname', 'count', 'is_top_user', 'enter_type', 'action', 'user_share_type', 'client_enter_source'],
            'likes': ['timestamp', 'user_id', 'nickname', 'count', 'total', 'color', 'effect_cnt']
        }

    def create_csv_files(self, username: str, start_time: datetime) -> Dict[str, Path]:
        """Create CSV files for a streamer recording session"""
        timestamp = start_time.strftime("%Y%m%d_%H%M%S")
        username_clean = username.replace("@", "")

        csv_files = {}
        for event_type in self.get_csv_headers().keys():
            filename = f"{username_clean}_{timestamp}_{event_type}.csv"
            csv_files[event_type] = self.output_directory / filename

        return csv_files

    def initialize_csv_writers(self, username: str, csv_files: Dict[str, Path]) -> bool:
        """Initialize CSV writers with headers and keep file handles open"""
        if username in self.active_writers:
            self.logger.warning(f"CSV writers already exist for {username}")
            return False

        csv_writers = {}
        opened_files = []  # Track opened files for cleanup on error
        headers = self.get_csv_headers()

        try:
            for csv_type, filepath in csv_files.items():
                # Open file and create writer
                file_handle = open(filepath, 'w', newline='', encoding='utf-8')
                opened_files.append(file_handle)  # Track for cleanup
                writer = csv.writer(file_handle)
                writer.writerow(headers[csv_type])

                # Store both file handle and writer for proper cleanup
                csv_writers[csv_type] = {
                    'file_handle': file_handle,
                    'writer': writer,
                    'filepath': filepath
                }

            self.active_writers[username] = csv_writers
            self.logger.debug(f"Initialized CSV writers for {username}")
            return True

        except Exception as e:
            # Clean up any files we managed to open
            self.logger.error(f"Error opening CSV files for {username}, cleaning up: {e}")
            for file_handle in opened_files:
                try:
                    file_handle.close()
                except:
                    pass
            return False

    def write_comment(self, username: str, event) -> bool:
        """Write a comment event to CSV"""
        return self._write_event(username, 'comments', [
            datetime.now().isoformat(),
            getattr(event.user, 'unique_id', ''),
            getattr(event.user, 'nickname', ''),
            event.comment,
            getattr(event.user, 'follower_count', 0)
        ])

    def write_gift(self, username: str, event) -> bool:
        """Write a gift event to CSV"""
        return self._write_event(username, 'gifts', [
            datetime.now().isoformat(),
            getattr(event.user, 'unique_id', ''),
            getattr(event.user, 'nickname', ''),
            event.gift.name,
            event.repeat_count,
            event.gift.streakable,
            event.streaking
        ])

    def write_follow(self, username: str, event) -> bool:
        """Write a follow event to CSV"""
        return self._write_event(username, 'follows', [
            datetime.now().isoformat(),
            getattr(event.user, 'unique_id', ''),
            getattr(event.user, 'nickname', ''),
            getattr(event, 'follow_count', 0),
            getattr(event, 'share_type', 0),
            getattr(event, 'action', 0)
        ])

    def write_share(self, username: str, event) -> bool:
        """Write a share event to CSV"""
        return self._write_event(username, 'shares', [
            datetime.now().isoformat(),
            getattr(event.user, 'unique_id', ''),
            getattr(event.user, 'nickname', ''),
            getattr(event, 'share_type', 0),
            getattr(event, 'share_target', 'unknown'),
            getattr(event, 'share_count', 0),
            getattr(event, 'users_joined', 0) or 0,
            getattr(event, 'action', 0)
        ])

    def write_join(self, username: str, event) -> bool:
        """Write a join event to CSV"""
        return self._write_event(username, 'joins', [
            datetime.now().isoformat(),
            getattr(event.user, 'unique_id', ''),
            getattr(event.user, 'nickname', ''),
            getattr(event, 'count', 0),
            getattr(event, 'is_top_user', False),
            getattr(event, 'enter_type', 0),
            getattr(event, 'action', 0),
            getattr(event, 'user_share_type', ''),
            getattr(event, 'client_enter_source', '')
        ])

    def write_like(self, username: str, event) -> bool:
        """Write a like event to CSV"""
        return self._write_event(username, 'likes', [
            datetime.now().isoformat(),
            getattr(event.user, 'unique_id', ''),
            getattr(event.user, 'nickname', ''),
            getattr(event, 'count', 0),
            getattr(event, 'total', 0),
            getattr(event, 'color', 0),
            getattr(event, 'effect_cnt', 0)
        ])

    def _write_event(self, username: str, event_type: str, row_data: list) -> bool:
        """Write an event to the appropriate CSV file"""
        if username not in self.active_writers:
            self.logger.warning(f"No active CSV writers for {username}")
            return False

        if event_type not in self.active_writers[username]:
            self.logger.warning(f"No {event_type} CSV writer for {username}")
            return False

        try:
            csv_info = self.active_writers[username][event_type]
            writer = csv_info['writer']
            file_handle = csv_info['file_handle']

            # Check if file is still open
            if file_handle.closed:
                self.logger.warning(f"CSV file for {username} {event_type} is closed")
                return False

            writer.writerow(row_data)
            file_handle.flush()  # Ensure data is written immediately
            return True

        except Exception as e:
            self.logger.error(f"Error writing {event_type} event for {username}: {e}")
            return False

    def close_csv_writers(self, username: str) -> bool:
        """Close all CSV writers for a username"""
        if username not in self.active_writers:
            self.logger.debug(f"No active CSV writers to close for {username}")
            return True

        success = True
        csv_writers = self.active_writers[username]

        for csv_type, csv_info in csv_writers.items():
            try:
                file_handle = csv_info['file_handle']
                if file_handle and not file_handle.closed:
                    file_handle.flush()  # Ensure all data is written
                    file_handle.close()
                    self.logger.debug(f"Closed {csv_type} CSV file for {username}")
                else:
                    self.logger.debug(f"{csv_type} CSV file already closed for {username}")
            except Exception as e:
                self.logger.error(f"Error closing {csv_type} CSV file for {username}: {e}")
                success = False

        # Remove from active writers
        del self.active_writers[username]
        return success

    def close_all_writers(self) -> bool:
        """Close all active CSV writers"""
        success = True
        usernames = list(self.active_writers.keys())

        for username in usernames:
            if not self.close_csv_writers(username):
                success = False

        return success

    def is_writing(self, username: str) -> bool:
        """Check if CSV writers are active for a username"""
        return username in self.active_writers

    def get_active_writers_count(self) -> int:
        """Get the number of active CSV writer sessions"""
        return len(self.active_writers)

    def get_csv_statistics(self, username: str) -> Optional[Dict[str, Any]]:
        """Get statistics about CSV files for a username"""
        if username not in self.active_writers:
            return None

        stats = {}
        csv_writers = self.active_writers[username]

        for csv_type, csv_info in csv_writers.items():
            filepath = csv_info['filepath']
            try:
                if filepath.exists():
                    file_size = filepath.stat().st_size
                    # Count lines (approximate event count)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        line_count = sum(1 for _ in f) - 1  # Subtract header

                    stats[csv_type] = {
                        'file_size_bytes': file_size,
                        'event_count': max(0, line_count),
                        'filepath': str(filepath)
                    }
                else:
                    stats[csv_type] = {
                        'file_size_bytes': 0,
                        'event_count': 0,
                        'filepath': str(filepath)
                    }
            except Exception as e:
                self.logger.debug(f"Error getting stats for {csv_type}: {e}")
                stats[csv_type] = {
                    'file_size_bytes': 0,
                    'event_count': 0,
                    'filepath': str(filepath),
                    'error': str(e)
                }

        return stats

    def cleanup_empty_files(self, username: str):
        """Clean up empty CSV files after recording"""
        if username not in self.active_writers:
            return

        csv_writers = self.active_writers[username]
        for csv_type, csv_info in csv_writers.items():
            filepath = csv_info['filepath']
            try:
                if filepath.exists():
                    file_size = filepath.stat().st_size
                    if file_size <= 100:  # Very small file, probably just headers
                        filepath.unlink()
                        self.logger.debug(f"Removed empty {csv_type} file for {username}")
            except Exception as e:
                self.logger.debug(f"Error cleaning up {csv_type} file: {e}")
