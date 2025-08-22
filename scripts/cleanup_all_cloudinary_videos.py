#!/usr/bin/env python3
"""
One-shot script to cleanup ALL historical Cloudinary videos.

This script will:
1. List ALL videos on Cloudinary
2. Protect videos that are still pending (not posted)
3. Delete all other historical videos

DANGER: This is a destructive operation!
Use --dry-run first to see what would be deleted.

Usage:
    uv run python scripts/cleanup_all_cloudinary_videos.py --dry-run  # Preview
    uv run python scripts/cleanup_all_cloudinary_videos.py            # Actually delete
"""

import os
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Set, List, Dict

import cloudinary
import cloudinary.api
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)


def get_protected_video_urls() -> Set[str]:
    """
    Get all video URLs that should be protected (from pending posts).
    
    Returns:
        Set of video URLs that should NOT be deleted
    """
    config_dir = Path(__file__).parent.parent / 'config'
    protected_urls = set()
    
    if not config_dir.exists():
        print("⚠️ No config directory found")
        return protected_urls
    
    pending_count = 0
    
    for config_file in config_dir.glob('reel_*.json'):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Protect videos from non-posted configs
            if not config.get('posted', False) and config.get('video_url'):
                protected_urls.add(config['video_url'])
                pending_count += 1
                print(f"🛡️ Protecting: {config_file.name} - {config.get('scheduled_time', 'No schedule')}")
                
        except (json.JSONDecodeError, IOError) as e:
            print(f"❌ Error reading {config_file.name}: {e}")
    
    print(f"\n🛡️ Found {pending_count} pending posts - their videos will be protected")
    return protected_urls


def get_public_id_from_url(video_url: str) -> str:
    """Extract public_id from Cloudinary URL."""
    import re
    
    if not video_url or 'cloudinary.com' not in video_url:
        return None
    
    # Pattern to extract public_id from Cloudinary URL
    pattern = r'/v\d+/([^/.]+)(?:\.[^/]*)?$'
    match = re.search(pattern, video_url)
    
    if match:
        return match.group(1)
    
    # Fallback: try to get filename without extension
    parts = video_url.split('/')
    if parts:
        filename = parts[-1]
        return filename.split('.')[0] if '.' in filename else filename
    
    return None


def get_all_cloudinary_videos() -> List[Dict]:
    """
    Get all videos from Cloudinary.
    
    Returns:
        List of video resources from Cloudinary
    """
    print("📡 Fetching all videos from Cloudinary...")
    
    all_videos = []
    next_cursor = None
    
    try:
        while True:
            # Get videos with pagination
            params = {
                'resource_type': 'video',
                'type': 'upload',
                'max_results': 500  # Maximum allowed by Cloudinary
            }
            
            if next_cursor:
                params['next_cursor'] = next_cursor
            
            result = cloudinary.api.resources(**params)
            
            videos = result.get('resources', [])
            all_videos.extend(videos)
            
            print(f"   Fetched {len(videos)} videos (total: {len(all_videos)})")
            
            next_cursor = result.get('next_cursor')
            if not next_cursor:
                break
        
        print(f"📊 Found {len(all_videos)} total videos on Cloudinary")
        return all_videos
        
    except Exception as e:
        print(f"❌ Error fetching videos from Cloudinary: {e}")
        return []


def build_url_from_public_id(public_id: str, cloud_name: str) -> str:
    """Build Cloudinary URL from public_id."""
    # Assume mp4 format and version (common pattern)
    return f"https://res.cloudinary.com/{cloud_name}/video/upload/v1/{public_id}.mp4"


