"""
Status management for TikTok Live Stream Monitor
Handles status file updates and monitoring state tracking
"""

import json
import logging
import os
import platform
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


class StatusManager:
    """Manages status file updates and monitoring state"""

    def __init__(self, status_file: str = "monitor_status.txt"):
        self.status_file = Path(status_file)
        self.logger = logging.getLogger(__name__)

    def update_status_file(self, status: str, extra_info: str = "",
                          currently_recording: Optional[List[str]] = None,
                          pending_disconnects: Optional[List[str]] = None):
        """Update the status file with current monitoring state"""
        currently_recording = currently_recording or []
        pending_disconnects = pending_disconnects or []

        try:
            status_info = {
                "timestamp": datetime.now().isoformat(),
                "status": status,
                "active_recordings": len(currently_recording),
                "currently_recording": currently_recording,
                "pending_disconnects": len(pending_disconnects),
                "pending_disconnect_users": pending_disconnects,
                "extra_info": extra_info,
                "pid": os.getpid(),
                "platform": platform.system()
            }

            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(status_info, f, indent=2, ensure_ascii=False)

        except Exception as e:
            self.logger.debug(f"Could not update status file: {e}")

    def read_status_file(self) -> Optional[Dict[str, Any]]:
        """Read the current status from the status file"""
        try:
            if self.status_file.exists():
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
        except Exception as e:
            self.logger.debug(f"Could not read status file: {e}")
            return None

    def get_monitor_status(self) -> Dict[str, Any]:
        """Get comprehensive monitor status information"""
        status_data = self.read_status_file()

        if not status_data:
            return {
                "status": "unknown",
                "error": "Status file not found or unreadable"
            }

        # Add some computed fields
        try:
            timestamp = datetime.fromisoformat(status_data['timestamp'])
            age_seconds = (datetime.now() - timestamp).total_seconds()
            status_data['status_age_seconds'] = age_seconds
            status_data['is_recent'] = age_seconds < 300  # Within 5 minutes
        except:
            status_data['status_age_seconds'] = None
            status_data['is_recent'] = False

        return status_data

    def is_monitor_running(self) -> bool:
        """Check if the monitor appears to be running"""
        status = self.get_monitor_status()

        if 'error' in status:
            return False

        # Check if status is recent and not in a stopped state
        return (status.get('is_recent', False) and
                status.get('status') not in ['stopped', 'error', 'shutting_down'])

    def cleanup_status_file(self) -> bool:
        """Clean up the status file"""
        try:
            if self.status_file.exists():
                self.status_file.unlink()
                self.logger.debug(f"Cleaned up status file: {self.status_file}")
                return True
            return True
        except Exception as e:
            self.logger.warning(f"Could not clean up status file: {e}")
            return False

    def get_status_summary(self) -> str:
        """Get a human-readable status summary"""
        status = self.get_monitor_status()

        if 'error' in status:
            return "Monitor status: Unknown (status file not available)"

        current_status = status.get('status', 'unknown')
        active_recordings = status.get('active_recordings', 0)
        pending_disconnects = status.get('pending_disconnects', 0)

        summary = f"Monitor status: {current_status.title()}"

        if active_recordings > 0:
            summary += f" | {active_recordings} active recording(s)"

        if pending_disconnects > 0:
            summary += f" | {pending_disconnects} pending disconnect(s)"

        # Add age info
        age_seconds = status.get('status_age_seconds')
        if age_seconds is not None:
            if age_seconds < 60:
                summary += f" | Updated {int(age_seconds)}s ago"
            elif age_seconds < 3600:
                summary += f" | Updated {int(age_seconds/60)}m ago"
            else:
                summary += f" | Updated {int(age_seconds/3600)}h ago"

        return summary

    def log_status_change(self, old_status: str, new_status: str, details: str = ""):
        """Log when status changes"""
        if old_status != new_status:
            self.logger.info(f"Status changed: {old_status} → {new_status}")
            if details:
                self.logger.info(f"Details: {details}")
