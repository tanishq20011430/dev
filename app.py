from flask import Flask, config, render_template, request, jsonify, session, redirect, url_for, send_file, send_from_directory
from urllib.parse import quote_plus
import os
import time
import csv
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import create_engine, text
from werkzeug.utils import secure_filename
import subprocess
from functools import wraps
from config import ProductionConfig
from users import UserManager
from predefined_queries import PREDEFINED_QUERIES, predefined_queries_bp
import logging
import re

app = Flask(__name__)
app.config.from_object(ProductionConfig)

# Register the predefined queries blueprint
app.register_blueprint(predefined_queries_bp)

# Set up logging
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Initialize UserManager with app context
with app.app_context():
    user_manager = UserManager()

# Login decorator with role-based access
def login_required(permission='view'):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'username' not in session:
                return redirect(url_for('login'))
            if not user_manager.has_permission(session['username'], permission):
                app.logger.warning(f"Permission denied for {session['username']} - required: {permission}")
                return jsonify({'error': 'Permission denied'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Ensure batch files root directory exists
os.makedirs(app.config['BATCH_FILES_ROOT'], exist_ok=True)

# Configure download directory
QUERY_RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'query_results')
os.makedirs(QUERY_RESULTS_DIR, exist_ok=True)

@app.route('/sql_output/<filename>')
@login_required('run')
def sql_output(filename):
    """Display SQL query results with efficient filtering and pagination."""
    try:
        # Security check: verify filename belongs to user
        if not filename.startswith(f"query_results_{session['username']}_"):
            app.logger.warning(f"Unauthorized access attempt: {filename}")
            return "Unauthorized", 403
            
        filepath = os.path.join(QUERY_RESULTS_DIR, secure_filename(filename))
        if not os.path.exists(filepath):
            return "File not found", 404

        # Get file size
        file_size = os.path.getsize(filepath)
        
        # For large files (>100MB), just read headers
        if file_size > 100 * 1024 * 1024:  # 100MB
            with open(filepath, 'r') as f:
                csv_reader = csv.reader(f)
                columns = next(csv_reader)  # Get header row only
        else:
            # For smaller files, read all headers
            df = pd.read_csv(filepath, nrows=1)
            columns = list(df.columns)

        # Create a URL for accessing the CSV file
        csv_url = url_for('download_results', filename=filename, _external=True)
        
        return render_template('sql_output.html',
                             columns=columns,
                             csv_url=csv_url,
                             username=session['username'],
                             role=session['role'])
    except Exception as e:
        app.logger.error(f"Error displaying SQL output: {str(e)}")
        return str(e), 500

@app.route('/delete_temp_csv', methods=['POST'])
@login_required('run')
def delete_temp_csv():
    """Delete a temporary CSV file generated for the current user."""
    try:
        data = request.get_json()
        filename = data.get('filename')
        if not filename:
            return jsonify({'success': False, 'error': 'No filename provided'}), 400

        # Security: Only allow deletion of files belonging to the current user
        expected_prefix = f"query_results_{session['username']}_"
        if not filename.startswith(expected_prefix):
            app.logger.warning(f"User {session['username']} tried to delete unauthorized file: {filename}")
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403

        filepath = os.path.join(QUERY_RESULTS_DIR, secure_filename(filename))
        if os.path.exists(filepath):
            os.remove(filepath)
            app.logger.info(f"Deleted temp CSV: {filename} for user {session['username']}")
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'File not found'}), 404
    except Exception as e:
        app.logger.error(f"Error deleting temp CSV: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

def clean_sql_query(query, schema=None):
    """Clean and validate SQL query with schema handling"""
    query = query.strip()
    
    # If no schema specified, use default
    if not schema:
        schema = ProductionConfig.get_default_schema()
        
    # Validate schema
    available_schemas = ProductionConfig.get_available_schemas()
    if schema not in available_schemas:
        raise ValueError(f"Invalid schema. Available schemas: {', '.join(available_schemas)}")

    # Remove comments and normalize whitespace
    lines = [line.split('--')[0].strip() for line in query.splitlines()]
    query = ' '.join(line for line in lines if line)

    # Handle parentheses and functions
    stack = []
    result = []
    buffer = ''
    for char in query:
        if char == '(':
            if buffer.strip().upper() in ('SELECT', 'FROM', 'WHERE', 'AND', 'OR'):
                result.append(f"{buffer} ")
                buffer = char
            else:
                buffer += char
            stack.append(char)
        elif char == ')':
            if not stack:
                raise ValueError("Unmatched closing parenthesis")
            stack.pop()
            buffer += char
        else:
            buffer += char
        
        if not stack and char in ' \n':
            if buffer.strip():
                result.append(buffer)
            buffer = ''

    if stack:
        raise ValueError("Unclosed parenthesis")
    
    if buffer.strip():
        result.append(buffer)

    query = ' '.join(result).strip()
    
    # Validate SELECT and FROM
    query_lower = query.lower()
    if not query_lower.startswith('select'):
        raise ValueError("Query must start with SELECT")
    if 'from' not in query_lower:
        raise ValueError("Query must contain FROM clause")

    # Check for schema in table references
    parts = query.lower().split('from')
    if len(parts) > 1:
        table_part = parts[1].strip()
        # Only add schema if table name does not already contain a dot
        if table_part:
            table_name = table_part.split()[0]
            if '.' not in table_name:
                remaining = ' '.join(table_part.split()[1:])
                parts[1] = f" {schema}.{table_name} {remaining}"
                query = 'FROM'.join(parts)

    return query

def get_db_connection():
    """Get database connection with proper configuration"""
    creds = ProductionConfig.PG_CREDENTIALS
    try:
        db_url = (
            f"postgresql://{quote_plus(creds['username'])}:{quote_plus(creds['password'])}@"
            f"{creds['hostname']}:{creds['port']}/{creds['maintenance_db']}"
        )
        engine = create_engine(
            db_url,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800
        )
        return engine
    except Exception as e:
        app.logger.error(f"Database connection error: {str(e)}")
        raise

def execute_query_internal(query, schema):
    """Internal function to execute SQL queries, used by both direct and predefined queries"""
    try:
        # Block queries that modify or delete data
        forbidden_keywords = [
            'delete', 'update', 'insert', 'alter', 'drop', 'truncate', 'create', 'replace', 'grant', 'revoke', 'comment', 'rename', 'set', 'call', 'merge', 'attach', 'detach', 'vacuum', 'reindex', 'analyze', 'cluster', 'discard', 'refresh', 'copy', 'lock', 'unlisten', 'listen', 'notify', 'unlisten', 'execute', 'prepare', 'deallocate', 'commit', 'rollback', 'savepoint', 'release', 'begin', 'end', 'abort', 'purge', 'backup', 'restore', 'load', 'unload', 'shutdown', 'start', 'stop', 'restart', 'grant', 'revoke', 'explain analyze'
        ]
        # Only block if the query starts with or contains a forbidden keyword as a statement (not as a column/table name)
        lowered = query.strip().lower()
        for keyword in forbidden_keywords:
            # Block if query starts with forbidden keyword or contains it as a statement
            if re.match(rf"^\s*{keyword}\\b", lowered) or re.search(rf";\s*{keyword}\\b", lowered):
                return jsonify({
                    'success': False,
                    'error': f'Queries that modify or delete data (e.g., {keyword.upper()}) are not allowed.'
                }), 400

        engine = get_db_connection()
        
        # Set timeout and row limit
        MAX_ROWS = 1000000  # 1 million rows limit
        CHUNK_SIZE = 5000   # Reduced chunk size for memory efficiency
        
        # Add LIMIT if not present to prevent accidental huge result sets
        if 'limit' not in query.lower() and 'offset' not in query.lower():
            query += ' LIMIT 1000000'  # Default limit of 1 million rows
        
        try:
            # Generate unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"query_results_{session['username']}_{timestamp}.csv"
            filepath = os.path.join(QUERY_RESULTS_DIR, secure_filename(filename))
            
            # Execute query with server-side cursor and write directly to CSV in chunks
            with engine.connect() as connection:
                query_result = connection.execute(text(query))
                
                # Write headers first
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(query_result.keys())
                    
                    row_count = 0
                    while True:
                        chunk = query_result.fetchmany(CHUNK_SIZE)
                        if not chunk:
                            break
                            
                        # Check row limit
                        if row_count + len(chunk) > MAX_ROWS:
                            raise Exception(f"Query would return more than {MAX_ROWS:,} rows. Please add a LIMIT clause.")
                            
                        writer.writerows(chunk)
                        row_count += len(chunk)

            # Log the action
            details = (f"Query: {query}\n"
                    f"Rows returned: {row_count}\n"
                    f"Output file: {filename}")
            user_manager.log_action(session['username'], 'query_execution', details)
            
            return jsonify({
                'success': True,
                'redirect_url': url_for('sql_output', filename=filename)
            })

        except Exception as e:
            error_msg = str(e)
            if "would return more than" in error_msg:
                error_msg = f"Query result too large. {error_msg}"
            
            error_details = f"Failed Query: {query}\nError: {error_msg}"
            user_manager.log_action(session['username'], 'query_execution_failed', error_details)
            
            app.logger.error(f"Query execution error: {error_msg}")
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        if 'engine' in locals():
            engine.dispose()

@app.route('/execute_query', methods=['POST'])
@login_required('run')
def execute_query():
    """Execute SQL query with schema support"""
    try:
        query = request.json.get('query', '').strip()
        schema = request.json.get('schema', ProductionConfig.get_default_schema())
        
        # Clean and validate query with schema
        query = clean_sql_query(query, schema)
        
        return execute_query_internal(query, schema)
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        app.logger.error(f"Query execution error: {str(e)}")
        return jsonify({
            'success': False,
            'error': "An error occurred while executing the query"
        }), 500

@app.route('/download/<filename>')
@login_required('run')
def download_results(filename):
    """Handle file downloads with security checks."""
    try:
        # Security check: verify filename belongs to user
        if not filename.startswith(f"query_results_{session['username']}_"):
            app.logger.warning(f"Unauthorized download attempt: {filename}")
            return "Unauthorized", 403
            
        filepath = os.path.join(QUERY_RESULTS_DIR, secure_filename(filename))
        if not os.path.exists(filepath):
            return "File not found", 404
            
        return send_file(filepath, 
                        mimetype='text/csv',
                        as_attachment=False,  # Changed to false to allow browser display
                        download_name=filename)
    except Exception as e:
        app.logger.error(f"Download error: {str(e)}")
        return "Download failed", 500

@app.route('/execute_predefined_query/<query_type>')
@login_required('run')
def execute_predefined_query(query_type):
    """Execute a predefined query and return results as JSON"""
    try:
        if query_type not in PREDEFINED_QUERIES:
            return jsonify({
                'success': False,
                'error': 'Invalid query type'
            }), 400

        schema = ProductionConfig.get_default_schema()
        query = PREDEFINED_QUERIES[query_type].format(schema=schema).strip()

        return execute_query_internal(query, schema)

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Add cleanup function for old files
def cleanup_old_files():
    """Remove files older than 1 hour."""
    try:
        current_time = datetime.now()
        for filename in os.listdir(QUERY_RESULTS_DIR):
            filepath = os.path.join(QUERY_RESULTS_DIR, filename)
            file_modified = datetime.fromtimestamp(os.path.getmtime(filepath))
            if current_time - file_modified > timedelta(hours=1):
                os.remove(filepath)
    except Exception as e:
        app.logger.error(f"Cleanup error: {str(e)}")

# Add cleanup to existing routes
@app.before_request
def before_request():
    """Cleanup old files before processing requests."""
    cleanup_old_files()

@app.route('/')
def index():
    """Redirect to login page if not authenticated, otherwise go to home."""
    if 'username' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('home'))

