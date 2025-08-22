#!/usr/bin/env python3
"""
Instagram Reel Automation - Admin Panel

A Flask-based web interface for managing the Instagram reel workflow locally.
Provides status overview and action buttons for the complete workflow.

Usage:
    uv sync --extra admin
    uv run python admin_panel.py
"""

import json
import os
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytz
from dotenv import load_dotenv
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'admin-panel-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global variables for managing processes
running_processes = {}
process_logs = {}


class WorkflowStatus:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.config_dir = self.project_root / 'config'
        self.scripts_dir = self.project_root / 'scripts'
        
    def get_config_files_status(self):
        """Get status of configuration files."""
        if not self.config_dir.exists():
            return {'instagram_configs': 0, 'notion_configs': 0, 'pending_posts': 0, 'recent_posts': 0}
        
        instagram_configs = list(self.config_dir.glob('reel_*.json'))
        notion_configs = list(self.config_dir.glob('notion_*.json'))
        
        pending_posts = 0
        recent_posts = 0
        
        for config_file in instagram_configs:
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                if not config.get('posted', False):
                    pending_posts += 1
                else:
                    # Check if posted in last 7 days
                    posted_at = config.get('posted_at')
                    if posted_at:
                        try:
                            posted_date = datetime.fromisoformat(posted_at)
                            one_week_ago = datetime.now(pytz.timezone('Europe/Paris')) - timedelta(weeks=1)
                            
                            if posted_date.tzinfo is None:
                                paris_tz = pytz.timezone('Europe/Paris')
                                posted_date = paris_tz.localize(posted_date)
                            
                            if posted_date > one_week_ago:
                                recent_posts += 1
                        except (ValueError, TypeError):
                            pass
                            
            except (json.JSONDecodeError, IOError):
                pass
        
        return {
            'instagram_configs': len(instagram_configs),
            'notion_configs': len(notion_configs),
            'pending_posts': pending_posts,
            'recent_posts': recent_posts
        }
    
    def get_git_status(self):
        """Get git status information."""
        try:
            # Check if there are unstaged changes
            result = subprocess.run(['git', 'status', '--porcelain'], 
                                  capture_output=True, text=True, 
                                  cwd=self.project_root)
            
            if result.returncode != 0:
                return {'status': 'error', 'message': 'Not a git repository'}
            
            changes = result.stdout.strip().split('\n') if result.stdout.strip() else []
            config_changes = [change for change in changes if 'config/' in change]
            
            # Get current branch
            branch_result = subprocess.run(['git', 'branch', '--show-current'],
                                         capture_output=True, text=True,
                                         cwd=self.project_root)
            current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else 'unknown'
            
            return {
                'status': 'clean' if not changes else 'dirty',
                'total_changes': len(changes),
                'config_changes': len(config_changes),
                'current_branch': current_branch,
                'changes': changes
            }
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def get_notion_status(self):
        """Check if Notion configuration exists and estimate pending videos."""
        notion_config_path = self.project_root / 'notion_config.json'
        
        if not notion_config_path.exists():
            return {'status': 'no_config', 'message': 'notion_config.json not found'}
        
        try:
            with open(notion_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Check if required environment variables are set
            required_env_vars = ['NOTION_API_TOKEN', 'NOTION_DATABASE_ID']
            missing_vars = [var for var in required_env_vars if not os.getenv(var)]
            
            if missing_vars:
                return {
                    'status': 'missing_env',
                    'message': f'Missing environment variables: {", ".join(missing_vars)}'
                }
            
            return {
                'status': 'ready',
                'message': 'Notion configuration ready',
                'config': config
            }
            
        except Exception as e:
            return {'status': 'error', 'message': f'Error reading notion_config.json: {str(e)}'}


def run_command_with_logging(command, process_id):
    """Run a command and capture all output, then emit via WebSocket."""
    global running_processes, process_logs
    
    try:
        process_logs[process_id] = []
        
        # Emit start event
        socketio.emit('process_started', {'process_id': process_id, 'command': ' '.join(command)})
        
        # For Python scripts, add explicit unbuffered flag
        if len(command) > 1 and 'python' in command[1]:
            command.insert(2, '-u')
        elif 'python' in command[0]:
            command.insert(1, '-u')
        
        # Run the command and capture all output
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent,
                env={**os.environ, 'PYTHONUNBUFFERED': '1'},
                timeout=300  # 5 minute timeout
            )
            
            # Emit all output lines
            if result.stdout:
                for line in result.stdout.splitlines():
                    if line.strip():
                        log_entry = {'timestamp': datetime.now().isoformat(), 'message': line}
                        process_logs[process_id].append(log_entry)
                        socketio.emit('process_output', {'process_id': process_id, 'line': line})
                        socketio.sleep(0.001)  # Small delay for UI updates
            
            if result.stderr:
                for line in result.stderr.splitlines():
                    if line.strip():
                        log_entry = {'timestamp': datetime.now().isoformat(), 'message': f"ERROR: {line}"}
                        process_logs[process_id].append(log_entry)
                        socketio.emit('process_output', {'process_id': process_id, 'line': f"ERROR: {line}"})
                        socketio.sleep(0.001)
            
            return_code = result.returncode
            
        except subprocess.TimeoutExpired:
            error_msg = "Command timed out after 5 minutes"
            socketio.emit('process_error', {'process_id': process_id, 'error': error_msg})
            return_code = -1
            
        except Exception as e:
            error_msg = f"Command execution failed: {str(e)}"
            socketio.emit('process_error', {'process_id': process_id, 'error': error_msg})
            return_code = -1
        
        # Emit completion event
        socketio.emit('process_completed', {
            'process_id': process_id, 
            'return_code': return_code,
            'success': return_code == 0
        })
        
    except Exception as e:
        error_msg = f"Error running command: {str(e)}"
        socketio.emit('process_error', {'process_id': process_id, 'error': error_msg})
        print(f"Command error for {process_id}: {error_msg}")
        
    finally:
        # Cleanup
        if process_id in running_processes:
            del running_processes[process_id]


