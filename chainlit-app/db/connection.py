"""
Database connection utilities
"""
import os
from pathlib import Path
from dotenv import load_dotenv
import sqlite3
from chainlit.logger import logger

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

# SQLite Database Configuration
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "../database/ironmountain.db")


def get_db_connection():
    """Get SQLite connection to ironmountain database"""
    try:
        possible_paths = [
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", SQLITE_DB_PATH)),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "database", "ironmountain.db")),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "database", "ironmountain.db")),
        ]
        
        for db_path in possible_paths:
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                return conn
        
        # Create at first location if not found
        db_path = possible_paths[0]
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None
