#!/usr/bin/env python3
"""
Process Notion configuration files and upload videos to Cloudinary.
This script reads Notion-generated config files and calls upload_to_cloudinary.py 
with the appropriate parameters to create the final Instagram config files.

Usage: python scripts/process_notion_configs.py [config_pattern]
"""

import os
import sys
import json
import subprocess
import tempfile
from pathlib import Path
from glob import glob
from datetime import datetime
import argparse

import pytz


class NotionConfigProcessor:
    def __init__(self):
        self.paris_tz = pytz.timezone('Europe/Paris')
        self.scripts_dir = Path(__file__).parent
        self.upload_script = self.scripts_dir / "upload_to_cloudinary.py"
        
        if not self.upload_script.exists():
            raise FileNotFoundError(f"upload_to_cloudinary.py not found at {self.upload_script}")
    
    def find_notion_configs(self, pattern: str = "notion_*.json") -> list[Path]:
        """Find all Notion configuration files matching the pattern."""
        config_dir = Path("config")
        if not config_dir.exists():
            print("No config directory found.")
            return []
        
        config_files = list(config_dir.glob(pattern))
        return [f for f in config_files if self.is_notion_config(f)]
    
    def is_notion_config(self, config_path: Path) -> bool:
        """Check if a config file is a Notion-generated config."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Check for Notion-specific fields
            return ('notion_page_id' in config and 
                    'local_video_path' in config and 
                    config.get('video_url') is None)
        except (json.JSONDecodeError, FileNotFoundError):
            return False
    
    def load_notion_config(self, config_path: Path) -> dict:
        """Load and validate a Notion configuration file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            required_fields = ['local_video_path', 'caption', 'scheduled_time']
            missing_fields = [field for field in required_fields if not config.get(field)]
            
            if missing_fields:
                raise ValueError(f"Missing required fields: {missing_fields}")
            
            return config
            
        except Exception as e:
            raise Exception(f"Failed to load config {config_path}: {str(e)}")
    
    def calculate_hours_until_scheduled(self, scheduled_time_str: str) -> int:
        """Calculate hours from now until the scheduled time."""
        try:
            # Parse the scheduled time
            scheduled_dt = datetime.fromisoformat(scheduled_time_str.replace('Z', '+00:00'))
            if scheduled_dt.tzinfo is None:
                # Assume Europe/Paris if no timezone
                scheduled_dt = self.paris_tz.localize(scheduled_dt)
            else:
                # Convert to Paris timezone
                scheduled_dt = scheduled_dt.astimezone(self.paris_tz)
            
            # Current time in Paris timezone
            now = datetime.now(self.paris_tz)
            
            # Calculate difference in hours
            time_diff = scheduled_dt - now
            hours = max(1, int(time_diff.total_seconds() / 3600))  # At least 1 hour
            
            return hours
            
        except Exception as e:
            print(f"Warning: Failed to parse scheduled time '{scheduled_time_str}': {str(e)}")
            return 24  # Default to 24 hours
    
    def create_caption_file(self, caption: str) -> str:
        """Create a temporary file with the caption content."""
        # Create a temporary file for the caption
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(caption)
            return f.name
    
    def process_config(self, config_path: Path) -> bool:
        """Process a single Notion config file by calling upload_to_cloudinary.py."""
        try:
            print(f"\n🔄 Processing: {config_path.name}")
            
            # Load the Notion config
            config = self.load_notion_config(config_path)
            
            # Extract parameters
            video_path = config['local_video_path']
            caption = config['caption']
            scheduled_time = config['scheduled_time']
            
            # Validate video file exists
            video_path_obj = Path(video_path)
            if not video_path_obj.exists():
                print(f"❌ Error: Video file not found: {video_path}")
                print(f"   Resolved path: {video_path_obj.resolve()}")
                return False
            
            # Create temporary caption file
            caption_file = self.create_caption_file(caption)
            
            try:
                # Build command to call upload_to_cloudinary.py
                # Use str() to ensure proper path handling and quoting
                cmd = [
                    "uv", "run", "python", str(self.upload_script),
                    str(video_path),  # Ensure path is properly converted to string
                    "--caption-file", str(caption_file),
                    "--scheduled-time", scheduled_time  # Pass exact scheduled time
                ]
                
                # Add public ID based on video name if available
                video_name = Path(video_path).stem
                cmd.extend(["--public-id", video_name])
                
                print(f"📤 Uploading video: {Path(video_path).name}")
                print(f"⏰ Scheduled for: {scheduled_time}")
                
                # Execute the command
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    print("✅ Upload successful!")
                    if result.stdout:
                        print(result.stdout)
                    
                    # Remove the processed Notion config file
                    config_path.unlink()
                    print(f"🗑️  Removed Notion config: {config_path.name}")
                    
                    return True
                else:
                    print(f"❌ Upload failed (exit code: {result.returncode}):")
                    if result.stdout:
                        print("STDOUT:")
                        print(result.stdout)
                    if result.stderr:
                        print("STDERR:")
                        print(result.stderr)
                    # Also print the command that was executed for debugging
                    print(f"Command executed: {' '.join(cmd)}")
                    return False
                    
            finally:
                # Clean up temporary caption file
                try:
                    os.unlink(caption_file)
                except OSError:
                    pass
                    
        except Exception as e:
            print(f"❌ Error processing {config_path.name}: {str(e)}")
            return False
    
    def process_all_configs(self, pattern: str = "notion_*.json") -> dict:
        """Process all Notion configuration files."""
        config_files = self.find_notion_configs(pattern)
        
        if not config_files:
            print(f"No Notion config files found matching pattern: {pattern}")
            return {"processed": 0, "failed": 0}
        
        print(f"Found {len(config_files)} Notion config files to process:")
        for config_file in config_files:
            print(f"  • {config_file.name}")
        
        processed = 0
        failed = 0
        
        for config_file in config_files:
            if self.process_config(config_file):
                processed += 1
            else:
                failed += 1
        
        return {"processed": processed, "failed": failed}


def main():
    """Main function to process Notion configuration files."""
    parser = argparse.ArgumentParser(description='Process Notion config files and upload to Cloudinary')
    parser.add_argument('pattern', nargs='?', default='notion_*.json',
                       help='Pattern to match Notion config files (default: notion_*.json)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be processed without actually doing it')
    
    args = parser.parse_args()
    
    try:
        processor = NotionConfigProcessor()
        
        if args.dry_run:
            config_files = processor.find_notion_configs(args.pattern)
            if config_files:
                print(f"Would process {len(config_files)} files:")
                for config_file in config_files:
                    print(f"  • {config_file.name}")
            else:
                print("No Notion config files found to process.")
            return
        
        results = processor.process_all_configs(args.pattern)
        
        print(f"\n📊 Summary:")
        print(f"   ✅ Processed: {results['processed']}")
        print(f"   ❌ Failed: {results['failed']}")
        
        if results['failed'] > 0:
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()