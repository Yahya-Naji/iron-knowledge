"""
Email service for Iron Mountain using Resend API (primary) or SMTP (fallback)
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
from chainlit.logger import logger

# Try to import Resend
try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    logger.warning("Resend not available. Install with: pip install resend")

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

# Email Configuration from environment variables
# Resend (preferred for Railway/cloud - simpler than SendGrid)
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")

# SMTP Configuration (fallback for local development)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Iron Mountain")
TO_EMAIL = os.getenv("TO_EMAIL", "")  # All emails sent to this address
CANCEL_BASE_URL = os.getenv("CANCEL_BASE_URL", "http://localhost:8002 ")


def _send_email_resend(
    to_email: str,
    subject: str,
    body_html: str,
    body_text: Optional[str] = None
) -> bool:
    """Send email using Resend API (simple, no domain verification needed)"""
    if not RESEND_AVAILABLE:
        return False
    
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set, skipping Resend")
        return False
    
    try:
        # Initialize Resend
        resend.api_key = RESEND_API_KEY
        
        # Prepare email
        from_email = SMTP_FROM_EMAIL or "onboarding@resend.dev"  # Resend default for testing
        from_name = SMTP_FROM_NAME or "Iron Mountain"
        
        # Create email params
        params = {
            "from": f"{from_name} <{from_email}>",
            "to": [to_email],
            "subject": subject,
            "html": body_html,
        }
        
        # Add text version if provided
        if body_text:
            params["text"] = body_text
        
        # Send email
        email_response = resend.Emails.send(params)
        
        if email_response and hasattr(email_response, 'id'):
            logger.info(f"✅ Email sent via Resend to {to_email} (id: {email_response.id})")
            return True
        else:
            logger.error(f"❌ Resend error: {email_response}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Resend error: {e}", exc_info=True)
        return False


def _send_email_smtp(
    to_email: str,
    subject: str,
    body_html: str,
    body_text: Optional[str] = None,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None
) -> bool:
    """Send email using SMTP (fallback for local development)"""
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured")
        return False
    
    if not SMTP_FROM_EMAIL:
        logger.warning("SMTP_FROM_EMAIL not configured")
        return False
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        
        if cc:
            msg['Cc'] = ', '.join(cc)
        
        # Create recipients list (to + cc + bcc)
        recipients = [to_email]
        if cc:
            recipients.extend(cc)
        if bcc:
            recipients.extend(bcc)
        
        # Add text and HTML parts
        if body_text:
            text_part = MIMEText(body_text, 'plain')
            msg.attach(text_part)
        
        html_part = MIMEText(body_html, 'html')
        msg.attach(html_part)
        
        # Connect to SMTP server and send
        logger.info(f"🔌 Connecting to SMTP server: {SMTP_HOST}:{SMTP_PORT}")
        
        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                logger.info(f"✅ Connected to SMTP server")
                server.starttls()  # Enable encryption
                logger.info(f"✅ TLS started")
                server.login(SMTP_USER, SMTP_PASSWORD)
                logger.info(f"✅ Authenticated with SMTP server")
                server.send_message(msg, to_addrs=recipients)
                logger.info(f"✅ Email sent successfully via SMTP to {to_email}")
                return True
        except OSError as e:
            logger.error(f"❌ Network error connecting to SMTP server: {e}")
            logger.error(f"   This might be due to Railway blocking outbound SMTP connections.")
            return False
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"❌ SMTP Authentication failed: {e}")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"❌ SMTP error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error sending email via SMTP: {e}", exc_info=True)
        return False


def send_email(
    to_email: str,
    subject: str,
    body_html: str,
    body_text: Optional[str] = None,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None
) -> bool:
    """
    Send email using Resend API (preferred) or SMTP (fallback)
    
    Args:
        to_email: Recipient email address (will be overridden by TO_EMAIL from env)
        subject: Email subject
        body_html: HTML email body
        body_text: Plain text email body (optional, will be generated from HTML if not provided)
        cc: List of CC email addresses (optional, only works with SMTP)
        bcc: List of BCC email addresses (optional, only works with SMTP)
    
    Returns:
        True if email sent successfully, False otherwise
    """
    # Always use TO_EMAIL from environment, ignoring the passed email
    actual_to_email = TO_EMAIL or to_email
    if not actual_to_email:
        logger.error("TO_EMAIL not configured. Set TO_EMAIL environment variable to receive emails.")
        return False
    
    logger.info(f"📧 Sending email to {actual_to_email} (original recipient was {to_email})")
    
    # Try Resend first (works on Railway, no domain verification needed)
    if RESEND_AVAILABLE and RESEND_API_KEY:
        logger.info("📧 Using Resend API")
        if _send_email_resend(actual_to_email, subject, body_html, body_text):
            return True
        logger.warning("⚠️ Resend failed, falling back to SMTP")
    
    # Fallback to SMTP (for local development)
    logger.info("📧 Using SMTP (fallback)")
    return _send_email_smtp(actual_to_email, subject, body_html, body_text, cc, bcc)


def send_box_request_confirmation(
    customer_email: str,
    customer_name: str,
    account_number: str,
    quantity: int,
    address: str,
    cancellation_token: Optional[str] = None
) -> bool:
    """
    Send box request confirmation email to customer
    
    Args:
        customer_email: Customer email address (will be overridden by TO_EMAIL from env)
        customer_name: Customer name
        account_number: Account number
        quantity: Number of boxes requested
        address: Delivery address
        cancellation_token: Cancellation token for the request (optional)
    
    Returns:
        True if email sent successfully, False otherwise
    """
    subject = f"Iron Mountain - Box Request Confirmation ({account_number})"
    
    # Build cancellation link if token is provided
    cancel_link_html = ""
    cancel_link_text = ""
    if cancellation_token:
        cancel_url = f"{CANCEL_BASE_URL}/cancel/{cancellation_token}"
        cancel_link_html = f"""
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{cancel_url}" style="background-color: #dc3545; color: white; text-decoration: none; padding: 15px 30px; border-radius: 6px; font-size: 16px; font-weight: bold; display: inline-block; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
                        🚫 Cancel This Request
                    </a>
                </div>
        """
        cancel_link_text = f"\n\nCancel this request: {cancel_url}"
    
    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333333; background-color: #f4f4f4; }}
            .email-wrapper {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; }}
            .header {{ background: linear-gradient(135deg, #0066cc 0%, #004499 100%); color: white; padding: 40px 20px; text-align: center; }}
            .header h1 {{ font-size: 32px; font-weight: 700; margin-bottom: 8px; letter-spacing: -0.5px; }}
            .header p {{ font-size: 14px; opacity: 0.95; font-weight: 300; }}
            .content {{ padding: 40px 30px; background-color: #ffffff; }}
            .content h2 {{ color: #0066cc; font-size: 24px; margin-bottom: 20px; font-weight: 600; }}
            .content p {{ margin-bottom: 16px; font-size: 16px; color: #555555; }}
            .info-box {{ background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%); border-left: 5px solid #0066cc; padding: 25px; margin: 25px 0; border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
            .info-box h3 {{ color: #0066cc; font-size: 18px; margin-bottom: 15px; font-weight: 600; }}
            .info-box p {{ margin-bottom: 12px; font-size: 15px; }}
            .info-box strong {{ color: #333333; font-weight: 600; }}
            .cancel-section {{ background-color: #fff3cd; border: 2px solid #ffc107; border-radius: 8px; padding: 25px; margin: 30px 0; text-align: center; }}
            .cancel-section p {{ color: #856404; font-size: 15px; margin-bottom: 20px; font-weight: 500; }}
            .footer {{ background-color: #f8f9fa; padding: 30px 20px; text-align: center; border-top: 1px solid #e9ecef; }}
            .footer p {{ color: #6c757d; font-size: 12px; margin: 5px 0; }}
            .divider {{ height: 1px; background: linear-gradient(to right, transparent, #e9ecef, transparent); margin: 30px 0; }}
        </style>
    </head>
    <body>
        <div class="email-wrapper">
            <div class="header">
                <h1>Iron Mountain</h1>
                <p>Document Storage & Information Management</p>
            </div>
            <div class="content">
                <h2>✅ Box Request Confirmation</h2>
                <p>Dear {customer_name},</p>
                <p>Thank you for your box request. We have received and processed your order.</p>
                
                <div class="info-box">
                    <h3>📦 Request Details</h3>
                    <p><strong>Account Number:</strong> {account_number}</p>
                    <p><strong>Quantity:</strong> {quantity} box{'es' if quantity != 1 else ''}</p>
                    <p><strong>Delivery Address:</strong> {address}</p>
                    <p><strong>Estimated Delivery:</strong> 3-5 business days</p>
                </div>
                
                {cancel_link_html}
                
                <div class="divider"></div>
                
                <p>Your boxes will be delivered to the address on file. You will receive a tracking notification once your order ships.</p>
                <p>If you have any questions or need to modify your request, please contact our support team.</p>
                
                <p style="margin-top: 30px;">Best regards,<br><strong>Iron Mountain Customer Service</strong></p>
            </div>
            <div class="footer">
                <p><strong>Iron Mountain</strong></p>
                <p>support@ironmountain.com | 1-800-899-IRON (4766)</p>
                <p style="margin-top: 15px; font-size: 11px; color: #adb5bd;">© {datetime.now().year} Iron Mountain. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    body_text = f"""
