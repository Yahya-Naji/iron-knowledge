"""
Iron Mountain Voice Assistant - Chainlit Application
Simplified version with direct SQLite access (no AutoGen)
"""
# ============================================================================
# SETUP - Must be done before Chainlit imports
# ============================================================================
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Set JWT secret for authentication
if "CHAINLIT_SECRET_KEY" not in os.environ:
    os.environ["CHAINLIT_SECRET_KEY"] = "YLYdeA-4wwjXw6-i_BNnGzkrPD01FwZySCDycRx4fM"

# ============================================================================
# IMPORTS
# ============================================================================
from typing import Optional
from uuid import uuid4
import chainlit as cl
from chainlit.logger import logger

# Custom OpenAI Realtime Client (from realtime module)
try:
    from realtime import RealtimeClient
    REALTIME_AVAILABLE = True
except ImportError:
    RealtimeClient = None
    REALTIME_AVAILABLE = False
    logger.warning("⚠️ Realtime Client not available. Voice features will be disabled.")

# Local imports
from db.queries import get_customer_account, get_box_inventory, update_box_request
from services.email import send_box_request_confirmation, send_box_request_notification

# ============================================================================
# CONFIGURATION
# ============================================================================
# Enable Chainlit data persistence
os.environ.setdefault("CHAINLIT_DATA_PERSISTENCE", "true")
logger.info("🗄️  Chainlit data persistence enabled with default file-based storage")


# ============================================================================
# REST API ROUTES (from api folder)
# ============================================================================
try:
    import chainlit.server as cl_server
    from api.routes import router
    
    app = None
    if hasattr(cl_server, 'app'):
        app = cl_server.app
    elif hasattr(cl_server, 'chainlit_app'):
        app = cl_server.chainlit_app
    
    if app:
        # Include API router
        app.include_router(router)
        logger.info("✅ REST API routes added from api/routes.py")
        logger.info("   - GET /api/customer/{account_number}")
        logger.info("   - GET /api/inventory/{account_number}")
        logger.info("   - POST /api/request-boxes")
        logger.info("   - GET /api/health")
except Exception as e:
    logger.warning(f"⚠️ Could not add REST API routes: {e}")

        
# ============================================================================
# CANCELLATION SERVICE ROUTES
# ============================================================================
try:
    import chainlit.server as cl_server
    from services.cancellation import register_cancellation_routes
    
    app = None
    if hasattr(cl_server, 'app'):
        app = cl_server.app
    elif hasattr(cl_server, 'chainlit_app'):
        app = cl_server.chainlit_app
    
    if app:
        register_cancellation_routes(app)
        logger.info("✅ Cancellation service routes added")
except Exception as e:
    logger.warning(f"⚠️ Could not add cancellation routes: {e}")


# ============================================================================
# AUTHENTICATION
# ============================================================================
@cl.password_auth_callback
async def auth_callback(username: str, password: str) -> Optional[cl.User]:
    """Simple authentication - enter any username"""
    if username:
        return cl.User(
            identifier=username,
            metadata={"role": "user", "name": username}
        )
    return None


