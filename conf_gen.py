import os
import random
import re
import time
import argparse
from bs4 import BeautifulSoup

PRIORITY_GROUPS = ["high", "medium", "low"]

TEMPLATE_STREAMERS = {
    "KEY": {
      "enabled": True,
      "session_id": None,
      "tt_target_idc": None,
      "tags": [
        "research",
        "automatic"
      ],
      "notes": "Added automatically"
    }
}

TEMPLATE_CONFIG = {
  "streamers": {},
  "settings": {
    "check_interval_seconds": 60,
    "max_concurrent_recordings": 15,
    "pause_monitoring_if_failure_seconds": 300,
    "output_directory": "recordings",
    "session_id": "4d1644a8b567dee2cdd8eceb95bbb32b",
    "tt_target_idc": "us-eastred",
    "whitelist_sign_server": "tiktok.eulerstream.com",
    "stability_threshold": 3,
    "min_action_cooldown_seconds": 90,
    "disconnect_confirmation_delay_seconds": 30,
    "individual_check_timeout": 20,
    "max_retries": 2
  }
}

def extract_usernames_from_live(sourcefile):
    with open(sourcefile, encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    usernames = set()
    for a in soup.find_all("a", href=True):
        m = re.match(r"^/@([A-Za-z0-9._]+)", a["href"])
        if m:
            usernames.add(m.group(1))

    return sorted(usernames)

def extract_visible_text(sourcefile):
    with open(sourcefile, encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    texts = []
    for tag in soup.find_all(["h1", "h2", "span", "p"]):
        t = tag.get_text(strip=True)
        if len(t) > 5:
            texts.append(t)
    return " ".join(texts)


def main(args):
    usernames = extract_usernames_from_live(args.source)
    print(f"Found {len(usernames)} usernames from Live page\n")

    conf_json = TEMPLATE_CONFIG.copy()
    
    if args.max_concur != -1:
        conf_json['settings']['max_concurrent_recordings'] = args.max_concur
    else:
        conf_json['settings']['max_concurrent_recordings'] = len(usernames)
    
    if args.priority:
        priorities = [0 for _ in range(len(PRIORITY_GROUPS))]

    for username in usernames:
        
        full_username = f"@{username}"
        conf_json["streamers"][full_username] = TEMPLATE_STREAMERS["KEY"].copy()
        if args.priority:
            rnd_int = random.randint(0, len(PRIORITY_GROUPS)-1)
            conf_json["streamers"][full_username]["priority_group"] = PRIORITY_GROUPS[rnd_int]
            conf_json["streamers"][full_username]["priority"] = priorities[rnd_int]
            priorities[rnd_int] += 1

    with open(args.config, "w", encoding="utf-8") as f:
        import json
        json.dump(conf_json, f, indent=2)
    print(f"\nConfiguration saved to {args.config}")


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(
        description='Config File generator for TikTok Live Stream Monitor',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python conf_gen.py
  python conf_gen.py --source html_file_source --config my_auto_config.json --max-concur 20
"""
    )

    parser.add_argument(
        '--source', '-s',
        type=str,
        default='live.html',
        help='HTML filename from TikTok Live webpage'
    )

    parser.add_argument(
        '--config', '-c',
        type=str,
        default='streamers_auto_config.json',
        help='Name of conf file to generate'
    )

    parser.add_argument(
        '--max-concur', '-m',
        type=int,
        default = 15,
        help='Max number of concurrent video recordings'
    )

    parser.add_argument(
        '--priority', '-p',
        action='store_true',
        default=False,
        help='Add priority parameters'
    )

    args = parser.parse_args()

    main(args)
