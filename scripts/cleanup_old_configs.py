#!/usr/bin/env python3
"""
Script to clean up old Instagram reel configuration files.

Removes configuration files from the config/ directory that:
- Have 'posted': true
- Have 'posted_at' timestamp older than one week

Usage:
    uv run python scripts/cleanup_old_configs.py
    uv run python scripts/cleanup_old_configs.py --dry-run  # Preview what would be deleted
"""

import json
import os
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import pytz


def parse_datetime(date_string):
    """Parse datetime string with timezone support."""
    try:
        # Try parsing with timezone info
        return datetime.fromisoformat(date_string)
    except ValueError:
        # Fallback: assume Europe/Paris timezone for backward compatibility
        dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            paris_tz = pytz.timezone('Europe/Paris')
            dt = paris_tz.localize(dt)
        return dt


def should_delete_config(config_data):
    """Check if a config file should be deleted based on posted status and date."""
    if not config_data.get('posted', False):
        return False
    
    posted_at = config_data.get('posted_at')
    if not posted_at:
        return False
    
    try:
        posted_date = parse_datetime(posted_at)
        one_week_ago = datetime.now(pytz.timezone('Europe/Paris')) - timedelta(weeks=1)
        
        # Ensure both dates have timezone info for comparison
        if posted_date.tzinfo is None:
            paris_tz = pytz.timezone('Europe/Paris')
            posted_date = paris_tz.localize(posted_date)
        
        return posted_date < one_week_ago
    except (ValueError, TypeError) as e:
        print(f"Error parsing posted_at date '{posted_at}': {e}")
        return False


def cleanup_old_configs(dry_run=False):
    """Clean up old configuration files."""
    config_dir = Path(__file__).parent.parent / 'config'
    
    if not config_dir.exists():
        print(f"Config directory not found: {config_dir}")
        return
    
    config_files = list(config_dir.glob('reel_*.json'))
    deleted_count = 0
    errors = []
    
    print(f"Found {len(config_files)} config files to check")
    print(f"Cutoff date: {datetime.now(pytz.timezone('Europe/Paris')) - timedelta(weeks=1)}")
    print()
    
    for config_file in config_files:
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            if should_delete_config(config_data):
                posted_at = config_data.get('posted_at', 'Unknown')
                if dry_run:
                    print(f"[DRY RUN] Would delete: {config_file.name} (posted at: {posted_at})")
                else:
                    config_file.unlink()
                    print(f"Deleted: {config_file.name} (posted at: {posted_at})")
                deleted_count += 1
            else:
                if config_data.get('posted', False):
                    posted_at = config_data.get('posted_at', 'Unknown')
                    print(f"Keeping: {config_file.name} (posted at: {posted_at}, still recent)")
                else:
                    print(f"Keeping: {config_file.name} (not posted yet)")
                    
        except (json.JSONDecodeError, IOError) as e:
            error_msg = f"Error processing {config_file.name}: {e}"
            errors.append(error_msg)
            print(f"ERROR: {error_msg}")
    
    print()
    if dry_run:
        print(f"[DRY RUN] Would delete {deleted_count} config files")
    else:
        print(f"Successfully deleted {deleted_count} config files")
    
    if errors:
        print(f"\nEncountered {len(errors)} errors:")
        for error in errors:
            print(f"  - {error}")
        return 1
    
    return 0


def main():
    parser = argparse.ArgumentParser(description="Clean up old Instagram reel configuration files")
    parser.add_argument('--dry-run', action='store_true', 
                       help='Preview what would be deleted without actually deleting files')
    
    args = parser.parse_args()
    
    try:
        exit_code = cleanup_old_configs(dry_run=args.dry_run)
        exit(exit_code)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        exit(1)


if __name__ == '__main__':
    main()