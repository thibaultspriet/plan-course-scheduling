#!/usr/bin/env python3
"""
Script to post reels to Instagram using the Graph API.
Can be run locally or via GitHub Actions.
Usage: python scripts/post_to_instagram.py [config_file.json]
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

import requests
import pytz
from dotenv import load_dotenv


class InstagramAPI:
    def __init__(self):
        load_dotenv()
        self.access_token = os.getenv('INSTAGRAM_ACCESS_TOKEN')
        self.business_account_id = os.getenv('INSTAGRAM_BUSINESS_ACCOUNT_ID')
        
        if not self.access_token or not self.business_account_id:
            raise ValueError("Missing Instagram API credentials in environment variables")
        
        self.base_url = "https://graph.instagram.com/v21.0"
        self.setup_logging()
    
    def setup_logging(self):
        """Configure logging for the application."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('instagram_posting.log')
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def create_media_container(self, video_url: str, caption: str, 
                             cover_url: str = None, location_id: str = None) -> str:
        """Create a media container for the reel."""
        url = f"{self.base_url}/{self.business_account_id}/media"
        
        data = {
            'media_type': 'REELS',
            'video_url': video_url,
            'caption': caption,
            'access_token': self.access_token
        }
        
        if cover_url:
            data['cover_url'] = cover_url
        if location_id:
            data['location_id'] = location_id
        
        try:
            response = requests.post(url, data=data)
            response.raise_for_status()
            
            result = response.json()
            container_id = result.get('id')
            
            if not container_id:
                raise Exception(f"No container ID returned: {result}")
            
            self.logger.info(f"Created media container: {container_id}")
            return container_id
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to create media container: {str(e)}")
            if hasattr(e, 'response') and e.response:
                try:
                    error_detail = e.response.json()
                    self.logger.error(f"API Error Details: {error_detail}")
                except:
                    self.logger.error(f"Response Text: {e.response.text}")
            raise
    
    def check_media_status(self, container_id: str) -> Dict[str, Any]:
        """Check the status of media processing."""
        url = f"{self.base_url}/{container_id}"
        params = {
            'fields': 'status_code,status',
            'access_token': self.access_token
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to check media status: {str(e)}")
            raise
    
    def wait_for_processing(self, container_id: str, max_wait: int = 300) -> bool:
        """Wait for media processing to complete."""
        self.logger.info(f"Waiting for media processing...")
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            status = self.check_media_status(container_id)
            status_code = status.get('status_code')
            
            if status_code == 'FINISHED':
                self.logger.info("Media processing completed successfully")
                return True
            elif status_code == 'ERROR':
                self.logger.error(f"Media processing failed: {status}")
                return False
            elif status_code in ['IN_PROGRESS', 'PUBLISHED']:
                self.logger.info(f"Processing status: {status_code}")
                time.sleep(10)  # Wait 10 seconds before checking again
            else:
                self.logger.warning(f"Unknown status: {status}")
                time.sleep(10)
        
        self.logger.error(f"Media processing timeout after {max_wait} seconds")
        return False
    
    def publish_media(self, container_id: str) -> str:
        """Publish the media container."""
        url = f"{self.base_url}/{self.business_account_id}/media_publish"
        
        data = {
            'creation_id': container_id,
            'access_token': self.access_token
        }
        
        try:
            self.logger.info(f"Publishing media container {container_id}...")
            response = requests.post(url, data=data)
            
            # Log response details for debugging
            self.logger.info(f"Publish response status: {response.status_code}")
            self.logger.info(f"Publish response headers: {dict(response.headers)}")
            
            # Check if it's actually successful despite the error
            if response.status_code == 200:
                result = response.json()
                self.logger.info(f"Publish response body: {result}")
                media_id = result.get('id')
                
                if not media_id:
                    raise Exception(f"No media ID returned: {result}")
                
                self.logger.info(f"Published reel with ID: {media_id}")
                return media_id
            else:
                # Log error details
                try:
                    error_detail = response.json()
                    self.logger.error(f"API Error Details: {error_detail}")
                except:
                    self.logger.error(f"Response Text: {response.text}")
                
                # Check for the specific "Fatal" error that actually succeeds
                if response.status_code == 400:
                    try:
                        error_detail = response.json()
                        if (error_detail.get('error', {}).get('error_subcode') == 2207032 and 
                            error_detail.get('error', {}).get('message') == 'Fatal'):
                            
                            self.logger.warning("Got 'Fatal' error but reel may have posted successfully")
                            # Return the container ID as media ID since posting likely succeeded
                            self.logger.info(f"✅ Reel likely posted successfully! Container ID: {container_id}")
                            return container_id
                    except:
                        pass
                
                # Still raise the error for other cases
                response.raise_for_status()
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to publish media: {str(e)}")
            if hasattr(e, 'response') and e.response:
                try:
                    error_detail = e.response.json()
                    self.logger.error(f"API Error Details: {error_detail}")
                except:
                    self.logger.error(f"Response Text: {e.response.text}")
            raise
    
    def post_reel(self, config: Dict[str, Any]) -> str:
        """Complete workflow to post a reel."""
        self.logger.info(f"Starting reel posting process...")
        
        try:
            # Create media container
            container_id = self.create_media_container(
                video_url=config['video_url'],
                caption=config['caption'],
                cover_url=config.get('cover_url'),
                location_id=config.get('location_id')
            )
            
            # Wait for processing
            if not self.wait_for_processing(container_id):
                raise Exception("Media processing failed or timed out")
            
            # Publish media
            media_id = self.publish_media(container_id)
            
            self.logger.info(f"✅ Reel posted successfully! Media ID: {media_id}")
            return media_id
            
        except Exception as e:
            self.logger.error(f"❌ Failed to post reel: {str(e)}")
            raise


class ReelScheduler:
    def __init__(self):
        self.instagram_api = InstagramAPI()
        self.config_dir = Path("config")
    
    def load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            required_fields = ['video_url', 'caption', 'scheduled_time']
            missing_fields = [field for field in required_fields if field not in config]
            
            if missing_fields:
                raise ValueError(f"Missing required fields: {missing_fields}")
            
            return config
        except Exception as e:
            raise Exception(f"Failed to load config file '{config_path}': {str(e)}")
    
    def is_time_to_post(self, scheduled_time_str: str) -> bool:
        """Check if it's time to post based on scheduled time."""
        try:
            # Parse scheduled time
            scheduled_time = datetime.fromisoformat(scheduled_time_str)
            paris_tz = pytz.timezone('Europe/Paris')
            
            if scheduled_time.tzinfo is None:
                # If no timezone info, assume Europe/Paris for backward compatibility
                scheduled_time = paris_tz.localize(scheduled_time)
            
            # Current time in Europe/Paris
            current_time = datetime.now(paris_tz)
            
            # Post if current time is past scheduled time
            is_ready = current_time >= scheduled_time
            
            if not is_ready:
                self.instagram_api.logger.info(
                    f"Not yet time to post. Current: {current_time}, Scheduled: {scheduled_time}"
                )
            
            return is_ready
        except Exception as e:
            self.instagram_api.logger.error(f"Invalid scheduled time format: {str(e)}")
            return False
    
    def mark_as_posted(self, config_path: str):
        """Mark configuration as posted."""
        try:
            config = self.load_config(config_path)
            config['posted'] = True
            paris_tz = pytz.timezone('Europe/Paris')
            config['posted_at'] = datetime.now(paris_tz).isoformat()
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.instagram_api.logger.error(f"Failed to mark config as posted: {str(e)}")
    
    def process_pending_posts(self) -> List[str]:
        """Process all pending reel configurations."""
        if not self.config_dir.exists():
            self.instagram_api.logger.info("No config directory found")
            return []
        
        posted_reels = []
        config_files = list(self.config_dir.glob("*.json"))
        
        self.instagram_api.logger.info(f"Found {len(config_files)} configuration files")
        
        for config_file in config_files:
            try:
                config = self.load_config(config_file)
                
                # Skip if already posted
                if config.get('posted', False):
                    continue
                
                # Check if it's time to post
                if not self.is_time_to_post(config['scheduled_time']):
                    scheduled_time = datetime.fromisoformat(config['scheduled_time'])
                    paris_tz = pytz.timezone('Europe/Paris')
                    if scheduled_time.tzinfo is None:
                        scheduled_time = paris_tz.localize(scheduled_time)
                    self.instagram_api.logger.info(
                        f"Skipping {config_file.name} - scheduled for {scheduled_time}"
                    )
                    continue
                
                # Post the reel
                self.instagram_api.logger.info(f"Processing {config_file.name}")
                media_id = self.instagram_api.post_reel(config)
                
                # Mark as posted
                self.mark_as_posted(config_file)
                posted_reels.append(media_id)
                
                self.instagram_api.logger.info(f"✅ Successfully posted {config_file.name}")
                
            except Exception as e:
                self.instagram_api.logger.error(f"Failed to process {config_file.name}: {str(e)}")
                continue
        
        return posted_reels


def main():
    try:
        scheduler = ReelScheduler()
        
        if len(sys.argv) > 1:
            # Single config file mode
            config_path = sys.argv[1]
            if not Path(config_path).exists():
                print(f"Error: Config file '{config_path}' not found")
                sys.exit(1)
            
            config = scheduler.load_config(config_path)
            print(f"Posting reel from config: {config_path}")
            media_id = scheduler.instagram_api.post_reel(config)
            scheduler.mark_as_posted(config_path)
            print(f"✅ Reel posted successfully! Media ID: {media_id}")
        else:
            # Batch processing mode (for GitHub Actions)
            print("Processing all pending reel configurations...")
            posted_reels = scheduler.process_pending_posts()
            
            if posted_reels:
                print(f"✅ Posted {len(posted_reels)} reels: {posted_reels}")
            else:
                print("No reels to post at this time")
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()