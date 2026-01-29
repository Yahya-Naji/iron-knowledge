"""
Iron Mountain Voice Assistant - Chainlit Application
Customer service assistant for document storage management
"""
# ============================================================================
# IMPORTS
# ============================================================================
import os
import asyncio
import json
import subprocess
import requests
import websockets
import random
import secrets
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional
from uuid import uuid4
from datetime import datetime
import chainlit as cl
from chainlit.logger import logger
from openai import AsyncOpenAI
from realtime import RealtimeClient
from fastapi.responses import HTMLResponse

# Import PostgreSQL data layer
from chainlit_postgres_layer import chainlit_data_layer


# ============================================================================
# CONFIGURATION
# ============================================================================
# Initialize OpenAI client
openai_client = AsyncOpenAI()

# Autogen Studio Configuration
AUTOGEN_BASE_URL = os.getenv("AUTOGEN_API_URL", "https://awedly-unstaid-marc.ngrok-free.dev")
AUTOGEN_WS_URL = os.getenv("AUTOGEN_WS_URL", "wss://awedly-unstaid-marc.ngrok-free.dev")
USER_ID = os.getenv("AUTOGEN_USER_ID", "guestuser@gmail.com")

# Iron Mountain Team IDs
DB_TEAM_ID = int(os.getenv("IRONMOUNTAIN_DB_TEAM_ID", "1"))  # Database team (Team 1)
EMAIL_TEAM_ID = int(os.getenv("IRONMOUNTAIN_EMAIL_TEAM_ID", "2"))  # Email team (Team 2)

# Cancellation Service Configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "quanterra_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_DB = os.getenv("POSTGRES_DB", "ironmountain")

# ============================================================================
# DATA PERSISTENCE (Chainlit PostgreSQL data layer)
# ============================================================================
# Enable Chainlit data persistence
os.environ.setdefault("CHAINLIT_DATA_PERSISTENCE", "true")

# Set data layer globally - must be done before any Chainlit decorators
import chainlit.data as cl_data_module
cl_data_module._data_layer = chainlit_data_layer

logger.info(f"🗄️  Chainlit data persistence enabled with PostgreSQL backend")


