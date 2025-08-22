#!/usr/bin/env python3
"""
Precision tests for cron schedule generation and workflow updates.
These tests ensure cron expressions are calculated correctly for various scenarios.
"""

import json
import sys
import tempfile
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, mock_open
import pytz

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from calculate_next_post_time import calculate_optimal_cron_schedule, get_next_post_time
from update_workflow_cron import update_workflow_cron


class TestCronPrecision:
    """Test cron expression generation precision."""
    
    def setup_method(self):
        """Setup test environment."""
        self.paris_tz = pytz.timezone('Europe/Paris')
        self.utc_tz = pytz.UTC
        
    def test_summer_time_calculations(self):
        """Test cron calculations during summer time (CEST = UTC+2)."""
        # Summer: Paris is UTC+2
        test_cases = [
            # (Paris time, expected UTC cron)
            (datetime(2025, 8, 22, 20, 0, tzinfo=self.paris_tz), "1 18 22 8 *"),   # 20:00+2 -> 18:00 UTC
            (datetime(2025, 7, 15, 9, 30, tzinfo=self.paris_tz), "31 7 15 7 *"),   # 09:30+2 -> 07:30 UTC
            (datetime(2025, 6, 1, 23, 45, tzinfo=self.paris_tz), "46 21 1 6 *"),   # 23:45+2 -> 21:45 UTC
        ]
        
        for paris_time, expected_cron in test_cases:
            cron = calculate_optimal_cron_schedule(paris_time)
            assert cron == expected_cron, f"Summer time: {paris_time} -> expected '{expected_cron}', got '{cron}'"
    
    def test_winter_time_calculations(self):
        """Test cron calculations during winter time (CET = UTC+1)."""
        # Winter: Paris is UTC+1
        test_cases = [
            # (Paris time, expected UTC cron)
            (datetime(2025, 12, 25, 20, 0, tzinfo=self.paris_tz), "1 19 25 12 *"), # 20:00+1 -> 19:00 UTC
            (datetime(2025, 1, 15, 9, 30, tzinfo=self.paris_tz), "31 8 15 1 *"),   # 09:30+1 -> 08:30 UTC
            (datetime(2025, 2, 1, 23, 45, tzinfo=self.paris_tz), "46 22 1 2 *"),   # 23:45+1 -> 22:45 UTC
        ]
        
        for paris_time, expected_cron in test_cases:
            cron = calculate_optimal_cron_schedule(paris_time)
            assert cron == expected_cron, f"Winter time: {paris_time} -> expected '{expected_cron}', got '{cron}'"
    
    def test_dst_transition_periods(self):
        """Test cron calculations around DST transitions."""
        # These dates are approximate DST transition periods
        dst_transitions = [
            # Spring forward (last Sunday of March 2025 - March 30)
            datetime(2025, 3, 29, 20, 0, tzinfo=self.paris_tz),  # Day before
            datetime(2025, 3, 31, 20, 0, tzinfo=self.paris_tz),  # Day after
            
            # Fall back (last Sunday of October 2025 - October 26) 
            datetime(2025, 10, 25, 20, 0, tzinfo=self.paris_tz),  # Day before
            datetime(2025, 10, 27, 20, 0, tzinfo=self.paris_tz),  # Day after
        ]
        
        for paris_time in dst_transitions:
            cron = calculate_optimal_cron_schedule(paris_time)
            
            # Verify cron format
            parts = cron.split()
            assert len(parts) == 5, f"Cron should have 5 parts: {cron}"
            
            # Verify all parts are valid numbers/wildcards
            minute, hour, day, month, weekday = parts
            assert 0 <= int(minute) <= 59, f"Invalid minute: {minute}"
            assert 0 <= int(hour) <= 23, f"Invalid hour: {hour}"
            assert 1 <= int(day) <= 31, f"Invalid day: {day}"
            assert 1 <= int(month) <= 12, f"Invalid month: {month}"
            assert weekday == "*", f"Expected wildcard for weekday: {weekday}"
    
    def test_edge_times(self):
        """Test edge cases for time calculations."""
        edge_cases = [
            # Midnight
            datetime(2025, 8, 22, 0, 0, tzinfo=self.paris_tz),
            # Just before midnight  
            datetime(2025, 8, 22, 23, 59, tzinfo=self.paris_tz),
            # Noon
            datetime(2025, 8, 22, 12, 0, tzinfo=self.paris_tz),
        ]
        
        for paris_time in edge_cases:
            cron = calculate_optimal_cron_schedule(paris_time)
            
            # Parse the cron to verify it makes sense
            minute, hour, day, month, weekday = cron.split()
            
            # Calculate what UTC time this represents
            expected_utc = (paris_time + timedelta(minutes=1)).astimezone(self.utc_tz)
            
            assert int(minute) == expected_utc.minute, f"Minute mismatch for {paris_time}"
            assert int(hour) == expected_utc.hour, f"Hour mismatch for {paris_time}"
            assert int(day) == expected_utc.day, f"Day mismatch for {paris_time}"
            assert int(month) == expected_utc.month, f"Month mismatch for {paris_time}"


