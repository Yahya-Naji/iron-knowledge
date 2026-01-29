# Iron Mountain Demo - Architecture & Connections

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenAI Realtime Bot                       │
│              (Voice Assistant - IronAssist)                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ Calls Tools Directly
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Tool 1:     │ │  Tool 2:     │ │  Tool 3:     │
│  Query       │ │  Check       │ │  Request     │
│  Customer    │ │  Inventory   │ │  Boxes       │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                 │
       │                │                 │
       ▼                ▼                 ▼
┌─────────────────────────────────────────────────────┐
│              Database Layer (db/)                   │
│  - get_customer_account()                           │
│  - get_box_inventory()                              │
│  - update_box_request()                             │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  SQLite Database │
              │  ironmountain.db │
              └─────────────────┘

┌─────────────────────────────────────────────────────┐
│              REST API Routes (api/)                  │
│  - GET /api/customer/{account}                      │
│  - GET /api/inventory/{account}                     │
│  - POST /api/request-boxes                         │
│  - POST /api/send-email                            │
│  - POST /api/send-box-confirmation                 │
└──────────────────────┬──────────────────────────────┘
                       │
                       │ Uses
                       ▼
┌─────────────────────────────────────────────────────┐
│         Database Layer (db/)                        │
│         Email Service (services/email.py)           │
└─────────────────────────────────────────────────────┘
```

## Bot Tools & Connections

### ✅ **Connected Tools (Voice Bot)**

The OpenAI Realtime bot has **3 tools** registered:

1. **`query_customer_account`**
   - **Calls:** `db.queries.get_customer_account()`
   - **Database:** SQLite `ironmountain_customers` table
   - **Status:** ✅ Connected

2. **`check_box_inventory`**
   - **Calls:** `db.queries.get_box_inventory()`
   - **Database:** SQLite `ironmountain_customers` table
   - **Status:** ✅ Connected

3. **`request_empty_boxes`**
   - **Calls:** `db.queries.update_box_request()`
   - **Also Calls:** `services.email.send_box_request_confirmation()`
   - **Database:** SQLite `ironmountain_customers` + `box_requests` tables
   - **Email:** Sends confirmation email to customer
   - **Status:** ✅ Connected (now includes email!)

### 📡 **REST API Routes**

The API routes are **separate** from the bot tools. They can be called directly via HTTP:

- `GET /api/customer/{account_number}` → Uses `db.queries.get_customer_account()`
- `GET /api/inventory/{account_number}` → Uses `db.queries.get_box_inventory()`
- `POST /api/request-boxes` → Uses `db.queries.update_box_request()`
- `POST /api/send-email` → Uses `services.email.send_email()`
- `POST /api/send-box-confirmation` → Uses `services.email.send_box_request_confirmation()`

**Note:** The bot doesn't call these API routes - it calls the database/email functions directly. This is more efficient.

## Data Flow Examples

### Example 1: Customer asks "Check my account IM-10001"

```
User (Voice) 
  → OpenAI Realtime Bot
  → Calls: query_customer_account("IM-10001")
  → db.queries.get_customer_account("IM-10001")
  → SQLite Query
  → Returns customer data
  → Bot speaks response
```

### Example 2: Customer says "I need 5 boxes"

```
User (Voice)
  → OpenAI Realtime Bot
  → Calls: request_empty_boxes("IM-10001", 5)
  → db.queries.update_box_request("IM-10001", 5)
  → Updates SQLite database
  → services.email.send_box_request_confirmation(...)
  → Sends email via SMTP
  → Bot confirms: "Your 5 boxes will be delivered..."
```

### Example 3: API call to get customer

```
HTTP GET /api/customer/IM-10001
  → api.routes.get_customer_api("IM-10001")
  → db.queries.get_customer_account("IM-10001")
  → SQLite Query
  → Returns JSON response
```

## Connection Status

| Component | Status | Connected To |
|-----------|--------|--------------|
| Bot Tool: query_customer_account | ✅ | `db.queries.get_customer_account()` |
| Bot Tool: check_box_inventory | ✅ | `db.queries.get_box_inventory()` |
| Bot Tool: request_empty_boxes | ✅ | `db.queries.update_box_request()` + `services.email.send_box_request_confirmation()` |
| API: /api/customer/{account} | ✅ | `db.queries.get_customer_account()` |
| API: /api/inventory/{account} | ✅ | `db.queries.get_box_inventory()` |
| API: /api/request-boxes | ✅ | `db.queries.update_box_request()` |
| API: /api/send-email | ✅ | `services.email.send_email()` |
| API: /api/send-box-confirmation | ✅ | `services.email.send_box_request_confirmation()` |
| Email Service | ✅ | SMTP (Gmail configured) |
| Database Functions | ✅ | SQLite database |

## Summary

✅ **Everything is connected!**

- The bot knows which database functions to call
- The bot now sends emails when boxes are requested
- API routes are available for external integrations
- All components use the same database layer
- Email service is configured and ready

The bot will automatically:
1. Look up customer accounts
2. Check box inventory
3. Process box requests
4. **Send confirmation emails** (newly added!)
