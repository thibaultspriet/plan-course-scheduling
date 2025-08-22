#!/usr/bin/env python3
"""
Script to update the cron schedule in the GitHub Actions workflow.
Usage: 
  python scripts/update_workflow_cron.py "5 14 25 8 *"  # Set new cron
  python scripts/update_workflow_cron.py --disable      # Disable scheduling
"""

import sys
import re
from pathlib import Path


def update_workflow_cron(cron_schedule=None, disable=False):
    """Update the cron schedule in the post-reels workflow."""
    workflow_path = Path('.github/workflows/post-reels.yml')
    
    if not workflow_path.exists():
        print(f"Error: Workflow file not found at {workflow_path}")
        sys.exit(1)
    
    # Read current workflow
    with open(workflow_path, 'r') as f:
        content = f.read()
    
    if disable:
        # Comment out the schedule section
        new_content = re.sub(
            r'(  schedule:\s*\n(?:    [^\n]*\n)*)',
            r'  # schedule: # Disabled - no future posts\n  #   - cron: "0 * * * *"\n',
            content,
            flags=re.MULTILINE
        )
        action_type = "disabled"
        
    elif cron_schedule:
        # First, uncomment schedule section if it was commented
        content = re.sub(
            r'  # schedule: # Disabled - no future posts\s*\n  #   - cron: "[^"]*"\s*\n',
            '',
            content,
            flags=re.MULTILINE
        )
        
        # Update or add the cron schedule
        if 'schedule:' in content:
            # Update existing cron
            new_content = re.sub(
                r'(    - cron: )[\'"][^\'\"]*[\'"]',
                f"\\1'{cron_schedule}'",
                content
            )
            # Also update the comment
            new_content = re.sub(
                r'    # Run every hour at minute 0.*',
                f'    # Optimized schedule for next post',
                new_content
            )
        else:
            # Add schedule section after workflow_dispatch
            new_content = re.sub(
                r'(  workflow_dispatch:.*?\n(?:    .*?\n)*)',
                f"\\1  schedule:\n    # Optimized schedule for next post\n    - cron: '{cron_schedule}'\n",
                content,
                flags=re.DOTALL
            )
        action_type = f"updated to '{cron_schedule}'"
    else:
        print("Error: Must provide either cron_schedule or --disable")
        sys.exit(1)
    
    # Write updated workflow
    if content != new_content:
        with open(workflow_path, 'w') as f:
            f.write(new_content)
        print(f"✅ Workflow schedule {action_type}")
    else:
        print("ℹ️  No changes needed to workflow")


def main():
    if len(sys.argv) < 2:
        print("Usage: python update_workflow_cron.py '<cron_schedule>' | --disable")
        sys.exit(1)
    
    if sys.argv[1] == '--disable':
        update_workflow_cron(disable=True)
    else:
        cron_schedule = sys.argv[1]
        # Validate basic cron format (5 parts)
        parts = cron_schedule.split()
        if len(parts) != 5:
            print(f"Error: Invalid cron format '{cron_schedule}'. Expected 5 parts: minute hour day month weekday")
            sys.exit(1)
        
        update_workflow_cron(cron_schedule)


if __name__ == "__main__":
    main()