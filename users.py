import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
from config import ProductionConfig

# User roles
ROLES = {
    'admin': ['view', 'run', 'manage'],
    'user': ['view', 'run'],
    'guest': ['view']
}

class UserManager:
    def __init__(self):
        self.pg_config = ProductionConfig.PG_CREDENTIALS
        self.schema = self.pg_config['default_schema']  # Use default schema
        self.init_db()

    def get_db_connection(self):
        """Get database connection"""
        try:
            return psycopg2.connect(
                host=self.pg_config['hostname'],
                port=self.pg_config['port'],
                database=self.pg_config['maintenance_db'],
                user=self.pg_config['username'],
                password=self.pg_config['password']
            )
        except Exception as e:
            print(f"Database connection error: {e}")
            return None

    def init_db(self):
        """Initialize the database"""
        conn = self.get_db_connection()
        if conn is None:
            return
        
        with conn:
            with conn.cursor() as cursor:
                # Create users table in default schema
                cursor.execute(f'''
                    CREATE TABLE IF NOT EXISTS {self.schema}.users (
                        id SERIAL PRIMARY KEY,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        role TEXT NOT NULL
                    )
                ''')

                # Create default admin user if not exists
                admin_password = generate_password_hash('admin123')
                cursor.execute(f'''
                    INSERT INTO {self.schema}.users (username, password_hash, role)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (username) DO NOTHING
                ''', ('admin', admin_password, 'admin'))

                cursor.execute(f'''
                    CREATE TABLE IF NOT EXISTS {self.schema}.executions (
                        id SERIAL PRIMARY KEY,
                        username TEXT NOT NULL,
                        action TEXT NOT NULL,
                        details TEXT,
                        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                ''')

        conn.close()

    def validate_user(self, username, password):
        """Validate user credentials"""
        conn = self.get_db_connection()
        if conn is None:
            return None
        
        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute(f'SELECT username, password_hash, role FROM {self.schema}.users WHERE username = %s', (username,))
                    user = cursor.fetchone()
                    if user and check_password_hash(user[1], password):  # user[1] is password_hash
                        return {'username': user[0], 'role': user[2]}  # user[0] is username, user[2] is role
            return None
        finally:
            conn.close()

    def has_permission(self, username, permission):
        """Check if user has specific permission"""
        conn = self.get_db_connection()
        if conn is None:
            return False
        
        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute(f'SELECT role FROM {self.schema}.users WHERE username = %s', (username,))
                    user = cursor.fetchone()
                    return user and user[0] in ROLES and permission in ROLES[user[0]]
        finally:
            conn.close()

    def add_user(self, username, password, role):
        """Add a new user"""
        if role not in ROLES:
            raise ValueError("Invalid role")
        
        conn = self.get_db_connection()
        if conn is None:
            return False

        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute(f'''
                        INSERT INTO {self.schema}.users (username, password_hash, role)
                        VALUES (%s, %s, %s)
                    ''', (username, generate_password_hash(password), role))
            return True
        except psycopg2.IntegrityError:
            return False
        finally:
            conn.close()

    def get_all_users(self):
        """Get all users"""
        conn = self.get_db_connection()
        if conn is None:
            return []

        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute(f'SELECT username, role FROM {self.schema}.users')
                    users = cursor.fetchall()
            return [{'username': user[0], 'role': user[1]} for user in users]
        finally:
            conn.close()

    def log_action(self, username, action, details=None):
        """Log user actions"""
        conn = self.get_db_connection()
        if conn is None:
            return False
        
        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute(f'''
                        INSERT INTO {self.schema}.executions (username, action, details, timestamp)
                        VALUES (%s, %s, %s, NOW())
                    ''', (username, action, details))
            return True
        finally:
            conn.close()

    def get_execution_history(self):
        """Get all execution history"""
        conn = self.get_db_connection()
        if conn is None:
            return []

        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute(f'SELECT id, username, action, details, timestamp FROM {self.schema}.executions ORDER BY timestamp DESC')
                    history = cursor.fetchall()
            return [{'id': row[0], 'username': row[1], 'action': row[2], 'details': row[3], 'timestamp': row[4]} 
                    for row in history]
        finally:
            conn.close()

    def delete_user(self, username):
        """Delete a user"""
        # Don't allow deleting the admin user
        if username == 'admin' and username == 'tanishq':
            return False
            
        conn = self.get_db_connection()
        if conn is None:
            return False
        
        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute(f'DELETE FROM {self.schema}.users WHERE username = %s', (username,))
                    # Return True if at least one row was affected
                    return cursor.rowcount > 0
        finally:
            conn.close()