class TestCronRoundTrip:
    """Test that cron expressions correctly represent the intended times."""
    
    def test_cron_roundtrip_accuracy(self):
        """Test that generated cron expressions trigger at the right time."""
        # Test case: Post at Aug 22, 2025, 20:00 Paris time
        paris_tz = pytz.timezone('Europe/Paris')
        post_time = datetime(2025, 8, 22, 20, 0, tzinfo=paris_tz)
        
        # Generate cron (should be 1 minute after post time)
        cron = calculate_optimal_cron_schedule(post_time)
        
        # Parse cron back to datetime
        minute, hour, day, month, weekday = cron.split()
        
        # Construct the UTC time this cron represents
        utc_trigger_time = datetime(
            2025, int(month), int(day), int(hour), int(minute),
            tzinfo=pytz.UTC
        )
        
        # Convert back to Paris time
        paris_trigger_time = utc_trigger_time.astimezone(paris_tz)
        
        # Should be 1 minute after original post time
        expected_trigger = post_time + timedelta(minutes=1)
        
        assert paris_trigger_time == expected_trigger, (
            f"Roundtrip failed: {post_time} -> cron '{cron}' -> {paris_trigger_time} "
            f"(expected {expected_trigger})"
        )
    
    def test_multiple_posts_ordering(self):
        """Test that multiple posts get correct cron ordering."""
        paris_tz = pytz.timezone('Europe/Paris')
        
        # Create multiple post times
        posts = [
            datetime(2025, 8, 22, 20, 0, tzinfo=paris_tz),
            datetime(2025, 8, 25, 18, 30, tzinfo=paris_tz), 
            datetime(2025, 8, 29, 19, 15, tzinfo=paris_tz),
        ]
        
        # Generate crons
        crons_and_times = []
        for post_time in posts:
            cron = calculate_optimal_cron_schedule(post_time)
            
            # Convert cron back to UTC datetime for comparison
            minute, hour, day, month, weekday = cron.split()
            utc_time = datetime(2025, int(month), int(day), int(hour), int(minute), tzinfo=pytz.UTC)
            
            crons_and_times.append((utc_time, cron, post_time))
        
        # Sort by UTC trigger time
        crons_and_times.sort(key=lambda x: x[0])
        
        # Verify they're in the same order as original posts
        sorted_post_times = [item[2] for item in crons_and_times]
        assert sorted_post_times == sorted(posts), "Cron ordering doesn't match post time ordering"


