#!/usr/bin/env python3
"""
Utility script to kill admin panel processes running on port 5001.

Usage:
    uv run python scripts/kill_admin_panel.py
"""

import subprocess
import sys

def kill_processes_on_port(port=5001):
    """Kill all processes using the specified port."""
    try:
        # Find processes using the port
        result = subprocess.run(['lsof', '-ti', f':{port}'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print(f"🔍 Found {len(pids)} process(es) using port {port}")
            
            for pid in pids:
                if pid:
                    try:
                        # Get process info
                        ps_result = subprocess.run(['ps', '-p', pid, '-o', 'comm='], 
                                                 capture_output=True, text=True)
                        process_name = ps_result.stdout.strip() if ps_result.returncode == 0 else 'unknown'
                        
                        print(f"🔪 Killing process {pid} ({process_name})")
                        subprocess.run(['kill', '-9', pid], check=True)
                        
                    except subprocess.CalledProcessError as e:
                        print(f"⚠️ Failed to kill process {pid}: {e}")
            
            print(f"✅ Cleaned up processes on port {port}")
            return True
        else:
            print(f"✨ No processes found using port {port}")
            return True
            
    except FileNotFoundError:
        print("❌ 'lsof' command not found. This script works on macOS/Linux only.")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Main function."""
    print("🛠️ Admin Panel Port Cleanup Utility")
    print("=" * 40)
    
    success = kill_processes_on_port(5001)
    
    if success:
        print("\n💡 You can now start the admin panel:")
        print("   uv run python admin_panel.py")
        print("   or")
        print("   uv run python dev_server.py")
        return 0
    else:
        return 1

if __name__ == '__main__':
    exit(main())