# ============================================================================
# OPENAI REALTIME VOICE SETUP
# ============================================================================
async def setup_openai_realtime():
    """Setup OpenAI Realtime Client with direct SQLite tools"""
    if not REALTIME_AVAILABLE:
        logger.warning("⚠️ OpenAI Realtime not available - voice features disabled")
        return None
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("⚠️ OPENAI_API_KEY not set - voice features disabled")
        return None
    
    try:
        rt = RealtimeClient(api_key=api_key)
    except Exception as e:
        logger.error(f"⚠️ Failed to initialize RealtimeClient: {e}", exc_info=True)
        return None
    
    # Set up track ID for audio streaming
    track_id = str(uuid4())
    cl.user_session.set("track_id", track_id)
    
    # Set up event handler for conversation updates (audio/text deltas)
    async def on_conv_updated(event):
        """Handle conversation updates - forward audio/text to Chainlit"""
        try:
            delta = event.get("delta") or {}
            
            # Handle audio deltas - send directly to Chainlit audio output
            if "audio" in delta and delta["audio"]:
                audio_data = delta["audio"]
                if isinstance(audio_data, bytes):
                    # Send audio chunk to Chainlit
                    try:
                        await cl.context.emitter.send_audio_chunk(
                            cl.OutputAudioChunk(
                                mimeType="audio/pcm",
                                data=audio_data,
                                track=cl.user_session.get("track_id"),
                            )
                        )
                    except Exception as send_error:
                        # If send fails, log but don't crash
                        logger.debug(f"Could not send audio chunk: {send_error}")
                elif isinstance(audio_data, list):
                    # Handle list of audio chunks
                    for chunk in audio_data:
                        if isinstance(chunk, bytes):
                            try:
                                await cl.context.emitter.send_audio_chunk(
                                    cl.OutputAudioChunk(
                                        mimeType="audio/pcm",
                                        data=chunk,
                                        track=cl.user_session.get("track_id"),
                                    )
                                )
                            except Exception as send_error:
                                logger.debug(f"Could not send audio chunk: {send_error}")
                else:
                    logger.debug(f"Audio data type: {type(audio_data)}, value: {str(audio_data)[:50]}")
            
            # Handle text deltas - optional: show text too
            if "text" in delta and delta["text"]:
                text = delta["text"]
                logger.debug(f"📤 Received text delta: {text[:50]}...")
        except Exception as e:
            logger.error(f"Error in conversation.updated handler: {e}", exc_info=True)
    
    # Handle interruptions - reset track ID (but don't log every time to avoid spam)
    async def on_interrupt(_event):
        """Handle conversation interruption"""
        # Only log occasionally to avoid spam
        import time
        last_interrupt_log = cl.user_session.get("last_interrupt_log", 0)
        if time.time() - last_interrupt_log > 2.0:  # Log at most once every 2 seconds
            logger.debug("🔄 Conversation interrupted - resetting track")
            cl.user_session.set("last_interrupt_log", time.time())
        cl.user_session.set("track_id", str(uuid4()))
        try:
            await cl.context.emitter.send_audio_interrupt()
        except Exception as e:
            logger.debug(f"Could not send audio interrupt: {e}")
    
    # Optional: log all realtime events for debugging
    def on_realtime_event(event):
        """Log realtime events for debugging"""
        event_type = event.get("event", {}).get("type", "unknown")
        logger.debug(f"🔔 Realtime event: {event_type}")
    
    # Register event handlers
    rt.on("conversation.updated", on_conv_updated)
    rt.on("conversation.interrupted", on_interrupt)
    rt.on("realtime.event", on_realtime_event)
    
    logger.info("✅ Event handlers registered for conversation.updated and conversation.interrupted")
    
    # Register tools with RealtimeClient
    # Tool: Query Customer Account
    async def query_customer_account(account_number: str) -> str:
        """Query customer account directly from SQLite"""
        logger.info("=" * 80)
        logger.info("🔍 API CALL: query_customer_account")
        logger.info(f"   Account Number: {account_number}")
        logger.info("=" * 80)
        try:
            status_msg = cl.Message(content="🔍 Looking up your account...")
            await status_msg.send()
            
            logger.info(f"📤 Calling get_customer_account({account_number})...")
            customer = get_customer_account(account_number)
            
            if not customer:
                logger.warning(f"❌ Account not found: {account_number}")
                status_msg.content = "❌ Account not found. Please check your account number."
                await status_msg.update()
                return f"I couldn't find an account with number {account_number}. Please verify your account number and try again."
            
            logger.info(f"✅ Account found: {customer.get('customer_name', 'Unknown')}")
            logger.info(f"   Company: {customer.get('company_name', 'N/A')}")
            logger.info(f"   Boxes in Storage: {customer.get('boxes_retained', 0)}")
            logger.info(f"   Boxes Requested: {customer.get('boxes_requested', 0)}")
            
            # Format response
            response = f"""Account Details for {account_number}:
- Customer Name: {customer['customer_name']}
- Company: {customer['company_name']}
- Address: {customer['address']}
- Phone: {customer['phone_number']}
- Email: {customer['email']}
- Boxes in Storage: {customer['boxes_retained']}
- Boxes Requested: {customer['boxes_requested']}"""
            
            # Personalized welcome
            first_name = customer['customer_name'].split()[0] if customer['customer_name'] else "there"
            status_msg.content = f"👋 Welcome back, {first_name}!"
            await status_msg.update()
            
            logger.info(f"📥 Returning response: {len(response)} characters")
            logger.info("=" * 80)
            return response
        except Exception as e:
            logger.error(f"❌ Error querying account: {e}", exc_info=True)
            return f"I encountered an error while looking up your account. Please try again."
    
    # Tool: Check Box Inventory
    async def check_box_inventory(account_number: str) -> str:
        """Check customer's box inventory directly from SQLite"""
        logger.info("=" * 80)
        logger.info("📦 API CALL: check_box_inventory")
        logger.info(f"   Account Number: {account_number}")
        logger.info("=" * 80)
        try:
            status_msg = cl.Message(content="📦 Checking your box inventory...")
            await status_msg.send()
            
            logger.info(f"📤 Calling get_box_inventory({account_number})...")
            inventory = get_box_inventory(account_number)
            
            if not inventory:
                logger.warning(f"❌ Account not found: {account_number}")
                status_msg.content = "❌ Account not found."
                await status_msg.update()
                return f"I couldn't find an account with number {account_number}."
            
            boxes_retained = inventory['boxes_retained']
            boxes_requested = inventory['boxes_requested']
            
            logger.info(f"✅ Inventory retrieved:")
            logger.info(f"   Customer: {inventory.get('customer_name', 'Unknown')}")
            logger.info(f"   Boxes in Storage: {boxes_retained}")
            logger.info(f"   Boxes Requested: {boxes_requested}")
            
            status_msg.content = f"✅ Found {boxes_retained} boxes in storage, {boxes_requested} requested"
            await status_msg.update()
            
            if boxes_requested > 0:
                response = f"Customer {inventory['customer_name']} has {boxes_retained} boxes currently in storage and {boxes_requested} boxes requested for delivery."
            else:
                response = f"Customer {inventory['customer_name']} has {boxes_retained} boxes currently in storage with no pending delivery requests."
            
            logger.info(f"📥 Returning response: {len(response)} characters")
            logger.info("=" * 80)
            return response
        except Exception as e:
            logger.error(f"❌ Error checking inventory: {e}", exc_info=True)
            return f"I encountered an error while checking your inventory. Please try again."
    
    # Tool: Request Empty Boxes
    async def request_empty_boxes(account_number: str, quantity: int) -> str:
        """Request empty storage boxes - direct SQLite update"""
        logger.info("=" * 80)
        logger.info("📦 API CALL: request_empty_boxes")
        logger.info(f"   Account Number: {account_number}")
        logger.info(f"   Quantity: {quantity}")
        logger.info("=" * 80)
        try:
            status_msg = cl.Message(content=f"📦 Processing your request for {quantity} boxes...")
            await status_msg.send()
            
            # Get customer details first
            logger.info(f"📤 Step 1: Calling get_customer_account({account_number})...")
            customer = get_customer_account(account_number)
            if not customer:
                logger.warning(f"❌ Account not found: {account_number}")
                status_msg.content = "❌ Account not found."
                await status_msg.update()
                return f"I couldn't find an account with number {account_number}. Please verify your account number."
            
            customer_name = customer.get('customer_name', '')
            address = customer.get('address', '')
            customer_email = customer.get('email', '')
            first_name = customer_name.split()[0] if customer_name else "there"
            
            logger.info(f"✅ Customer found: {customer_name}")
            logger.info(f"   Address: {address}")
            logger.info(f"   Email: {customer_email}")
            
            status_msg.content = f"✅ Got your info, {first_name}! Updating your account..."
            await status_msg.update()
            
            # Update database
            logger.info(f"📤 Step 2: Calling update_box_request({account_number}, {quantity})...")
            result = update_box_request(account_number, quantity)
            if not result or not result.get("success"):
                logger.error(f"❌ Failed to update box request in database")
                status_msg.content = "❌ Failed to process request. Please try again."
                await status_msg.update()
                return "I encountered an error while processing your box request. Please try again."
            
            cancellation_token = result.get("cancellation_token")
            logger.info(f"✅ Database updated successfully (cancellation token: {cancellation_token[:20]}...)")
            
            # Get updated inventory
            logger.info(f"📤 Step 3: Calling get_box_inventory({account_number})...")
            inventory = get_box_inventory(account_number)
            boxes_requested = inventory['boxes_requested'] if inventory else quantity
            logger.info(f"✅ Updated boxes_requested: {boxes_requested}")
            
            # Send confirmation emails (always send, regardless of customer_email in DB)
            status_msg.content = f"📧 Sending confirmation emails..."
            await status_msg.update()
            
            logger.info(f"📤 Step 4: Sending confirmation email...")
            # Send customer confirmation email (will be sent to TO_EMAIL from env)
            email_sent = send_box_request_confirmation(
                customer_email=customer_email,  # This will be overridden by TO_EMAIL
                customer_name=customer_name,
                account_number=account_number,
                quantity=quantity,
                address=address,
                cancellation_token=cancellation_token
            )
                
            if email_sent:
                logger.info(f"✅ Customer confirmation email sent successfully")
            else:
                logger.warning(f"⚠️ Customer confirmation email failed to send")
            
            # Send internal notification (optional - you can set this email)
            internal_email = os.getenv("INTERNAL_NOTIFICATION_EMAIL", "")
            if internal_email:
                logger.info(f"📤 Step 5: Sending internal notification to {internal_email}...")
                internal_sent = send_box_request_notification(
                    internal_email=internal_email,
                    customer_name=customer_name,
                    account_number=account_number,
                    quantity=quantity,
                    address=address
                )
                if internal_sent:
                    logger.info(f"✅ Internal notification sent successfully")
                else:
                    logger.warning(f"⚠️ Internal notification failed to send")
            
            if email_sent:
                to_email = os.getenv("TO_EMAIL", "your email")
                status_msg.content = f"✅ Perfect! Your {quantity} boxes will be delivered to {address} in 3-5 business days! Confirmation email sent to {to_email}."
            else:
                status_msg.content = f"✅ Your {quantity} boxes will be delivered to {address} in 3-5 business days! (Note: Email may not have been sent - check SMTP configuration)"
            
            await status_msg.update()
            
            email_note = f" I've sent a confirmation email to {customer_email}." if customer_email else ""
            response = f"Perfect! Your request for {quantity} boxes has been processed. They'll be delivered to your address in 3-5 business days. Your account now shows {boxes_requested} boxes requested for delivery.{email_note}"
            
            logger.info(f"📥 Returning response: {len(response)} characters")
            logger.info("=" * 80)
            return response
        except Exception as e:
            logger.error(f"❌ Error requesting boxes: {e}", exc_info=True)
            return f"Error: {e}"
    
    # Register tools with RealtimeClient using add_tool()
    tools_config = [
        {
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
        },
        {
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
        },
        {
            "name": "request_empty_boxes",
            "description": "Request empty storage boxes for delivery to customer. Use this when customer wants to order boxes. This will update database directly.",
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
    ]
    
    # Register each tool
    for tool_def in tools_config:
        tool_name = tool_def["name"]
        handler = locals()[tool_name]  # Get the handler function by name
        await rt.add_tool(tool_def, handler)
        logger.info(f"✅ Registered tool: {tool_name}")
    
    cl.user_session.set("openai_realtime", rt)
    logger.info("✅ OpenAI Realtime client initialized (will configure after connection)")
    return rt


# ============================================================================
# CHAINLIT EVENT HANDLERS
# ============================================================================
@cl.on_chat_resume
async def on_chat_resume(thread: dict):
    """Resume a previous chat thread"""
    try:
        await setup_openai_realtime()
        await cl.Message(content="✅ Welcome back! Continuing your conversation...").send()
    except Exception as e:
        logger.error(f"Failed to resume chat: {e}")
        await cl.ErrorMessage(content="Couldn't resume chat.").send()


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
        f"{'**🎤 Press `P` to talk, or ' if REALTIME_AVAILABLE else '**'}Type your account number to get started!**\n\n"
        "_Example: 'My account number is IM-10001'_"
    ).send()
    
    loading_msg = cl.Message(content="⏳ Connecting to Iron Mountain systems...")
    await loading_msg.send()
    
    try:
        rt = await setup_openai_realtime()
        if rt and REALTIME_AVAILABLE:
            loading_msg.content = "✅ **Ready!** All systems connected. Press **P** to talk!"
        elif REALTIME_AVAILABLE:
            loading_msg.content = "✅ **Ready!** Text chat is available. (Voice requires OPENAI_API_KEY to be set)"
        else:
            loading_msg.content = "✅ **Ready!** Text chat is available. (Voice requires Python 3.10+)"
        await loading_msg.update()
    except Exception as e:
        logger.error(f"Initialization error: {e}", exc_info=True)
        try:
            await cl.ErrorMessage(content=f"Setup error: {e}").send()
        except Exception as send_error:
            # Fallback if ErrorMessage fails
            logger.error(f"Failed to send error message: {send_error}")
            loading_msg.content = f"⚠️ Setup error: {e}"
            await loading_msg.update()


