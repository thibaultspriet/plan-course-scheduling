#!/usr/bin/env python3
"""
pytest configuration and fixtures for the posting system tests.
"""

import pytest
import sys
from pathlib import Path

def pytest_configure(config):
    """Configure pytest with custom settings."""
    # Add scripts directory to Python path
    scripts_dir = Path(__file__).parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

def pytest_collection_modifyitems(config, items):
    """Modify test collection to add custom markers."""
    for item in items:
        # Add marker for critical tests
        if "critical" in item.name or "validation" in item.name:
            item.add_marker(pytest.mark.critical)
        
        # Add marker for integration tests
        if "integration" in item.name or "workflow" in item.name:
            item.add_marker(pytest.mark.integration)

# Custom markers
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "critical: marks tests as critical functionality tests"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )

@pytest.fixture(scope="session")
def paris_tz():
    """Fixture providing Paris timezone."""
    import pytz
    return pytz.timezone('Europe/Paris')

@pytest.fixture(scope="session") 
def utc_tz():
    """Fixture providing UTC timezone."""
    import pytz
    return pytz.UTC