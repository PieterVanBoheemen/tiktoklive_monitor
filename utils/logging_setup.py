"""
Logging setup for TikTok Live Stream Monitor
Configures logging with appropriate levels and filters
"""

import logging
from datetime import datetime
from pathlib import Path


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Setup logging configuration"""
    # Create log file with date
    log_file = Path(f"monitor_{datetime.now().strftime('%Y%m%d')}.log")

    # Set log level based on verbose flag
    log_level = logging.DEBUG if verbose else logging.INFO

    if verbose:
        format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s'
    else:
        format='%(asctime)s - %(levelname)s - %(message)s'
        
    # Configure logging
    logging.basicConfig(
        level=log_level,
        format=format,
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    logger = logging.getLogger(__name__)

    # Filter noisy logs unless verbose mode
    if not verbose:
        # Silence verbose HTTP logs from TikTokLive and httpx
        logging.getLogger("TikTokLive").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)
    else:
        # In verbose mode, show more logs but still filter the noisiest ones
        # logging.getLogger("TikTokLive").setLevel(logging.INFO)
        # logging.getLogger("httpx").setLevel(logging.INFO)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)


    logger.info(f"📝 Logging initialized - Level: {logging.getLevelName(log_level)}")
    logger.info(f"📂 Log file: {log_file}")

    return logger
