#!/usr/bin/env python3
"""
Final validation tests using pytest.
Essential tests to ensure the posting system works correctly.
"""

import sys
import pytest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch
import pytz

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from post_to_instagram import ReelScheduler
from calculate_next_post_time import get_next_post_time, calculate_optimal_cron_schedule
from update_workflow_cron import update_workflow_cron


class TestCriticalFunctionality:
    """Test critical functionality that must work for the system to be viable."""
    
    def test_imports_work(self):
        """Test that all critical modules can be imported."""
        # These imports should not raise exceptions
        from post_to_instagram import ReelScheduler, InstagramAPI
        from calculate_next_post_time import get_next_post_time, calculate_optimal_cron_schedule
        from update_workflow_cron import update_workflow_cron
        
        # Basic instantiation test
        scheduler = ReelScheduler()
        assert scheduler is not None
    
    def test_next_post_detection(self):
        """Test that the system can find the next post from real configs."""
        next_post = get_next_post_time()
        
        if next_post:
            # If there's a next post, it should be a valid datetime
            assert isinstance(next_post, datetime)
            assert next_post.tzinfo is not None, "Next post should have timezone info"
            
            # Should be in the future (allowing some flexibility for test timing)
            paris_tz = pytz.timezone('Europe/Paris')
            current_time = datetime.now(paris_tz)
            # Allow up to 5 minutes in the past for edge cases during testing
            assert next_post >= (current_time - timedelta(minutes=5)), "Next post should be current or future"
        
        # If no next post, that's also valid (no assertion needed)
    
    def test_cron_calculation_format(self):
        """Test that cron calculations produce valid format."""
        paris_tz = pytz.timezone('Europe/Paris')
        test_post_time = datetime(2025, 8, 22, 20, 0, tzinfo=paris_tz)
        
        cron = calculate_optimal_cron_schedule(test_post_time)
        
        # Verify cron format (5 parts)
        parts = cron.split()
        assert len(parts) == 5, f"Cron should have 5 parts, got: {cron}"
        
        minute, hour, day, month, weekday = parts
        
        # Verify each part is valid
        assert 0 <= int(minute) <= 59, f"Invalid minute: {minute}"
        assert 0 <= int(hour) <= 23, f"Invalid hour: {hour}"
        assert 1 <= int(day) <= 31, f"Invalid day: {day}"
        assert 1 <= int(month) <= 12, f"Invalid month: {month}"
        assert weekday == "*", f"Expected wildcard for weekday, got: {weekday}"
    
    def test_posting_logic_consistency(self):
        """Test that workflow and posting logic are consistent."""
        # Only run this test if we have a real next post
        next_post = get_next_post_time()
        
        if not next_post:
            pytest.skip("No future posts available for testing")
        
        test_scenarios = [
            ("before", next_post - timedelta(minutes=1)),
            ("at_time", next_post),
            ("after", next_post + timedelta(minutes=1)),
        ]
        
        scheduler = ReelScheduler()
        
        for scenario, test_time in test_scenarios:
            # Workflow logic: scheduled_time <= current_time
            workflow_result = next_post <= test_time
            
            # Simulate posting logic
            with patch('post_to_instagram.datetime') as mock_dt:
                mock_dt.now.return_value = test_time
                mock_dt.fromisoformat = datetime.fromisoformat
                
                posting_result = scheduler.is_time_to_post(next_post.isoformat())
            
            assert workflow_result == posting_result, (
                f"Logic inconsistency at {scenario}: "
                f"workflow={workflow_result}, posting={posting_result}"
            )
    
    def test_cron_precision(self):
        """Test that cron calculations are precise."""
        paris_tz = pytz.timezone('Europe/Paris')
        test_post_time = datetime(2025, 8, 22, 20, 0, tzinfo=paris_tz)
        
        cron = calculate_optimal_cron_schedule(test_post_time)
        
        # Parse cron back to datetime
        minute, hour, day, month, weekday = cron.split()
        utc_trigger_time = datetime(
            2025, int(month), int(day), int(hour), int(minute), 
            tzinfo=pytz.UTC
        )
        paris_trigger_time = utc_trigger_time.astimezone(paris_tz)
        
        # Should trigger 1 minute after post time
        expected_trigger = test_post_time + timedelta(minutes=1)
        
        assert paris_trigger_time == expected_trigger, (
            f"Cron precision failed: expected {expected_trigger}, "
            f"got {paris_trigger_time} from cron '{cron}'"
        )


class TestWorkflowIntegration:
    """Test workflow integration aspects."""
    
    def test_workflow_update_function_exists(self):
        """Test that workflow update functions exist and are callable."""
        # Test that the function exists and is callable
        assert callable(update_workflow_cron)
        
        # Test that it handles basic validation
        with pytest.raises(SystemExit):  # Should exit with error for invalid input
            update_workflow_cron()  # No arguments


class TestRealWorldScenarios:
    """Test with real-world scenarios using actual configuration data."""
    
    def test_system_with_current_configs(self):
        """Test the system with current actual configuration files."""
        # This test uses whatever configs are currently in the system
        next_post = get_next_post_time()
        
        if next_post:
            # Test cron generation
            cron = calculate_optimal_cron_schedule(next_post)
            assert isinstance(cron, str)
            assert len(cron.split()) == 5
            
            # Test consistency check at multiple time points
            paris_tz = pytz.timezone('Europe/Paris')
            current_time = datetime.now(paris_tz)
            
            # Test scenarios around the scheduled time
            test_times = [
                next_post - timedelta(minutes=2),
                next_post,
                next_post + timedelta(minutes=2),
            ]
            
            scheduler = ReelScheduler()
            
            for test_time in test_times:
                workflow_result = next_post <= test_time
                
                with patch('post_to_instagram.datetime') as mock_dt:
                    mock_dt.now.return_value = test_time
                    mock_dt.fromisoformat = datetime.fromisoformat
                    
                    posting_result = scheduler.is_time_to_post(next_post.isoformat())
                
                assert workflow_result == posting_result, (
                    f"Inconsistency at {test_time}: "
                    f"workflow={workflow_result}, posting={posting_result}"
                )


# Test runner function for manual execution
def run_validation_tests():
    """Run validation tests and return results."""
    print("🎯 RUNNING PYTEST VALIDATION TESTS")
    print("=" * 50)
    
    # Run tests with pytest
    test_file = __file__
    result = pytest.main([test_file, "-v", "--tb=short"])
    
    if result == 0:
        print("\n✅ ALL VALIDATION TESTS PASSED!")
        print("   Your posting system is working correctly.")
        return True
    else:
        print("\n❌ SOME VALIDATION TESTS FAILED!")
        print("   Review the test output above.")
        return False


if __name__ == "__main__":
    # Allow running this file directly
    success = run_validation_tests()
    sys.exit(0 if success else 1)