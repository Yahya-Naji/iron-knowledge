#!/usr/bin/env python3
"""
Create SQLite database for Iron Mountain with schema and sample data
"""
import sqlite3
import os
from datetime import datetime

# Database file path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database', 'ironmountain.db')
DB_DIR = os.path.dirname(DB_PATH)

# Create database directory if it doesn't exist
os.makedirs(DB_DIR, exist_ok=True)

# Remove existing database if it exists
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
    print(f"🗑️  Removed existing database: {DB_PATH}")

# Create connection
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print(f"🚀 Creating Iron Mountain SQLite database at: {DB_PATH}")

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

# Create index on account_number for faster lookups
cursor.execute("""
    CREATE INDEX idx_account_number ON ironmountain_customers(account_number)
""")

# Create box_requests table for tracking requests with cancellation tokens
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

# Create indexes for faster lookups
cursor.execute("""
    CREATE INDEX idx_box_requests_account ON box_requests(account_number)
""")

cursor.execute("""
    CREATE INDEX idx_box_requests_token ON box_requests(cancellation_token)
""")

cursor.execute("""
    CREATE INDEX idx_box_requests_status ON box_requests(status)
""")

# Insert dummy customer data (5 customers for demo)
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

# Commit changes
conn.commit()

# Verify data was inserted
cursor.execute("SELECT COUNT(*) FROM ironmountain_customers")
count = cursor.fetchone()[0]

print(f"✅ Iron Mountain SQLite database created with {count} customer accounts!")
print(f"📁 Database location: {DB_PATH}")

# Close connection
cursor.close()
conn.close()
