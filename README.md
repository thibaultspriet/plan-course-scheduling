# Instagram Reel Automation

Automate Instagram reel posting using Cloudinary for video hosting and the Instagram Graph API for scheduled publishing.

## Features

- 📹 Upload videos to Cloudinary with a simple command
- ⏰ Schedule reels for automatic posting
- 🤖 GitHub Actions integration for hands-off automation
- 🔧 Comprehensive error handling and logging
- ✅ Test coverage for core functionality

## Quick Start

1. **Clone and setup**:
   ```bash
   git clone <repository-url>
   cd instagram-reel-automation
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your API credentials
   ```

3. **Upload a video**:
   ```bash
   python scripts/upload_to_cloudinary.py my_video.mp4 --caption "My awesome reel!"
   ```

4. **Set up GitHub secrets** for automation:
   - `INSTAGRAM_ACCESS_TOKEN`
   - `INSTAGRAM_BUSINESS_ACCOUNT_ID`

## Workflow

1. **Local**: Use `upload_to_cloudinary.py` to upload videos and create scheduling configs
2. **Automated**: GitHub Actions runs hourly to post scheduled reels using `post_to_instagram.py`

## API Requirements

### Instagram Graph API
- Business/Creator Instagram account
- Facebook Page connected to Instagram account
- Instagram Basic Display API access token
- Instagram Business Account ID

### Cloudinary
- Free account provides generous storage and bandwidth
- API credentials (cloud name, API key, API secret)

## Configuration

Reel configurations are JSON files in the `config/` directory:

```json
{
  "video_url": "https://res.cloudinary.com/your-cloud/video/upload/video.mp4",
  "caption": "Your reel caption #hashtags",
  "scheduled_time": "2024-01-15T14:30:00",
  "location_id": null,
  "cover_url": null,
  "posted": false
}
```

## Development

```bash
# Run tests
python -m pytest tests/

# Format code
black scripts/ tests/
flake8 scripts/ tests/

# Test single config
python scripts/post_to_instagram.py config/my_reel.json
```

## GitHub Actions Setup

The workflow runs automatically every hour. To set it up:

1. Add required secrets to your GitHub repository
2. Push your code to trigger the workflow
3. Monitor execution in the Actions tab

## Troubleshooting

- Check logs in `instagram_posting.log`
- Verify Instagram API permissions and rate limits
- Ensure video format compatibility (MP4 recommended)
- Confirm Cloudinary URL accessibility

## License

MIT License - see LICENSE file for details.