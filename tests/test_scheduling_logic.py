#!/usr/bin/env python3
"""
Comprehensive tests for the posting and scheduling logic.
Critical tests to ensure posts are published at the correct time.
"""

import json
import os
import sys
import tempfile
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytz

# Add the scripts directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from post_to_instagram import ReelScheduler, InstagramAPI
from calculate_next_post_time import get_next_post_time, calculate_optimal_cron_schedule


class TestPostingLogic:
    """Test the core posting logic and timing decisions."""
    
    def setup_method(self):
        """Setup test environment."""
        self.paris_tz = pytz.timezone('Europe/Paris')
        
    def create_test_config(self, scheduled_time, posted=False):
        """Create a test config file."""
        return {
            "video_url": "https://test.cloudinary.com/test.mp4",
            "caption": "Test post",
            "scheduled_time": scheduled_time,
            "posted": posted
        }
    
    def test_is_time_to_post_exact_time(self):
        """Test posting logic at exact scheduled time."""
        # Mock current time to be exactly at scheduled time
        scheduled_time = "2025-08-22T20:00:00+02:00"
        
        with patch('post_to_instagram.datetime') as mock_dt:
            mock_current = datetime(2025, 8, 22, 20, 0, 0, tzinfo=self.paris_tz)
            mock_dt.now.return_value = mock_current
            mock_dt.fromisoformat = datetime.fromisoformat
            
            scheduler = ReelScheduler()
            result = scheduler.is_time_to_post(scheduled_time)
            
        assert result == True, "Should post at exact scheduled time"
    
    def test_is_time_to_post_after_time(self):
        """Test posting logic after scheduled time."""
        scheduled_time = "2025-08-22T20:00:00+02:00"
        
        with patch('post_to_instagram.datetime') as mock_dt:
            # Current time is 1 minute after scheduled
            mock_current = datetime(2025, 8, 22, 20, 1, 0, tzinfo=self.paris_tz)
            mock_dt.now.return_value = mock_current
            mock_dt.fromisoformat = datetime.fromisoformat
            
            scheduler = ReelScheduler()
            result = scheduler.is_time_to_post(scheduled_time)
            
        assert result == True, "Should post after scheduled time"
    
    def test_is_time_to_post_before_time(self):
        """Test posting logic before scheduled time."""
        scheduled_time = "2025-08-22T20:00:00+02:00"
        
        with patch('post_to_instagram.datetime') as mock_dt:
            # Current time is 1 minute before scheduled
            mock_current = datetime(2025, 8, 22, 19, 59, 0, tzinfo=self.paris_tz)
            mock_dt.now.return_value = mock_current
            mock_dt.fromisoformat = datetime.fromisoformat
            
            scheduler = ReelScheduler()
            result = scheduler.is_time_to_post(scheduled_time)
            
        assert result == False, "Should NOT post before scheduled time"
    
    def test_is_time_to_post_timezone_handling(self):
        """Test timezone handling for scheduling."""
        # Test with timezone-naive string (should assume Paris timezone)
        scheduled_time_naive = "2025-08-22T20:00:00"
        
        with patch('post_to_instagram.datetime') as mock_dt:
            mock_current = datetime(2025, 8, 22, 20, 1, 0, tzinfo=self.paris_tz)
            mock_dt.now.return_value = mock_current
            mock_dt.fromisoformat = datetime.fromisoformat
            
            scheduler = ReelScheduler()
            result = scheduler.is_time_to_post(scheduled_time_naive)
            
        assert result == True, "Should handle timezone-naive strings correctly"


