"""
System utilities for TikTok Live Stream Monitor
Platform detection, resource limits, and system-specific configurations
"""

import asyncio
import logging
import os
import platform
import resource
import subprocess
# from pathlib import Path
from typing import Dict, Any
# from urllib import response  # ← ADD THIS MISSING IMPORT
import requests_async
from httpx import HTTPError, TimeoutException

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
                logger.warning(f"⚠️  Consider reducing to {max_concurrent} or increasing ulimit")
                limits_info['warning'] = f"May exceed system limits"
            else:
                limits_info['status'] = 'ok'

    except Exception as e:
        logger.debug(f"Could not check system limits: {e}")
        limits_info['error'] = str(e)

    return limits_info

async def check_rate_limit() -> Dict[str, Any]:
    """Check TikTok API rate limits using EulerStream endpoint"""
    logger = logging.getLogger(__name__)
    limits_info = {}

    api_key = os.environ.get("SIGN_API_KEY")
    host = os.environ.get('WHITELIST_AUTHENTICATED_SESSION_ID_HOST')
    

    if host == "tiktok.eulerstream.com":
        if api_key:
            url = f"https://tiktok.eulerstream.com/webcast/rate_limits?apiKey={api_key}"
        else:
            url = "https://tiktok.eulerstream.com/webcast/rate_limits"
    
        headers = {}
        async with requests_async.AsyncSession(timeout=30.0, headers=headers) as session:
            try:
                response = await session.get(url)
                logger.debug(f"📊 TikTok API Rate Limits reply: {response.text}")
                # debug_breakpoint()
                if response.status_code == 200:
                    data = response.json()
                    limits_info['rate_limits'] = data
                    # debug_breakpoint()
                    if data.get('code', 0) != 200:
                        limits_info['error'] = data.get('message', 'Unknown error')
                        logger.warning(f"⚠️  Rate limit error: {limits_info['error']}")
                    else:
                        remaining_day = data['day']['remaining']
                        day_reset = data['day']['reset_at']
                        # from datetime import datetime
                        # from dateutil.tz import gettz
                        # zone = os.environ.get('TIMEZONE', 'UTC') or 'Europe/Amsterdam'
                        # datetime.strptime(data['day']['reset_at'], '%Y-%m-%dT%H:%M:%S.%f%z').astimezone(gettz(zone)).isoformat(timespec='seconds')
                        remaining_hour = data['hour']['remaining']
                        hour_reset = data['hour']['reset_at']
                        remaining_min = data['minute']['remaining']
                        min_reset = data['minute']['reset_at']

                        limits_info['info'] = f'Remaining calls: Day: {remaining_day}{" (resets at " + day_reset + ")" if day_reset else ""}, ' \
                                            f'Hour: {remaining_hour}{" (resets at " + hour_reset + ")" if hour_reset else ""}, ' \
                                            f'Minute: {remaining_min}{" (resets at " + min_reset + ")" if min_reset else ""}'

                else:
                    logger.warning(f"⚠️  Could not fetch rate limits, status code: {response.status_code}")
                    limits_info['error'] = f"API status code: {response.status_code}"
            except HTTPError as e:
                err_msg = f"❌ Error fetching data from {url}: {e}"
                limits_info['error'] = err_msg
                logger.error(err_msg)
            except TimeoutError:
                err_msg = f"❌ Request to {url} timed out"
                limits_info['error'] = err_msg
                logger.error(err_msg)
    else:
        logger.debug("⚠️  Rate limit check skipped, not using EulerStream host")
        limits_info['info'] = "Rate limit check skipped, not using EulerStream host"

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

activate_breakpoint = False

def activate_debug_breakpoint():
    global activate_breakpoint
    activate_breakpoint = True


def debug_breakpoint():
    if activate_breakpoint:
        breakpoint()  # This will trigger the debugger only when activate_breakpoint is True


def check_disk_space(directory: str, min_free_gb: float = 10.0) -> Dict[str, Any]:
    """
    Check available disk space for a given directory

    Args:
        directory: Path to check disk space for
        min_free_gb: Minimum free space in GB required (default: 10GB)

    Returns:
        Dict with disk space info and status
    """
    logger = logging.getLogger(__name__)
    disk_info = {}

    try:
        # Get disk usage statistics
        if platform.system() == "Windows":
            import shutil
            total, used, free = shutil.disk_usage(directory)
        else:
            stat = os.statvfs(directory)
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bavail * stat.f_frsize
            used = total - free

        # Convert to GB
        total_gb = total / (1024**3)
        used_gb = used / (1024**3)
        free_gb = free / (1024**3)
        used_percent = (used / total) * 100

        disk_info = {
            'total_gb': round(total_gb, 2),
            'used_gb': round(used_gb, 2),
            'free_gb': round(free_gb, 2),
            'used_percent': round(used_percent, 2),
            'min_required_gb': min_free_gb,
            'sufficient_space': free_gb >= min_free_gb
        }

        if free_gb < min_free_gb:
            logger.warning(f"⚠️  Low disk space: {free_gb:.2f}GB free (minimum: {min_free_gb}GB)")
            disk_info['status'] = 'low_space'
        elif free_gb < min_free_gb * 1.5:
            logger.warning(f"💾 Disk space warning: {free_gb:.2f}GB free")
            disk_info['status'] = 'warning'
        else:
            disk_info['status'] = 'ok'

        logger.debug(f"💾 Disk space: {free_gb:.2f}GB free / {total_gb:.2f}GB total ({used_percent:.1f}% used)")

    except Exception as e:
        logger.error(f"❌ Failed to check disk space: {e}")
        disk_info['error'] = str(e)
        disk_info['status'] = 'error'

    return disk_info