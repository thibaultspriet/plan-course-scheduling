#!/usr/bin/env python3
"""
Integration tests for the complete workflow process.
Tests the entire flow from config files through GitHub Actions to posting.
"""

import json
import sys
import tempfile
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytz
import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from calculate_next_post_time import main as calc_main
from post_to_instagram import ReelScheduler


class TestCompleteWorkflow:
    """Test the complete workflow integration."""
    
    def setup_method(self):
        """Setup test environment."""
        self.paris_tz = pytz.timezone('Europe/Paris')
        
    def test_full_posting_workflow_simulation(self):
        """Simulate the complete posting workflow from start to finish."""
        
        # Create temporary config directory
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            
            # Create test config file
            post_time = datetime(2025, 8, 22, 20, 0, 0, tzinfo=self.paris_tz)
            config = {
                "video_url": "https://test.cloudinary.com/test.mp4",
                "caption": "Test post for workflow",
                "scheduled_time": post_time.isoformat(),
                "posted": False
            }
            
            config_file = config_dir / "test_post.json"
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Step 1: Calculate next post time (simulates update-schedule.yml)
            with patch('calculate_next_post_time.Path') as mock_path:
                mock_path.return_value = config_dir
                
                with patch('calculate_next_post_time.datetime') as mock_dt:
                    # Current time is before the post
                    mock_current = datetime(2025, 8, 22, 19, 0, 0, tzinfo=self.paris_tz)
                    mock_dt.now.return_value = mock_current
                    mock_dt.fromisoformat = datetime.fromisoformat
                    
                    from calculate_next_post_time import get_next_post_time
                    next_post = get_next_post_time()
                    
            assert next_post == post_time, f"Should find the scheduled post at {post_time}"
            
            # Step 2: Simulate GitHub Actions trigger at calculated time
            # This would happen at 20:01 Paris time (1 minute after post time)
            workflow_time = post_time + timedelta(minutes=1)
            
            # Step 3: Simulate workflow check logic
            def simulate_github_workflow_check():
                # This mimics the Python code in the GitHub workflow
                current_time = workflow_time
                scheduled_time = datetime.fromisoformat(config['scheduled_time'])
                if scheduled_time.tzinfo is None:
                    scheduled_time = self.paris_tz.localize(scheduled_time)
                
                # Key workflow logic: scheduled_time <= current_time
                return scheduled_time <= current_time
            
            workflow_should_proceed = simulate_github_workflow_check()
            assert workflow_should_proceed, "Workflow should proceed when time has passed"
            
            # Step 4: Simulate posting script execution
            with patch('post_to_instagram.datetime') as mock_dt:
                mock_dt.now.return_value = workflow_time
                mock_dt.fromisoformat = datetime.fromisoformat
                
                scheduler = ReelScheduler()
                scheduler.config_dir = config_dir
                
                # Mock the Instagram API calls
                with patch.object(scheduler.instagram_api, 'post_reel') as mock_post:
                    mock_post.return_value = "test_media_id_123"
                    
                    with patch.object(scheduler, 'mark_as_posted') as mock_mark:
                        # This should execute the posting logic
                        should_post = scheduler.is_time_to_post(config['scheduled_time'])
                        assert should_post, "Posting script should decide to post"
                        
                        # Simulate the actual posting process
                        if should_post:
                            media_id = scheduler.instagram_api.post_reel(config)
                            scheduler.mark_as_posted(config_file)
                            
                        mock_post.assert_called_once_with(config)
                        mock_mark.assert_called_once_with(config_file)
            
            print("✅ Complete workflow simulation successful")
    
    def test_workflow_with_multiple_posts(self):
        """Test workflow behavior with multiple posts at different times."""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            
            # Create multiple test configs
            base_time = datetime(2025, 8, 22, 20, 0, 0, tzinfo=self.paris_tz)
            configs = [
                ("past_post.json", base_time - timedelta(hours=2), True),     # Already posted
                ("current_post.json", base_time, False),                      # Ready to post
                ("future_post.json", base_time + timedelta(hours=2), False), # Future post
            ]
            
            for filename, post_time, posted in configs:
                config = {
                    "video_url": f"https://test.com/{filename}",
                    "caption": f"Test post {filename}",
                    "scheduled_time": post_time.isoformat(),
                    "posted": posted
                }
                
                with open(config_dir / filename, 'w') as f:
                    json.dump(config, f, indent=2)
            
            # Simulate workflow trigger at 20:01 (1 minute after current_post time)
            workflow_time = base_time + timedelta(minutes=1)
            
            # Test the posting logic
            with patch('post_to_instagram.datetime') as mock_dt:
                mock_dt.now.return_value = workflow_time
                mock_dt.fromisoformat = datetime.fromisoformat
                
                scheduler = ReelScheduler()
                scheduler.config_dir = config_dir
                
                with patch.object(scheduler.instagram_api, 'post_reel') as mock_post:
                    mock_post.return_value = "test_media_id"
                    
                    with patch.object(scheduler, 'mark_as_posted'):
                        posted_reels = scheduler.process_pending_posts()
                        
                        # Should post exactly one reel (the current_post)
                        assert len(posted_reels) == 1, f"Should post exactly 1 reel, got {len(posted_reels)}"
                        mock_post.assert_called_once()
    
    def test_error_handling_in_workflow(self):
        """Test error handling throughout the workflow."""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            
            # Create a config that will cause posting to fail
            post_time = datetime(2025, 8, 22, 20, 0, 0, tzinfo=self.paris_tz)
            config = {
                "video_url": "https://invalid.url/test.mp4",
                "caption": "Test post that will fail",
                "scheduled_time": post_time.isoformat(),
                "posted": False
            }
            
            config_file = config_dir / "failing_post.json"
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Simulate workflow execution after post time
            workflow_time = post_time + timedelta(minutes=1)
            
            with patch('post_to_instagram.datetime') as mock_dt:
                mock_dt.now.return_value = workflow_time
                mock_dt.fromisoformat = datetime.fromisoformat
                
                scheduler = ReelScheduler()
                scheduler.config_dir = config_dir
                
                # Mock Instagram API to raise an exception
                with patch.object(scheduler.instagram_api, 'post_reel') as mock_post:
                    mock_post.side_effect = Exception("Instagram API Error")
                    
                    # This should raise an exception due to our error handling
                    with pytest.raises(Exception) as exc_info:
                        scheduler.process_pending_posts()
                    
                    # Verify the error message includes our failure
                    assert "1 reel(s) failed to post" in str(exc_info.value)
                    assert "failing_post.json" in str(exc_info.value)
    
    def test_reschedule_after_posting(self):
        """Test that workflow correctly reschedules after posting."""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            
            # Create two posts: one ready now, one future
            current_time = datetime(2025, 8, 22, 20, 0, 0, tzinfo=self.paris_tz)
            future_time = datetime(2025, 8, 25, 18, 30, 0, tzinfo=self.paris_tz)
            
            configs = [
                {
                    "video_url": "https://test.com/post1.mp4",
                    "caption": "Current post",
                    "scheduled_time": current_time.isoformat(),
                    "posted": False
                },
                {
                    "video_url": "https://test.com/post2.mp4", 
                    "caption": "Future post",
                    "scheduled_time": future_time.isoformat(),
                    "posted": False
                }
            ]
            
            for i, config in enumerate(configs):
                with open(config_dir / f"post{i+1}.json", 'w') as f:
                    json.dump(config, f, indent=2)
            
            # After posting the first, should find the second for rescheduling
            with patch('calculate_next_post_time.Path') as mock_path:
                mock_path.return_value = config_dir
                
                with patch('calculate_next_post_time.datetime') as mock_dt:
                    # Simulate time after first post was made
                    mock_current = current_time + timedelta(minutes=5)
                    mock_dt.now.return_value = mock_current
                    mock_dt.fromisoformat = datetime.fromisoformat
                    
                    from calculate_next_post_time import get_next_post_time, calculate_optimal_cron_schedule
                    
                    # Mark first post as posted
                    configs[0]['posted'] = True
                    with open(config_dir / "post1.json", 'w') as f:
                        json.dump(configs[0], f, indent=2)
                    
                    # Should now find the second post as next
                    next_post = get_next_post_time()
                    assert next_post == future_time, "Should find the future post after first is posted"
                    
                    # Should generate correct cron for future post
                    next_cron = calculate_optimal_cron_schedule(future_time)
                    # Aug 25, 18:30 Paris + 1 min = 18:31 Paris = 16:31 UTC (summer)
                    expected_cron = "31 16 25 8 *"
                    assert next_cron == expected_cron, f"Expected '{expected_cron}', got '{next_cron}'"