class TestWorkflowUpdate:
    """Test workflow file updates."""
    
    def test_workflow_cron_update(self):
        """Test updating workflow file with new cron schedule."""
        # Sample workflow content
        original_workflow = """name: Post Instagram Reels

on:
  schedule:
    # Optimized schedule for next post
    - cron: '0 * * * *'
  workflow_dispatch:
    inputs:
      force:
        default: 'false'

jobs:
  post-reels:
    runs-on: ubuntu-latest"""
        
        expected_workflow = """name: Post Instagram Reels

on:
  schedule:
    # Optimized schedule for next post
    - cron: '1 18 22 8 *'
  workflow_dispatch:
    inputs:
      force:
        default: 'false'

jobs:
  post-reels:
    runs-on: ubuntu-latest"""
        
        with patch('builtins.open', mock_open(read_data=original_workflow)) as mock_file:
            with patch('update_workflow_cron.Path.exists', return_value=True):
                update_workflow_cron("1 18 22 8 *")
                
                # Check that file was written with correct content
                handle = mock_file()
                written_content = ''.join(call.args[0] for call in handle.write.call_args_list)
                
        assert "- cron: '1 18 22 8 *'" in written_content, "Cron should be updated in workflow"
    
    def test_workflow_disable(self):
        """Test disabling workflow schedule."""
        original_workflow = """name: Post Instagram Reels

on:
  schedule:
    - cron: '1 18 22 8 *'
  workflow_dispatch:

jobs:
  post-reels:
    runs-on: ubuntu-latest"""
        
        with patch('builtins.open', mock_open(read_data=original_workflow)) as mock_file:
            with patch('update_workflow_cron.Path.exists', return_value=True):
                update_workflow_cron(disable=True)
                
                handle = mock_file()
                written_content = ''.join(call.args[0] for call in handle.write.call_args_list)
                
        assert "# schedule: # Disabled - no future posts" in written_content, "Schedule should be disabled"
        assert "cron:" not in written_content or "#   - cron:" in written_content, "Cron should be commented out"


def run_end_to_end_cron_test():
    """End-to-end test of the complete cron workflow."""
    print("\n🎯 END-TO-END CRON PRECISION TEST")
    print("=" * 50)
    
    # Create a realistic scenario with multiple posts
    paris_tz = pytz.timezone('Europe/Paris')
    
    test_posts = [
        ("Post 1", datetime(2025, 8, 22, 20, 0, tzinfo=paris_tz)),
        ("Post 2", datetime(2025, 8, 25, 18, 30, tzinfo=paris_tz)),
        ("Post 3", datetime(2025, 8, 29, 19, 15, tzinfo=paris_tz)),
    ]
    
    print(f"📋 Testing {len(test_posts)} posts:")
    
    for name, post_time in test_posts:
        # Calculate cron
        cron = calculate_optimal_cron_schedule(post_time)
        
        # Verify cron triggers at the right time
        minute, hour, day, month, weekday = cron.split()
        utc_trigger = datetime(2025, int(month), int(day), int(hour), int(minute), tzinfo=pytz.UTC)
        paris_trigger = utc_trigger.astimezone(paris_tz)
        
        # Should trigger 1 minute after post time
        expected_trigger = post_time + timedelta(minutes=1)
        
        print(f"  {name}: {post_time.strftime('%Y-%m-%d %H:%M %Z')}")
        print(f"    Cron: {cron}")
        print(f"    Triggers: {paris_trigger.strftime('%Y-%m-%d %H:%M %Z')}")
        print(f"    Expected: {expected_trigger.strftime('%Y-%m-%d %H:%M %Z')}")
        
        success = paris_trigger == expected_trigger
        print(f"    Result: {'✅ CORRECT' if success else '❌ WRONG'}")
        
        if not success:
            raise AssertionError(f"Cron calculation failed for {name}")
        
        print()
    
    print("🎯 ALL CRON CALCULATIONS CORRECT!")
    return True


if __name__ == "__main__":
    # Run end-to-end test
    run_end_to_end_cron_test()
    
    # Run all tests  
    pytest.main([__file__, "-v"])