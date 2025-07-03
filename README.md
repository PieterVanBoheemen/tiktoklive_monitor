# TikTok Live Stream Monitor

🎥 **Automatically monitor and record TikTok live streams when your favorite creators go live!**

This tool monitors multiple TikTok streamers simultaneously and automatically starts recording when they begin streaming. It captures both video content and detailed interaction data (comments, gifts, follows, etc.) for research and archival purposes.

## ✨ Features

### 🎯 **Core Functionality**
- **Multi-streamer monitoring** - Track dozens of streamers simultaneously
- **Automatic recording** - Starts recording the moment someone goes live
- **Stability tracking** - Prevents false starts with configurable stability thresholds
- **Graceful shutdown** - Properly finalizes all recordings when stopped
- **Hot configuration reload** - Edit streamers list without restarting

### 📊 **Data Capture**
- **Video recording** - Full stream video in MP4 format
- **Interaction data** - Comments, gifts, follows, shares, joins, likes
- **CSV export** - All interaction data saved in structured format
- **Session logging** - Comprehensive monitoring statistics and events

### 🛡️ **Reliability Features**
- **Disconnect handling** - Smart reconnection and confirmation delays
- **Error recovery** - Robust error handling with automatic retries
- **Resource monitoring** - Tracks file descriptors and system limits
- **Cross-platform** - Works on Windows, macOS, and Linux

### 🔒 **Privacy & Authentication**
- **Session ID support** - Access age-restricted and private streams
- **Configurable data centers** - Choose optimal TikTok endpoints
- **Per-streamer authentication** - Individual session IDs per creator

## 🚀 Quick Start

### Prerequisites
```bash
# Install Python 3.8+ and pip
python3 --version

# Install required package
pip install TikTokLive
```

### Installation
```bash
# Clone the repository
git clone https://github.com/yourusername/tiktoklive_monitor.git
cd tiktoklive_monitor

# Install dependencies
pip install TikTokLive

# Create required directories
mkdir recordings
```

### First Run
```bash
# Start with default configuration (creates config file)
python3 main.py

# Edit the configuration file
nano streamers_config.json

# Start monitoring with your config
python3 main.py -c streamers_config.json
```

## 📖 Usage

### Basic Commands
```bash
# Monitor with default settings
python3 main.py

# Use custom configuration file
python3 main.py -c my_streamers.json

# Add session ID for authenticated access
python3 main.py -s your_session_id -c config.json

# Override settings from command line
python3 main.py -c config.json -i 30 -o /recordings --verbose
```

### Command Line Options
| Option | Description | Example |
|--------|-------------|---------|
| `-c, --config` | Configuration file path | `-c streamers.json` |
| `-s, --session-id` | TikTok session ID | `-s abc123xyz` |
| `-d, --data-center` | TikTok data center | `-d eu-ttp2` |
| `-i, --check-interval` | Check interval (seconds) | `-i 45` |
| `-o, --output-dir` | Output directory | `-o /recordings` |
| `-v, --verbose` | Enable verbose logging | `-v` |

### Runtime Control
Create these files to control the monitor while running:

```bash
# Stop monitoring gracefully
echo "user_requested" > stop_monitor.txt

# Pause for 60 seconds
echo "60" > pause_monitor.txt

# Check current status
cat monitor_status.txt
```

## ⚙️ Configuration

### Basic Configuration File
```json
{
  "streamers": {
    "creator1": {
      "username": "@creator1",
      "enabled": true,
      "session_id": null,
      "tags": ["gaming", "research"],
      "notes": "Popular gaming streamer"
    },
    "creator2": {
      "username": "@creator2",
      "enabled": true,
      "session_id": "custom_session_id",
      "tags": ["music"],
      "notes": "Music content creator"
    }
  },
  "settings": {
    "check_interval_seconds": 60,
    "max_concurrent_recordings": 5,
    "output_directory": "recordings",
    "session_id": "global_session_id",
    "stability_threshold": 3,
    "min_action_cooldown_seconds": 90
  }
}
```

### Configuration Options

#### Streamer Settings
- **`username`** - TikTok username (with @)
- **`enabled`** - Whether to monitor this streamer
- **`session_id`** - Individual session ID (overrides global)
- **`tags`** - Categories for organization
- **`notes`** - Description or notes

#### Global Settings
- **`check_interval_seconds`** - How often to check if streamers are live
- **`max_concurrent_recordings`** - Maximum simultaneous recordings
- **`stability_threshold`** - Consecutive checks before starting recording
- **`min_action_cooldown_seconds`** - Minimum time between actions
- **`disconnect_confirmation_delay_seconds`** - Time to wait before confirming disconnect

## 📂 Output Files

### Generated Files
```
recordings/
├── creator1_20240703_143022.mp4              # Video recording
├── creator1_20240703_143022_comments.csv     # Chat comments
├── creator1_20240703_143022_gifts.csv        # Gifts and donations
├── creator1_20240703_143022_follows.csv      # New followers
├── creator1_20240703_143022_shares.csv       # Stream shares
├── creator1_20240703_143022_joins.csv        # Viewer joins
└── creator1_20240703_143022_likes.csv        # Likes and reactions

monitoring_sessions_20240703.csv               # Session statistics
monitor_20240703.log                          # Application logs
monitor_status.txt                            # Current status
```

### CSV Data Format
Each interaction type is saved with timestamps and user details:

**Comments CSV:**
```csv
timestamp,user_id,nickname,comment,follower_count
2024-07-03T14:30:22,user123,StreamFan,Great stream!,1250
```

