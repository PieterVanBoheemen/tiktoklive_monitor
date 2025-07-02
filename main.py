#!/usr/bin/env python3
"""
TikTok Live Stream Monitor - Main Entry Point
Automatically record TikTok streamers when they go live
"""

import sys
import platform
import argparse
import asyncio
import logging
from pathlib import Path

# Import our modular components
from config.config_manager import ConfigManager
from monitor.stream_monitor import StreamMonitor
from utils.logging_setup import setup_logging
from utils.system_utils import setup_platform_specific


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='TikTok Live Stream Monitor - Automatically record streamers when they go live',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py
  python main.py --session-id your_session_id_here
  python main.py --config custom_config.json --session-id abc123
  python main.py --session-id abc123 --data-center eu-ttp2

Windows Examples:
  python.exe main.py
  py -3 main.py --session-id your_session_id_here
        """
    )

    parser.add_argument(
        '--session-id', '-s',
        type=str,
        help='TikTok session ID for accessing age-restricted streams'
    )

    parser.add_argument(
        '--config', '-c',
        type=str,
        default='streamers_config.json',
        help='Path to configuration file (default: streamers_config.json)'
    )

    parser.add_argument(
        '--data-center', '-d',
        type=str,
        help='TikTok data center (e.g., us-eastred, eu-ttp2) - overrides config file'
    )

    parser.add_argument(
        '--check-interval', '-i',
        type=int,
        help='How often to check for live streams in seconds (overrides config)'
    )

    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        help='Output directory for recordings (overrides config)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    return parser.parse_args()


def print_startup_info(args):
    """Print startup information"""
    print("🚀 TikTok Live Stream Monitor Starting...")
    print(f"🖥️  Platform: {platform.system()} {platform.release()}")
    print(f"📁 Configuration file: {args.config}")

    if args.session_id:
        print("🔑 Session ID provided via command line")
    if args.data_center:
        print(f"🌍 Data center: {args.data_center}")
    if args.verbose:
        print("📝 Verbose logging enabled")

    print("📊 Session logs will be saved to: monitoring_sessions_[date].csv")
    print("📝 Debug logs will be saved to: monitor_[date].log")
    print("📄 Control options:")
    print("   • Create 'stop_monitor.txt' to stop monitoring gracefully")
    print("   • Create 'pause_monitor.txt' to pause monitoring temporarily")
    print("   • Check 'monitor_status.txt' for current status")
    print("   • Edit config file to modify streamers (auto-reloads)")

    if platform.system() == "Windows":
        print("⏹️  Press Ctrl+C or Ctrl+Break for immediate stop")
        print("💡 Windows users: Use 'py -3' instead of 'python3' if needed")
    else:
        print("⏹️  Press Ctrl+C for immediate stop")
    print()


def apply_command_line_overrides(config_manager, args):
    """Apply command line argument overrides to configuration"""
    logger = logging.getLogger(__name__)

    if args.data_center:
        config_manager.config['settings']['tt_target_idc'] = args.data_center
        logger.info(f"🌍 Data center overridden to: {args.data_center}")

    if args.check_interval:
        config_manager.config['settings']['check_interval_seconds'] = args.check_interval
        logger.info(f"⏱️  Check interval overridden to: {args.check_interval}s")

    if args.output_dir:
        config_manager.config['settings']['output_directory'] = args.output_dir
        logger.info(f"📁 Output directory overridden to: {args.output_dir}")


async def main():
    """Main entry point"""
    args = parse_args()

    # Setup platform-specific configurations
    setup_platform_specific()

    # Print startup information
    print_startup_info(args)

    try:
        # Initialize configuration manager
        config_manager = ConfigManager(
            config_file=args.config,
            session_id_override=args.session_id
        )

        # Setup logging
        logger = setup_logging(verbose=args.verbose)

        # Apply command line overrides
        apply_command_line_overrides(config_manager, args)

        # Create and run the stream monitor
        monitor = StreamMonitor(config_manager)
        await monitor.run()

    except FileNotFoundError as e:
        print(f"❌ Configuration file not found: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Monitor stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        if platform.system() == "Windows":
            print("💡 Windows troubleshooting:")
            print("   • Check Windows Defender/Antivirus isn't blocking the script")
            print("   • Ensure you have proper internet connectivity")
            print("   • Try running the script from Command Prompt as administrator")
        sys.exit(1)


if __name__ == "__main__":
    try:
        if platform.system() == "Windows":
            # Windows-specific event loop policy for better compatibility
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            except AttributeError:
                # Fallback for older Python versions
                pass

        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Monitor stopped by user")
        sys.exit(0)