# ============================================================================
# UI ERROR HANDLING - Catch database errors and show "no threads" instead
# ============================================================================
# Add exception handler to catch all errors from Chainlit's server
# This prevents UI crashes when database fails to provide threads/history
try:
    import chainlit.server as cl_server
    from fastapi import Request
    from fastapi.responses import JSONResponse
    
    # Get the FastAPI app from Chainlit's server
    app = None
    if hasattr(cl_server, 'app'):
        app = cl_server.app
    elif hasattr(cl_server, 'chainlit_app'):
        app = cl_server.chainlit_app
    elif hasattr(cl, 'context') and hasattr(cl.context, 'server'):
        app = cl.context.server
    
    if app:
        # Handler for all database-related exceptions
        # NOTE: We removed the AttributeError handler because our data layer now properly
        # handles dict/object conversion. If AttributeError still occurs, it will be
        # caught by the general exception handler below.
        @app.exception_handler(Exception)
        async def general_exception_handler(request: Request, exc: Exception):
            error_str = str(exc)
            request_path = str(request.url.path)
            # Check if it's a threads/history request and the error is database-related
            if "/project/threads" in request_path or "/threads" in request_path:
                # Catch database errors, connection errors, query errors, etc.
                # Only catch actual database errors, NOT serialization errors like 'to_dict'
                # Don't catch "no attribute" errors - they might be code bugs we need to fix
                is_db_error = any(keyword in error_str.lower() for keyword in [
                    "database", "connection", "query", "postgres", "sql", 
                    "foreign key", "constraint", "operational", "psycopg",
                    "relation", "table", "column", "does not exist"
                ]) and "to_dict" not in error_str.lower()
                
                if is_db_error:
                    logger.warning(f"⚠️ Caught database error in threads route: {error_str[:200]}")
                    return JSONResponse(
                        status_code=200,
                        content={"data": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}
                    )
            # For other routes or non-database errors, re-raise
            raise exc
        
        logger.info("✅ Added exception handlers for database errors - UI will show 'no threads' instead of errors")
        
        # ============================================================================
        # CANCELLATION SERVICE ROUTES (Integrated into Chainlit)
        # ============================================================================
        # Reuse connection pattern - connect to ironmountain database (same host as chainlit DB)
        def get_ironmountain_db_connection():
            """Get PostgreSQL connection to ironmountain database (reuses existing DB connection pattern)"""
            try:
                # Build connection string similar to chainlit_data_layer but for ironmountain DB
                db_uri = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
                return psycopg2.connect(db_uri, cursor_factory=RealDictCursor)
            except Exception as e:
                logger.error(f"Database connection error: {e}")
                return None
        
        @app.get("/cancel/{token}", response_class=HTMLResponse)
        async def cancel_request_form(token: str):
            """Show cancellation confirmation form"""
            conn = get_ironmountain_db_connection()
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
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                
                # Find the request by token
                cursor.execute(
                    """
                    SELECT 
                        br.*,
                        c.customer_name,
                        c.company_name,
                        c.account_number
                    FROM box_requests br
                    JOIN ironmountain_customers c ON br.account_number = c.account_number
                    WHERE br.cancellation_token = %s 
                    AND br.status = 'pending'
                    AND br.cancelled_at IS NULL
                    """,
                    (token,)
                )
                
                request_data = cursor.fetchone()
                cursor.close()
                conn.close()
                
                if not request_data:
                    # Token not found or already cancelled
                    return HTMLResponse("""
                    <html>
                        <body style="font-family: Arial, sans-serif; padding: 40px; max-width: 600px; margin: 0 auto;">
                            <div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 20px; border-radius: 4px; margin-bottom: 20px;">
                                <h2 style="color: #721c24; margin: 0;">❌ Request Not Found</h2>
                            </div>
                            <p>This cancellation link is invalid or has already been used. The request may have already been cancelled or processed.</p>
                            <p>If you need assistance, please contact us at <strong>support@ironmountain.com</strong> or call <strong>1-800-899-IRON (4766)</strong>.</p>
                        </body>
                    </html>
                    """)
                
                # Show confirmation form
                return HTMLResponse(f"""
                <html>
                    <body style="font-family: Arial, sans-serif; padding: 40px; max-width: 600px; margin: 0 auto; background-color: #f5f5f5;">
                        <div style="background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            <div style="text-align: center; margin-bottom: 30px;">
                                <h1 style="color: #0066cc; margin: 0;">Iron Mountain</h1>
                                <p style="color: #666; margin: 5px 0;">Document Storage & Information Management</p>
                            </div>
                            
                            <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 20px; border-radius: 4px; margin-bottom: 30px;">
                                <h2 style="color: #856404; margin: 0;">⚠️ Cancel Box Request?</h2>
                            </div>
                            
                            <p style="font-size: 16px;">Dear {request_data['customer_name']},</p>
                            
                            <p>You are about to cancel the following box request:</p>
                            
                            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 4px; margin: 20px 0;">
                                <table style="width: 100%; border-collapse: collapse;">
                                    <tr>
                                        <td style="padding: 8px; font-weight: bold; width: 40%;">Account Number:</td>
                                        <td style="padding: 8px;">{request_data['account_number']}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 8px; font-weight: bold;">Quantity:</td>
                                        <td style="padding: 8px;">{request_data['quantity']} boxes</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 8px; font-weight: bold;">Request Date:</td>
                                        <td style="padding: 8px;">{request_data['created_at'].strftime('%B %d, %Y at %I:%M %p') if request_data['created_at'] else 'N/A'}</td>
                                    </tr>
                                </table>
                            </div>
                            
                            <p style="color: #666;">Are you sure you want to cancel this request? This action cannot be undone.</p>
                            
                            <form method="POST" action="/cancel/{token}/confirm" style="margin-top: 30px;">
                                <div style="display: flex; gap: 15px; justify-content: center;">
                                    <button type="submit" style="background-color: #dc3545; color: white; border: none; padding: 12px 30px; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: bold;">
                                        Yes, Cancel Request
                                    </button>
                                    <a href="/cancel/{token}/cancel-action" style="background-color: #6c757d; color: white; text-decoration: none; padding: 12px 30px; border-radius: 4px; font-size: 16px; font-weight: bold; display: inline-block;">
                                        Keep Request
                                    </a>
                                </div>
                            </form>
                            
                            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px; text-align: center;">
                                <p>Need help? Contact us at <strong>support@ironmountain.com</strong> or <strong>1-800-899-IRON (4766)</strong></p>
                            </div>
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
            conn = get_ironmountain_db_connection()
            if not conn:
                return HTMLResponse("""
                <html>
                    <body style="font-family: Arial, sans-serif; padding: 40px; max-width: 600px; margin: 0 auto;">
                        <div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 20px; border-radius: 4px;">
                            <h2 style="color: #721c24; margin: 0;">❌ Cancellation Failed</h2>
                        </div>
                        <p>Database connection failed. Please try again later.</p>
                    </body>
                </html>
                """, status_code=500)
            
            try:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                
                # Find the request
                cursor.execute(
                    """
                    SELECT * FROM box_requests 
                    WHERE cancellation_token = %s 
                    AND status = 'pending'
                    AND cancelled_at IS NULL
                    FOR UPDATE
                    """,
                    (token,)
                )
                
                request_data = cursor.fetchone()
                
                if not request_data:
                    cursor.close()
                    conn.close()
                    return HTMLResponse("""
                    <html>
                        <body style="font-family: Arial, sans-serif; padding: 40px; max-width: 600px; margin: 0 auto;">
                            <div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 20px; border-radius: 4px;">
                                <h2 style="color: #721c24; margin: 0;">❌ Cancellation Failed</h2>
                            </div>
                            <p>This request could not be cancelled. It may have already been processed or cancelled.</p>
                        </body>
                    </html>
                    """)
                
                # Mark as cancelled
                cursor.execute(
                    """
                    UPDATE box_requests 
                    SET status = 'cancelled',
                        cancelled_at = %s
                    WHERE cancellation_token = %s
                    """,
                    (datetime.now(), token)
                )
                
                # Update customer's boxes_requested count
                cursor.execute(
                    """
                    UPDATE ironmountain_customers
                    SET boxes_requested = boxes_requested - %s
                    WHERE account_number = %s
                    """,
                    (request_data['quantity'], request_data['account_number'])
                )
                
                conn.commit()
                cursor.close()
                conn.close()
                
                # Return success page
                return HTMLResponse(f"""
                <html>
                    <body style="font-family: Arial, sans-serif; padding: 40px; max-width: 600px; margin: 0 auto; background-color: #f5f5f5;">
                        <div style="background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            <div style="text-align: center; margin-bottom: 30px;">
                                <h1 style="color: #0066cc; margin: 0;">Iron Mountain</h1>
                                <p style="color: #666; margin: 5px 0;">Document Storage & Information Management</p>
                            </div>
                            
                            <div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 20px; border-radius: 4px; margin-bottom: 30px; text-align: center;">
                                <h2 style="color: #155724; margin: 0;">✅ Request Cancelled Successfully</h2>
                            </div>
                            
                            <p style="font-size: 16px;">Your request for <strong>{request_data['quantity']} boxes</strong> (Account: {request_data['account_number']}) has been cancelled.</p>
                            
                            <p>Your account has been updated, and no boxes will be delivered for this request.</p>
                            
                            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 4px; margin-top: 30px;">
                                <p style="margin: 0;"><strong>Need to place a new request?</strong></p>
                                <p style="margin: 5px 0;">You can request boxes again through your account portal or by contacting our support team.</p>
                                <p style="margin: 5px 0;">📧 support@ironmountain.com</p>
                                <p style="margin: 5px 0;">📞 1-800-899-IRON (4766)</p>
                            </div>
                            
                            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px; text-align: center;">
                                <p>Thank you for choosing Iron Mountain.</p>
                            </div>
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
            """User clicked 'Keep Request' - just redirect to a thank you message"""
            return HTMLResponse("""
            <html>
                <body style="font-family: Arial, sans-serif; padding: 40px; max-width: 600px; margin: 0 auto; background-color: #f5f5f5;">
                    <div style="background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center;">
                        <div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 20px; border-radius: 4px; margin-bottom: 30px;">
                            <h2 style="color: #155724; margin: 0;">✅ Request Maintained</h2>
                        </div>
                        <p>Your box request will continue to be processed as scheduled.</p>
                        <p>Thank you for choosing Iron Mountain!</p>
                    </div>
                </body>
            </html>
            """)
        
        logger.info("✅ Cancellation service routes added to Chainlit")
    else:
        logger.warning("⚠️ Could not find FastAPI app to add exception handlers")
except Exception as e:
    logger.warning(f"⚠️ Could not add exception handlers: {e}")


# ============================================================================
# AUTHENTICATION
# ============================================================================
# Simple authentication
@cl.password_auth_callback
async def auth_callback(username: str, password: str) -> Optional[cl.User]:
    """Simple authentication - enter any username (no password validation)"""
    if username:
        return cl.User(
            identifier=username,
            metadata={"role": "user", "name": username}
        )
    return None

# ============================================================================
# AUTOGEN STUDIO INTEGRATION (Sessions, Runs, Team Config)
# ============================================================================
def get_team_config(team_id: int) -> Optional[dict]:
    """Fetch team configuration from PostgreSQL database"""
    try:
        logger.info(f"🔄 Loading team config for team_id={team_id}...")
        result = subprocess.run(
            [
                "docker",
                "exec",
                "quanterra_postgres",
                "psql",
                "-U",
                "quanterra_user",
                "-d",
                "autogen",
                "-c",
                f"SELECT component FROM team WHERE id = {team_id};",
                "-t",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info(f"📥 Raw output length: {len(result.stdout)} chars")
        team_config = json.loads(result.stdout.strip())
        logger.info(f"✅ Team config loaded for team_id={team_id}, config keys: {list(team_config.keys())}")
        return team_config
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Docker command failed for team {team_id}: {e.stderr}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON decode failed for team {team_id}: {e}")
        logger.error(f"Raw output: {result.stdout[:200]}")
        return None
    except Exception as e:
        logger.error(f"❌ Failed to load team config for team {team_id}: {e}")
        return None


def create_session(team_id: int, user_id: str) -> Optional[int]:
    """Create a new Autogen Studio session"""
    try:
        response = requests.post(
            f"{AUTOGEN_BASE_URL}/api/sessions/",
            json={
                "team_id": team_id,
                "user_id": user_id,
                "name": f"Iron Mountain Session - {cl.user_session.get('id')}",
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        session_id = data["data"]["id"]
        logger.info(f"✅ Session created for team {team_id}: {session_id}")
        return session_id
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        return None


def create_run(session_id: int, user_id: str) -> Optional[int]:
    """Create a new run for the session"""
    try:
        response = requests.post(
            f"{AUTOGEN_BASE_URL}/api/runs/",
            json={"session_id": session_id, "user_id": user_id},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        run_id = data["data"]["run_id"]
        logger.info(f"✅ Run created: {run_id}")
        return run_id
    except Exception as e:
        logger.error(f"Failed to create run: {e}")
        return None


async def query_autogen_team(run_id: int, team_config: dict, message: str, status_msg=None) -> str:
    """Send a message to Autogen team and get the response"""
    uri = f"{AUTOGEN_WS_URL}/api/ws/runs/{run_id}"
    try:
        logger.info(f"🔌 Connecting to Autogen WebSocket: {uri}")
        
        # Add timeout protection (120 seconds max)
        try:
            async with asyncio.timeout(120):
                async with websockets.connect(uri) as websocket:
                    logger.info("✅ Autogen WebSocket connected")
                    
                    # Send start message
                    start_msg = {
                        "type": "start",
                        "task": message,
                        "team_config": team_config,
                    }
                    await websocket.send(json.dumps(start_msg))
                    logger.info(f"📤 Message sent to team: {message[:50]}...")
                    
                    # Collect all responses
                    full_response = ""
                    async for response in websocket:
                        try:
                            data = json.loads(response)
                            msg_type = data.get("type")
                            
                            if msg_type == "message":
                                msg_data = data.get("data", {})
                                content = msg_data.get("content", "")
                                source = msg_data.get("source", "")
                                if content and source:
                                    full_response += f"\n{content}"
                                    logger.info(f"📥 Team ({source}): {content[:50]}...")
                            elif msg_type == "result":
                                logger.info("✅ Team task complete!")
                                if status_msg:
                                    status_msg.content = "✅ Done!"
                                    await status_msg.update()
                                break
                            elif msg_type == "error":
                                error_msg = data.get("error", "Unknown error")
                                logger.error(f"❌ Team error: {error_msg}")
                                if status_msg:
                                    status_msg.content = f"❌ Error: {error_msg}"
                                    await status_msg.update()
                                return f"Error: {error_msg}"
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON received")
                        except websockets.exceptions.ConnectionClosed:
                            logger.info("🔌 Connection closed")
                            break
                    
                    return full_response.strip() if full_response else "No response from team."
        except TimeoutError:
            logger.error(f"⏱️ Autogen WebSocket timeout after 120s")
            if status_msg:
                status_msg.content = "⏱️ This is taking longer than expected..."
                await status_msg.update()
            return "I'm taking longer than expected to process this. Please try again."
    except Exception as e:
        logger.error(f"Autogen WebSocket error: {e}")
        if status_msg:
            status_msg.content = "❌ Connection error. Please try again."
            await status_msg.update()
        return f"Failed to communicate with team: {e}"


# ============================================================================
# OPENAI REALTIME VOICE SETUP (tools + instructions)
# ============================================================================
async def setup_openai_realtime():
    """Setup OpenAI Realtime Client for Iron Mountain"""
    openai_realtime = RealtimeClient(api_key=os.getenv("OPENAI_API_KEY"))
    cl.user_session.set("track_id", str(uuid4()))
    
    async def handle_conversation_updated(event):
        """Stream audio back to client"""
        item = event.get("item")
        delta = event.get("delta")
        if delta:
            if "audio" in delta:
                audio = delta["audio"]
                await cl.context.emitter.send_audio_chunk(
                    cl.OutputAudioChunk(
                        mimeType="pcm16",
                        data=audio,
                        track=cl.user_session.get("track_id"),
                    )
                )
            if "transcript" in delta:
                transcript = delta["transcript"]
                logger.info(f"🎤 Transcript: {transcript}")
    
    async def handle_conversation_interrupt(event):
        """Cancel previous audio playback"""
        cl.user_session.set("track_id", str(uuid4()))
        await cl.context.emitter.send_audio_interrupt()
    
    async def handle_error(event):
        logger.error(f"OpenAI Realtime error: {event}")
    
    # Register event handlers
    openai_realtime.on("conversation.updated", handle_conversation_updated)
    openai_realtime.on("conversation.interrupted", handle_conversation_interrupt)
    openai_realtime.on("error", handle_error)
    
    # Tool: Query Customer Account
    async def query_customer_account(account_number: str) -> str:
        """Query customer account from database team"""
        try:
            db_session_id = cl.user_session.get("db_session_id")
            db_team_config = cl.user_session.get("db_team_config")
            if not db_session_id or not db_team_config:
                return "Database session not initialized."
            
            # Show processing message on screen
            status_msg = cl.Message(content="🔍 Looking up your account...")
            await status_msg.send()
            
            # Create run and query - CALL API FIRST
            run_id = create_run(db_session_id, USER_ID)
            if not run_id:
                status_msg.content = "❌ Connection issue. Please try again."
                await status_msg.update()
                return "I'm having trouble connecting to the database right now. Please try again in a moment."
            
            status_msg.content = "📊 Fetching your account details..."
            await status_msg.update()
            query = f"Get full customer account details for account number: {account_number}"
            response = await query_autogen_team(run_id, db_team_config, query, status_msg=status_msg)
            
            # Parse response to extract customer name for personalized message
            try:
                import re
                json_match = re.search(r'\{.*"status".*"data".*\}', response, re.DOTALL)
                if json_match:
                    customer_json = json.loads(json_match.group())
                    if customer_json.get("status") == "success" and "data" in customer_json:
                        customer_data = customer_json["data"]
                        customer_name = customer_data.get("customer_name")
                        # Update with personalized welcome
                        if customer_name:
                            first_name = customer_name.split()[0] if customer_name else "there"
                            status_msg.content = f"👋 Welcome back, {first_name}!"
                            await status_msg.update()
            except:
                pass
            
            logger.info(f"📊 Database response: {response[:100]}...")
            return response
            
        except Exception as e:
            logger.error(f"Error querying account: {e}")
            return f"I encountered an error while looking up your account. Please try again."
    
    # Tool: Check Box Inventory
    async def check_box_inventory(account_number: str) -> str:
        """Check customer's box inventory"""
        try:
            db_session_id = cl.user_session.get("db_session_id")
            db_team_config = cl.user_session.get("db_team_config")
            if not db_session_id or not db_team_config:
                return "Database session not initialized."
            
            status_msg = cl.Message(content="📦 Checking your box inventory...")
            await status_msg.send()
            
            # Call API FIRST
            run_id = create_run(db_session_id, USER_ID)
            if not run_id:
                status_msg.content = "❌ Connection issue. Please try again."
                await status_msg.update()
                return "I'm having trouble connecting to the database right now. Please try again in a moment."
            
            status_msg.content = "🔍 Fetching inventory details..."
            await status_msg.update()
            
            query = f"Get box inventory for account number: {account_number}. Show boxes retained and boxes requested."
            response = await query_autogen_team(run_id, db_team_config, query, status_msg=status_msg)
            
            # Parse and show personalized message
            try:
                import re
                json_match = re.search(r'\{.*"status".*"data".*\}', response, re.DOTALL)
                if json_match:
                    inventory_json = json.loads(json_match.group())
                    if inventory_json.get("status") == "success" and "data" in inventory_json:
                        data = inventory_json["data"]
                        boxes_retained = data.get("boxes_retained", 0)
                        boxes_requested = data.get("boxes_requested", 0)
                        status_msg.content = f"✅ Found {boxes_retained} boxes in storage, {boxes_requested} requested"
                        await status_msg.update()
            except:
                pass
            
            return response
            
        except Exception as e:
            logger.error(f"Error checking inventory: {e}")
            return f"I encountered an error while checking your inventory. Please try again."
    
    # Tool: Request Empty Boxes
    async def request_empty_boxes(account_number: str, quantity: int) -> str:
        """Request empty storage boxes"""
        try:
            db_session_id = cl.user_session.get("db_session_id")
            email_session_id = cl.user_session.get("email_session_id")
            db_team_config = cl.user_session.get("db_team_config")
            email_team_config = cl.user_session.get("email_team_config")
            
            if not db_session_id or not email_session_id or not db_team_config or not email_team_config:
                return "Sessions not initialized."
            
            status_msg = cl.Message(content=f"📦 Processing your request for {quantity} boxes...")
            await status_msg.send()
            
            # Step 1: Get customer details - CALL API FIRST
            run_id = create_run(db_session_id, USER_ID)
            if not run_id:
                status_msg.content = "❌ Connection issue. Please try again."
                await status_msg.update()
                return "I'm having trouble accessing your account. Please try again in a moment."
            
            status_msg.content = "👤 Fetching your account information..."
            await status_msg.update()
            customer_query = f"Get full customer account details for {account_number}"
            customer_info = await query_autogen_team(run_id, db_team_config, customer_query, status_msg=status_msg)
            
            # Parse customer data from JSON response
            customer_data = None
            boxes_retained = 0
            boxes_requested_old = 0
            try:
                # Extract JSON from response (database returns JSON)
                import re
                json_match = re.search(r'\{.*"status".*"data".*\}', customer_info, re.DOTALL)
                if json_match:
                    customer_json = json.loads(json_match.group())
                    if customer_json.get("status") == "success" and "data" in customer_json:
                        customer_data = customer_json["data"]
                        boxes_retained = customer_data.get("boxes_retained", 0)
                        boxes_requested_old = customer_data.get("boxes_requested", 0)
                elif customer_info.strip().startswith("{"):
                    customer_json = json.loads(customer_info)
                    if customer_json.get("status") == "success" and "data" in customer_json:
                        customer_data = customer_json["data"]
                        boxes_retained = customer_data.get("boxes_retained", 0)
                        boxes_requested_old = customer_data.get("boxes_requested", 0)
            except Exception as parse_error:
                logger.warning(f"Could not parse customer data: {parse_error}")
            
            # Step 2: Update database - extract customer name first for personalized message
            customer_name = None
            address = None
            if customer_data:
                customer_name = customer_data.get('customer_name', '')
                address = customer_data.get('address', '')
                first_name = customer_name.split()[0] if customer_name else "there"
                status_msg.content = f"✅ Got your info, {first_name}! Updating your account..."
                await status_msg.update()
            
            run_id = create_run(db_session_id, USER_ID)
            if not run_id:
                status_msg.content = "❌ Failed to update. Please try again."
                await status_msg.update()
                return "I was able to get your information, but I'm having trouble updating your request. Please try again."
            
            status_msg.content = "💾 Saving your box request..."
            await status_msg.update()
            update_query = f"Update box request for account {account_number}: add {quantity} boxes to boxes_requested"
            update_response = await query_autogen_team(run_id, db_team_config, update_query, status_msg=status_msg)
            
            # Calculate new boxes_requested (after update)
            boxes_requested = boxes_requested_old + quantity
            
            # Personalized email sending message
            if address:
                status_msg.content = f"📧 Sending confirmation emails to {address}..."
            else:
                status_msg.content = "📧 Sending your confirmation emails..."
            await status_msg.update()
            
            # Step 3: Send emails via email team with STRUCTURED data
            run_id = create_run(email_session_id, USER_ID)
            if not run_id:
                logger.error("Failed to create email session")
                return f"Your box request has been processed! {quantity} boxes will be delivered in 3-5 business days. However, I'm having trouble sending confirmation emails right now. Your request is confirmed in our system."
            
            # Build email query with structured data - tell agent exactly what to do
            if customer_data:
                email_query = f"""Call the send_box_request_emails tool with these exact parameters:

account_number: {customer_data.get('account_number', account_number)}
customer_name: {customer_data.get('customer_name', 'Customer')}
company_name: {customer_data.get('company_name', 'N/A')}
address: {customer_data.get('address', 'N/A')}
quantity: {quantity}
boxes_retained: {boxes_retained}
boxes_requested: {boxes_requested}

This will send both internal notification and customer confirmation emails."""
            else:
                # Fallback if parsing failed
                email_query = f"""Extract customer information from this database response and call send_box_request_emails tool:

Database Response: {customer_info[:800]}

You need to extract: account_number, customer_name, company_name, address, boxes_retained, boxes_requested
Then call send_box_request_emails with:
- account_number: {account_number}
- quantity: {quantity}
- boxes_requested: {quantity} (since we just added this quantity)
- And the extracted customer_name, company_name, address, boxes_retained"""
            
            # Call email API and get response
            email_response = await query_autogen_team(run_id, email_team_config, email_query, status_msg=status_msg)
            
            # Parse email response to check if emails were sent - enhanced parsing
            email_sent = False
            email_error = None
            try:
                if isinstance(email_response, str):
                    # Try to parse JSON response from MCP tool
                    if "{" in email_response:
                        import re
                        # Look for JSON objects in the response
                        json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', email_response)
                        for json_str in json_matches:
                            try:
                                email_data = json.loads(json_str)
                                if email_data.get("status") == "success":
                                    email_sent = True
                                    break
                                elif email_data.get("status") == "error":
                                    email_error = email_data.get("message", "Unknown error")
                            except:
                                continue
                    # Check for success indicators in response text
                    response_lower = email_response.lower()
                    if ("success" in response_lower or "sent" in response_lower) and "error" not in response_lower:
                        email_sent = True
                    if "error" in response_lower and not email_sent:
                        email_error = "Email sending failed"
            except Exception as parse_error:
                logger.warning(f"Could not parse email response: {parse_error}")
                logger.info(f"Raw email response: {email_response[:500]}")
            
            if email_sent:
                logger.info(f"📧 Email sent successfully. Response: {email_response[:200]}")
                if address:
                    status_msg.content = f"✅ Perfect! Your {quantity} boxes will be delivered to {address} in 3-5 business days!"
                else:
                    status_msg.content = f"✅ Perfect! Your {quantity} boxes will be delivered in 3-5 business days!"
                await status_msg.update()
                return f"Perfect! Your request for {quantity} boxes has been processed. They'll be delivered to your address in 3-5 business days. I've just sent confirmation emails to your inbox with all the details."
            else:
                logger.warning(f"⚠️ Email may not have been sent. Response: {email_response[:500]}")
                status_msg.content = "⚠️ Box request processed, but email may have issues. Check logs."
                await status_msg.update()
                return (
                    f"Your box request for {quantity} boxes has been processed and will be delivered in 3-5 business days. "
                    "I'm having trouble sending the confirmation email right now, but your request is confirmed in our system. "
                    "You should receive an email shortly."
                )
            
        except Exception as e:
            logger.error(f"Error requesting boxes: {e}")
            return f"Error: {e}"
    
    # Register tools with OpenAI Realtime (definition dict + handler pattern)
    query_customer_account_def = {
        "name": "query_customer_account",
        "description": "Look up customer account details by account number. Use this when customer provides their account number or wants to check their account.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_number": {
                    "type": "string",
                    "description": "Customer account number in format IM-XXXXX"
                }
            },
            "required": ["account_number"]
        }
    }
    await openai_realtime.add_tool(query_customer_account_def, query_customer_account)
    
    check_box_inventory_def = {
        "name": "check_box_inventory",
        "description": "Check how many boxes a customer has in storage. Use this when customer asks about their box count or inventory.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_number": {
                    "type": "string",
                    "description": "Customer account number"
                }
            },
            "required": ["account_number"]
        }
    }
    await openai_realtime.add_tool(check_box_inventory_def, check_box_inventory)
    
    request_empty_boxes_def = {
        "name": "request_empty_boxes",
        "description": "Request empty storage boxes for delivery to customer. Use this when customer wants to order boxes. This will update database and send confirmation emails.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_number": {
                    "type": "string",
                    "description": "Customer account number"
                },
                "quantity": {
                    "type": "integer",
                    "description": "Number of empty boxes to request"
                }
            },
            "required": ["account_number", "quantity"]
        }
    }
    await openai_realtime.add_tool(request_empty_boxes_def, request_empty_boxes)
    
    # Configure session with Iron Mountain personality
    await openai_realtime.update_session(
        instructions=(
            "You are IronAssist, a professional multilingual voice assistant for Iron Mountain, "
            "the world's leading information management company.\n\n"
            
            "ABOUT IRON MOUNTAIN:\n"
            "- Global leader in storage and information management since 1951\n"
            "- Trusted by 95% of Fortune 1000 companies\n"
            "- Services: Document storage, box delivery, secure records management\n\n"
            
            "YOUR ROLE:\n"
            "- Help customers check their account and storage inventory\n"
            "- Process requests for empty storage boxes\n"
            "- Provide professional, efficient service\n"
            "- Support customers in their preferred language\n\n"
            
            "MULTILINGUAL SUPPORT:\n"
            "- Detect the customer's language from their first message\n"
            "- Respond in the SAME language they use (English, Arabic, French, Spanish, etc.)\n"
            "- If they switch languages mid-conversation, switch with them\n"
            "- Maintain professionalism across all languages\n"
            "- Example: If customer says 'مرحبا' (Arabic hello), respond in Arabic\n"
            "- Example: If customer says 'Bonjour' (French hello), respond in French\n\n"
            
            "PERSONALITY:\n"
            "- Professional but warm and approachable\n"
            "- Efficient and detail-oriented\n"
            "- Use culturally appropriate greetings and phrases\n"
            "- Keep responses concise (2-3 sentences) unless details are needed\n\n"
            
            "WORKFLOWS:\n\n"
            
            "1. ACCOUNT LOOKUP:\n"
            "   - Always ask for account number first (format: IM-XXXXX)\n"
            "   - Use query_customer_account tool\n"
            "   - Greet customer by name and confirm their company\n"
            "   - Example: 'Welcome back, Yousef! I see you're with Tech Innovations LLC. How can I help?'\n\n"
            
            "2. CHECK BOX INVENTORY:\n"
            "   - Verify account number\n"
            "   - Use check_box_inventory tool\n"
            "   - Report boxes_retained and boxes_requested clearly\n"
            "   - Example: 'You currently have 15 boxes in storage with no pending requests.'\n\n"
            
            "3. REQUEST EMPTY BOXES:\n"
            "   - Confirm account number first\n"
            "   - Ask how many boxes needed\n"
            "   - Confirm delivery address\n"
            "   - Use request_empty_boxes tool\n"
            "   - Mention: '3-5 business days delivery' and 'confirmation emails sent'\n"
            "   - Example: 'Perfect! I've requested 5 boxes to Dubai Marina. Delivery in 3-5 days. Check your email for confirmation.'\n\n"
            
            "NATURAL CONVERSATION DURING OPERATIONS:\n"
            "- When using tools (like checking accounts, inventory, or processing requests), speak naturally as if in a phone call\n"
            "- Say things like 'Let me check that for you', 'Just a moment', 'I'm looking that up now' while tools are running\n"
            "- Don't just wait silently - keep the customer informed naturally\n"
            "- Example: Customer says 'Check my account IM-10001', you say 'Sure, let me pull that up for you right now' [tool runs] 'Great! I've got your information here...'\n\n"
            
            "IMPORTANT RULES:\n"
            "- Always verify account number before providing sensitive information\n"
            "- Be clear about delivery timeframes (3-5 business days)\n"
            "- Mention that TWO emails are sent (internal + customer confirmation)\n"
            "- If customer seems uncertain, offer to help them find their account number\n"
            "- Stay professional but friendly\n"
            "- Keep the conversation flowing naturally during all operations\n\n"
            
            "SAMPLE INTERACTIONS:\n"
            "Customer: 'Hi, my account is IM-10001'\n"
            "You: 'Welcome back! Let me pull up your account.' [use query_customer_account]\n"
            "     'Great! I see you're Yousef with Tech Innovations. How can I help today?'\n\n"
            
            "Customer: 'How many boxes do I have?'\n"
            "You: 'I'd be happy to check! What's your account number?' [get account] [use check_box_inventory]\n"
            "     'You have 15 boxes in storage with us, with no pending deliveries.'\n\n"
            
            "Customer: 'I need 5 boxes'\n"
            "You: 'Sure thing! Let me confirm - is your delivery address still Dubai Marina?' [confirm]\n"
            "     'Perfect! Processing that now...' [use request_empty_boxes]\n"
            "     'All set! 5 boxes will arrive in 3-5 days. You'll get two confirmation emails shortly.'\n"
        ),
        turn_detection={"type": "server_vad"},
        voice="echo",  # Male voice as requested
        temperature=0.6
    )
    
    cl.user_session.set("openai_realtime", openai_realtime)
    logger.info("✅ OpenAI Realtime client configured for Iron Mountain")
    
    # Return the client instance
    return openai_realtime