@cl.on_message
async def on_message(message: cl.Message):
    """Handle text messages - direct SQLite queries"""
    user_query = message.content.lower()
    
    # Simple keyword-based routing
    if "account" in user_query or "im-" in user_query:
        # Extract account number if present
        import re
        account_match = re.search(r'im-?\d+', user_query, re.IGNORECASE)
        if account_match:
            account_number = account_match.group(0).upper().replace('-', '-')
            if not account_number.startswith('IM-'):
                account_number = 'IM-' + account_number.split('-')[-1]
            
            thinking_msg = cl.Message(content="🔍 Looking up your account...")
            await thinking_msg.send()
            
            customer = get_customer_account(account_number)
            if customer:
                response = f"""**Account Details for {account_number}**
- **Customer:** {customer['customer_name']}
- **Company:** {customer['company_name']}
- **Address:** {customer['address']}
- **Phone:** {customer['phone_number']}
- **Email:** {customer['email']}
- **Boxes in Storage:** {customer['boxes_retained']}
- **Boxes Requested:** {customer['boxes_requested']}"""
                thinking_msg.content = response
            else:
                thinking_msg.content = f"❌ Account {account_number} not found. Please check your account number."
            await thinking_msg.update()
        return
    
    elif "inventory" in user_query or ("box" in user_query and ("how many" in user_query or "count" in user_query)):
        # Extract account number
        import re
        account_match = re.search(r'im-?\d+', user_query, re.IGNORECASE)
        if account_match:
            account_number = account_match.group(0).upper().replace('-', '-')
            if not account_number.startswith('IM-'):
                account_number = 'IM-' + account_number.split('-')[-1]
            
            thinking_msg = cl.Message(content="📦 Checking your box inventory...")
            await thinking_msg.send()
            
            inventory = get_box_inventory(account_number)
            if inventory:
                response = f"""**Box Inventory for {account_number}**
- **Customer:** {inventory['customer_name']}
- **Boxes in Storage:** {inventory['boxes_retained']}
- **Boxes Requested:** {inventory['boxes_requested']}"""
                thinking_msg.content = response
            else:
                thinking_msg.content = f"❌ Account {account_number} not found."
            await thinking_msg.update()
            return
        
    elif "request" in user_query or "order" in user_query or "need" in user_query:
        thinking_msg = cl.Message(content="📦 To request boxes, please provide:\n1. Your account number (e.g., IM-10001)\n2. Number of boxes needed\n\nOr use voice by pressing **P**!")
        await thinking_msg.send()
        return
    
    # Default response
    await cl.Message(
        content="I can help you with:\n"
        "- Checking your account (provide account number like IM-10001)\n"
        "- Checking box inventory\n"
        "- Requesting empty boxes\n\n"
        "**Or press P to use voice!**"
    ).send()


