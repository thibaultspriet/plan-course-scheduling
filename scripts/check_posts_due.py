#!/usr/bin/env python3
"""
Check if any posts are due for posting.
Used by GitHub Actions workflow to determine if posting should proceed.

Outputs:
- "posts_due" if any posts should be posted now
- "no_posts_due" if no posts are ready
"""

import json
import sys
from datetime import datetime
from pathlib import Path
import pytz


def main():
    """Check if any posts are due for posting."""
    config_dir = Path("config")
    
    if not config_dir.exists():
        print("no_posts_due")
        return
    
    paris_tz = pytz.timezone('Europe/Paris')
    current_time = datetime.now(paris_tz)
    
    for config_file in config_dir.glob("*.json"):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Skip if already posted
            if config.get('posted', False):
                continue
            
            # Parse scheduled time
            scheduled_time = datetime.fromisoformat(config['scheduled_time'])
            if scheduled_time.tzinfo is None:
                scheduled_time = paris_tz.localize(scheduled_time)
            
            # Check if it's time to post (current time >= scheduled time)
            if scheduled_time <= current_time:
                print("posts_due")
                return
                
        except Exception:
            # Skip malformed config files
            continue
    
    print("no_posts_due")


if __name__ == "__main__":
    main()