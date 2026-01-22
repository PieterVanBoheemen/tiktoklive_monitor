"""
Configuration management for TikTok Live Stream Monitor
Handles loading, reloading, and validation of configuration files
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


class ConfigManager:
    """Manages configuration loading, reloading, and validation"""

    def __init__(self, args: Dict):
        self.config_file = args.config
        self.session_id_override = args.session_id
        self.logger = logging.getLogger(__name__)
        self.config = self.load_config()
        self.config_last_modified = self.get_config_mtime()
        
        # Apply session ID override if provided
        if self.session_id_override:
            self.config['settings']['session_id'] = self.session_id_override
            self.logger.info("🔑 Using session ID from command line argument")
        elif self.config['settings'].get('session_id'):
            self.logger.info("🔑 Using session ID from config file")
        else:
            self.logger.info("ℹ️  No session ID provided - only public streams accessible")

        # Apply command line argument overrides to configuration
        self.data_center = args.data_center
        if self.data_center:
            self.config['settings']['tt_target_idc'] = self.data_center
            self.logger.info(f"🌍 Data center overridden to: {self.data_center}")

        self.check_interval = args.check_interval
        if self.check_interval:
            self.config['settings']['check_interval_seconds'] = self.check_interval
            self.logger.info(f"⏱️  Check interval overridden to: {self.check_interval}s")

        self.output_dir = args.output_dir
        if self.output_dir:
            self.config['settings']['output_directory'] = self.output_dir
            self.logger.info(f"📁 Output directory overridden to: {self.output_dir}")


        # Setup environment variables for authenticated sessions
        self._setup_authentication()
    

    def _setup_authentication(self):
        """Setup authentication environment variables"""
        if self.config['settings'].get('session_id'):
            whitelist_host = self.config['settings'].get('whitelist_sign_server', 'tiktok.eulerstream.com')
            os.environ['WHITELIST_AUTHENTICATED_SESSION_ID_HOST'] = whitelist_host
            self.logger.info(f"🔐 Sign server whitelisted: {whitelist_host}")

    def get_default_config(self) -> dict:
        """Get the default configuration structure"""
        return {
            "streamers": {
                "@example_user1": {
                    "enabled": True,
                    "session_id": None,
                    "tt_target_idc": None,
                    "tags": ["research", "category1"],
                    "notes": "Example streamer for research"
                },
                "@example_user2": {
                    "enabled": True,
                    "session_id": None,
                    "tt_target_idc": None,
                    "tags": ["research", "category2"],
                    "notes": "Another example streamer"
                }
            },
            "settings": {
                "check_interval_seconds": 60,
                "max_concurrent_recordings": 5,
                "pause_monitoring_if_failure_seconds": 300,
                "output_directory": "recordings",
                "session_id": None,
                "tt_target_idc": "us-eastred",
                "whitelist_sign_server": "tiktok.eulerstream.com",
                "stability_threshold": 3,
                "min_action_cooldown_seconds": 90,
                "disconnect_confirmation_delay_seconds": 30,
                "individual_check_timeout": 20,
                "max_retries": 2
            }
        }

    def load_config(self) -> dict:
        """Load or create configuration file"""
        config_path = Path(self.config_file)

        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Validate and merge with defaults to ensure all required keys exist
                    return self._merge_with_defaults(config)
            except Exception as e:
                self.logger.error(f"❌ Error loading config: {e}")
                return self.get_default_config()
        else:
            # Create default config file
            default_config = self.get_default_config()
            self._save_config(default_config)
            self.logger.info(f"Created default config file: {config_path}")
            return default_config

    def _merge_with_defaults(self, config: dict) -> dict:
        """Merge loaded config with defaults to ensure all keys exist"""
        default_config = self.get_default_config()

        # Merge settings
        if 'settings' not in config:
            config['settings'] = {}

        for key, value in default_config['settings'].items():
            if key not in config['settings']:
                config['settings'][key] = value

        # Ensure streamers section exists
        if 'streamers' not in config:
            config['streamers'] = {}

        return config

    def _save_config(self, config: dict):
        """Save configuration to file"""
        config_path = Path(self.config_file)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    def get_config_mtime(self) -> float:
        """Get the modification time of the config file"""
        try:
            config_path = Path(self.config_file)
            if config_path.exists():
                return config_path.stat().st_mtime
            return 0.0
        except Exception:
            return 0.0

    def check_config_changes(self) -> bool:
        """Check if the config file has been modified and reload if needed"""
        try:
            current_mtime = self.get_config_mtime()
            if current_mtime > self.config_last_modified:
                self.logger.info("📝 Config file changed, reloading...")

                # Store old config for comparison
                old_streamers = set(self.config.get('streamers', {}).keys())
                old_enabled = {k: v.get('enabled', True) for k, v in self.config.get('streamers', {}).items()}

                # Reload config
                new_config = self.load_config()

                # TODO: decide what command line arguments should be reinstated when check_config_changes is run,
                # Preserve command line session ID override
                if self.session_id_override:
                    new_config['settings']['session_id'] = self.session_id_override

                if self.data_center:
                    self.config['settings']['tt_target_idc'] = self.data_center

                if self.check_interval:
                    self.config['settings']['check_interval_seconds'] = self.check_interval

                if self.output_dir:
                    self.config['settings']['output_directory'] = self.output_dir

                self.config = new_config
                self.config_last_modified = current_mtime

                # Re-setup authentication with new config
                self._setup_authentication()

                # Compare changes
                new_streamers = set(self.config.get('streamers', {}).keys())
                new_enabled = {k: v.get('enabled', True) for k, v in self.config.get('streamers', {}).items()}

                # Log changes
                added = new_streamers - old_streamers
                removed = old_streamers - new_streamers
                status_changed = []

                for streamer in old_streamers & new_streamers:
                    old_status = old_enabled.get(streamer, True)
                    new_status = new_enabled.get(streamer, True)
                    if old_status != new_status:
                        status = "enabled" if new_status else "disabled"
                        status_changed.append(f"{streamer}({status})")

                if added:
                    self.logger.info(f"➕ Added streamers: {', '.join(added)}")
                if removed:
                    self.logger.info(f"➖ Removed streamers: {', '.join(removed)}")
                if status_changed:
                    self.logger.info(f"🔄 Status changed: {', '.join(status_changed)}")

                total_enabled = len([s for s in self.config['streamers'].values() if s.get('enabled', True)])
                self.logger.info(f"📋 Now monitoring {total_enabled} streamers")

                return True

        except Exception as e:
            self.logger.error(f"❌ Error checking config changes: {e}")

        return False

    def get_enabled_streamers(self) -> Dict[str, dict]:
        """Get all enabled streamers from configuration"""
        return {
            k: v for k, v in self.config['streamers'].items()
            if v.get('enabled', True)
        }

    def get_streamers(self) -> Dict[str, dict]:
        """Get all streamers from configuration"""
        return self.config['streamers']
    
    def get_settings(self) -> Dict[str, dict]:
        """Get the current settings"""
        return self.config['settings']
    
    def enable_streamer(self, streamer:str) -> bool:
        """Enable a streamer"""
        if not streamer in self.config['streamers']:
            self.logger.error(f"Trying to enable a non-existing streamer {streamer}")
            return False
        else:
            self.config['streamers'][streamer]['enabled'] = True
        return True
    
    def disable_streamer(self, streamer:str) -> bool:
        """Disable a streamer"""
        if not streamer in self.config['streamers']:
            self.logger.error(f"Trying to disable a non-existing streamer {streamer}")
            return False
        else:
            self.config['streamers'][streamer]['enabled'] = False
        return True
    
    def set_streamer_priority(self, streamer:str, priority_group:str, priority:int) -> bool:
        if not streamer in self.config['streamers']:
            self.logger.error(f"Trying to set priority for a non-existing streamer {streamer}")
            return False
        else:
            self.config['streamers'][streamer]['priority_group'] = priority_group
            self.config['streamers'][streamer]['priority'] = priority
        return True

    def add_streamer(self, streamer:dict[str,any]) -> bool:
        """Get all streamers from configuration"""
        # get the only key in the dict, the username
        key = next(iter(streamer))
        if key in self.config['streamers']:
            self.logger.error(f"Trying to add already existing streamer {key}")
            return False
        else:
            self.config['streamers'][key] = streamer[key]
        return True
    
    def get_streamer_config(self, username: str) -> dict:
        """Get configuration for a specific streamer"""
        # keys are now the usernames, following line is commented out
        # streamer_key = username.replace('@', '')
        streamer_key = username
        return self.config['streamers'].get(streamer_key, {})

    def get_session_id_for_streamer(self, username: str) -> Optional[str]:
        """Get session ID for a specific streamer (falls back to global)"""
        streamer_config = self.get_streamer_config(username)
        return (streamer_config.get('session_id') or
                self.config['settings'].get('session_id'))

    def get_target_idc_for_streamer(self, username: str) -> Optional[str]:
        """Get target IDC for a specific streamer (falls back to global)"""
        streamer_config = self.get_streamer_config(username)
        return (streamer_config.get('tt_target_idc') or
                self.config['settings'].get('tt_target_idc'))

    def validate_config(self) -> bool:
        """Validate configuration structure and values"""
        try:
            # Check required sections
            if 'streamers' not in self.config or 'settings' not in self.config:
                return False

            # Check settings values
            settings = self.config['settings']
            required_settings = [
                'check_interval_seconds', 'max_concurrent_recordings',
                'output_directory', 'stability_threshold',
                'min_action_cooldown_seconds', 'disconnect_confirmation_delay_seconds'
            ]

            for setting in required_settings:
                if setting not in settings:
                    return False

            # Validate numeric settings
            numeric_settings = [
                'check_interval_seconds', 'max_concurrent_recordings',
                'stability_threshold', 'min_action_cooldown_seconds',
                'disconnect_confirmation_delay_seconds', 'individual_check_timeout',
                'max_retries'
            ]

            for setting in numeric_settings:
                if setting in settings and not isinstance(settings[setting], (int, float)):
                    return False

            return True

        except Exception as e:
            self.logger.error(f"❌ Config validation error: {e}")
            return False