# ============================================================================
# CHAINLIT EVENT HANDLERS
# ============================================================================
@cl.on_chat_resume
async def on_chat_resume(thread: dict):
    """Resume a previous chat thread and restore session state"""
    thread_id = thread.get('id')
    
    # Verify thread exists in database before resuming
    try:
        thread_data = await chainlit_data_layer.get_thread(thread_id)
        if not thread_data:
            await cl.ErrorMessage(content="Thread not found.").send()
            return
    except Exception as e:
        logger.error(f"Error verifying thread: {e}")
        await cl.ErrorMessage(content="Couldn't resume chat: Thread not found.").send()
        return
    
    # Reinitialize Autogen teams
    try:
        db_team_config = get_team_config(DB_TEAM_ID)
        email_team_config = get_team_config(EMAIL_TEAM_ID)
        
        db_session_id = create_session(DB_TEAM_ID, USER_ID)
        email_session_id = create_session(EMAIL_TEAM_ID, USER_ID)
        
        cl.user_session.set("db_session_id", db_session_id)
        cl.user_session.set("email_session_id", email_session_id)
        cl.user_session.set("db_team_config", db_team_config)
        cl.user_session.set("email_team_config", email_team_config)
        
        # Setup OpenAI Realtime for voice features
        await setup_openai_realtime()
        
        await cl.Message(content="✅ Welcome back! Continuing your conversation...").send()
    except Exception as e:
        logger.error(f"Failed to resume chat: {e}")
        await cl.ErrorMessage(content="Couldn't resume chat: Thread not found.").send()