@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('admin.html')


@app.route('/api/status')
def get_status():
    """API endpoint to get current workflow status."""
    workflow = WorkflowStatus()
    
    return jsonify({
        'configs': workflow.get_config_files_status(),
        'git': workflow.get_git_status(),
        'notion': workflow.get_notion_status(),
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/run/<action>', methods=['POST'])
def run_action(action):
    """API endpoint to run workflow actions."""
    actions = {
        'generate_configs': ['uv', 'run', 'python', 'scripts/generate_config_from_notion.py'],
        'process_configs': ['uv', 'run', 'python', 'scripts/process_notion_configs.py'],
        'cleanup_old': ['uv', 'run', 'python', 'scripts/cleanup_old_configs.py'],
        'git_status': ['git', 'status'],
        'git_add_configs': ['git', 'add', 'config/'],
    }
    
    if action not in actions:
        return jsonify({'error': f'Unknown action: {action}'}), 400
    
    process_id = f"{action}_{int(time.time())}"
    command = actions[action]
    
    # Run command with logging using gevent-compatible approach
    import gevent
    gevent.spawn(run_command_with_logging, command, process_id)
    
    return jsonify({'process_id': process_id, 'command': ' '.join(command)})


@app.route('/api/git/commit', methods=['POST'])
def git_commit():
    """API endpoint for git commit with custom message."""
    data = request.json
    commit_message = data.get('message', 'Update configurations via admin panel')
    
    process_id = f"git_commit_{int(time.time())}"
    command = ['git', 'commit', '-m', commit_message]
    
    # Run command with logging using gevent-compatible approach
    import gevent
    gevent.spawn(run_command_with_logging, command, process_id)
    
    return jsonify({'process_id': process_id, 'command': ' '.join(command)})


@app.route('/api/git/push', methods=['POST'])
def git_push():
    """API endpoint for git push."""
    process_id = f"git_push_{int(time.time())}"
    command = ['git', 'push']
    
    # Run command with logging using gevent-compatible approach
    import gevent
    gevent.spawn(run_command_with_logging, command, process_id)
    
    return jsonify({'process_id': process_id, 'command': ' '.join(command)})


@app.route('/api/files/<file_type>')
def get_files(file_type):
    """API endpoint to get detailed file information for modals."""
    workflow = WorkflowStatus()
    config_dir = workflow.config_dir
    
    try:
        files = []
        
        if file_type == 'instagram-configs':
            # Get all Instagram config files
            for config_file in config_dir.glob('reel_*.json'):
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    files.append({
                        'name': config_file.name,
                        'path': str(config_file),
                        'scheduled_time': config.get('scheduled_time'),
                        'posted': config.get('posted', False),
                        'posted_at': config.get('posted_at'),
                        'video_url': config.get('video_url'),
                        'caption_preview': config.get('caption', '')[:100] + '...' if config.get('caption', '') else '',
                        'modified': config_file.stat().st_mtime
                    })
                except Exception:
                    continue
                    
        elif file_type == 'notion-configs':
            # Get all Notion config files
            for config_file in config_dir.glob('notion_*.json'):
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    files.append({
                        'name': config_file.name,
                        'path': str(config_file),
                        'scheduled_time': config.get('scheduled_time'),
                        'video_path': config.get('video_path'),
                        'modified': config_file.stat().st_mtime
                    })
                except Exception:
                    continue
                    
        elif file_type == 'pending-posts':
            # Get pending Instagram posts
            for config_file in config_dir.glob('reel_*.json'):
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    if not config.get('posted', False):
                        files.append({
                            'name': config_file.name,
                            'path': str(config_file),
                            'scheduled_time': config.get('scheduled_time'),
                            'posted': False,
                            'video_url': config.get('video_url'),
                            'caption_preview': config.get('caption', '')[:100] + '...' if config.get('caption', '') else '',
                            'modified': config_file.stat().st_mtime
                        })
                except Exception:
                    continue
                    
        elif file_type == 'recent-posts':
            # Get recent posted Instagram posts (last 7 days)
            one_week_ago = datetime.now(pytz.timezone('Europe/Paris')) - timedelta(weeks=1)
            
            for config_file in config_dir.glob('reel_*.json'):
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    if config.get('posted', False):
                        posted_at = config.get('posted_at')
                        if posted_at:
                            try:
                                posted_date = datetime.fromisoformat(posted_at)
                                if posted_date.tzinfo is None:
                                    paris_tz = pytz.timezone('Europe/Paris')
                                    posted_date = paris_tz.localize(posted_date)
                                
                                if posted_date > one_week_ago:
                                    files.append({
                                        'name': config_file.name,
                                        'path': str(config_file),
                                        'scheduled_time': config.get('scheduled_time'),
                                        'posted': True,
                                        'posted_at': posted_at,
                                        'video_url': config.get('video_url'),
                                        'caption_preview': config.get('caption', '')[:100] + '...' if config.get('caption', '') else '',
                                        'modified': config_file.stat().st_mtime
                                    })
                            except (ValueError, TypeError):
                                continue
                except Exception:
                    continue
        
        # Sort files by modification time (newest first)
        files.sort(key=lambda x: x['modified'], reverse=True)
        
        return jsonify(files)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/file/content')
def get_file_content():
    """API endpoint to get file content for viewing."""
    file_path = request.args.get('path')
    
    if not file_path:
        return "Missing file path", 400
    
    try:
        # Security check - ensure path is within project directory
        project_root = Path(__file__).parent
        requested_path = Path(file_path).resolve()
        
        if not str(requested_path).startswith(str(project_root)):
            return "Access denied", 403
        
        if not requested_path.exists():
            return "File not found", 404
        
        with open(requested_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return content, 200, {'Content-Type': 'text/plain; charset=utf-8'}
        
    except Exception as e:
        return f"Error reading file: {str(e)}", 500


@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection."""
    print('Client connected')
    emit('connected', {'data': 'Connected to admin panel'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection."""
    print('Client disconnected')


if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    templates_dir = Path(__file__).parent / 'templates'
    templates_dir.mkdir(exist_ok=True)
    
    # Find available port
    import socket
    def find_free_port(start_port=5000):
        for port in range(start_port, start_port + 10):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(('localhost', port))
                    return port
                except OSError:
                    continue
        return None
    
    port = find_free_port()
    if not port:
        print("❌ No available ports found in range 5000-5009")
        exit(1)
    
    print("🚀 Starting Instagram Reel Automation Admin Panel...")
    print(f"🌐 Access the panel at: http://localhost:{port}")
    print("📱 Press Ctrl+C to stop")
    print("🔧 Starting server with hot reloading...")
    print("💡 Hot reloading enabled - server will restart on file changes")
    
    # Configure reloader to watch additional files
    import os
    extra_files = [
        str(Path(__file__).parent / 'templates' / 'admin.html'),
        str(Path(__file__).parent / '.env'),
    ]
    
    try:
        socketio.run(
            app, 
            host='0.0.0.0', 
            port=port, 
            debug=True, 
            use_reloader=True,
            reloader_options={'extra_files': extra_files},
            allow_unsafe_werkzeug=True
        )
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        exit(1)