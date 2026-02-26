"""Database connection and initialization manager"""

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path


class DBManager:
    """Manages SQLite database connection and initialization"""

    def __init__(self, db_path: str = 'data/tags.db'):
        self.db_path = db_path
        self.connection = None
        self._lock = threading.Lock()
        self._initialize()

    @contextmanager
    def get_cursor(self):
        """Thread-safe cursor access with automatic commit/rollback."""
        with self._lock:
            cursor = self.connection.cursor()
            try:
                yield cursor
                self.connection.commit()
            except Exception:
                self.connection.rollback()
                raise

    def _initialize(self):
        """Initialize database connection and create tables"""
        # Ensure data directory exists
        db_dir = Path(self.db_path).parent
        if not db_dir.exists():
            db_dir.mkdir(parents=True, exist_ok=True)

        # Connect to database
        self.connection = sqlite3.connect(
            self.db_path,
            check_same_thread=False  # Allow multi-threaded access
        )
        self.connection.row_factory = sqlite3.Row  # Access columns by name

        # Create tables from schema
        self._create_tables()

    def _create_tables(self):
        """Create database tables from schema.sql"""
        schema_path = Path(__file__).parent / 'schema.sql'

        try:
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
                self.connection.executescript(schema_sql)
                self.connection.commit()
        except FileNotFoundError:
            # Fallback: create tables inline if schema.sql not found
            self._create_tables_inline()

    def _create_tables_inline(self):
        """Fallback method to create tables if schema.sql is missing"""
        cursor = self.connection.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tags (
                tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                data_type TEXT NOT NULL,
                value_blob BLOB,
                description TEXT,
                is_array INTEGER DEFAULT 0,
                array_dimensions TEXT,
                udt_type_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS udts (
                udt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                definition_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS server_config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_udts_name ON udts(name)')

        self.connection.commit()

    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

    def __del__(self):
        """Cleanup on deletion"""
        self.close()
