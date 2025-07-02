"""
Session logging for TikTok Live Stream Monitor
Handles CSV logging of monitoring events and statistics
"""

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


class SessionLogger:
    """Handles session event logging to CSV"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.session_log_file = Path(f"monitoring_sessions_{datetime.now().strftime('%Y%m%d')}.csv")
        self.init_session_log()

    def init_session_log(self):
        """Initialize the session monitoring log CSV"""
        if not self.session_log_file.exists():
            with open(self.session_log_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'username', 'action', 'status', 'duration_minutes',
                    'comments_count', 'gifts_count', 'follows_count', 'shares_count',
                    'joins_count', 'likes_count', 'tags', 'notes', 'error_message'
                ])

    def log_session_event(self, username: str, action: str, status: str = 'success',
                         duration_minutes: float = 0, stats: Optional[Dict[str, int]] = None,
                         error_message: str = '', streamer_config: Optional[Dict] = None):
        """Log monitoring events to CSV"""
        stats = stats or {}
        streamer_config = streamer_config or {}

        try:
            with open(self.session_log_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    username,
                    action,
                    status,
                    round(duration_minutes, 2),
                    stats.get('comments', 0),
                    stats.get('gifts', 0),
                    stats.get('follows', 0),
