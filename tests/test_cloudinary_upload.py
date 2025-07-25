"""Tests for Cloudinary upload functionality."""

import json
import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from scripts.upload_to_cloudinary import CloudinaryUploader


class TestCloudinaryUploader:
    
    @patch.dict(os.environ, {
        'CLOUDINARY_CLOUD_NAME': 'test_cloud',
        'CLOUDINARY_API_KEY': 'test_key',
        'CLOUDINARY_API_SECRET': 'test_secret'
    })
    def test_setup_cloudinary_success(self):
        """Test successful Cloudinary setup with valid credentials."""
        uploader = CloudinaryUploader()
        assert uploader is not None
    
    @patch.dict(os.environ, {}, clear=True)
    @patch('scripts.upload_to_cloudinary.load_dotenv')
    def test_setup_cloudinary_missing_credentials(self, mock_load_dotenv):
        """Test Cloudinary setup fails with missing credentials."""
        mock_load_dotenv.return_value = None
        with pytest.raises(ValueError, match="Missing Cloudinary credentials"):
            CloudinaryUploader()
    
    @patch.dict(os.environ, {
        'CLOUDINARY_CLOUD_NAME': 'test_cloud',
        'CLOUDINARY_API_KEY': 'test_key',
        'CLOUDINARY_API_SECRET': 'test_secret'
    })
    @patch('cloudinary.uploader.upload')
    def test_upload_video_success(self, mock_upload):
        """Test successful video upload."""
        mock_upload.return_value = {
            'secure_url': 'https://test.cloudinary.com/video.mp4',
            'public_id': 'test_video'
        }
        
        uploader = CloudinaryUploader()
        result = uploader.upload_video('test_video.mp4')
        
        assert result['secure_url'] == 'https://test.cloudinary.com/video.mp4'
        assert result['public_id'] == 'test_video'
        mock_upload.assert_called_once()
    
    @patch.dict(os.environ, {
        'CLOUDINARY_CLOUD_NAME': 'test_cloud',
        'CLOUDINARY_API_KEY': 'test_key',
        'CLOUDINARY_API_SECRET': 'test_secret'
    })
    @patch('cloudinary.uploader.upload')
    def test_upload_video_failure(self, mock_upload):
        """Test video upload failure handling."""
        mock_upload.side_effect = Exception("Upload failed")
        
        uploader = CloudinaryUploader()
        
        with pytest.raises(Exception, match="Failed to upload video to Cloudinary"):
            uploader.upload_video('test_video.mp4')
    
    @patch.dict(os.environ, {
        'CLOUDINARY_CLOUD_NAME': 'test_cloud',
        'CLOUDINARY_API_KEY': 'test_key',
        'CLOUDINARY_API_SECRET': 'test_secret'
    })
    def test_create_config_file(self, tmp_path):
        """Test configuration file creation."""
        # Change to temporary directory
        os.chdir(tmp_path)
        
        uploader = CloudinaryUploader()
        config_path = uploader.create_config_file(
            video_url='https://test.cloudinary.com/video.mp4',
            video_name='test_video',
            caption='Test caption',
            scheduled_hours=1
        )
        
        # Verify file was created
        assert Path(config_path).exists()
        
        # Verify file contents
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        assert config['video_url'] == 'https://test.cloudinary.com/video.mp4'
        assert config['caption'] == 'Test caption'
        assert 'scheduled_time' in config
        assert config['posted'] is False