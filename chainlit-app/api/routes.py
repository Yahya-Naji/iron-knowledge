"""
REST API Routes for Iron Mountain
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from chainlit.logger import logger
from db.queries import get_customer_account, get_box_inventory, update_box_request
from services.email import send_email, send_box_request_confirmation, send_box_request_notification

# Create API router
router = APIRouter(prefix="/api", tags=["ironmountain"])


@router.get("/customer/{account_number}")
async def get_customer_api(account_number: str):
    """Get customer account details"""
    try:
        customer = get_customer_account(account_number)
        if customer:
            return JSONResponse({
                "status": "success",
                "data": customer
            })
        return JSONResponse({
            "status": "error",
            "message": "Customer not found"
        }, status_code=404)
    except Exception as e:
        logger.error(f"Error in get_customer_api: {e}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


@router.get("/inventory/{account_number}")
async def get_inventory_api(account_number: str):
    """Get customer box inventory"""
    try:
        inventory = get_box_inventory(account_number)
        if inventory:
            return JSONResponse({
                "status": "success",
                "data": inventory
            })
        return JSONResponse({
            "status": "error",
            "message": "Customer not found"
        }, status_code=404)
    except Exception as e:
        logger.error(f"Error in get_inventory_api: {e}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


@router.post("/request-boxes")
async def request_boxes_api(request: Request):
    """Request boxes for a customer"""
    try:
        data = await request.json()
        account_number = data.get("account_number")
        quantity = data.get("quantity")
        
        if not account_number or not quantity:
            return JSONResponse({
                "status": "error",
                "message": "account_number and quantity are required"
            }, status_code=400)
        
        # Verify customer exists
        customer = get_customer_account(account_number)
        if not customer:
            return JSONResponse({
                "status": "error",
                "message": "Customer not found"
            }, status_code=404)
        
        # Update box request
        success = update_box_request(account_number, quantity)
        if success:
            # Get updated inventory
            inventory = get_box_inventory(account_number)
            return JSONResponse({
                "status": "success",
                "message": f"Request for {quantity} boxes processed",
                "data": inventory
            })
        else:
            return JSONResponse({
                "status": "error",
                "message": "Failed to process request"
            }, status_code=500)
    except Exception as e:
        logger.error(f"Error in request-boxes API: {e}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


@router.post("/send-email")
async def send_email_api(request: Request):
    """Send email using SMTP"""
    try:
        data = await request.json()
        to_email = data.get("to_email")
        subject = data.get("subject")
        body_html = data.get("body_html")
        body_text = data.get("body_text")
        cc = data.get("cc", [])
        bcc = data.get("bcc", [])
        
        if not to_email or not subject or not body_html:
            return JSONResponse({
                "status": "error",
                "message": "to_email, subject, and body_html are required"
            }, status_code=400)
        
        success = send_email(
            to_email=to_email,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            cc=cc if isinstance(cc, list) else [],
            bcc=bcc if isinstance(bcc, list) else []
        )
        
        if success:
            return JSONResponse({
                "status": "success",
                "message": f"Email sent successfully to {to_email}"
            })
        else:
            return JSONResponse({
                "status": "error",
                "message": "Failed to send email. Check SMTP configuration and logs."
            }, status_code=500)
    except Exception as e:
        logger.error(f"Error in send-email API: {e}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


@router.post("/send-box-confirmation")
async def send_box_confirmation_api(request: Request):
    """Send box request confirmation email to customer"""
    try:
        data = await request.json()
        customer_email = data.get("customer_email")
        customer_name = data.get("customer_name")
        account_number = data.get("account_number")
        quantity = data.get("quantity")
        address = data.get("address")
        
        if not all([customer_email, customer_name, account_number, quantity, address]):
            return JSONResponse({
                "status": "error",
                "message": "customer_email, customer_name, account_number, quantity, and address are required"
            }, status_code=400)
        
        success = send_box_request_confirmation(
            customer_email=customer_email,
            customer_name=customer_name,
            account_number=account_number,
            quantity=quantity,
            address=address
        )
        
        if success:
            return JSONResponse({
                "status": "success",
                "message": f"Confirmation email sent to {customer_email}"
            })
        else:
            return JSONResponse({
                "status": "error",
                "message": "Failed to send confirmation email. Check SMTP configuration and logs."
            }, status_code=500)
    except Exception as e:
        logger.error(f"Error in send-box-confirmation API: {e}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


@router.post("/send-box-notification")
async def send_box_notification_api(request: Request):
    """Send internal notification email for box request"""
    try:
        data = await request.json()
        internal_email = data.get("internal_email")
        customer_name = data.get("customer_name")
        account_number = data.get("account_number")
        quantity = data.get("quantity")
        address = data.get("address")
        
        if not all([internal_email, customer_name, account_number, quantity, address]):
            return JSONResponse({
                "status": "error",
                "message": "internal_email, customer_name, account_number, quantity, and address are required"
            }, status_code=400)
        
        success = send_box_request_notification(
            internal_email=internal_email,
            customer_name=customer_name,
            account_number=account_number,
            quantity=quantity,
            address=address
        )
        
        if success:
            return JSONResponse({
                "status": "success",
                "message": f"Notification email sent to {internal_email}"
            })
        else:
            return JSONResponse({
                "status": "error",
                "message": "Failed to send notification email. Check SMTP configuration and logs."
            }, status_code=500)
    except Exception as e:
        logger.error(f"Error in send-box-notification API: {e}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse({
        "status": "ok",
        "message": "Iron Mountain API is running"
    })
