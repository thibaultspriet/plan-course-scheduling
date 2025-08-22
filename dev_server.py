#!/usr/bin/env python3
"""
Development server with advanced hot reloading

Features:
- Hot reloading on Python files
- Auto-refresh browser on HTML/CSS changes  
- Watch additional file patterns
- Better error handling

Usage:
    uv sync --extra admin
    uv run python dev_server.py
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import the Flask app
from admin_panel import app, socketio

# Enhanced development configuration
app.config.update(
    DEBUG=True,
    TEMPLATES_AUTO_RELOAD=True,
    SEND_FILE_MAX_AGE_DEFAULT=0,  # Disable caching for development
)

def check_port_available(port=5001):
    """Check if the preferred port is available."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', port))
            return True
    except OSError:
        return False

def run_dev_server():
    """Run development server with hot reloading."""
    
    # Use fixed port for development consistency
    port = 5001
    
    if not check_port_available(port):
        print(f"⚠️ Port {port} is already in use!")
        print("💡 Tips to resolve:")
        print(f"   • Kill existing process: lsof -ti:{port} | xargs kill -9")
        print("   • Wait a moment for the previous server to fully stop")
        print("   • Check if another admin panel is running")
        print()
        print("⏭️ Continuing anyway - Flask will handle the port conflict...")
        print()
    
    # Files to watch for changes
    extra_files = [
        str(project_root / 'templates' / 'admin.html'),
        str(project_root / '.env'),
        str(project_root / 'notion_config.json'),
    ]
    
    # Add all Python files in scripts directory
    scripts_dir = project_root / 'scripts'
    if scripts_dir.exists():
        for py_file in scripts_dir.glob('*.py'):
            extra_files.append(str(py_file))
    
    print("🚀 Starting Instagram Reel Automation Admin Panel (Development Mode)")
    print(f"🌐 Access the panel at: http://localhost:{port}")
    print("🔥 Hot reloading enabled for:")
    print("   - Python files (.py)")
    print("   - Templates (.html)")
    print("   - Environment files (.env)")
    print("   - Configuration files (.json)")
    print("📱 Press Ctrl+C to stop")
    print()
    
    try:
        socketio.run(
            app,
            host='0.0.0.0',
            port=port,
            debug=True,
            use_reloader=True,
            reloader_options={
                'extra_files': extra_files,
                'reloader_type': 'stat'  # Use stat reloader for better compatibility
            },
            allow_unsafe_werkzeug=True
        )
    except KeyboardInterrupt:
        print("\n👋 Development server stopped")
    except Exception as e:
        print(f"❌ Error starting development server: {e}")
        return 1

if __name__ == '__main__':
    exit_code = run_dev_server()
    sys.exit(exit_code or 0)