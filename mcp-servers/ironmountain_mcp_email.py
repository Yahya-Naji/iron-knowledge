"""
Iron Mountain MCP Email Server
Provides email sending capabilities via MCP protocol
"""
import os
import sys
import asyncio
import json
import secrets
from datetime import datetime
from typing import Any
from mcp.server import Server
from mcp.types import Tool, TextContent
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import psycopg2
from psycopg2.extras import RealDictCursor

# Initialize MCP Server
app = Server("ironmountain-email")

# SMTP Configuration from environment
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USER)
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Iron Mountain Assistant")
EMAIL_INTERNAL = os.getenv("EMAIL_INTERNAL", "yahya.naji@git-me.ae")
EMAIL_CUSTOMER = os.getenv("EMAIL_CUSTOMER", "yahya.naji@git-me.ae")
CANCEL_BASE_URL = os.getenv("CANCEL_BASE_URL", "http://localhost:8002")

# PostgreSQL Configuration for saving requests with tokens
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "quanterra_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_DB = os.getenv("POSTGRES_DB", "ironmountain")


def get_db_connection():
    """Get PostgreSQL database connection"""
    try:
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            dbname=POSTGRES_DB
        )
        return conn
    except Exception as e:
        print(f"❌ Database connection error: {e}", file=sys.stderr)
        return None


def generate_cancellation_token() -> str:
    """Generate a secure unique cancellation token"""
    return secrets.token_urlsafe(32)


def save_box_request(account_number: str, quantity: int, cancellation_token: str) -> bool:
    """Save box request to database with cancellation token"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO box_requests (account_number, quantity, cancellation_token, status)
            VALUES (%s, %s, %s, 'pending')
            """,
            (account_number, quantity, cancellation_token)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error saving box request: {e}", file=sys.stderr)
        conn.rollback()
        cursor.close()
        conn.close()
        return False