@cl.on_chat_start
async def start():
    """Initialize Iron Mountain assistant"""
    await cl.Message(
        content="👋 **Welcome to Iron Mountain!**\n\n"
        "I'm **IronAssist**, your virtual storage assistant.\n\n"
        "I can help you with:\n"
        "📦 **Check your account** - View your storage details\n"
        "📊 **Box inventory** - See how many boxes you have with us\n"
        "🚚 **Request empty boxes** - Order boxes for document storage\n\n"
        "**🎤 Press `P` to talk, or type your account number to get started!**\n\n"
        "_Example: 'My account number is IM-10001'_"
    ).send()
    
    loading_msg = cl.Message(content="⏳ Connecting to Iron Mountain systems...")
    await loading_msg.send()
    
    try:
        # Load team configurations
        db_team_config = get_team_config(DB_TEAM_ID)
        email_team_config = get_team_config(EMAIL_TEAM_ID)
        
        # Try to create sessions for both teams (optional)
        db_session_id = create_session(DB_TEAM_ID, USER_ID)
        email_session_id = create_session(EMAIL_TEAM_ID, USER_ID)
        
        # Store session IDs and configs (can be None if teams not created yet)
        cl.user_session.set("db_session_id", db_session_id)
        cl.user_session.set("email_session_id", email_session_id)
        cl.user_session.set("db_team_config", db_team_config)
        cl.user_session.set("email_team_config", email_team_config)
        
        # Setup OpenAI Realtime (always available)
        await setup_openai_realtime()
        
        if db_session_id and email_session_id and db_team_config and email_team_config:
            loading_msg.content = "✅ **Ready!** All systems connected. Press **P** to talk!"
        else:
            loading_msg.content = (
                "✅ **Voice Ready!** Press **P** to talk.\n\n"
                "⚠️ _Note: Create Autogen Teams 2 & 3 in Autogen Studio to enable full database & email features._"
            )
        await loading_msg.update()
        
    except Exception as e:
        logger.error(f"Initialization error: {e}")
        await cl.ErrorMessage(content=f"Setup error: {e}").send()


