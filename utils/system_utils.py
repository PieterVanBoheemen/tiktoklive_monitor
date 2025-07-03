"""
System utilities for TikTok Live Stream Monitor
Platform detection, resource limits, and system-specific configurations
"""

import logging
import os
import platform
import resource
import subprocess
from pathlib import Path
from typing import Dict, Any  # ← ADD THIS MISSING IMPORT


def setup_platform_specific():
    """Setup platform-specific configurations"""
    logger = logging.getLogger(__name__)

    if platform.system() == "Windows":
        try:
            # Enable ANSI escape sequences on Windows 10+
            subprocess.run("", shell=True, check=True)

            # Set console to UTF-8 if possible
            try:
                import sys
                import codecs
                sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
                sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
                logger.debug("Windows UTF-8 console setup complete")
            except Exception as e:
                logger.debug(f"Windows UTF-8 setup failed: {e}")
        except Exception as e:
            logger.debug(f"Windows console setup failed: {e}")


def check_system_limits(max_concurrent_recordings: int) -> Dict[str, Any]:
    """Check system resource limits"""
    logger = logging.getLogger(__name__)
    limits_info = {}

    try:
        if platform.system() != "Windows":  # Unix-like systems
            soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
            limits_info['file_descriptors'] = {
                'soft_limit': soft_limit,
                'hard_limit': hard_limit
            }

            logger.info(f"📊 File descriptor limits: soft={soft_limit}, hard={hard_limit}")

            # Each recording uses ~6 files (5 CSV + 1 video), warn if approaching limit
            max_concurrent = soft_limit // 10  # Conservative estimate

            if max_concurrent_recordings > max_concurrent:
                logger.warning(f"⚠️  Configured max recordings ({max_concurrent_recordings}) may exceed system limits")
                logger.warning(f"   Consider reducing to {max_concurrent} or increasing ulimit")
                limits_info['warning'] = f"May exceed system limits"
            else:
                limits_info['status'] = 'ok'

    except Exception as e:
        logger.debug(f"Could not check system limits: {e}")
        limits_info['error'] = str(e)

    return limits_info


def get_open_file_count() -> int:
    """Get current number of open file descriptors (Unix only)"""
    try:
        if platform.system() != "Windows":
            import glob
            return len(glob.glob(f'/proc/{os.getpid()}/fd/*'))
        return 0
    except:
        return 0
