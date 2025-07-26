#!/usr/bin/env python3
"""
Generate configuration files from Notion database for Instagram reel automation.
Usage: python scripts/generate_config_from_notion.py [--config path/to/notion_config.json]
"""

import os
import json
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import pytz
from dotenv import load_dotenv
from notion_client import Client


class NotionConfigGenerator:
    def __init__(self, config_path: str = "notion_config.json"):
        load_dotenv()
        self.load_notion_config(config_path)
        self.setup_notion_client()
        self.paris_tz = pytz.timezone('Europe/Paris')
    
    def load_notion_config(self, config_path: str) -> None:
        """Load Notion configuration from JSON file."""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Notion config file not found: {config_path}")
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file {config_path}: {str(e)}")
        
        # Validate required configuration sections
        required_sections = ['database_properties', 'content_extraction', 'filters', 'output']
        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"Missing required config section: {section}")
    
    def setup_notion_client(self) -> None:
        """Initialize Notion client with API token."""
        notion_token = os.getenv('NOTION_API_TOKEN')
        if not notion_token:
            raise ValueError("Missing NOTION_API_TOKEN in environment variables")
        
        self.notion = Client(auth=notion_token)
        
        # Get database ID from environment
        self.database_id = os.getenv('NOTION_DATABASE_ID')
        if not self.database_id:
            raise ValueError("Missing NOTION_DATABASE_ID in environment variables")
    
    def fetch_future_videos(self) -> List[Dict[str, Any]]:
        """Fetch videos scheduled for future posting from Notion database."""
        try:
            filters = []
            db_props = self.config['database_properties']
            filter_config = self.config['filters']
            
            # Add future videos filter if enabled
            if filter_config.get('future_videos_only', True):
                now = datetime.now(self.paris_tz)
                filters.append({
                    "property": db_props['scheduled_time'],
                    "date": {
                        "after": now.isoformat()
                    }
                })
            
            # Add posted filter if enabled
            if filter_config.get('exclude_posted', True):
                posted_status_values = filter_config.get('posted_status_values', ['Posted'])
                # Create a filter that excludes videos with posted status values
                if len(posted_status_values) == 1:
                    filters.append({
                        "property": db_props['status'],
                        "status": {
                            "does_not_equal": posted_status_values[0]
                        }
                    })
                else:
                    # For multiple posted status values, use "not in" logic with OR
                    status_filters = []
                    for status_value in posted_status_values:
                        status_filters.append({
                            "property": db_props['status'],
                            "status": {
                                "does_not_equal": status_value
                            }
                        })
                    filters.append({
                        "and": status_filters
                    })
            
            # Build query
            query = {
                "database_id": self.database_id,
                "sorts": [
                    {
                        "property": db_props['scheduled_time'],
                        "direction": "ascending"
                    }
                ]
            }
            
            if filters:
                query["filter"] = {"and": filters} if len(filters) > 1 else filters[0]
            
            response = self.notion.databases.query(**query)
            return response.get('results', [])
            
        except Exception as e:
            raise Exception(f"Failed to fetch videos from Notion: {str(e)}")
    
    def extract_page_properties(self, page: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant properties from a Notion page using config mappings."""
        properties = page.get('properties', {})
        db_props = self.config['database_properties']
        
        # Extract scheduled_time
        scheduled_time_prop = properties.get(db_props['scheduled_time'], {})
        scheduled_time = None
        if scheduled_time_prop.get('date'):
            scheduled_time = scheduled_time_prop['date']['start']
        
        # Extract video_path (supports both rich_text and formula types)
        video_path_prop = properties.get(db_props['video_path'], {})
        video_path = None
        
        # Check if it's a rich_text property
        if video_path_prop.get('rich_text') and video_path_prop['rich_text']:
            video_path = video_path_prop['rich_text'][0]['text']['content']
        # Check if it's a formula property
        elif video_path_prop.get('formula') and video_path_prop['formula'].get('string'):
            video_path = video_path_prop['formula']['string']
        
        # Extract title
        title_prop = properties.get(db_props['title'], {})
        title = None
        if title_prop.get('title') and title_prop['title']:
            title = title_prop['title'][0]['text']['content']
        
        # Extract status
        status_prop = properties.get(db_props['status'], {})
        status = None
        if status_prop.get('status'):
            status = status_prop['status']['name']
        
        return {
            'page_id': page['id'],
            'scheduled_time': scheduled_time,
            'video_path': video_path,
            'title': title,
            'status': status
        }
    
    def fetch_page_content(self, page_id: str) -> Optional[str]:
        """Fetch the description section content from a Notion page."""
        try:
            content_config = self.config['content_extraction']
            description_heading = content_config['description_heading']
            heading_type = content_config['description_heading_type']
            
            # Get page blocks
            blocks_response = self.notion.blocks.children.list(block_id=page_id)
            blocks = blocks_response.get('results', [])
            
            # Find the description heading and extract content after it
            description_content = []
            found_description = False
            
            for block in blocks:
                block_type = block.get('type')
                
                # Check if this is the target heading with description text
                if block_type == heading_type:
                    heading_text = self._extract_text_from_block(block)
                    if heading_text and description_heading.lower() in heading_text.lower():
                        found_description = True
                        continue
                    elif found_description and block_type.startswith('heading_'):
                        # Found another heading, stop collecting
                        break
                
                # Collect content after description heading
                if found_description:
                    text_content = self._extract_text_from_block(block)
                    if text_content:
                        description_content.append(text_content)
            
            return self._format_for_instagram(description_content) if description_content else None
            
        except Exception as e:
            print(f"Warning: Failed to fetch content for page {page_id}: {str(e)}")
            return None
    
    def _extract_text_from_block(self, block: Dict[str, Any]) -> Optional[str]:
        """Extract text content from a Notion block."""
        block_type = block.get('type')
        
        if block_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3']:
            rich_text = block.get(block_type, {}).get('rich_text', [])
            return ''.join([text.get('plain_text', '') for text in rich_text])
        
        elif block_type == 'bulleted_list_item':
            rich_text = block.get('bulleted_list_item', {}).get('rich_text', [])
            return '• ' + ''.join([text.get('plain_text', '') for text in rich_text])
        
        elif block_type == 'numbered_list_item':
            rich_text = block.get('numbered_list_item', {}).get('rich_text', [])
            return ''.join([text.get('plain_text', '') for text in rich_text])
        
        return None
    
    def _format_for_instagram(self, content_blocks: List[str]) -> str:
        """Format content blocks for Instagram with proper paragraph spacing."""
        if not content_blocks:
            return ""
        
        formatted_blocks = []
        
        for i, block in enumerate(content_blocks):
            block = block.strip()
            if not block:
                continue
                
            # Add the block
            formatted_blocks.append(block)
            
            # Add paragraph spacing between blocks (except for the last block)
            # Instagram needs double line breaks for paragraph spacing
            if i < len(content_blocks) - 1:
                next_block = content_blocks[i + 1].strip() if i + 1 < len(content_blocks) else ""
                if next_block:
                    current_is_bullet = block.startswith('•')
                    next_is_bullet = next_block.startswith('•')
                    
                    # Add spacing between different types of blocks:
                    # - Between regular paragraphs
                    # - Between bullet list and paragraph
                    # - Between paragraph and bullet list
                    # But NOT between consecutive bullet points
                    if not (current_is_bullet and next_is_bullet):
                        formatted_blocks.append("")
        
        return '\n'.join(formatted_blocks)
    
    def _check_existing_config(self, page_id: str) -> Optional[str]:
        """Check if a config file already exists for this Notion page ID."""
        config_dir = Path("config")
        if not config_dir.exists():
            return None
        
        # Look for existing config files with this page ID
        for config_file in config_dir.glob("notion_*.json"):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    if config.get('notion_page_id') == page_id:
                        return str(config_file)
            except (json.JSONDecodeError, FileNotFoundError):
                continue
        
        return None
    
    def generate_config_file(self, video_data: Dict[str, Any], description: str) -> str:
        """Generate a Notion-specific configuration file for processing."""
        config_dir = Path("config")
        config_dir.mkdir(exist_ok=True)
        
        # Parse scheduled time
        scheduled_time = video_data['scheduled_time']
        if scheduled_time:
            print(f"Debug: Original scheduled_time from Notion: {scheduled_time}")
            
            # Convert to Europe/Paris timezone if not already
            if '+' not in scheduled_time and 'Z' not in scheduled_time:
                # Assume it's already in Europe/Paris timezone
                dt = datetime.fromisoformat(scheduled_time)
                dt = self.paris_tz.localize(dt)
            else:
                dt = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
                dt = dt.astimezone(self.paris_tz)
            
            print(f"Debug: Parsed datetime: {dt}")
            scheduled_time = dt.isoformat()
            print(f"Debug: Final scheduled_time: {scheduled_time}")
        
        # Generate Notion-specific config structure (separate from Instagram configs)
        config = {
            "notion_page_id": video_data['page_id'],
            "local_video_path": video_data['video_path'],
            "caption": description or video_data.get('title', 'New reel'),
            "scheduled_time": scheduled_time,
            "title": video_data.get('title', 'Untitled'),
            "status": video_data.get('status', 'Unknown'),
            "generated_at": datetime.now(self.paris_tz).isoformat()
        }
        
        # Create filename based on video path and timestamp
        video_path = Path(video_data['video_path']) if video_data['video_path'] else Path("unknown")
        video_name = video_path.stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_config = self.config['output']
        prefix = output_config.get('config_prefix', 'notion')
        config_filename = f"{prefix}_{timestamp}_{video_name}.json"
        config_path = config_dir / config_filename
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        return str(config_path)
    
    def process_notion_videos(self) -> List[str]:
        """Process all future videos from Notion and generate config files."""
        try:
            print("Fetching future videos from Notion...")
            pages = self.fetch_future_videos()
            
            if not pages:
                print("No future videos found in Notion database.")
                return []
            
            print(f"Found {len(pages)} future videos to process.")
            
            config_files = []
            
            for page in pages:
                try:
                    # Extract page properties
                    video_data = self.extract_page_properties(page)
                    
                    # Check if config already exists for this page
                    existing_config = self._check_existing_config(video_data['page_id'])
                    if existing_config:
                        print(f"⏭️  Skipping '{video_data['title']}' - config already exists: {Path(existing_config).name}")
                        continue
                    
                    if not video_data['video_path']:
                        print(f"Warning: Skipping page '{video_data['title']}' - no video_path specified")
                        continue
                    
                    if not video_data['scheduled_time']:
                        print(f"Warning: Skipping page '{video_data['title']}' - no scheduled_time specified")
                        continue
                    
                    # Fetch description content
                    print(f"Processing: {video_data['title']}")
                    description = self.fetch_page_content(video_data['page_id'])
                    
                    if not description:
                        print(f"Warning: No description found for '{video_data['title']}', using title as caption")
                        description = video_data['title']
                    
                    # Generate config file
                    config_path = self.generate_config_file(video_data, description)
                    config_files.append(config_path)
                    
                    print(f"✅ Config created: {config_path}")
                    
                except Exception as e:
                    print(f"❌ Error processing page '{video_data.get('title', 'unknown')}': {str(e)}")
                    continue
            
            return config_files
            
        except Exception as e:
            raise Exception(f"Failed to process Notion videos: {str(e)}")


def main():
    """Main function to generate config files from Notion."""
    parser = argparse.ArgumentParser(description='Generate Instagram config files from Notion database')
    parser.add_argument('--config', '-c', default='notion_config.json',
                       help='Path to Notion configuration file (default: notion_config.json)')
    
    args = parser.parse_args()
    
    try:
        generator = NotionConfigGenerator(args.config)
        config_files = generator.process_notion_videos()
        
        if config_files:
            print(f"\n✅ Successfully generated {len(config_files)} configuration files:")
            for config_file in config_files:
                print(f"   • {config_file}")
            print(f"\nNext steps:")
            print(f"1. Review the generated config files in the 'config/' directory")
            print(f"2. Run upload_to_cloudinary.py for each video to upload and finalize configs")
            print(f"   Example: uv run python scripts/upload_to_cloudinary.py /path/to/video.mp4")
        else:
            print("No configuration files were generated.")
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()