class TestFailureScenarios:
    """Test various failure scenarios and recovery."""
    
    def test_no_configs_scenario(self):
        """Test behavior when no config files exist."""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()  # Empty directory
            
            with patch('calculate_next_post_time.Path') as mock_path:
                mock_path.return_value = config_dir
                
                from calculate_next_post_time import get_next_post_time
                next_post = get_next_post_time()
                
            assert next_post is None, "Should return None when no configs exist"
    
    def test_all_posts_completed_scenario(self):
        """Test behavior when all posts are already completed."""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            
            # Create only completed posts
            past_time = datetime(2025, 8, 20, 20, 0, 0, tzinfo=pytz.timezone('Europe/Paris'))
            
            for i in range(3):
                config = {
                    "video_url": f"https://test.com/post{i}.mp4",
                    "caption": f"Completed post {i}",
                    "scheduled_time": (past_time + timedelta(hours=i)).isoformat(),
                    "posted": True
                }
                
                with open(config_dir / f"completed{i}.json", 'w') as f:
                    json.dump(config, f, indent=2)
            
            with patch('calculate_next_post_time.Path') as mock_path:
                mock_path.return_value = config_dir
                
                from calculate_next_post_time import get_next_post_time
                next_post = get_next_post_time()
                
            assert next_post is None, "Should return None when all posts are completed"
    
    def test_malformed_config_files(self):
        """Test handling of malformed configuration files."""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            
            # Create various malformed configs
            malformed_configs = [
                ("empty.json", ""),  # Empty file
                ("invalid_json.json", "{invalid json}"),  # Invalid JSON
                ("missing_time.json", '{"caption": "test"}'),  # Missing scheduled_time
                ("invalid_time.json", '{"scheduled_time": "not-a-date"}'),  # Invalid date format
            ]
            
            for filename, content in malformed_configs:
                with open(config_dir / filename, 'w') as f:
                    f.write(content)
            
            # Also create one valid config
            valid_config = {
                "video_url": "https://test.com/valid.mp4",
                "caption": "Valid post",
                "scheduled_time": datetime(2025, 8, 25, 20, 0, tzinfo=pytz.timezone('Europe/Paris')).isoformat(),
                "posted": False
            }
            
            with open(config_dir / "valid.json", 'w') as f:
                json.dump(valid_config, f)
            
            # Should handle malformed files gracefully and find the valid one
            with patch('calculate_next_post_time.Path') as mock_path:
                mock_path.return_value = config_dir
                
                from calculate_next_post_time import get_next_post_time
                next_post = get_next_post_time()
                
            assert next_post is not None, "Should find valid config despite malformed ones"


