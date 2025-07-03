"""
Session logging for TikTok Live Stream Monitor
Handles CSV logging of monitoring events and statistics
"""

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any, List


class SessionLogger:
    """Handles session event logging to CSV"""

    def __init__(self, log_directory: str = "."):
        self.logger = logging.getLogger(__name__)
        self.log_directory = Path(log_directory)
        self.log_directory.mkdir(parents=True, exist_ok=True)

        # Create session log file with date
        self.session_log_file = self.log_directory / f"monitoring_sessions_{datetime.now().strftime('%Y%m%d')}.csv"
        self.init_session_log()

    def init_session_log(self):
        """Initialize the session monitoring log CSV"""
        if not self.session_log_file.exists():
            try:
                with open(self.session_log_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        'timestamp', 'username', 'action', 'status', 'duration_minutes',
                        'comments_count', 'gifts_count', 'follows_count', 'shares_count',
                        'joins_count', 'likes_count', 'tags', 'notes', 'error_message'
                    ])
                self.logger.debug(f"Initialized session log: {self.session_log_file}")
            except Exception as e:
                self.logger.error(f"Failed to initialize session log: {e}")

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
                    stats.get('shares', 0),
                    stats.get('joins', 0),
                    stats.get('likes', 0),
                    ';'.join(streamer_config.get('tags', [])),
                    streamer_config.get('notes', ''),
                    error_message
                ])
        except Exception as e:
            self.logger.error(f"Failed to log session event: {e}")

    def log_recording_started(self, username: str, streamer_config: Optional[Dict] = None):
        """Log when a recording starts"""
        self.log_session_event(
            username=username,
            action='recording_started',
            status='success',
            streamer_config=streamer_config
        )

    def log_recording_stopped(self, username: str, reason: str, duration_minutes: float,
                             stats: Optional[Dict[str, int]] = None,
                             streamer_config: Optional[Dict] = None):
        """Log when a recording stops"""
        self.log_session_event(
            username=username,
            action=f'recording_stopped_{reason}',
            status='success',
            duration_minutes=duration_minutes,
            stats=stats,
            streamer_config=streamer_config
        )

    def log_recording_failed(self, username: str, error_message: str,
                            streamer_config: Optional[Dict] = None):
        """Log when a recording fails to start"""
        self.log_session_event(
            username=username,
            action='recording_started',
            status='failed',
            error_message=error_message,
            streamer_config=streamer_config
        )

    def log_status_check(self, username: str, is_live: bool, check_duration_seconds: float = 0):
        """Log status check events (optional, for detailed monitoring)"""
        status = 'live' if is_live else 'offline'
        self.log_session_event(
            username=username,
            action='status_check',
            status=status,
            duration_minutes=check_duration_seconds / 60.0
        )

    def log_stability_action(self, username: str, action: str, consecutive_checks: int,
                           streamer_config: Optional[Dict] = None):
        """Log stability tracking actions"""
        self.log_session_event(
            username=username,
            action=f'stability_{action}',
            status='success',
            error_message=f'consecutive_checks:{consecutive_checks}',
            streamer_config=streamer_config
        )

    def log_disconnect_event(self, username: str, event_type: str,
                           streamer_config: Optional[Dict] = None):
        """Log disconnect-related events"""
        self.log_session_event(
            username=username,
            action=f'disconnect_{event_type}',
            status='info',
            streamer_config=streamer_config
        )

    def log_system_event(self, event_type: str, details: str = '', status: str = 'info'):
        """Log system-level events (startup, shutdown, errors)"""
        self.log_session_event(
            username='SYSTEM',
            action=event_type,
            status=status,
            error_message=details
        )

    def get_session_statistics(self, date: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics from session log for a specific date"""
        if date is None:
            date = datetime.now().strftime('%Y%m%d')

        log_file = self.log_directory / f"monitoring_sessions_{date}.csv"

        if not log_file.exists():
            return {'error': f'No log file found for date {date}'}

        stats = {
            'total_events': 0,
            'recordings_started': 0,
            'recordings_stopped': 0,
            'recordings_failed': 0,
            'total_recording_time_minutes': 0,
            'streamers': set(),
            'actions': {},
            'hourly_activity': {},
            'events_by_streamer': {}
        }

        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    stats['total_events'] += 1
                    username = row['username']
                    action = row['action']

                    if username != 'SYSTEM':
                        stats['streamers'].add(username)

                        # Track events by streamer
                        if username not in stats['events_by_streamer']:
                            stats['events_by_streamer'][username] = 0
                        stats['events_by_streamer'][username] += 1

                    # Track actions
                    if action not in stats['actions']:
                        stats['actions'][action] = 0
                    stats['actions'][action] += 1

                    # Track specific recording events
                    if action == 'recording_started' and row['status'] == 'success':
                        stats['recordings_started'] += 1
                    elif action.startswith('recording_stopped_'):
                        stats['recordings_stopped'] += 1
                        # Add recording duration
                        try:
                            duration = float(row['duration_minutes'])
                            stats['total_recording_time_minutes'] += duration
                        except (ValueError, TypeError):
                            pass
                    elif action == 'recording_started' and row['status'] == 'failed':
                        stats['recordings_failed'] += 1

                    # Track hourly activity
                    try:
                        timestamp = datetime.fromisoformat(row['timestamp'])
                        hour = timestamp.hour
                        if hour not in stats['hourly_activity']:
                            stats['hourly_activity'][hour] = 0
                        stats['hourly_activity'][hour] += 1
                    except:
                        pass

            # Convert set to list for JSON serialization
            stats['streamers'] = list(stats['streamers'])

            # Calculate average recording duration
            if stats['recordings_stopped'] > 0:
                stats['average_recording_duration_minutes'] = (
                    stats['total_recording_time_minutes'] / stats['recordings_stopped']
                )
            else:
                stats['average_recording_duration_minutes'] = 0

            return stats

        except Exception as e:
            self.logger.error(f"Error reading session statistics: {e}")
            return {'error': str(e)}

    def get_streamer_history(self, username: str, days: int = 7) -> List[Dict[str, Any]]:
        """Get recording history for a specific streamer over the last N days"""
        history = []

        for i in range(days):
            date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            date = date.replace(day=date.day - i)
            date_str = date.strftime('%Y%m%d')

            log_file = self.log_directory / f"monitoring_sessions_{date_str}.csv"

            if not log_file.exists():
                continue

            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)

                    for row in reader:
                        if row['username'] == username:
                            history.append({
                                'date': date_str,
                                'timestamp': row['timestamp'],
                                'action': row['action'],
                                'status': row['status'],
                                'duration_minutes': float(row['duration_minutes']) if row['duration_minutes'] else 0,
                                'stats': {
                                    'comments': int(row['comments_count']) if row['comments_count'] else 0,
                                    'gifts': int(row['gifts_count']) if row['gifts_count'] else 0,
                                    'follows': int(row['follows_count']) if row['follows_count'] else 0,
                                    'shares': int(row['shares_count']) if row['shares_count'] else 0,
                                    'joins': int(row['joins_count']) if row['joins_count'] else 0,
                                    'likes': int(row['likes_count']) if row['likes_count'] else 0,
                                },
                                'tags': row['tags'].split(';') if row['tags'] else [],
                                'notes': row['notes'],
                                'error_message': row['error_message']
                            })
            except Exception as e:
                self.logger.debug(f"Error reading history for {date_str}: {e}")
                continue

        # Sort by timestamp (most recent first)
        history.sort(key=lambda x: x['timestamp'], reverse=True)
        return history

    def export_session_data(self, output_file: str, date_range: Optional[List[str]] = None) -> bool:
        """Export session data to a different format (JSON)"""
        try:
            import json

            if date_range is None:
                # Export today's data by default
                date_range = [datetime.now().strftime('%Y%m%d')]

            all_data = []

            for date in date_range:
                log_file = self.log_directory / f"monitoring_sessions_{date}.csv"

                if not log_file.exists():
                    continue

                with open(log_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)

                    for row in reader:
                        # Convert to proper data types
                        processed_row = dict(row)
                        try:
                            processed_row['duration_minutes'] = float(row['duration_minutes']) if row['duration_minutes'] else 0
                            for stat_field in ['comments_count', 'gifts_count', 'follows_count', 'shares_count', 'joins_count', 'likes_count']:
                                processed_row[stat_field] = int(row[stat_field]) if row[stat_field] else 0
                            processed_row['tags'] = row['tags'].split(';') if row['tags'] else []
                        except (ValueError, TypeError):
                            pass  # Keep original string values if conversion fails

                        all_data.append(processed_row)

            # Write to JSON file
            output_path = Path(output_file)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Exported {len(all_data)} session records to {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error exporting session data: {e}")
            return False

    def cleanup_old_logs(self, days_to_keep: int = 30) -> int:
        """Clean up old log files, keeping only the specified number of days"""
        cleaned_count = 0
        cutoff_date = datetime.now().replace(day=datetime.now().day - days_to_keep)

        try:
            for log_file in self.log_directory.glob("monitoring_sessions_*.csv"):
                try:
                    # Extract date from filename
                    date_str = log_file.stem.split('_')[-1]  # Get the date part
                    file_date = datetime.strptime(date_str, '%Y%m%d')

                    if file_date < cutoff_date:
                        log_file.unlink()
                        cleaned_count += 1
                        self.logger.info(f"Cleaned up old log file: {log_file}")

                except (ValueError, IndexError) as e:
                    self.logger.debug(f"Could not parse date from {log_file}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error during log cleanup: {e}")

        if cleaned_count > 0:
            self.logger.info(f"Cleaned up {cleaned_count} old log files")

        return cleaned_count

    def get_log_file_path(self, date: Optional[str] = None) -> Path:
        """Get the path to the session log file for a specific date"""
        if date is None:
            date = datetime.now().strftime('%Y%m%d')
        return self.log_directory / f"monitoring_sessions_{date}.csv"

    def rotate_log_if_needed(self) -> bool:
        """Check if we need to create a new log file for today"""
        expected_file = self.get_log_file_path()

        if expected_file != self.session_log_file:
            self.session_log_file = expected_file
            self.init_session_log()
            self.logger.info(f"Rotated to new session log file: {self.session_log_file}")
            return True

        return False
