"""
Iron Mountain MCP Database Server
Provides database query capabilities via MCP protocol
"""
import os
import sys
import asyncio
import json
from typing import Any
from mcp.server import Server
from mcp.types import Tool, TextContent
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Initialize MCP Server
app = Server("ironmountain-database")

# PostgreSQL Configuration
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


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available database tools"""
    return [
        Tool(
            name="get_customer_account",
            description="Retrieve customer account information by account number",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_number": {
                        "type": "string",
                        "description": "Customer account number (e.g., IM-10001)"
                    }
                },
                "required": ["account_number"]
            }
        ),
        Tool(
            name="get_box_inventory",
            description="Get customer's current box inventory (retained and requested)",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_number": {
                        "type": "string",
                        "description": "Customer account number"
                    }
                },
                "required": ["account_number"]
            }
        ),
        Tool(
            name="update_box_request",
            description="Update customer's box request (add to boxes_requested)",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_number": {
                        "type": "string",
                        "description": "Customer account number"
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Number of boxes to request"
                    }
                },
                "required": ["account_number", "quantity"]
            }
        ),
        Tool(
            name="list_all_customers",
            description="List all customer accounts in the system",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls"""
    
    conn = get_db_connection()
    if not conn:
        return [TextContent(
            type="text",
            text=json.dumps({
                "status": "error",
                "message": "Failed to connect to database"
            })
        )]
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        if name == "get_customer_account":
            account_number = arguments["account_number"]
            
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
                WHERE account_number = %s
                """,
                (account_number,)
            )
            
            result = cursor.fetchone()
            
            if result:
                # Convert datetime to string
                if result['last_request_date']:
                    result['last_request_date'] = result['last_request_date'].isoformat()
                if result['created_at']:
                    result['created_at'] = result['created_at'].isoformat()
                
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "status": "success",
                        "data": dict(result)
                    })
                )]
            else:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "status": "not_found",
                        "message": f"No customer found with account number: {account_number}"
                    })
                )]
        
        elif name == "get_box_inventory":
            account_number = arguments["account_number"]
            
            cursor.execute(
                """
                SELECT 
                    account_number,
                    customer_name,
                    boxes_retained,
                    boxes_requested
                FROM ironmountain_customers
                WHERE account_number = %s
                """,
                (account_number,)
            )
            
            result = cursor.fetchone()
            
            if result:
                total_boxes = result['boxes_retained'] + result['boxes_requested']
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "status": "success",
                        "data": {
                            "account_number": result['account_number'],
                            "customer_name": result['customer_name'],
                            "boxes_retained": result['boxes_retained'],
                            "boxes_requested": result['boxes_requested'],
                            "total_boxes": total_boxes
                        }
                    })
                )]
            else:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "status": "not_found",
                        "message": f"No customer found with account number: {account_number}"
                    })
                )]
        
        elif name == "update_box_request":
            account_number = arguments["account_number"]
            quantity = arguments["quantity"]
            
            # First, get current values
            cursor.execute(
                "SELECT boxes_requested FROM ironmountain_customers WHERE account_number = %s",
                (account_number,)
            )
            
            result = cursor.fetchone()
            if not result:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "status": "not_found",
                        "message": f"No customer found with account number: {account_number}"
                    })
                )]
            
            new_requested = result['boxes_requested'] + quantity
            
            # Update the database
            cursor.execute(
                """
                UPDATE ironmountain_customers
                SET boxes_requested = %s,
                    last_request_date = %s
                WHERE account_number = %s
                RETURNING boxes_retained, boxes_requested
                """,
                (new_requested, datetime.now(), account_number)
            )
            
            updated = cursor.fetchone()
            conn.commit()
            
            return [TextContent(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "message": f"Updated box request for {account_number}",
                    "data": {
                        "account_number": account_number,
                        "boxes_retained": updated['boxes_retained'],
                        "boxes_requested": updated['boxes_requested'],
                        "quantity_added": quantity
                    }
                })
            )]
        
        elif name == "list_all_customers":
            cursor.execute(
                """
                SELECT 
                    account_number,
                    customer_name,
                    company_name,
                    boxes_retained,
                    boxes_requested
                FROM ironmountain_customers
                ORDER BY account_number
                """
            )
            
            results = cursor.fetchall()
            
            customers = [dict(row) for row in results]
            
            return [TextContent(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "count": len(customers),
                    "data": customers
                })
            )]
        
        else:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "status": "error",
                    "message": f"Unknown tool: {name}"
                })
            )]
    
    except Exception as e:
        print(f"❌ Database error: {e}", file=sys.stderr)
        return [TextContent(
            type="text",
            text=json.dumps({
                "status": "error",
                "message": f"Database error: {str(e)}"
            })
        )]
    
    finally:
        cursor.close()
        conn.close()


async def main():
    """Run MCP server"""
    from mcp.server.stdio import stdio_server
    
    print("🚀 Starting Iron Mountain Database MCP Server...", file=sys.stderr)
    print(f"🗄️ PostgreSQL: {POSTGRES_USER}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}", file=sys.stderr)
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())