Iron Mountain - Box Request Confirmation

Dear {customer_name},

Thank you for your box request. We have received and processed your order.

Request Details:
- Account Number: {account_number}
- Quantity: {quantity} box{'es' if quantity != 1 else ''}
- Delivery Address: {address}
- Estimated Delivery: 3-5 business days
{cancel_link_text}

Your boxes will be delivered to the address on file. You will receive a tracking notification once your order ships.

If you have any questions or need to modify your request, please contact our support team.

Best regards,
Iron Mountain Customer Service

Iron Mountain | support@ironmountain.com | 1-800-899-IRON (4766)
    """
    
    return send_email(customer_email, subject, body_html, body_text)


def send_box_request_notification(
    internal_email: str,
    customer_name: str,
    account_number: str,
    quantity: int,
    address: str
) -> bool:
    """
    Send internal notification email for box request
    
    Args:
        internal_email: Internal team email address
        customer_name: Customer name
        account_number: Account number
        quantity: Number of boxes requested
        address: Delivery address
    
    Returns:
        True if email sent successfully, False otherwise
    """
    subject = f"New Box Request - {account_number} ({quantity} boxes)"
    
    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #dc3545; color: white; padding: 20px; text-align: center; }}
            .content {{ background-color: #f9f9f9; padding: 20px; }}
            .info-box {{ background-color: white; padding: 15px; margin: 15px 0; border-left: 4px solid #dc3545; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>New Box Request</h1>
            </div>
            <div class="content">
                <h2>Action Required</h2>
                <p>A new box request has been submitted and requires processing.</p>
                
                <div class="info-box">
                    <h3>Request Details</h3>
                    <p><strong>Customer:</strong> {customer_name}</p>
                    <p><strong>Account Number:</strong> {account_number}</p>
                    <p><strong>Quantity:</strong> {quantity} boxes</p>
                    <p><strong>Delivery Address:</strong> {address}</p>
                </div>
                
                <p>Please process this request and schedule delivery within 3-5 business days.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    body_text = f"""
New Box Request - Action Required

A new box request has been submitted and requires processing.

Request Details:
- Customer: {customer_name}
- Account Number: {account_number}
- Quantity: {quantity} boxes
- Delivery Address: {address}

Please process this request and schedule delivery within 3-5 business days.
    """
    
    return send_email(internal_email, subject, body_html, body_text)
