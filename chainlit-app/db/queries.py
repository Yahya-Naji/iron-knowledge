"""
Database query functions for Iron Mountain
"""
import secrets
from typing import Optional, Dict
from datetime import datetime
from chainlit.logger import logger
from db.connection import get_db_connection


def get_customer_account(account_number: str) -> Optional[Dict]:
    """Get customer account details by account number"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                account_number,
                customer_name,
                company_name,
                address,
                phone_number,
                email,
                boxes_retained,
                boxes_requested,
                last_request_date,
                created_at
            FROM ironmountain_customers
            WHERE account_number = ?
            """,
            (account_number,)
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if row:
            return dict(row)
        return None
    except Exception as e:
        logger.error(f"Error getting customer account: {e}")
        conn.close()
        return None


def get_box_inventory(account_number: str) -> Optional[Dict]:
    """Get customer's box inventory"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                account_number,
                customer_name,
                boxes_retained,
                boxes_requested
            FROM ironmountain_customers
            WHERE account_number = ?
            """,
            (account_number,)
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if row:
            return dict(row)
        return None
    except Exception as e:
        logger.error(f"Error getting box inventory: {e}")
        conn.close()
        return None


def update_box_request(account_number: str, quantity: int) -> Optional[Dict]:
    """Update customer's box request (add to boxes_requested) and return cancellation token"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        
        # Update boxes_requested
        cursor.execute(
            """
            UPDATE ironmountain_customers
            SET boxes_requested = boxes_requested + ?,
                last_request_date = ?
            WHERE account_number = ?
            """,
            (quantity, datetime.now().isoformat(), account_number)
        )
        
        # Create box request record with cancellation token
        cancellation_token = secrets.token_urlsafe(32)
        cursor.execute(
            """
            INSERT INTO box_requests (account_number, quantity, cancellation_token, status)
            VALUES (?, ?, ?, 'pending')
            """,
            (account_number, quantity, cancellation_token)
        )
        
        conn.commit()
        cursor.close()
        conn.close()
        return {"success": True, "cancellation_token": cancellation_token}
    except Exception as e:
        logger.error(f"Error updating box request: {e}")
        conn.rollback()
        conn.close()
        return None
