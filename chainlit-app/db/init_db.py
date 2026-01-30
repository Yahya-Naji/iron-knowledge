"""
Initialize database with schema and sample data
"""
import sqlite3
import os
from pathlib import Path
from chainlit.logger import logger

def init_database(db_path: str):
    """Initialize database with schema and sample data if tables don't exist"""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if customers table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='ironmountain_customers'
        """)
        
        if cursor.fetchone():
            logger.info("✅ Database already initialized")
            cursor.close()
            conn.close()
            return
        
        logger.info("🚀 Initializing database with schema and sample data...")
        
        # Create Iron Mountain customers table
        cursor.execute("""
            CREATE TABLE ironmountain_customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_number VARCHAR(20) UNIQUE NOT NULL,
                customer_name VARCHAR(100) NOT NULL,
                company_name VARCHAR(150),
                address TEXT NOT NULL,
                phone_number VARCHAR(20),
                email VARCHAR(100),
                boxes_retained INTEGER DEFAULT 0,
                boxes_requested INTEGER DEFAULT 0,
                last_request_date TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create index on account_number
        cursor.execute("""
            CREATE INDEX idx_account_number ON ironmountain_customers(account_number)
        """)
        
        # Create box_requests table
        cursor.execute("""
            CREATE TABLE box_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_number VARCHAR(20) NOT NULL,
                quantity INTEGER NOT NULL,
                cancellation_token VARCHAR(255) UNIQUE NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                cancelled_at TIMESTAMP,
                FOREIGN KEY (account_number) REFERENCES ironmountain_customers(account_number) ON DELETE CASCADE
            )
        """)
        
        # Create indexes for box_requests
        cursor.execute("""
            CREATE INDEX idx_box_requests_account ON box_requests(account_number)
        """)
        
        cursor.execute("""
            CREATE INDEX idx_box_requests_token ON box_requests(cancellation_token)
        """)
        
        cursor.execute("""
            CREATE INDEX idx_box_requests_status ON box_requests(status)
        """)
        
        # Insert sample customer data
        customers = [
            ('IM-10001', 'Yousef Al-Mansoori', 'Tech Innovations LLC', 'Dubai Marina, Dubai, UAE', '+971-50-123-4567', 'yousef@techinnovations.ae', 15, 0),
            ('IM-10002', 'Sarah Johnson', 'Legal Associates', 'Al Maryah Island, Abu Dhabi, UAE', '+971-50-234-5678', 'sarah@legalassoc.ae', 8, 0),
            ('IM-10003', 'Ahmed Hassan', 'Financial Consultants', 'Business Bay, Dubai, UAE', '+971-50-345-6789', 'ahmed@finconsult.ae', 22, 0),
            ('IM-10004', 'Emily Roberts', 'Healthcare Solutions', 'Dubai Healthcare City, Dubai, UAE', '+971-50-456-7890', 'emily@healthsol.ae', 12, 0),
            ('IM-10005', 'Mohammed Ali', 'Trading Partners LLC', 'Deira, Dubai, UAE', '+971-50-567-8901', 'mohammed@tradingpartners.ae', 30, 0)
        ]
        
        cursor.executemany("""
            INSERT INTO ironmountain_customers 
            (account_number, customer_name, company_name, address, phone_number, email, boxes_retained, boxes_requested)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, customers)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info("✅ Database initialized successfully with 5 customer accounts!")
        
    except Exception as e:
        logger.error(f"❌ Error initializing database: {e}")
