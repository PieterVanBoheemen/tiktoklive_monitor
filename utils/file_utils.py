"""
File utilities for TikTok Live Stream Monitor
Cross-platform file operations and path handling
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional


def safe_create_directory(directory: Path) -> bool:
    """Safely create a directory with proper error handling"""
    logger = logging.getLogger(__name__)

    try:
        directory.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Failed to create directory {directory}: {e}")
        return False


def safe_read_json(file_path: Path) -> Optional[Dict[str, Any]]:
    """Safely read a JSON file with error handling"""
    logger = logging.getLogger(__name__)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.debug(f"JSON file not found: {file_path}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error reading JSON file {file_path}: {e}")
        return None


def safe_write_json(file_path: Path, data: Dict[str, Any]) -> bool:
    """Safely write data to a JSON file"""
    logger = logging.getLogger(__name__)

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error writing JSON file {file_path}: {e}")
        return False


def cleanup_file(file_path: Path) -> bool:
    """Safely remove a file"""
    logger = logging.getLogger(__name__)

    try:
        if file_path.exists():
            file_path.unlink()
            logger.debug(f"Removed file: {file_path}")
            return True
        return True  # File doesn't exist, consider it cleaned up
    except Exception as e:
        logger.warning(f"Could not remove file {file_path}: {e}")
        return False


def get_file_size_mb(file_path: Path) -> float:
    """Get file size in megabytes"""
    try:
        if file_path.exists():
            return file_path.stat().st_size / (1024 * 1024)
        return 0.0
    except:
        return 0.0
