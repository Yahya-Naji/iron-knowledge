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

# SQLite Database Configuration - use /tmp for Railway (persistent storage)
# In production, use /tmp which is writable, or Railway's persistent volume
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "/tmp/database/ironmountain.db")

# Initialize flag to prevent multiple initializations
_db_initialized = False


def get_db_connection():
    """Get SQLite connection to ironmountain database"""
    global _db_initialized
    
    try:
        # Use the configured path
        db_path = SQLITE_DB_PATH
        
        # If relative path, try to resolve it
        if not os.path.isabs(db_path):
            possible_paths = [
                os.path.abspath(os.path.join(os.path.dirname(__file__), "..", db_path)),
                os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "database", "ironmountain.db")),
                os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "database", "ironmountain.db")),
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    db_path = path
                    break
            else:
                # Use first path if none exist
                db_path = possible_paths[0]
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Connect to database
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        # Initialize database if not already done
        if not _db_initialized:
            from db.init_db import init_database
            init_database(db_path)
            _db_initialized = True
        
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None
