#!/usr/bin/env python3
"""
Cloudinary utilities for video management.

Provides functions to:
- Delete videos from Cloudinary
- Extract public_id from Cloudinary URLs
- Cleanup unused videos
"""

import os
import re
import json
import cloudinary
import cloudinary.api
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)


def extract_public_id_from_url(video_url):
    """
    Extract public_id from Cloudinary video URL.
    
    Example:
    https://res.cloudinary.com/dsf9byaya/video/upload/v1753525076/20250802-meme-jet.mp4
    Returns: 20250802-meme-jet
    """
    if not video_url or 'cloudinary.com' not in video_url:
        return None
    
    # Pattern to extract public_id from Cloudinary URL
    # Matches: /v{version}/{public_id}.{extension}
    pattern = r'/v\d+/([^/.]+)(?:\.[^/]*)?$'
    match = re.search(pattern, video_url)
    
    if match:
        return match.group(1)
    
    # Fallback: try to get filename without extension
    parts = video_url.split('/')
    if parts:
        filename = parts[-1]
        # Remove extension
        return filename.split('.')[0] if '.' in filename else filename
    
    return None


def delete_video_from_cloudinary(video_url, dry_run=False):
    """
    Delete a video from Cloudinary using its URL.
    
    Args:
        video_url (str): Cloudinary video URL
        dry_run (bool): If True, only print what would be deleted
    
    Returns:
        dict: Result with success status and message
    """
    try:
        public_id = extract_public_id_from_url(video_url)
        
        if not public_id:
            return {
                'success': False,
                'message': f'Could not extract public_id from URL: {video_url}'
            }
        
        if dry_run:
            return {
                'success': True,
                'message': f'[DRY RUN] Would delete video with public_id: {public_id}',
                'public_id': public_id
            }
        
        # Delete the video from Cloudinary
        result = cloudinary.api.delete_resources([public_id], resource_type='video')
        
        deleted = result.get('deleted', {})
        if public_id in deleted and deleted[public_id] == 'deleted':
            return {
                'success': True,
                'message': f'Successfully deleted video: {public_id}',
                'public_id': public_id
            }
        else:
            return {
                'success': False,
                'message': f'Failed to delete video: {public_id}. Response: {result}',
                'public_id': public_id
            }
            
    except Exception as e:
        return {
            'success': False,
            'message': f'Error deleting video from Cloudinary: {str(e)}',
            'public_id': public_id if 'public_id' in locals() else None
        }


def get_all_posted_video_urls():
    """
    Get all Cloudinary video URLs from posted Instagram configurations.
    
    Returns:
        list: List of video URLs from posted configs
    """
    config_dir = Path(__file__).parent.parent / 'config'
    video_urls = []
    
    if not config_dir.exists():
        return video_urls
    
    for config_file in config_dir.glob('reel_*.json'):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            if config.get('posted', False) and config.get('video_url'):
                video_urls.append({
                    'url': config['video_url'],
                    'config_file': config_file.name,
                    'posted_at': config.get('posted_at')
                })
                
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error reading {config_file.name}: {e}")
    
    return video_urls


def get_all_pending_video_urls():
    """
    Get all Cloudinary video URLs from pending Instagram configurations.
    
    Returns:
        set: Set of video URLs that should NOT be deleted
    """
    config_dir = Path(__file__).parent.parent / 'config'
    video_urls = set()
    
    if not config_dir.exists():
        return video_urls
    
    for config_file in config_dir.glob('reel_*.json'):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            if not config.get('posted', False) and config.get('video_url'):
                video_urls.add(config['video_url'])
                
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error reading {config_file.name}: {e}")
    
    return video_urls


def cleanup_posted_videos(dry_run=False):
    """
    Delete all Cloudinary videos from posted Instagram configs.
    
    Args:
        dry_run (bool): If True, only show what would be deleted
    
    Returns:
        dict: Summary of cleanup operation
    """
    posted_videos = get_all_posted_video_urls()
    pending_urls = get_all_pending_video_urls()
    
    results = {
        'total_posted': len(posted_videos),
        'deleted_count': 0,
        'failed_count': 0,
        'skipped_count': 0,
        'deleted': [],
        'failed': [],
        'skipped': []
    }
    
    print(f"Found {len(posted_videos)} posted videos")
    print(f"Found {len(pending_urls)} pending videos (will be protected)")
    
    for video_info in posted_videos:
        video_url = video_info['url']
        config_file = video_info['config_file']
        
        # Skip if this video is still used by a pending post
        if video_url in pending_urls:
            results['skipped_count'] += 1
            results['skipped'].append({
                'url': video_url,
                'reason': 'Still used by pending post',
                'config_file': config_file
            })
            print(f"SKIPPED: {config_file} - video still used by pending post")
            continue
        
        result = delete_video_from_cloudinary(video_url, dry_run)
        
        if result['success']:
            results['deleted_count'] += 1
            results['deleted'].append({
                'url': video_url,
                'public_id': result['public_id'],
                'config_file': config_file
            })
            print(f"{'[DRY RUN] ' if dry_run else ''}DELETED: {config_file} - {result['public_id']}")
        else:
            results['failed_count'] += 1
            results['failed'].append({
                'url': video_url,
                'error': result['message'],
                'config_file': config_file
            })
            print(f"FAILED: {config_file} - {result['message']}")
    
    return results


def main():
    """Command line interface for Cloudinary cleanup."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Cleanup Cloudinary videos")
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be deleted without actually deleting')
    parser.add_argument('--url', type=str,
                       help='Delete specific video by URL')
    
    args = parser.parse_args()
    
    if args.url:
        # Delete specific video
        result = delete_video_from_cloudinary(args.url, args.dry_run)
        print(result['message'])
        return 0 if result['success'] else 1
    else:
        # Cleanup all posted videos
        print("🧹 Starting Cloudinary cleanup for posted videos...")
        results = cleanup_posted_videos(args.dry_run)
        
        print(f"\n📊 Cleanup Summary:")
        print(f"   Total posted videos: {results['total_posted']}")
        print(f"   {'Would delete' if args.dry_run else 'Deleted'}: {results['deleted_count']}")
        print(f"   Failed: {results['failed_count']}")
        print(f"   Skipped (still in use): {results['skipped_count']}")
        
        return 0 if results['failed_count'] == 0 else 1


if __name__ == '__main__':
    exit(main())