"""Tests for Instagram API functionality."""

import json
import os
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from scripts.post_to_instagram import InstagramAPI, ReelScheduler


class TestInstagramAPI:
    
    @patch.dict(os.environ, {
        'INSTAGRAM_ACCESS_TOKEN': 'test_token',
        'INSTAGRAM_BUSINESS_ACCOUNT_ID': 'test_account_id'
    })
    def test_init_success(self):
        """Test successful Instagram API initialization."""
        api = InstagramAPI()
        assert api.access_token == 'test_token'
        assert api.business_account_id == 'test_account_id'
    
    @patch.dict(os.environ, {}, clear=True)
    @patch('scripts.post_to_instagram.load_dotenv')
    def test_init_missing_credentials(self, mock_load_dotenv):
        """Test Instagram API initialization fails with missing credentials."""
        mock_load_dotenv.return_value = None
        with pytest.raises(ValueError, match="Missing Instagram API credentials"):
            InstagramAPI()
    
    @patch.dict(os.environ, {
        'INSTAGRAM_ACCESS_TOKEN': 'test_token',
        'INSTAGRAM_BUSINESS_ACCOUNT_ID': 'test_account_id'
    })
    @patch('requests.post')
    def test_create_media_container_success(self, mock_post):
        """Test successful media container creation."""
        mock_response = MagicMock()
        mock_response.json.return_value = {'id': 'container_123'}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        api = InstagramAPI()
        container_id = api.create_media_container(
            video_url='https://test.com/video.mp4',
            caption='Test caption'
        )
        
        assert container_id == 'container_123'
        mock_post.assert_called_once()
    
    @patch.dict(os.environ, {
        'INSTAGRAM_ACCESS_TOKEN': 'test_token',
        'INSTAGRAM_BUSINESS_ACCOUNT_ID': 'test_account_id'
    })
    @patch('requests.get')
    def test_check_media_status(self, mock_get):
        """Test media status checking."""
        mock_response = MagicMock()
        mock_response.json.return_value = {'status_code': 'FINISHED', 'status': 'Complete'}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        api = InstagramAPI()
        status = api.check_media_status('container_123')
        
        assert status['status_code'] == 'FINISHED'
        mock_get.assert_called_once()


class TestReelScheduler:
    
    @patch.dict(os.environ, {
        'INSTAGRAM_ACCESS_TOKEN': 'test_token',
        'INSTAGRAM_BUSINESS_ACCOUNT_ID': 'test_account_id'
    })
    def test_is_time_to_post_true(self):
        """Test time checking returns True for past time."""
        scheduler = ReelScheduler()
        past_time = (datetime.now() - timedelta(hours=1)).isoformat()
        
        assert scheduler.is_time_to_post(past_time) is True
    
    @patch.dict(os.environ, {
        'INSTAGRAM_ACCESS_TOKEN': 'test_token',
        'INSTAGRAM_BUSINESS_ACCOUNT_ID': 'test_account_id'
    })
    def test_is_time_to_post_false(self):
        """Test time checking returns False for future time."""
        scheduler = ReelScheduler()
        future_time = (datetime.now() + timedelta(hours=1)).isoformat()
        
        assert scheduler.is_time_to_post(future_time) is False
    
    @patch.dict(os.environ, {
        'INSTAGRAM_ACCESS_TOKEN': 'test_token',
        'INSTAGRAM_BUSINESS_ACCOUNT_ID': 'test_account_id'
    })
    def test_load_config_success(self, tmp_path):
        """Test successful configuration loading."""
        config_data = {
            'video_url': 'https://test.com/video.mp4',
            'caption': 'Test caption',
            'scheduled_time': datetime.now().isoformat(),
            'posted': False
        }
        
        config_file = tmp_path / 'test_config.json'
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        scheduler = ReelScheduler()
        config = scheduler.load_config(str(config_file))
        
        assert config['video_url'] == 'https://test.com/video.mp4'
        assert config['caption'] == 'Test caption'
    
    @patch.dict(os.environ, {
        'INSTAGRAM_ACCESS_TOKEN': 'test_token',
        'INSTAGRAM_BUSINESS_ACCOUNT_ID': 'test_account_id'
    })
    def test_load_config_missing_fields(self, tmp_path):
        """Test configuration loading fails with missing required fields."""
        config_data = {
            'video_url': 'https://test.com/video.mp4'
            # Missing caption and scheduled_time
        }
        
        config_file = tmp_path / 'test_config.json'
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        scheduler = ReelScheduler()
        
        with pytest.raises(Exception, match="Missing required fields"):
            scheduler.load_config(str(config_file))