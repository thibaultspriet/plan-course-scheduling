#!/usr/bin/env python3
"""
Calculate the next post time to optimize GitHub Actions scheduling.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pytz


def get_next_post_time() -> Optional[datetime]:
    """Get the next scheduled post time from config files."""
    config_dir = Path("config")
    
    if not config_dir.exists():
        return None
    
    next_post_time = None
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
            
            # Only consider future posts
            if scheduled_time <= current_time:
                continue
            
            # Find the earliest future post
            if next_post_time is None or scheduled_time < next_post_time:
                next_post_time = scheduled_time
                
        except Exception as e:
            print(f"Error processing {config_file}: {e}", file=sys.stderr)
            continue
    
    return next_post_time


def calculate_optimal_cron_schedule(next_post_time: datetime) -> str:
    """Calculate optimal cron schedule based on next post time."""
    # Schedule to run exactly at the post time (or 1 minute after to ensure it's passed)
    check_time = next_post_time + timedelta(minutes=1)
    
    # Convert to UTC for GitHub Actions
    utc_time = check_time.astimezone(pytz.UTC)
    
    # Generate cron expression (minute hour day month weekday)
    return f"{utc_time.minute} {utc_time.hour} {utc_time.day} {utc_time.month} *"


def main():
    next_post = get_next_post_time()
    
    if next_post is None:
        print("No pending posts found")
        print("STATUS: NO_POSTS")
        # Exit with special code to indicate no posts
        sys.exit(0)
    
    cron_schedule = calculate_optimal_cron_schedule(next_post)
    
    print(f"Next post scheduled for: {next_post}")
    print(f"Optimal cron schedule: {cron_schedule}")
    print(f"STATUS: HAS_POSTS")
    print(f"# - cron: '{cron_schedule}'")


if __name__ == "__main__":
    main()