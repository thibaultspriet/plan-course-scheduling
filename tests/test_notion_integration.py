#!/usr/bin/env python3
"""
Tests for Notion integration functionality.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from datetime import datetime

import pytz

# Import the module to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from generate_config_from_notion import NotionConfigGenerator


class TestNotionConfigGenerator:
    """Test cases for NotionConfigGenerator class."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        return {
            "database_properties": {
                "scheduled_time": "scheduled_time",
                "video_path": "video_path",
                "title": "Name",
                "status": "Status"
            },
            "content_extraction": {
                "description_heading": "Description",
                "description_heading_type": "heading_1"
            },
            "filters": {
                "future_videos_only": True,
                "exclude_posted": True,
                "posted_status_values": ["Posted", "Publié"]
            },
            "output": {
                "config_prefix": "notion",
                "include_notion_metadata": True
            }
        }
    
    @pytest.fixture
    def mock_notion_page(self):
        """Mock Notion page data."""
        return {
            "id": "test-page-id-123",
            "properties": {
                "scheduled_time": {
                    "date": {
                        "start": "2025-07-27T14:30:00.000+01:00"
                    }
                },
                "video_path": {
                    "rich_text": [
                        {
                            "text": {
                                "content": "/path/to/video.mp4"
                            }
                        }
                    ]
                },
                "Name": {
                    "title": [
                        {
                            "text": {
                                "content": "Test Video Title"
                            }
                        }
                    ]
                },
                "Status": {
                    "status": {
                        "name": "Draft"
                    }
                }
            }
        }
    
    @patch.dict('os.environ', {
        'NOTION_API_TOKEN': 'test-token',
        'NOTION_DATABASE_ID': 'test-database-id'
    })
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.exists')
    def test_load_notion_config(self, mock_exists, mock_file, mock_config):
        """Test loading Notion configuration from file."""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps(mock_config)
        
        with patch('notion_client.Client'):
            generator = NotionConfigGenerator("test_config.json")
            
        assert generator.config == mock_config
        mock_file.assert_called_once()
    
    @patch.dict('os.environ', {
        'NOTION_API_TOKEN': 'test-token',
        'NOTION_DATABASE_ID': 'test-database-id'
    })
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.exists')
    def test_extract_page_properties(self, mock_exists, mock_file, mock_config, mock_notion_page):
        """Test extracting properties from a Notion page."""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps(mock_config)
        
        with patch('notion_client.Client'):
            generator = NotionConfigGenerator("test_config.json")
            
        result = generator.extract_page_properties(mock_notion_page)
        
        assert result['page_id'] == "test-page-id-123"
        assert result['scheduled_time'] == "2025-07-27T14:30:00.000+01:00"
        assert result['video_path'] == "/path/to/video.mp4"
        assert result['title'] == "Test Video Title"
        assert result['status'] == "Draft"
    
    @patch.dict('os.environ', {
        'NOTION_API_TOKEN': 'test-token',
        'NOTION_DATABASE_ID': 'test-database-id'
    })
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.exists')
    def test_generate_config_file(self, mock_exists, mock_file, mock_config, tmp_path):
        """Test generating configuration file."""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps(mock_config)
        
        video_data = {
            'page_id': 'test-page-id',
            'scheduled_time': '2025-07-27T14:30:00+01:00',
            'video_path': '/path/to/test_video.mp4',
            'title': 'Test Video'
        }
        description = "This is a test description"
        
        with patch('notion_client.Client'):
            generator = NotionConfigGenerator("test_config.json")
        
        # Mock the config directory creation and file writing
        with patch('pathlib.Path.mkdir'), \
             patch('builtins.open', mock_open()) as mock_config_file:
            
            config_path = generator.generate_config_file(video_data, description)
            
            # Verify the config file was created
            assert "config/notion_" in config_path
            assert "_test_video.json" in config_path
            
            # Verify the config content structure
            mock_config_file.assert_called()
            written_calls = mock_config_file().write.call_args_list
            written_content = ''.join([call[0][0] for call in written_calls])
            config_data = json.loads(written_content)
            
            assert config_data['caption'] == description
            assert config_data['video_url'] is None
            assert config_data['posted'] is False
            assert config_data['notion_page_id'] == 'test-page-id'
            assert config_data['local_video_path'] == '/path/to/test_video.mp4'


if __name__ == '__main__':
    pytest.main([__file__])