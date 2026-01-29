#!/bin/bash
set -e

echo "🚀 Initializing Iron Mountain database..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create Iron Mountain database
    CREATE DATABASE ironmountain;
    GRANT ALL PRIVILEGES ON DATABASE ironmountain TO $POSTGRES_USER;
    
    -- Connect to ironmountain database and create schema
    \c ironmountain
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    CREATE EXTENSION IF NOT EXISTS "pg_trgm";
    
    -- Create Iron Mountain customers table
    CREATE TABLE ironmountain_customers (
        id SERIAL PRIMARY KEY,
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
    );
    
    -- Create index on account_number for faster lookups
    CREATE INDEX idx_account_number ON ironmountain_customers(account_number);
    
    -- Create box_requests table for tracking requests with cancellation tokens
    CREATE TABLE box_requests (
        id SERIAL PRIMARY KEY,
        account_number VARCHAR(20) NOT NULL,
        quantity INTEGER NOT NULL,
        cancellation_token VARCHAR(255) UNIQUE NOT NULL,
        status VARCHAR(20) DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        cancelled_at TIMESTAMP,
        FOREIGN KEY (account_number) REFERENCES ironmountain_customers(account_number) ON DELETE CASCADE
    );
    
    -- Create indexes for faster lookups
    CREATE INDEX idx_box_requests_account ON box_requests(account_number);
    CREATE INDEX idx_box_requests_token ON box_requests(cancellation_token);
    CREATE INDEX idx_box_requests_status ON box_requests(status);
    
    -- Insert dummy customer data (5 customers for demo)
    INSERT INTO ironmountain_customers (account_number, customer_name, company_name, address, phone_number, email, boxes_retained, boxes_requested) VALUES
    ('IM-10001', 'Yousef Al-Mansoori', 'Tech Innovations LLC', 'Dubai Marina, Dubai, UAE', '+971-50-123-4567', 'yousef@techinnovations.ae', 15, 0),
    ('IM-10002', 'Sarah Johnson', 'Legal Associates', 'Al Maryah Island, Abu Dhabi, UAE', '+971-50-234-5678', 'sarah@legalassoc.ae', 8, 0),
    ('IM-10003', 'Ahmed Hassan', 'Financial Consultants', 'Business Bay, Dubai, UAE', '+971-50-345-6789', 'ahmed@finconsult.ae', 22, 0),
    ('IM-10004', 'Emily Roberts', 'Healthcare Solutions', 'Dubai Healthcare City, Dubai, UAE', '+971-50-456-7890', 'emily@healthsol.ae', 12, 0),
    ('IM-10005', 'Mohammed Ali', 'Trading Partners LLC', 'Deira, Dubai, UAE', '+971-50-567-8901', 'mohammed@tradingpartners.ae', 30, 0);
    
    -- Verify data was inserted
    SELECT COUNT(*) as customer_count FROM ironmountain_customers;
EOSQL

echo "✅ Iron Mountain database initialized with 5 customer accounts!"