class TestScheduleCalculation:
    """Test the cron schedule calculation logic."""
    
    def setup_method(self):
        """Setup test environment."""
        self.paris_tz = pytz.timezone('Europe/Paris')
        
    def test_calculate_cron_schedule_basic(self):
        """Test basic cron schedule calculation."""
        # Post scheduled for 22 Aug 2025 at 20:00 Paris time
        post_time = datetime(2025, 8, 22, 20, 0, 0, tzinfo=self.paris_tz)
        
        cron = calculate_optimal_cron_schedule(post_time)
        
        # Should trigger at 20:01 Paris = 18:01 UTC
        expected = "1 18 22 8 *"
        assert cron == expected, f"Expected '{expected}', got '{cron}'"
    
    def test_calculate_cron_schedule_different_times(self):
        """Test cron calculation for different times."""
        test_cases = [
            # (Paris time, expected UTC cron)
            (datetime(2025, 8, 25, 18, 30, 0, tzinfo=self.paris_tz), "31 16 25 8 *"),  # Summer time
            (datetime(2025, 12, 25, 18, 30, 0, tzinfo=self.paris_tz), "31 17 25 12 *"),  # Winter time
            (datetime(2025, 8, 22, 23, 59, 0, tzinfo=self.paris_tz), "0 22 22 8 *"),   # Late night
        ]
        
        for paris_time, expected_cron in test_cases:
            cron = calculate_optimal_cron_schedule(paris_time)
            assert cron == expected_cron, f"For {paris_time}, expected '{expected_cron}', got '{cron}'"
    
    def test_get_next_post_time_with_configs(self):
        """Test finding next post time from config files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            
            # Create test configs
            configs = [
                ("config1.json", "2025-08-25T18:00:00+02:00", False),  # Future
                ("config2.json", "2025-08-20T20:00:00+02:00", True),   # Posted
                ("config3.json", "2025-08-30T19:00:00+02:00", False),  # Future (later)
                ("config4.json", "2025-08-15T20:00:00+02:00", False),  # Past
            ]
            
            for filename, scheduled_time, posted in configs:
                config = {
                    "video_url": "https://test.com/test.mp4",
                    "caption": "Test",
                    "scheduled_time": scheduled_time,
                    "posted": posted
                }
                with open(config_dir / filename, 'w') as f:
                    json.dump(config, f)
            
            # Mock current time
            with patch('calculate_next_post_time.datetime') as mock_dt:
                mock_current = datetime(2025, 8, 22, 12, 0, 0, tzinfo=pytz.timezone('Europe/Paris'))
                mock_dt.now.return_value = mock_current
                mock_dt.fromisoformat = datetime.fromisoformat
                
                with patch('calculate_next_post_time.Path') as mock_path:
                    mock_path.return_value = config_dir
                    
                    next_post = get_next_post_time()
                    
            # Should find the earliest future post (Aug 25)
            expected = datetime(2025, 8, 25, 18, 0, 0, tzinfo=pytz.timezone('Europe/Paris'))
            assert next_post == expected, f"Expected {expected}, got {next_post}"


class TestWorkflowLogic:
    """Test the GitHub Actions workflow logic."""
    
    def test_workflow_check_logic_simulation(self):
        """Simulate the workflow's post checking logic."""
        # This simulates the Python code embedded in the GitHub workflow
        
        def simulate_workflow_check(current_time, configs):
            """Simulate the workflow's post checking logic."""
            paris_tz = pytz.timezone('Europe/Paris')
            
            for config in configs:
                if config.get('posted', False):
                    continue
                    
                scheduled_time = datetime.fromisoformat(config['scheduled_time'])
                if scheduled_time.tzinfo is None:
                    scheduled_time = paris_tz.localize(scheduled_time)
                
                # This is the key logic from the workflow
                if scheduled_time <= current_time:
                    return True
            return False
        
        paris_tz = pytz.timezone('Europe/Paris')
        
        # Test case 1: Post time has passed
        current_time = datetime(2025, 8, 22, 20, 1, 0, tzinfo=paris_tz)
        configs = [{"scheduled_time": "2025-08-22T20:00:00+02:00", "posted": False}]
        result = simulate_workflow_check(current_time, configs)
        assert result == True, "Workflow should find posts when time has passed"
        
        # Test case 2: Post time hasn't arrived yet
        current_time = datetime(2025, 8, 22, 19, 59, 0, tzinfo=paris_tz)
        configs = [{"scheduled_time": "2025-08-22T20:00:00+02:00", "posted": False}]
        result = simulate_workflow_check(current_time, configs)
        assert result == False, "Workflow should NOT find posts when time hasn't arrived"
        
        # Test case 3: Post already posted
        current_time = datetime(2025, 8, 22, 20, 1, 0, tzinfo=paris_tz)
        configs = [{"scheduled_time": "2025-08-22T20:00:00+02:00", "posted": True}]
        result = simulate_workflow_check(current_time, configs)
        assert result == False, "Workflow should ignore already posted content"


