"""
Cancellation service routes and utilities
"""
from datetime import datetime
from chainlit.logger import logger
from db.connection import get_db_connection


def format_date(date_value):
    """Format date from SQLite to readable format"""
    if not date_value:
        return 'N/A'
    try:
        if isinstance(date_value, datetime):
            return date_value.strftime('%B %d, %Y at %I:%M %p')
        if isinstance(date_value, str):
            try:
                dt = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                return dt.strftime('%B %d, %Y at %I:%M %p')
            except:
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S']:
                    try:
                        dt = datetime.strptime(date_value, fmt)
                        return dt.strftime('%B %d, %Y at %I:%M %p')
                    except:
                        continue
                return str(date_value)
        return str(date_value)
    except Exception as e:
        logger.warning(f"Error formatting date: {e}")
        return str(date_value) if date_value else 'N/A'


def register_cancellation_routes(app):
    """Register cancellation routes with FastAPI app"""
    from fastapi.responses import HTMLResponse
    
    @app.get("/cancel/{token}", response_class=HTMLResponse)
    async def cancel_request_form(token: str):
        """Show cancellation confirmation form"""
        conn = get_db_connection()
        if not conn:
            return HTMLResponse("""
            <html>
                <body style="font-family: Arial, sans-serif; padding: 40px; max-width: 600px; margin: 0 auto;">
                    <div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 20px; border-radius: 4px;">
                        <h2 style="color: #721c24; margin: 0;">❌ Database Connection Error</h2>
                    </div>
                    <p>Unable to connect to the database. Please try again later.</p>
                </body>
            </html>
            """, status_code=500)
        
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 
                    br.*,
                    c.customer_name,
                    c.company_name,
                    c.account_number
                FROM box_requests br
                JOIN ironmountain_customers c ON br.account_number = c.account_number
                WHERE br.cancellation_token = ? 
                AND br.status = 'pending'
                AND br.cancelled_at IS NULL
                """,
                (token,)
            )
            row = cursor.fetchone()
            request_data = dict(row) if row else None
            cursor.close()
            conn.close()
            
            if not request_data:
                return HTMLResponse("""
                <html>
                    <body style="font-family: Arial, sans-serif; padding: 40px; max-width: 600px; margin: 0 auto;">
                        <div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 20px; border-radius: 4px; margin-bottom: 20px;">
                            <h2 style="color: #721c24; margin: 0;">❌ Request Not Found</h2>
                        </div>
                        <p>This cancellation link is invalid or has already been used.</p>
                    </body>
                </html>
                """)
            
            return HTMLResponse(f"""
            <html>
                <body style="font-family: Arial, sans-serif; padding: 40px; max-width: 600px; margin: 0 auto; background-color: #f5f5f5;">
                    <div style="background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <h1 style="color: #0066cc; margin: 0;">Iron Mountain</h1>
                        <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 20px; border-radius: 4px; margin: 20px 0;">
                            <h2 style="color: #856404; margin: 0;">⚠️ Cancel Box Request?</h2>
                        </div>
                        <p>Dear {request_data['customer_name']},</p>
                        <p>You are about to cancel the following box request:</p>
                        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 4px; margin: 20px 0;">
                            <p><strong>Account:</strong> {request_data['account_number']}</p>
                            <p><strong>Quantity:</strong> {request_data['quantity']} boxes</p>
                            <p><strong>Request Date:</strong> {format_date(request_data.get('created_at'))}</p>
                        </div>
                        <form method="POST" action="/cancel/{token}/confirm" style="margin-top: 30px;">
                            <button type="submit" style="background-color: #dc3545; color: white; border: none; padding: 12px 30px; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: bold;">
                                Yes, Cancel Request
                            </button>
                            <a href="/cancel/{token}/cancel-action" style="background-color: #6c757d; color: white; text-decoration: none; padding: 12px 30px; border-radius: 4px; font-size: 16px; font-weight: bold; display: inline-block; margin-left: 15px;">
                                Keep Request
                            </a>
                        </form>
                    </div>
                </body>
            </html>
            """)
        except Exception as e:
            conn.close()
            logger.error(f"Error processing cancellation request: {e}")
            return HTMLResponse(f"<html><body><h1>Error</h1><p>{str(e)}</p></body></html>", status_code=500)
    
    @app.post("/cancel/{token}/confirm", response_class=HTMLResponse)
    async def confirm_cancellation(token: str):
        """Confirm and process cancellation"""
        conn = get_db_connection()
        if not conn:
            return HTMLResponse("""
            <html>
                <body style="font-family: Arial, sans-serif; padding: 40px; max-width: 600px; margin: 0 auto;">
                    <h2>❌ Cancellation Failed</h2>
                    <p>Database connection failed.</p>
                </body>
            </html>
            """, status_code=500)
        
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM box_requests 
                WHERE cancellation_token = ? 
                AND status = 'pending'
                AND cancelled_at IS NULL
                """,
                (token,)
            )
            row = cursor.fetchone()
            request_data = dict(row) if row else None
            
            if not request_data:
                cursor.close()
                conn.close()
                return HTMLResponse("""
                <html>
                    <body style="font-family: Arial, sans-serif; padding: 40px; max-width: 600px; margin: 0 auto;">
                        <h2>❌ Cancellation Failed</h2>
                        <p>Request not found or already cancelled.</p>
                    </body>
                </html>
                """)
            
            # Mark as cancelled
            cursor.execute(
                """
                UPDATE box_requests 
                SET status = 'cancelled',
                    cancelled_at = ?
                WHERE cancellation_token = ?
                """,
                (datetime.now().isoformat(), token)
            )
            
            # Update customer's boxes_requested count
            cursor.execute(
                """
                UPDATE ironmountain_customers
                SET boxes_requested = boxes_requested - ?
                WHERE account_number = ?
                """,
                (request_data['quantity'], request_data['account_number'])
            )
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return HTMLResponse(f"""
            <html>
                <body style="font-family: Arial, sans-serif; padding: 40px; max-width: 600px; margin: 0 auto; background-color: #f5f5f5;">
                    <div style="background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <h1 style="color: #0066cc; margin: 0;">Iron Mountain</h1>
                        <div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 20px; border-radius: 4px; margin: 20px 0; text-align: center;">
                            <h2 style="color: #155724; margin: 0;">✅ Request Cancelled Successfully</h2>
                        </div>
                        <p>Your request for <strong>{request_data['quantity']} boxes</strong> (Account: {request_data['account_number']}) has been cancelled.</p>
                    </div>
                </body>
            </html>
            """)
        except Exception as e:
            conn.rollback()
            cursor.close()
            conn.close()
            logger.error(f"Error cancelling request: {e}")
            return HTMLResponse(f"<html><body><h1>Error</h1><p>{str(e)}</p></body></html>", status_code=500)
    
    @app.get("/cancel/{token}/cancel-action", response_class=HTMLResponse)
    async def cancel_action(token: str):
        """User clicked 'Keep Request'"""
        return HTMLResponse("""
        <html>
            <body style="font-family: Arial, sans-serif; padding: 40px; max-width: 600px; margin: 0 auto; background-color: #f5f5f5;">
                <div style="background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center;">
                    <h2>✅ Request Maintained</h2>
                    <p>Your box request will continue to be processed as scheduled.</p>
                </div>
            </body>
        </html>
        """)