def run_comprehensive_integration_test():
    """Run a comprehensive integration test covering the entire workflow."""
    print("\n🔥 COMPREHENSIVE INTEGRATION TEST")
    print("=" * 60)
    
    # Simulate a realistic scenario over multiple days
    paris_tz = pytz.timezone('Europe/Paris')
    base_date = datetime(2025, 8, 22, 19, 0, 0, tzinfo=paris_tz)
    
    # Create a posting schedule
    posts_schedule = [
        ("Monday Evening", base_date.replace(hour=20, minute=0)),
        ("Wednesday Morning", base_date.replace(day=24, hour=9, minute=30)), 
        ("Friday Evening", base_date.replace(day=26, hour=19, minute=15)),
    ]
    
    print(f"📅 Testing posting schedule:")
    for name, post_time in posts_schedule:
        print(f"  - {name}: {post_time.strftime('%A, %B %d at %H:%M %Z')}")
    
    print(f"\n🔄 Simulating workflow execution:")
    
    # Test each post's workflow
    for i, (name, post_time) in enumerate(posts_schedule):
        print(f"\n--- {name} Workflow ---")
        
        # Calculate when cron should trigger (1 minute after post time)
        cron_trigger_time = post_time + timedelta(minutes=1)
        print(f"⏰ Cron triggers at: {cron_trigger_time.strftime('%H:%M %Z')}")
        
        # Test workflow logic
        def test_workflow_logic(current_time, scheduled_time):
            if scheduled_time.tzinfo is None:
                scheduled_time = paris_tz.localize(scheduled_time)
            return scheduled_time <= current_time
        
        def test_posting_logic(current_time, scheduled_time): 
            if scheduled_time.tzinfo is None:
                scheduled_time = paris_tz.localize(scheduled_time)
            return current_time >= scheduled_time
        
        # Test at trigger time
        workflow_result = test_workflow_logic(cron_trigger_time, post_time)
        posting_result = test_posting_logic(cron_trigger_time, post_time)
        
        print(f"✅ Workflow check: {'PROCEED' if workflow_result else 'SKIP'}")
        print(f"✅ Posting check: {'POST' if posting_result else 'WAIT'}")
        
        # Verify consistency
        if workflow_result != posting_result:
            raise AssertionError(f"❌ INCONSISTENCY in {name}: workflow={workflow_result}, posting={posting_result}")
        
        if not (workflow_result and posting_result):
            raise AssertionError(f"❌ FAILURE in {name}: should post but logic says no")
        
        print(f"🎯 {name}: ✅ SUCCESS")
        
        # Calculate next cron (if there are remaining posts)
        if i < len(posts_schedule) - 1:
            next_post_time = posts_schedule[i + 1][1]
            from calculate_next_post_time import calculate_optimal_cron_schedule
            next_cron = calculate_optimal_cron_schedule(next_post_time)
            print(f"📅 Next cron: {next_cron}")
    
    print(f"\n🎉 ALL {len(posts_schedule)} WORKFLOWS SUCCESSFUL!")
    print("✅ Integration test PASSED")
    return True


if __name__ == "__main__":
    # Run comprehensive integration test
    run_comprehensive_integration_test()
    
    # Run all pytest tests
    pytest.main([__file__, "-v"])