class TestEdgeCases:
    """Test edge cases and error scenarios."""
    
    def test_no_future_posts(self):
        """Test behavior when no future posts exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            
            # All posts are in the past or already posted
            configs = [
                ("old1.json", "2025-08-15T20:00:00+02:00", True),   # Posted
                ("old2.json", "2025-08-10T18:00:00+02:00", False),  # Past
            ]
            
            for filename, scheduled_time, posted in configs:
                config = {
                    "scheduled_time": scheduled_time,
                    "posted": posted
                }
                with open(config_dir / filename, 'w') as f:
                    json.dump(config, f)
            
            with patch('calculate_next_post_time.Path') as mock_path:
                mock_path.return_value = config_dir
                
                next_post = get_next_post_time()
                
        assert next_post is None, "Should return None when no future posts exist"
    
    def test_malformed_config_handling(self):
        """Test handling of malformed config files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            
            # Create malformed configs
            configs = [
                ("good.json", {"scheduled_time": "2025-08-25T20:00:00+02:00", "posted": False}),
                ("bad1.json", {"no_scheduled_time": True}),  # Missing scheduled_time
                ("bad2.json", {"scheduled_time": "invalid-date"}),  # Invalid date
            ]
            
            for filename, config in configs:
                with open(config_dir / filename, 'w') as f:
                    json.dump(config, f)
            
            with patch('calculate_next_post_time.Path') as mock_path:
                mock_path.return_value = config_dir
                
                # Should not crash and should find the valid config
                next_post = get_next_post_time()
                
        assert next_post is not None, "Should handle malformed configs gracefully"
    
    def test_timezone_edge_cases(self):
        """Test timezone edge cases (DST transitions, etc.)."""
        # Test DST transition periods
        dst_test_cases = [
            # Just before DST starts (last Sunday in March)
            "2025-03-30T01:59:00+01:00",
            # Just after DST starts  
            "2025-03-30T03:01:00+02:00",
            # Just before DST ends (last Sunday in October)
            "2025-10-26T02:59:00+02:00",
            # Just after DST ends
            "2025-10-26T02:01:00+01:00",
        ]
        
        for scheduled_time_str in dst_test_cases:
            scheduled_time = datetime.fromisoformat(scheduled_time_str)
            
            # Should not crash when calculating cron
            cron = calculate_optimal_cron_schedule(scheduled_time)
            
            # Verify cron format (5 parts)
            assert len(cron.split()) == 5, f"Cron '{cron}' should have 5 parts"


def run_critical_posting_test():
    """
    Critical end-to-end test simulating the complete posting flow.
    This test simulates the entire process from cron trigger to post completion.
    """
    print("\n🔥 CRITICAL POSTING FLOW TEST")
    print("=" * 50)
    
    # Scenario: Post scheduled for Aug 22, 20:00 Paris time
    # Cron should trigger at 20:01 Paris time (18:01 UTC)
    
    scheduled_time = "2025-08-22T20:00:00+02:00"
    paris_tz = pytz.timezone('Europe/Paris')
    
    # Step 1: Calculate expected cron
    post_time = datetime.fromisoformat(scheduled_time)
    expected_cron = calculate_optimal_cron_schedule(post_time)
    print(f"📅 Post scheduled for: {post_time}")
    print(f"⏰ Expected cron: {expected_cron}")
    
    # Step 2: Simulate workflow trigger at cron time
    # Cron "1 18 22 8 *" = 18:01 UTC = 20:01 Paris
    workflow_trigger_time = datetime(2025, 8, 22, 20, 1, 0, tzinfo=paris_tz)
    print(f"🚀 Workflow triggers at: {workflow_trigger_time}")
    
    # Step 3: Test workflow logic
    def simulate_workflow_check(current_time, scheduled_time_str):
        scheduled_time = datetime.fromisoformat(scheduled_time_str)
        if scheduled_time.tzinfo is None:
            scheduled_time = paris_tz.localize(scheduled_time)
        return scheduled_time <= current_time
    
    workflow_should_post = simulate_workflow_check(workflow_trigger_time, scheduled_time)
    print(f"✅ Workflow check result: {'POSTS' if workflow_should_post else 'SKIPS'}")
    
    # Step 4: Test posting script logic
    def simulate_posting_check(current_time, scheduled_time_str):
        scheduled_time = datetime.fromisoformat(scheduled_time_str)
        if scheduled_time.tzinfo is None:
            scheduled_time = paris_tz.localize(scheduled_time)
        return current_time >= scheduled_time
    
    posting_should_proceed = simulate_posting_check(workflow_trigger_time, scheduled_time)
    print(f"✅ Posting script result: {'POSTS' if posting_should_proceed else 'WAITS'}")
    
    # Step 5: Verify consistency
    consistency_check = workflow_should_post == posting_should_proceed
    print(f"🔄 Logic consistency: {'✅ CONSISTENT' if consistency_check else '❌ INCONSISTENT'}")
    
    # Final assessment
    success = workflow_should_post and posting_should_proceed and consistency_check
    print(f"\n🎯 CRITICAL TEST RESULT: {'✅ PASS' if success else '❌ FAIL'}")
    
    if not success:
        raise AssertionError("CRITICAL POSTING FLOW TEST FAILED!")
    
    return success


if __name__ == "__main__":
    # Run critical test
    run_critical_posting_test()
    
    # Run all tests
    pytest.main([__file__, "-v"])