@cl.on_message
async def on_message(message: cl.Message):
    """Handle text messages"""
    thread_id = cl.user_session.get("thread_id")
    message_count = cl.user_session.get("message_count", 0)
    user_query = message.content
    
    # Auto-generate thread title from first message
    if message_count == 0 and thread_id:
        try:
            # Wait a bit for Chainlit to create the thread in DB first
            await asyncio.sleep(0.2)
            
            # Verify thread exists before updating
            thread = await chainlit_data_layer.get_thread(thread_id)
            if thread:
                # Generate clean title from first user message
                title = chainlit_data_layer._extract_title_from_message(user_query)
                if not title:
                    title = user_query.strip()[:60] if user_query.strip() else "Chat"
                
                await chainlit_data_layer.update_thread(thread_id, name=title)
        except Exception as e:
            logger.error(f"Failed to update thread title: {e}")
    
    # Increment message count
    cl.user_session.set("message_count", message_count + 1)
    
    # REMOVED: Manual step creation - Chainlit handles this automatically
    # Chainlit's built-in persistence will save the message to the database
    # No need to manually call create_step() - it causes duplicate saves and FK errors
    
    db_session_id = cl.user_session.get("db_session_id")
    email_session_id = cl.user_session.get("email_session_id")
    db_team_config = cl.user_session.get("db_team_config")
    email_team_config = cl.user_session.get("email_team_config")
    
    if not db_session_id or not email_session_id or not db_team_config or not email_team_config:
        await cl.Message(
            content="⚠️ **Autogen teams not configured yet.**\n\n"
            "Please create Teams 2 & 3 in Autogen Studio:\n"
            "1. Open http://localhost:8000\n"
            "2. Create Team 2 (DB Team) with MCP Database tools\n"
            "3. Create Team 3 (Email Team) with MCP Email tools\n\n"
            "For now, you can still use voice features by pressing **P**!"
        ).send()
        return
    
    # Friendly processing messages (random selection)
    processing_messages = [
        "🔍 Let me check that for you...",
        "📋 Looking into that now...",
        "⏳ Give me just a moment to pull that up...",
        "🔄 Processing your request...",
        "📊 Let me find that information...",
        "✨ Working on that for you..."
    ]
    
    # Simple routing based on query content
    if "account" in user_query.lower() or "im-" in user_query.lower():
        session_id = db_session_id
        team_config = db_team_config
        # More specific message for account queries
        thinking_msg = cl.Message(content=random.choice([
            "🔍 Let me look up that account for you...",
            "📋 Checking your account details...",
            "🔎 Pulling up your account information..."
        ]))
    elif "email" in user_query.lower() or "send" in user_query.lower():
        session_id = email_session_id
        team_config = email_team_config
        thinking_msg = cl.Message(content="📧 Preparing to send emails...")
    elif "box" in user_query.lower() and ("how many" in user_query.lower() or "count" in user_query.lower() or "inventory" in user_query.lower()):
        session_id = db_session_id
        team_config = db_team_config
        thinking_msg = cl.Message(content="📦 Let me check your box inventory...")
    elif "box" in user_query.lower() and ("request" in user_query.lower() or "need" in user_query.lower() or "order" in user_query.lower()):
        session_id = db_session_id
        team_config = db_team_config
        thinking_msg = cl.Message(content="📦 Processing your box request...")
    else:
        session_id = db_session_id  # Default to database team
        team_config = db_team_config
        thinking_msg = cl.Message(content=random.choice(processing_messages))
    
    await thinking_msg.send()
    
    try:
        run_id = create_run(session_id, USER_ID)
        if not run_id:
            thinking_msg.content = "❌ Sorry, I'm having trouble processing that right now. Please try again."
            await thinking_msg.update()
            return
        
        response = await query_autogen_team(run_id, team_config, user_query)
        thinking_msg.content = response
        await thinking_msg.update()
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        thinking_msg.content = f"❌ Sorry, something went wrong: {str(e)}"
        await thinking_msg.update()


@cl.on_audio_start
async def on_audio_start():
    """Connect to OpenAI Realtime when voice starts"""
    try:
        openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
        await openai_realtime.connect()
        logger.info("🎤 Connected to OpenAI Realtime")
        return True
    except Exception as e:
        await cl.ErrorMessage(
            content=f"Failed to connect to voice service: {e}"
        ).send()
        return False


@cl.on_audio_chunk
async def on_audio_chunk(chunk: cl.InputAudioChunk):
    """Stream audio to OpenAI Realtime"""
    openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
    if openai_realtime and openai_realtime.is_connected():
        await openai_realtime.append_input_audio(chunk.data)
    else:
        logger.warning("RealtimeClient not connected")


@cl.on_audio_end
@cl.on_chat_end
@cl.on_stop
async def on_end():
    """Cleanup"""
    openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
    if openai_realtime and openai_realtime.is_connected():
        await openai_realtime.disconnect()
    logger.info("Iron Mountain session ended")



