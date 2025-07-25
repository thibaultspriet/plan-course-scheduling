#!/usr/bin/env python3
"""
Local script to upload videos to Cloudinary and generate configuration files.
Usage: python scripts/upload_to_cloudinary.py path/to/video.mp4
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any

import cloudinary
import cloudinary.uploader
import pytz
from dotenv import load_dotenv


class CloudinaryUploader:
    def __init__(self):
        load_dotenv()
        self.setup_cloudinary()
    
    def setup_cloudinary(self):
        """Configure Cloudinary with environment variables."""
        cloudinary.config(
            cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
            api_key=os.getenv('CLOUDINARY_API_KEY'),
            api_secret=os.getenv('CLOUDINARY_API_SECRET')
        )
        
        if not all([cloudinary.config().cloud_name, 
                   cloudinary.config().api_key, 
                   cloudinary.config().api_secret]):
            raise ValueError("Missing Cloudinary credentials in environment variables")
    
    def upload_video(self, video_path: str, public_id: str = None) -> Dict[str, Any]:
        """Upload video to Cloudinary and return upload result."""
        try:
            result = cloudinary.uploader.upload(
                video_path,
                resource_type="video",
                public_id=public_id,
                overwrite=True,
                format="mp4"
            )
            return result
        except Exception as e:
            raise Exception(f"Failed to upload video to Cloudinary: {str(e)}")
    
    def create_config_file(self, video_url: str, video_name: str, 
                          caption: str = "", scheduled_hours: int = 24) -> str:
        """Create configuration file for Instagram posting."""
        config_dir = Path("config")
        config_dir.mkdir(exist_ok=True)
        
        # Generate scheduled time in Europe/Paris timezone (default: 24 hours from now)
        paris_tz = pytz.timezone('Europe/Paris')
        scheduled_time = datetime.now(paris_tz) + timedelta(hours=scheduled_hours)
        
        config = {
            "video_url": video_url,
            "caption": caption or f"New reel from {video_name}",
            "scheduled_time": scheduled_time.isoformat(),
            "location_id": None,
            "cover_url": None,
            "posted": False
        }
        
        # Use timestamp for unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        config_filename = f"reel_{timestamp}_{video_name}.json"
        config_path = config_dir / config_filename
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        return str(config_path)


def main():
    parser = argparse.ArgumentParser(description='Upload video to Cloudinary and create config')
    parser.add_argument('video_path', help='Path to the video file')
    parser.add_argument('--caption', '-c', default='', help='Instagram caption')
    parser.add_argument('--caption-file', help='Path to file containing the caption')
    parser.add_argument('--hours', type=int, default=24, 
                       help='Hours from now to schedule posting (default: 24)')
    parser.add_argument('--public-id', '-p', help='Custom Cloudinary public ID')
    
    args = parser.parse_args()
    
    # Validate video file exists
    video_path = Path(args.video_path)
    if not video_path.exists():
        print(f"Error: Video file '{args.video_path}' not found")
        sys.exit(1)
    
    # Handle caption from file or argument
    caption = args.caption
    if args.caption_file:
        caption_file = Path(args.caption_file)
        if not caption_file.exists():
            print(f"Error: Caption file '{args.caption_file}' not found")
            sys.exit(1)
        try:
            with open(caption_file, 'r', encoding='utf-8') as f:
                caption = f.read().strip()
        except Exception as e:
            print(f"Error reading caption file: {str(e)}")
            sys.exit(1)
    
    if not video_path.suffix.lower() in ['.mp4', '.mov', '.avi', '.mkv']:
        print(f"Warning: '{video_path.suffix}' may not be supported by Instagram")
    
    try:
        uploader = CloudinaryUploader()
        
        print(f"Uploading '{video_path.name}' to Cloudinary...")
        result = uploader.upload_video(
            str(video_path), 
            public_id=args.public_id or video_path.stem
        )
        
        print(f"✅ Upload successful!")
        print(f"   URL: {result['secure_url']}")
        print(f"   Public ID: {result['public_id']}")
        
        # Create configuration file
        config_path = uploader.create_config_file(
            video_url=result['secure_url'],
            video_name=video_path.stem,
            caption=caption,
            scheduled_hours=args.hours
        )
        
        print(f"✅ Configuration file created: {config_path}")
        paris_tz = pytz.timezone('Europe/Paris')
        scheduled_datetime = datetime.now(paris_tz) + timedelta(hours=args.hours)
        print(f"   Scheduled for: {scheduled_datetime} (Europe/Paris)")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()