def send_email_smtp(to_email: str, subject: str, html_body: str, text_body: str = "") -> bool:
    """Send email via SMTP"""
    try:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
        message["To"] = to_email
        
        if text_body:
            part1 = MIMEText(text_body, "plain")
            message.attach(part1)
        
        part2 = MIMEText(html_body, "html")
        message.attach(part2)
        
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(message)
        
        return True
    except Exception as e:
        print(f"❌ SMTP Error: {e}", file=sys.stderr)
        return False


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available email tools"""
    return [
        Tool(
            name="send_internal_notification",
            description="Send internal notification email to Iron Mountain staff about a box request",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_number": {"type": "string", "description": "Customer account number (e.g., IM-10001)"},
                    "customer_name": {"type": "string", "description": "Customer full name"},
                    "company_name": {"type": "string", "description": "Company name"},
                    "address": {"type": "string", "description": "Delivery address"},
                    "quantity": {"type": "integer", "description": "Number of boxes requested"},
                    "boxes_retained": {"type": "integer", "description": "Current boxes in storage"}
                },
                "required": ["account_number", "customer_name", "company_name", "address", "quantity", "boxes_retained"]
            }
        ),
        Tool(
            name="send_customer_confirmation",
            description="Send confirmation email to customer about their box request",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_number": {"type": "string", "description": "Customer account number"},
                    "customer_name": {"type": "string", "description": "Customer full name"},
                    "address": {"type": "string", "description": "Delivery address"},
                    "quantity": {"type": "integer", "description": "Number of boxes requested"},
                    "boxes_retained": {"type": "integer", "description": "Current boxes in storage"},
                    "boxes_requested": {"type": "integer", "description": "Total boxes requested"}
                },
                "required": ["account_number", "customer_name", "address", "quantity", "boxes_retained", "boxes_requested"]
            }
        ),
        Tool(
            name="send_box_request_emails",
            description="Send both internal notification and customer confirmation emails for a box request",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_number": {"type": "string"},
                    "customer_name": {"type": "string"},
                    "company_name": {"type": "string"},
                    "address": {"type": "string"},
                    "quantity": {"type": "integer"},
                    "boxes_retained": {"type": "integer"},
                    "boxes_requested": {"type": "integer"}
                },
                "required": ["account_number", "customer_name", "company_name", "address", "quantity", "boxes_retained", "boxes_requested"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls"""
    
    if name == "send_internal_notification":
        account_number = arguments["account_number"]
        customer_name = arguments["customer_name"]
        company_name = arguments["company_name"]
        address = arguments["address"]
        quantity = arguments["quantity"]
        boxes_retained = arguments["boxes_retained"]
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total_boxes = boxes_retained + quantity
        
        subject = f"📦 New Box Request - Account {account_number}"
        
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
                    <h2 style="color: #0066cc; border-bottom: 2px solid #0066cc; padding-bottom: 10px;">
                        📦 Customer Box Request
                    </h2>
                    
                    <h3 style="color: #555;">Customer Details</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px; font-weight: bold; width: 40%;">Account Number:</td>
                            <td style="padding: 8px;">{account_number}</td>
                        </tr>
                        <tr style="background-color: #f9f9f9;">
                            <td style="padding: 8px; font-weight: bold;">Customer Name:</td>
                            <td style="padding: 8px;">{customer_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; font-weight: bold;">Company:</td>
                            <td style="padding: 8px;">{company_name}</td>
                        </tr>
                        <tr style="background-color: #f9f9f9;">
                            <td style="padding: 8px; font-weight: bold;">Delivery Address:</td>
                            <td style="padding: 8px;">{address}</td>
                        </tr>
                    </table>
                    
                    <h3 style="color: #555; margin-top: 20px;">Request Details</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px; font-weight: bold; width: 40%;">Boxes Requested:</td>
                            <td style="padding: 8px; color: #0066cc; font-size: 18px; font-weight: bold;">{quantity}</td>
                        </tr>
                        <tr style="background-color: #f9f9f9;">
                            <td style="padding: 8px; font-weight: bold;">Current Retained:</td>
                            <td style="padding: 8px;">{boxes_retained}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; font-weight: bold;">Total After Delivery:</td>
                            <td style="padding: 8px;">{total_boxes}</td>
                        </tr>
                        <tr style="background-color: #f9f9f9;">
                            <td style="padding: 8px; font-weight: bold;">Requested On:</td>
                            <td style="padding: 8px;">{timestamp}</td>
                        </tr>
                    </table>
                    
                    <div style="margin-top: 20px; padding: 15px; background-color: #fff3cd; border-left: 4px solid #ffc107; border-radius: 4px;">
                        <strong>⚠️ Action Required:</strong> Prepare {quantity} empty boxes for delivery to the customer.
                    </div>
                </div>
            </body>
        </html>
        """
        
        text_body = f"""
Customer Box Request Notification

Account: {account_number}
Customer: {customer_name}
Company: {company_name}
Address: {address}

Request Details:
- Boxes Requested: {quantity}
- Current Retained: {boxes_retained}
- Total After Delivery: {total_boxes}

Requested on: {timestamp}
        """
        
        success = send_email_smtp(EMAIL_INTERNAL, subject, html_body, text_body)
        
        if success:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "message": f"Internal notification sent to {EMAIL_INTERNAL}",
                    "recipient": EMAIL_INTERNAL,
                    "subject": subject
                })
            )]
        else:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "status": "error",
                    "message": "Failed to send internal notification"
                })
            )]
    
    elif name == "send_customer_confirmation":
        account_number = arguments["account_number"]
        customer_name = arguments["customer_name"]
        address = arguments["address"]
        quantity = arguments["quantity"]
        boxes_retained = arguments["boxes_retained"]
        boxes_requested = arguments["boxes_requested"]
        
        # Generate cancellation token and save request to database
        cancellation_token = generate_cancellation_token()
        save_box_request(account_number, quantity, cancellation_token)
        cancel_url = f"{CANCEL_BASE_URL}/cancel/{cancellation_token}"
        
        subject = f"✅ Your Box Request Confirmed - {account_number}"
        
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
                    <div style="text-align: center; margin-bottom: 20px;">
                        <h1 style="color: #0066cc; margin: 0;">Iron Mountain</h1>
                        <p style="color: #666; margin: 5px 0;">Document Storage & Information Management</p>
                    </div>
                    
                    <div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px; margin-bottom: 20px; border-radius: 4px;">
                        <h2 style="color: #155724; margin: 0;">✅ Request Confirmed!</h2>
                    </div>
                    
                    <p style="font-size: 16px;">Dear {customer_name},</p>
                    
                    <p>Thank you for choosing Iron Mountain! We have received your request for <strong>{quantity} empty storage boxes</strong>.</p>
                    
                    <h3 style="color: #555; border-bottom: 1px solid #ddd; padding-bottom: 8px;">Delivery Details</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px; font-weight: bold; width: 40%;">Delivery Address:</td>
                            <td style="padding: 8px;">{address}</td>
                        </tr>
                        <tr style="background-color: #f9f9f9;">
                            <td style="padding: 8px; font-weight: bold;">Expected Delivery:</td>
                            <td style="padding: 8px;">3-5 business days</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; font-weight: bold;">Account Number:</td>
                            <td style="padding: 8px;">{account_number}</td>
                        </tr>
                    </table>
                    
                    <h3 style="color: #555; border-bottom: 1px solid #ddd; padding-bottom: 8px; margin-top: 20px;">Your Storage Inventory</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px; font-weight: bold; width: 40%;">Boxes in Storage:</td>
                            <td style="padding: 8px;">{boxes_retained}</td>
                        </tr>
                        <tr style="background-color: #f9f9f9;">
                            <td style="padding: 8px; font-weight: bold;">Boxes Requested:</td>
                            <td style="padding: 8px;">{boxes_requested}</td>
                        </tr>
                    </table>
                    
                    <div style="margin-top: 30px; padding: 20px; background-color: #fff3cd; border-left: 4px solid #ffc107; border-radius: 4px;">
                        <p style="margin: 0 0 15px 0; font-weight: bold;">Need to cancel this request?</p>
                        <p style="margin: 0 0 15px 0;">If you need to cancel this request, you can do so by clicking the button below:</p>
                        <div style="text-align: center;">
                            <a href="{cancel_url}" style="background-color: #dc3545; color: white; text-decoration: none; padding: 12px 30px; border-radius: 4px; font-weight: bold; display: inline-block;">
                                Cancel This Request
                            </a>
                        </div>
                    </div>
                    
                    <div style="margin-top: 30px; padding: 15px; background-color: #f8f9fa; border-radius: 4px;">
                        <p style="margin: 0;"><strong>Need help?</strong> Contact us anytime:</p>
                        <p style="margin: 5px 0;">📧 support@ironmountain.com</p>
                        <p style="margin: 5px 0;">📞 1-800-899-IRON (4766)</p>
                    </div>
                    
                    <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px; text-align: center;">
                        <p>Best regards,<br><strong>Iron Mountain Team</strong></p>
                    </div>
                </div>
            </body>
        </html>
        """
        
        text_body = f"""
Dear {customer_name},

Thank you for choosing Iron Mountain!

We have received your request for {quantity} empty storage boxes.

Delivery Details:
- Delivery Address: {address}
- Expected Delivery: 3-5 business days
- Account Number: {account_number}

Your current storage inventory:
- Boxes in Storage: {boxes_retained}
- Boxes Requested: {boxes_requested}

Need to cancel this request?
If you need to cancel this request, visit: {cancel_url}

Best regards,
Iron Mountain Team
        """
        
        success = send_email_smtp(EMAIL_CUSTOMER, subject, html_body, text_body)
        
        if success:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "message": f"Customer confirmation sent to {EMAIL_CUSTOMER}",
                    "recipient": EMAIL_CUSTOMER,
                    "subject": subject
                })
            )]
        else:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "status": "error",
                    "message": "Failed to send customer confirmation"
                })
            )]
    
    elif name == "send_box_request_emails":
        # Send both emails
        account_number = arguments["account_number"]
        customer_name = arguments["customer_name"]
        company_name = arguments["company_name"]
        address = arguments["address"]
        quantity = arguments["quantity"]
        boxes_retained = arguments["boxes_retained"]
        boxes_requested = arguments["boxes_requested"]
        
        # Send internal notification
        internal_result = await call_tool("send_internal_notification", {
            "account_number": account_number,
            "customer_name": customer_name,
            "company_name": company_name,
            "address": address,
            "quantity": quantity,
            "boxes_retained": boxes_retained
        })
        
        # Send customer confirmation
        customer_result = await call_tool("send_customer_confirmation", {
            "account_number": account_number,
            "customer_name": customer_name,
            "address": address,
            "quantity": quantity,
            "boxes_retained": boxes_retained,
            "boxes_requested": boxes_requested
        })
        
        internal_data = json.loads(internal_result[0].text)
        customer_data = json.loads(customer_result[0].text)
        
        both_success = (internal_data["status"] == "success" and customer_data["status"] == "success")
        
        return [TextContent(
            type="text",
            text=json.dumps({
                "status": "success" if both_success else "partial",
                "message": "Both emails sent successfully" if both_success else "Some emails failed",
                "internal": internal_data,
                "customer": customer_data
            })
        )]
    
    else:
        return [TextContent(
            type="text",
            text=json.dumps({"status": "error", "message": f"Unknown tool: {name}"})
        )]


async def main():
    """Run MCP server"""
    from mcp.server.stdio import stdio_server
    
    print("🚀 Starting Iron Mountain Email MCP Server...", file=sys.stderr)
    print(f"📧 SMTP: {SMTP_USER} -> {SMTP_HOST}:{SMTP_PORT}", file=sys.stderr)
    print(f"📬 Recipients: Internal={EMAIL_INTERNAL}, Customer={EMAIL_CUSTOMER}", file=sys.stderr)
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())