@app.route('/home')
@login_required('view')
def home():
    """Serve the home page after login."""
    return render_template('home.html', username=session['username'], role=session['role'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = user_manager.validate_user(username, password)
        if user:
            session['username'] = user['username']
            session['role'] = user['role']
            # Log login event
            user_manager.log_action(username, 'login')
            app.logger.info(f"User {username} logged in successfully")
            return redirect(url_for('home'))
        else:
            error = 'Invalid username or password'
            app.logger.warning(f"Failed login attempt for username: {username}")
    
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    """Handle user logout."""
    username = session.get('username', 'Guest')  # Get username before clearing session
    if 'username' in session:
        app.logger.info(f"User {session['username']} logged out")
        user_manager.log_action(session['username'], 'logout')
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('thank_you', username=username))

@app.route('/thank_you/<username>')
def thank_you(username):
    """Display thank you page after logout."""
    return render_template('thank_you.html', username=username)

@app.route('/dashboard')
@login_required('view')
def dashboard():
    """Display the dashboard with folder list."""
    try:
        all_folders = [d for d in os.listdir(app.config['BATCH_FILES_ROOT']) 
                    if os.path.isdir(os.path.join(app.config['BATCH_FILES_ROOT'], d))]
        
        # Filter folders based on username and role
        if session['role'] == 'admin':
            # Admin can see all folders
            folders = all_folders
        else:
            # Other users can only see their matching folder name
            folders = [f for f in all_folders if f == session['username']]
            
        if not folders:
            app.logger.warning(f"No matching folder found for user: {session['username']}")
    except Exception as e:
        folders = []
        app.logger.error(f"Error loading folders: {str(e)}")
    
    return render_template('dashboard.html', 
                         username=session['username'],
                         folders=folders,
                         role=session['role'])

@app.route('/folder/<folder_name>')
@login_required('view')
def folder_view(folder_name):
    """Display contents of a specific folder."""
    # Check if user has access to this folder
    if session['role'] != 'admin' and folder_name != session['username']:
        app.logger.warning(f"User {session['username']} attempted to access unauthorized folder: {folder_name}")
        return redirect(url_for('dashboard'))

    try:
        folder_path = os.path.join(app.config['BATCH_FILES_ROOT'], folder_name)
        if not os.path.exists(folder_path):
            app.logger.warning(f"Folder not found: {folder_path}")
            return redirect(url_for('dashboard'))
        
        batch_files = [f for f in os.listdir(folder_path) 
                      if f.endswith('.bat')]
    except Exception as e:
        batch_files = []
        app.logger.error(f"Error loading batch files: {str(e)}")
    
    # Check if user is a guest
    is_guest = session['role'] == 'guest'
    
    return render_template('folder_view.html',
                         folder_name=folder_name,
                         batch_files=batch_files,
                         role=session['role'],
                         is_guest=is_guest)

@app.route('/run_batch/<folder>/<file>')
@login_required('run')
def run_batch(folder, file):
    """Execute a batch file and track new files."""
    if session['role'] != 'admin' and folder != session['username']:
        app.logger.warning(f"User {session['username']} attempted to run batch file from unauthorized folder: {folder}")
        return jsonify({'success': False, 'error': 'Access denied'}), 403

    try:
        output_folder = app.config['BATCH_OUTPUT_ROOT']
        os.makedirs(output_folder, exist_ok=True)
        
        # Execute batch file
        file_path = os.path.join(app.config['BATCH_FILES_ROOT'], folder, file)
        if not os.path.exists(file_path):
            app.logger.warning(f"Batch file not found: {file_path}")
            return jsonify({
                'success': False,
                'error': f"Batch file not found: {file}"
            }), 404

        # Get base filename without extension for matching
        base_filename = os.path.splitext(file)[0]
        
        result = subprocess.run(file_path, capture_output=True, text=True, shell=True)
        success = result.returncode == 0
        
        # Wait briefly for file creation
        time.sleep(2)
        
        # Look for any file in the output directory (most recent first)
        output_file = None
        if os.path.exists(output_folder):
            files = os.listdir(output_folder)
            if files:
                # Sort files by creation time, most recent first
                files.sort(key=lambda x: os.path.getctime(os.path.join(output_folder, x)), reverse=True)
                # Get the most recently created file
                last_modified = os.path.getmtime(os.path.join(output_folder, files[0]))
                # Only consider files created in the last 5 seconds
                if time.time() - last_modified < 5:
                    output_file = files[0]
        
        # Log action
        username = session['username']
        details = f"Folder: {folder}, File: {file}, Success: {success}"
        if output_file:
            details += f", Output file: {output_file}"
        user_manager.log_action(username, 'run_batch', details)
        
        app.logger.info(f"Batch execution completed. Output file: {output_file}")
        
        return jsonify({
            'success': success,
            'output': result.stdout,
            'error': result.stderr,
            'new_file': output_file
        })
    except Exception as e:
        app.logger.error(f"Error running batch file: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/download_output/<path:filename>')
@login_required('run')
def download_output(filename):
    """Download files created by batch execution."""
    try:
        output_folder = app.config['BATCH_OUTPUT_ROOT']
        if not os.path.exists(os.path.join(output_folder, filename)):
            return "File not found", 404
        
        return send_file(
            os.path.join(output_folder, filename),
            as_attachment=True,
            mimetype='text/csv',
            download_name=filename
        )
    except Exception as e:
        app.logger.error(f"Download error: {str(e)}")
        return "Download failed", 500

@app.route('/list_batch_files')
@login_required('run')
def list_batch_files():
    """List all available batch files."""
    files = []
    try:
        root_dir = app.config['BATCH_FILES_ROOT']
        for folder in os.listdir(root_dir):
            folder_path = os.path.join(root_dir, folder)
            if os.path.isdir(folder_path):
                for file in os.listdir(folder_path):
                    if file.endswith('.bat'):
                        files.append({
                            'folder': folder,
                            'name': file
                        })
    except Exception as e:
        app.logger.error(f"Error listing batch files: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
    
    return jsonify({'success': True, 'files': files})

@app.route('/get_batch_content/<path:file_path>')
@login_required('run')
def get_batch_content(file_path):
    """Get the content of a batch file."""
    try:
        folder, file = file_path.split('/')
        
        # Security check
        if session['role'] != 'admin' and folder != session['username']:
            return "Access denied", 403
        
        file_path = os.path.join(app.config['BATCH_FILES_ROOT'], folder, file)
        
        if not os.path.exists(file_path):
            return "File not found", 404
            
        with open(file_path, 'r') as f:
            content = f.read()
        return content
    except Exception as e:
        app.logger.error(f"Error reading batch file: {str(e)}")
        return str(e), 500

@app.route('/save_batch_file', methods=['POST'])
@login_required('run')
def save_batch_file():
    """Save changes to a batch file."""
    try:
        data = request.json
        file_path = data.get('file_path')
        content = data.get('content')
        
        if not file_path or not content:
            return jsonify({'success': False, 'error': 'Missing file path or content'}), 400
            
        folder, file = file_path.split('/')
        
        # Security check
        if session['role'] != 'admin' and folder != session['username']:
            return jsonify({'success': False, 'error': 'Access denied'}), 403
            
        full_path = os.path.join(app.config['BATCH_FILES_ROOT'], folder, file)
        
        # Save the file
        with open(full_path, 'w') as f:
            f.write(content)
            
        # Log the action
        user_manager.log_action(session['username'], 'edit_batch_file', f"Edited {file_path}")
        
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error saving batch file: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.context_processor
def inject_user():
    """Inject username and role into all templates from session."""
    username = session.get('username', 'Guest')  # Fallback to 'Guest' if not logged in
    role = session.get('role', 'guest')  # Fallback to 'guest' if not set
    return dict(username=username, role=role)

@app.route('/manage_users', methods=['GET', 'POST'])
@login_required('manage')
def manage_users():
    """Manage user accounts."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        
        try:
            if user_manager.add_user(username, password, role):
                user_manager.log_action(session['username'], 'add_user', f"Added user: {username} with role: {role}")
                app.logger.info(f"Admin {session['username']} added user: {username}")
                return redirect(url_for('manage_users'))
            else:
                app.logger.warning(f"Failed to add user {username}: Username already exists")
                return render_template('manage_users.html', 
                                    users=user_manager.get_all_users(),
                                    error='Username already exists')
        except ValueError as e:
            app.logger.error(f"Error adding user: {str(e)}")
            return render_template('manage_users.html',
                                 users=user_manager.get_all_users(),
                                 error=str(e))
    
    return render_template('manage_users.html', 
                         users=user_manager.get_all_users())

@app.route('/delete_user/<username>', methods=['POST'])
@login_required('manage')
def delete_user(username):
    """Delete a user account."""
    try:
        # Extra check to ensure only admins can delete users
        if session.get('role') != 'admin':
            app.logger.warning(f"Non-admin user {session['username']} attempted to delete a user")
            return jsonify({'success': False, 'error': 'Only administrators can delete users'}), 403
            
        if username == 'admin':
            app.logger.warning(f"Attempt to delete admin user by {session['username']}")
            return jsonify({'success': False, 'error': 'Cannot delete admin user'}), 403
        
        if username == session['username']:
            app.logger.warning(f"User {session['username']} attempted to delete their own account")
            return jsonify({'success': False, 'error': 'Cannot delete your own account'}), 403
        
        if user_manager.delete_user(username):
            # Log user deletion
            user_manager.log_action(session['username'], 'delete_user', f"Deleted user: {username}")
            app.logger.info(f"Admin {session['username']} deleted user: {username}")
            return jsonify({'success': True})
        else:
            app.logger.warning(f"Failed to delete user {username}")
            return jsonify({'success': False, 'error': 'User not found or could not be deleted'}), 404
    except Exception as e:
        app.logger.error(f"Error deleting user: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/execution_history')
@login_required('run')  # Change from 'manage' to 'run' so users can view history
def execution_history():
    """Display execution history."""
    try:
        # Only admin can see all history, others see only their own
        if session.get('role') == 'admin':
            history = user_manager.get_execution_history()
        else:
            username = session.get('username')
            all_history = user_manager.get_execution_history()
            history = [entry for entry in all_history if entry.get('username') == username]
        return render_template('execution_history.html', history=history)
    except Exception as e:
        app.logger.error(f"Error fetching execution history: {str(e)}")
        return render_template('execution_history.html', history=[], error=str(e))

@app.route('/query')
@login_required('run')
def query_interface():
    """Display SQL query interface."""
    schemas = ProductionConfig.get_available_schemas()
    default_schema = ProductionConfig.get_default_schema()
    return render_template('query_interface.html',
                         username=session['username'],
                         role=session['role'],
                         schemas=schemas,
                         default_schema=default_schema)

@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_from_directory(
            config.BATCH_OUTPUT_ROOT,
            filename,
            as_attachment=True
        )
    except FileNotFoundError:
        return {'error': 'File not found'}, 404

if __name__ == "__main__":
    app.secret_key = app.config['SECRET_KEY']  # Required for session management
    app.run(host="0.0.0.0", port=5001, debug=True)