**Gifts CSV:**
```csv
timestamp,user_id,nickname,gift_name,repeat_count,streakable,streaking
2024-07-03T14:30:25,user456,Supporter,Rose,5,true,false
```

## 🔧 Advanced Usage

### Session ID Setup
To access age-restricted or private streams, you need a TikTok session ID:

1. **Get Session ID:**
   - Log into TikTok in your browser
   - Open Developer Tools (F12)
   - Go to Application/Storage → Cookies
   - Copy the `sessionid` value

2. **Add to Configuration:**
   ```json
   {
     "settings": {
       "session_id": "your_session_id_here"
     }
   }
   ```

3. **Or use command line:**
   ```bash
   python3 main.py -s your_session_id_here
   ```

### Multiple Data Centers
For better performance, you can specify TikTok data centers:

```bash
# US East Coast
python3 main.py -d us-eastred

# Europe
python3 main.py -d eu-ttp2

# Asia Pacific
python3 main.py -d sg-ttp1
```

### Production Deployment

#### Using systemd (Linux)
Create `/etc/systemd/system/tiktok-monitor.service`:

```ini
[Unit]
Description=TikTok Live Stream Monitor
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/tiktoklive_monitor
ExecStart=/usr/bin/python3 main.py -c production_config.json
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable tiktok-monitor
sudo systemctl start tiktok-monitor
```

#### Using Docker
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY . .
RUN pip install TikTokLive

CMD ["python3", "main.py", "-c", "config.json"]
```

Build and run:
```bash
docker build -t tiktok-monitor .
docker run -v $(pwd)/recordings:/app/recordings tiktok-monitor
```

## 📊 Monitoring & Analytics

### Session Statistics
The tool automatically generates session logs with statistics:

```csv
timestamp,username,action,status,duration_minutes,comments_count,gifts_count
2024-07-03T14:30:22,@creator1,recording_started,success,0,0,0
2024-07-03T15:45:10,@creator1,recording_stopped_live_end,success,74.8,342,89
```

### Status Monitoring
Check `monitor_status.txt` for real-time status:

```json
{
  "timestamp": "2024-07-03T14:30:22",
  "status": "monitoring",
  "active_recordings": 2,
  "currently_recording": ["@creator1", "@creator2"],
  "pending_disconnects": 0
}
```

## 🔍 Troubleshooting

### Common Issues

#### Import Errors
```bash
# Ensure all __init__.py files exist
touch config/__init__.py monitor/__init__.py recording/__init__.py utils/__init__.py

# Test imports
python3 -c "from monitor.stream_monitor import StreamMonitor; print('OK')"
```

#### Connection Issues
```bash
# Enable verbose logging
python3 main.py --verbose

# Check session ID validity
python3 main.py -s your_session_id --verbose
```

#### Permission Errors
```bash
# Linux/macOS: Fix recording directory permissions
chmod 755 recordings/
chown -R $USER:$USER recordings/

# Windows: Run as administrator if needed
```

#### High CPU Usage
- Increase `check_interval_seconds` in configuration
- Reduce `max_concurrent_recordings`
- Monitor system resources with `--verbose`

### Debug Mode
```bash
# Maximum verbosity for troubleshooting
python3 main.py --verbose -c config.json

# Check specific component
python3 -c "
from config.config_manager import ConfigManager
config = ConfigManager('config.json')
print('Config loaded successfully')
"
```

## 🤝 Contributing

### Development Setup
```bash
# Clone and setup
git clone https://github.com/yourusername/tiktoklive_monitor.git
cd tiktoklive_monitor

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install TikTokLive

### Code Structure
```
tiktoklive_monitor/
├── main.py                    # Entry point
├── config/                    # Configuration management
│   ├── config_manager.py      # Config loading and validation
│   └── signal_handler.py      # Graceful shutdown handling
├── monitor/                   # Core monitoring logic
│   ├── stream_monitor.py      # Main monitoring coordinator
│   ├── stream_checker.py      # Live status checking
│   └── stability_tracker.py   # Stream stability tracking
├── recording/                 # Recording functionality
│   ├── stream_recorder.py     # Recording coordinator
│   ├── csv_writer.py          # Data persistence
│   └── video_handler.py       # Video recording management
└── utils/                     # Utility modules
    ├── logging_setup.py       # Logging configuration
    ├── session_logger.py      # Session event logging
    ├── status_manager.py      # Status file management
    ├── system_utils.py        # System utilities
    └── file_utils.py          # File operations
```

### Submitting Changes
1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and test thoroughly
4. Commit with clear messages: `git commit -m "Add new feature"`
5. Push and create a Pull Request

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](https://mit-license.org) file for details.

## ⚠️ Disclaimer

This tool is for educational and research purposes only. Please ensure you:

- **Respect creators' content** and privacy
- **Follow TikTok's Terms of Service**
- **Comply with local laws** regarding content recording
- **Use responsibly** and ethically
- **Do not redistribute** recorded content without permission

The developers are not responsible for any misuse of this tool.

## 🙏 Acknowledgments

- **TikTokLive Python Library** - Core TikTok API functionality
- **Contributors** - Everyone who has contributed to this project
- **TikTok Creator Community** - For creating amazing content

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/pietervanboheemen/tiktoklive_monitor/issues)
- **Discussions:** [GitHub Discussions](https://github.com/pietervanboheemen/tiktoklive_monitor/discussions)
- **Documentation:** [Wiki](https://github.com/pietervanboheemen/tiktoklive_monitor/wiki)

---

⭐ **If this tool helps you, please give it a star on GitHub!** ⭐