@cl.on_audio_start
async def on_audio_start():
    """Initialize voice connection"""
    status_msg = cl.Message(content="🔌 Connecting to voice service...")
    await status_msg.send()
    
    rt: RealtimeClient = cl.user_session.get("openai_realtime")
    if not rt:
        # Initialize if not already done
        rt = await setup_openai_realtime()
        if not rt:
            status_msg.content = "⚠️ Failed to initialize voice service"
            await status_msg.update()
            return False
    
    try:
        # Connect to OpenAI Realtime
        await rt.connect()
        logger.info("✅ Connected to OpenAI Realtime")
        
        # Configure session with turn detection and instructions
        # Allow interruptions but tune VAD to reduce false positives
        await rt.update_session(
            turn_detection={
                "type": "server_vad",
                "create_response": True,
                "interrupt_response": True,  # Allow user to interrupt assistant
                "threshold": 0.5,  # Voice activity threshold (0.0-1.0, higher = less sensitive)
                "prefix_padding_ms": 300,  # Padding before speech starts
                "silence_duration_ms": 500,  # Wait longer before considering speech ended (reduces cutting)
            },
            modalities=["audio", "text"],
            input_audio_format="pcm16",
            output_audio_format="pcm16",
            voice="echo",
            temperature=0.6,
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
                "CRITICAL WORKFLOW - ACCOUNT VERIFICATION:\n"
                "When you retrieve customer account information (using query_customer_account tool):\n"
                "1. ALWAYS welcome the customer by their FIRST NAME (extract from customer_name)\n"
                "2. ALWAYS confirm their address to ensure it's correct before proceeding\n"
                "3. Say something like: 'Hi [First Name]! I have your address on file as [address]. Is this still correct?'\n"
                "4. Wait for confirmation before processing any box requests or deliveries\n"
                "5. If address is wrong, acknowledge and note that they may need to update it\n"
                "6. This verification step is MANDATORY for security and accuracy\n\n"
                "EXAMPLE CONVERSATION:\n"
                "User: 'My account is IM-10001'\n"
                "You: [After query_customer_account] 'Hi John! Welcome back to Iron Mountain. I have your address on file as 123 Main St, New York, NY 10001. Is this still the correct delivery address for you?'\n"
                "User: 'Yes, that's correct'\n"
                "You: 'Perfect! How can I help you today?'\n\n"
                "IMPORTANT RULES:\n"
                "- Always verify account number before providing sensitive information\n"
                "- ALWAYS welcome customers by first name after retrieving their account\n"
                "- ALWAYS confirm address before processing any delivery requests\n"
                "- Be clear about delivery timeframes (3-5 business days)\n"
                "- Stay professional but friendly\n"
                "- Keep the conversation flowing naturally during all operations\n"
            ),
        )
        
        logger.info("✅ Session configured")
        status_msg.content = "✅ Voice ready! You can now speak."
        await status_msg.update()
        return True
    except Exception as e:
        logger.error(f"Failed to connect to voice service: {e}", exc_info=True)
        status_msg.content = f"⚠️ Failed to connect: {str(e)}"
        await status_msg.update()
        return False


@cl.on_audio_chunk
async def on_audio_chunk(chunk: cl.InputAudioChunk):
    """Stream audio to OpenAI Realtime"""
    if not REALTIME_AVAILABLE:
        return
    
    rt: RealtimeClient = cl.user_session.get("openai_realtime")
    if not rt or not rt.is_connected():
        return
    
    try:
        await rt.append_input_audio(chunk.data)
    except Exception as e:
        logger.debug(f"Error appending audio: {e}")


@cl.on_audio_end
async def on_audio_end():
    """Handle end of audio input - create response"""
    rt: RealtimeClient = cl.user_session.get("openai_realtime")
    if rt and rt.is_connected():
        try:
            # Force response creation (even if server_vad create_response is true, this is harmless)
            await rt.create_response()
            logger.info("✅ Audio ended → response.create sent")
        except Exception as e:
            logger.error(f"Error creating response: {e}", exc_info=True)


@cl.on_chat_end
@cl.on_stop
async def on_end():
    """Cleanup"""
    rt: RealtimeClient = cl.user_session.get("openai_realtime")
    if rt and rt.is_connected():
        try:
            await rt.disconnect()
        except Exception as e:
            logger.warning(f"Error closing Realtime client: {e}")
    logger.info("Iron Mountain session ended")