def cleanup_all_videos(dry_run: bool = False) -> Dict:
    """
    Delete all Cloudinary videos except those protected by pending posts.
    
    Args:
        dry_run: If True, only show what would be deleted
        
    Returns:
        Dictionary with cleanup results
    """
    print("🧹 Starting comprehensive Cloudinary video cleanup...")
    print("=" * 60)
    
    # Get protected URLs
    protected_urls = get_protected_video_urls()
    cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
    
    # Get all videos from Cloudinary
    all_videos = get_all_cloudinary_videos()
    
    if not all_videos:
        return {
            'total_videos': 0,
            'protected_count': len(protected_urls),
            'deleted_count': 0,
            'failed_count': 0,
            'deleted': [],
            'failed': [],
            'protected': list(protected_urls)
        }
    
    results = {
        'total_videos': len(all_videos),
        'protected_count': 0,
        'deleted_count': 0,
        'failed_count': 0,
        'deleted': [],
        'failed': [],
        'protected': []
    }
    
    print(f"\n🔍 Analyzing {len(all_videos)} videos...")
    print(f"🛡️ Will protect {len(protected_urls)} videos from pending posts")
    print()
    
    for video in all_videos:
        public_id = video['public_id']
        
        # Try different URL patterns to match with our protected URLs
        possible_urls = [
            video.get('secure_url', ''),
            video.get('url', ''),
            build_url_from_public_id(public_id, cloud_name),
            f"https://res.cloudinary.com/{cloud_name}/video/upload/{public_id}.mp4",
            f"https://res.cloudinary.com/{cloud_name}/video/upload/v{video.get('version', '1')}/{public_id}.mp4"
        ]
        
        # Check if any possible URL is in protected list
        is_protected = any(url in protected_urls for url in possible_urls if url)
        
        if is_protected:
            results['protected_count'] += 1
            results['protected'].append(public_id)
            print(f"🛡️ PROTECTED: {public_id} (used by pending post)")
            continue
        
        # Delete the video
        created_at = video.get('created_at', 'Unknown')
        if dry_run:
            results['deleted_count'] += 1
            results['deleted'].append({
                'public_id': public_id,
                'created_at': created_at,
                'bytes': video.get('bytes', 0)
            })
            print(f"[DRY RUN] Would delete: {public_id} (created: {created_at})")
        else:
            try:
                delete_result = cloudinary.api.delete_resources([public_id], resource_type='video')
                
                if public_id in delete_result.get('deleted', {}) and delete_result['deleted'][public_id] == 'deleted':
                    results['deleted_count'] += 1
                    results['deleted'].append({
                        'public_id': public_id,
                        'created_at': created_at,
                        'bytes': video.get('bytes', 0)
                    })
                    print(f"✅ DELETED: {public_id} (created: {created_at})")
                else:
                    results['failed_count'] += 1
                    results['failed'].append({
                        'public_id': public_id,
                        'error': f'Deletion failed: {delete_result}',
                        'created_at': created_at
                    })
                    print(f"❌ FAILED: {public_id} - {delete_result}")
                    
            except Exception as e:
                results['failed_count'] += 1
                results['failed'].append({
                    'public_id': public_id,
                    'error': str(e),
                    'created_at': created_at
                })
                print(f"❌ ERROR: {public_id} - {str(e)}")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="One-shot cleanup of ALL Cloudinary videos (except pending posts)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
⚠️  WARNING: This is a destructive operation!
This script will delete ALL videos on Cloudinary except those used by pending posts.

Examples:
  python cleanup_all_cloudinary_videos.py --dry-run    # Preview what would be deleted
  python cleanup_all_cloudinary_videos.py              # Actually delete videos
        """
    )
    
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be deleted without actually deleting')
    parser.add_argument('--force', action='store_true',
                       help='Skip interactive confirmation (for automated execution)')
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.force:
        print("⚠️" * 20)
        print("🚨 DANGER: This will DELETE ALL historical videos on Cloudinary!")
        print("   Only videos from pending posts will be protected.")
        print("   This action CANNOT be undone!")
        print("⚠️" * 20)
        
        confirm = input("\nType 'DELETE ALL VIDEOS' to confirm this destructive operation: ")
        if confirm != 'DELETE ALL VIDEOS':
            print("❌ Operation cancelled - confirmation text did not match")
            return 1
    elif not args.dry_run and args.force:
        print("🚨 FORCE MODE: Skipping interactive confirmation")
        print("🗑️ Proceeding with deletion of ALL historical videos...")
    
    # Perform cleanup
    results = cleanup_all_videos(dry_run=args.dry_run)
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 CLEANUP SUMMARY")
    print("=" * 60)
    print(f"Total videos on Cloudinary:     {results['total_videos']}")
    print(f"Protected (pending posts):      {results['protected_count']}")
    print(f"{'Would delete' if args.dry_run else 'Deleted successfully'}:       {results['deleted_count']}")
    print(f"Failed to delete:               {results['failed_count']}")
    
    if results['deleted']:
        total_bytes = sum(item.get('bytes', 0) for item in results['deleted'])
        total_mb = total_bytes / (1024 * 1024) if total_bytes > 0 else 0
        print(f"Storage {'would be' if args.dry_run else ''} freed:  {total_mb:.2f} MB")
    
    if args.dry_run and results['deleted_count'] > 0:
        print(f"\n💡 To actually delete these {results['deleted_count']} videos, run:")
        print(f"   uv run python scripts/cleanup_all_cloudinary_videos.py")
    
    if results['failed_count'] > 0:
        print(f"\n❌ {results['failed_count']} videos failed to delete:")
        for failed in results['failed'][:5]:  # Show first 5 failures
            print(f"   - {failed['public_id']}: {failed['error']}")
        if len(results['failed']) > 5:
            print(f"   ... and {len(results['failed']) - 5} more")
        return 1
    
    print(f"\n{'🔍' if args.dry_run else '✅'} Operation completed successfully!")
    return 0


if __name__ == '__main__':
    exit(main())