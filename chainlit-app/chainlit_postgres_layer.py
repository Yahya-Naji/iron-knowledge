"""
PostgreSQL Data Layer for Chainlit
Stores all chat history directly in PostgreSQL
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from typing import Optional, Dict, List
from datetime import datetime
from types import SimpleNamespace
from chainlit.data import BaseDataLayer
from chainlit.logger import logger


class AttrDict(dict):
    """Dict subclass that supports both dict and attribute access
    
    This allows Chainlit to access fields like user.identifier instead of user['identifier'],
    while still being a valid dict for FastAPI validation.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Convert nested dicts to AttrDict recursively
        for key, value in self.items():
            if isinstance(value, dict) and not isinstance(value, AttrDict):
                self[key] = AttrDict(value)
    
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{key}'")
    
    def __setattr__(self, key, value):
        self[key] = value
    
    def to_dict(self):
        """Convert to regular dict - some Chainlit code may call this
        Also handles datetime serialization for JSON compatibility
        """
        result = {}
        for key, value in self.items():
            if isinstance(value, datetime):
                # Convert datetime to ISO format string for JSON serialization
                # Ensure it's always a valid string, never None
                result[key] = value.isoformat() if value else None
            elif isinstance(value, AttrDict):
                # Recursively convert nested AttrDict
                result[key] = value.to_dict()
            elif isinstance(value, list):
                # Convert list items recursively
                result[key] = [
                    item.to_dict() if isinstance(item, AttrDict) else (
                        item.isoformat() if isinstance(item, datetime) and item else item
                    )
                    for item in value
                ]
            elif isinstance(value, dict):
                # Convert nested dicts recursively
                result[key] = {
                    k: (v.isoformat() if isinstance(v, datetime) and v else v)
                    for k, v in value.items()
                }
            else:
                result[key] = value
        return result


class PostgreSQLDataLayer(BaseDataLayer):
    """PostgreSQL-based data layer for Chainlit persistence"""
    
    def __init__(self):
        """Initialize PostgreSQL connection"""
        self.database_uri = os.getenv("CHAINLIT_DATABASE_URI")
        
        if not self.database_uri:
            logger.error("CHAINLIT_DATABASE_URI not configured!")
            raise ValueError("CHAINLIT_DATABASE_URI environment variable required")
        
        # Test connection
        try:
            conn = self._get_connection()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise
    
    def _get_connection(self):
        """Get PostgreSQL database connection"""
        return psycopg2.connect(self.database_uri, cursor_factory=RealDictCursor)
    
    def _extract_title_from_message(self, message_input):
        """Extract clean title text from message input (handles dict, JSON, string formats)
        
        Ensures thread titles are readable strings, not "{}" or empty.
        """
        if not message_input:
            return None
        
        # If input is a dict/JSON object, try to extract text content
        if isinstance(message_input, dict):
            # Try common message content fields
            text = message_input.get("content") or message_input.get("text") or message_input.get("message")
            if text:
                message_input = text
            else:
                # If dict is empty or only has metadata, skip it
                return None
        
        # Convert to string and clean up
        title = str(message_input).strip()
        
        # Skip if it looks like an empty object or invalid
        if not title or title in ["{}", "null", "None"]:
            return None
        
        # Clean whitespace
        title = ' '.join(title.split())
        
        # Remove common conversational prefixes for cleaner titles
        prefixes_to_remove = ["i want to ", "can you ", "please ", "i need ", "help me "]
        title_lower = title.lower()
        for prefix in prefixes_to_remove:
            if title_lower.startswith(prefix):
                title = title[len(prefix):].strip()
                break
        
        # Truncate to 60 chars at word boundary
        if len(title) > 60:
            title_short = title[:57]
            last_space = title_short.rfind(' ')
            if last_space > 40:
                title = title[:last_space] + "..."
            else:
                title = title[:57] + "..."
        
        return title if title and title.strip() else None
    
    def _dict_to_obj(self, data: dict):
        """Convert dict to object with attribute access for threads/steps/elements
        
        NOTE: We use this for threads/steps/elements but NOT for users, because
        FastAPI validation expects users to be dicts or User instances.
        For users, we return plain dicts which RealDictCursor already provides.
        """
        if data is None:
            return None
        if isinstance(data, dict):
            # Convert to AttrDict which supports both attribute access and to_dict() method
            return AttrDict(data)
        return data
    
    async def get_user(self, identifier: str = None, **kwargs) -> Optional[Dict]:
        """Get user by identifier - handles both string and dict inputs
        
        NOTE: Chainlit's internal code sometimes passes the identifier as a dict object
        instead of a string. This can cause AttributeError if we try to access .identifier
        on a dict. This method handles both cases defensively to prevent sidebar errors.
        """
        try:
            # Handle identifier being passed as dict or extracted from kwargs
            if identifier is None:
                # Chainlit might pass identifier in kwargs or as a dict
                identifier = kwargs.get("identifier")
            
            # If identifier is a dict, extract the identifier field
            # This prevents "dict has no attribute 'identifier'" errors in sidebar
            if isinstance(identifier, dict):
                identifier = identifier.get("identifier") or identifier.get("id")
            
            # If still no identifier, try to get from kwargs or use default
            if not identifier:
                identifier = kwargs.get("id") or "guest"
            
            # Ensure identifier is a string
            identifier = str(identifier) if identifier else "guest"
            
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM chainlit_users WHERE identifier = %s",
                (identifier,)
            )
            user = cursor.fetchone()
            conn.close()
            
            if user:
                # Return as AttrDict - supports both dict and attribute access
                # FastAPI accepts dict, and Chainlit can access .identifier attribute
                return AttrDict(user)
            return None
        except Exception as e:
            logger.error(f"Error getting user {identifier}: {e}", exc_info=True)
            return None
    
    async def create_user(self, variables: dict) -> Optional[Dict]:
        """Create new user"""
        try:
            identifier = variables.get("identifier", "guest")
            user_id = variables.get("id", identifier)
            metadata = variables.get("metadata", {})
            
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO chainlit_users (id, identifier, metadata)
                VALUES (%s, %s, %s)
                ON CONFLICT (identifier) DO UPDATE SET metadata = EXCLUDED.metadata
                RETURNING *
                """,
                (user_id, identifier, Json(metadata))
            )
            user = cursor.fetchone()
            conn.commit()
            conn.close()
            
            if user:
                # Return as AttrDict - supports both dict and attribute access
                return AttrDict(user)
            return None
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None
    
    async def get_thread(self, thread_id: str) -> Optional[Dict]:
        """Get thread by ID"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM chainlit_threads WHERE id = %s",
                (thread_id,)
            )
            thread = cursor.fetchone()
            conn.close()
            
            if thread:
                return self._dict_to_obj(dict(thread))
            return None
        except Exception as e:
            logger.error(f"Error getting thread {thread_id}: {e}")
            return None
    
    async def create_thread(self, thread: dict) -> Optional[Dict]:
        """Create new thread"""
        try:
            thread_id = thread.get("id")
            name = thread.get("name")
            user_id = thread.get("userId") or thread.get("user_id")
            metadata = thread.get("metadata", {})
            tags = thread.get("tags", [])
            
            # If name is None, "New Chat", or empty, set a temporary placeholder
            # The actual title will be set when the first message is sent
            if not name or name == "New Chat" or name.strip() == "":
                # Use a placeholder that will be updated later, or generate from metadata if available
                if metadata and isinstance(metadata, dict):
                    # Try to get a title hint from metadata
                    name = metadata.get("title") or metadata.get("name") or None
                if not name:
                    name = None  # Will be set by on_message handler
            
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO chainlit_threads (id, name, user_id, metadata, tags)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET 
                    name = COALESCE(NULLIF(EXCLUDED.name, 'New Chat'), chainlit_threads.name),
                    metadata = EXCLUDED.metadata,
                    tags = EXCLUDED.tags
                RETURNING *
                """,
                (thread_id, name, user_id, Json(metadata), tags)
            )
            created_thread = cursor.fetchone()
            conn.commit()
            conn.close()
            
            if created_thread:
                return self._dict_to_obj(dict(created_thread))
            return None
        except Exception as e:
            logger.error(f"Error creating thread: {e}")
            return None
    
    async def update_thread(self, thread_id: str, **kwargs) -> Optional[Dict]:
        """Update existing thread"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Build dynamic update query
            updates = []
            values = []
            for key, value in kwargs.items():
                if key in ['name', 'user_id', 'metadata', 'tags']:
                    updates.append(f"{key} = %s")
                    values.append(Json(value) if key in ['metadata'] else value)
            
            if not updates:
                return await self.get_thread(thread_id)
            
            values.append(thread_id)
            query = f"UPDATE chainlit_threads SET {', '.join(updates)} WHERE id = %s RETURNING *"
            cursor.execute(query, values)
            updated_thread = cursor.fetchone()
            conn.commit()
            conn.close()
            
            if updated_thread:
                return self._dict_to_obj(dict(updated_thread))
            return None
        except Exception as e:
            logger.error(f"Error updating thread {thread_id}: {e}")
            return None
    
    async def delete_thread(self, thread_id: str):
        """Delete thread"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chainlit_threads WHERE id = %s", (thread_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error deleting thread {thread_id}: {e}")
    
    async def list_threads(self, user_id: str = None, pagination: Optional[Dict] = None, filters: Optional[Dict] = None, **kwargs) -> Dict:
        """List threads for user - handles errors gracefully
        
        This method is called by Chainlit's sidebar to display chat history.
        It handles cases where Chainlit passes user_id as a dict instead of string,
        preventing AttributeError when accessing .identifier on dict objects.
        
        Returns empty list on any error to prevent UI crashes - the sidebar will
        simply show "no conversations" instead of an error.
        """
        try:
            # IMPORTANT: Chainlit may pass userId in pagination (dict or ThreadFilter object)!
            # Check pagination first (both dict and object), then kwargs, then user_id parameter
            if pagination:
                if isinstance(pagination, dict):
                    user_id_from_pagination = pagination.get("userId") or pagination.get("user_id") or pagination.get("identifier")
                else:
                    # It's a ThreadFilter object, use getattr
                    user_id_from_pagination = getattr(pagination, "userId", None) or getattr(pagination, "user_id", None) or getattr(pagination, "identifier", None)
                
                if user_id_from_pagination:
                    user_id = user_id_from_pagination
            
            # Handle user_id being passed as dict, string, object, or extracted from kwargs
            if user_id is None or not isinstance(user_id, str) or "=" in str(user_id):
                # If user_id looks wrong (contains "=" means it might be a stringified dict), reset it
                user_id = kwargs.get("user_id") or kwargs.get("identifier") or kwargs.get("userId")
            
            # Handle user_id being passed as dict (from Chainlit's internal code)
            # This prevents "dict has no attribute 'identifier'" errors that cause sidebar elu errors
            if isinstance(user_id, dict):
                user_id = user_id.get("identifier") or user_id.get("id") or user_id.get("userId") or str(user_id)
            # Handle user_id being passed as object with .identifier attribute
            elif hasattr(user_id, 'identifier'):
                user_id = getattr(user_id, 'identifier', None) or getattr(user_id, 'id', None) or str(user_id)
            
            # Ensure user_id is a string and doesn't look like a dict string
            user_id = str(user_id) if user_id else "guest"
            if "=" in user_id or user_id.startswith("{") or "cursor" in user_id.lower():
                # This looks like it might be a mis-parsed parameter, try to get from pagination
                if pagination and isinstance(pagination, dict):
                    user_id = pagination.get("userId") or pagination.get("user_id") or "guest"
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Handle pagination - might be dict or object
            limit = 35
            offset = 0
            if pagination:
                if isinstance(pagination, dict):
                    limit = pagination.get("first", 35)
                    cursor_val = pagination.get("cursor")
                else:
                    # It's an object, try to get attributes
                    limit = getattr(pagination, "first", 35)
                    cursor_val = getattr(pagination, "cursor", None)
                
                if cursor_val is not None:
                    try:
                        offset = int(cursor_val)
                    except (ValueError, TypeError):
                        offset = 0
            
            # Handle filters - might be dict or ThreadFilter object
            # We don't use filters in the query, but we need to handle it gracefully
            if filters and not isinstance(filters, dict):
                # Convert ThreadFilter object to dict if needed, or ignore
                try:
                    filters = filters.__dict__ if hasattr(filters, "__dict__") else {}
                except:
                    filters = {}
            
            
            # Only return threads with actual messages, prioritize threads with proper names
            cursor.execute(
                """
                SELECT t.* FROM chainlit_threads t
                WHERE t.user_id = %s 
                AND EXISTS (
                    SELECT 1 FROM chainlit_steps s 
                    WHERE s.thread_id = t.id
                )
                ORDER BY 
                    CASE WHEN t.name IS NULL OR t.name = 'New Chat' THEN 1 ELSE 0 END,
                    t.created_at DESC 
                LIMIT %s OFFSET %s
                """,
                (user_id, limit + 1, offset)  # Fetch one extra to check if there's more
            )
            threads = cursor.fetchall()
            conn.close()
            
            
            has_next_page = len(threads) > limit
            # Iron Mountain: Process threads - auto-generate titles and ensure proper formatting
            data = []
            for t in threads[:limit]:
                thread_dict = dict(t)
                
                # If thread name is "New Chat" or empty, try to generate title from first message
                if not thread_dict.get("name") or thread_dict.get("name") == "New Chat":
                    try:
                        # Get first message from steps
                        conn_temp = self._get_connection()
                        cursor_temp = conn_temp.cursor()
                        cursor_temp.execute(
                            """
                            SELECT input FROM chainlit_steps 
                            WHERE thread_id = %s AND input IS NOT NULL AND input != ''
                            ORDER BY created_at ASC 
                            LIMIT 1
                            """,
                            (thread_dict["id"],)
                        )
                        first_step = cursor_temp.fetchone()
                        cursor_temp.close()
                        conn_temp.close()
                        
                        if first_step and first_step.get("input"):
                            # Iron Mountain: Extract clean title from first message (handles dict/JSON/string)
                            title = self._extract_title_from_message(first_step["input"])
                            
                            if title:
                                # Update thread name in database with clean title
                                await self.update_thread(thread_dict["id"], name=title)
                                thread_dict["name"] = title
                    except Exception:
                        # Silent failure - thread will show without title if extraction fails
                        pass
                
                # Iron Mountain: Ensure thread name is never empty or "{}" - use fallback
                if not thread_dict.get("name") or thread_dict.get("name") in ["{}", "null"] or str(thread_dict.get("name", "")).strip() == "":
                    thread_dict["name"] = "Chat"
                
                # Convert to AttrDict for attribute access (required by Chainlit)
                thread_attrdict = AttrDict(thread_dict)
                data.append(thread_attrdict)
            
            # Return in Chainlit's expected format
            result = AttrDict({
                "data": data,
                "pageInfo": {
                    "hasNextPage": bool(has_next_page),
                    "endCursor": str(offset + limit) if has_next_page else None
                }
            })
            
            return result
        except Exception as e:
            logger.error(f"Error listing threads: {e}")
            return AttrDict({"data": [], "pageInfo": {"hasNextPage": False, "endCursor": None}})
    
    async def get_thread_author(self, thread_id: str) -> Optional[str]:
        """Get thread author ID"""
        thread = await self.get_thread(thread_id)
        if thread:
            return thread.get("user_id")
        return None
    
    async def delete_feedback(self, feedback_id: str):
        """Delete feedback"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chainlit_feedback WHERE id = %s", (feedback_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error deleting feedback {feedback_id}: {e}")
    
    async def upsert_feedback(self, feedback: dict) -> Optional[Dict]:
        """Create or update feedback"""
        try:
            feedback_id = feedback.get("id")
            thread_id = feedback.get("threadId") or feedback.get("thread_id")
            step_id = feedback.get("stepId") or feedback.get("step_id")
            value = feedback.get("value")
            comment = feedback.get("comment")
            
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO chainlit_feedback (id, thread_id, step_id, value, comment)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET 
                    value = EXCLUDED.value,
                    comment = EXCLUDED.comment
                RETURNING *
                """,
                (feedback_id, thread_id, step_id, value, comment)
            )
            created_feedback = cursor.fetchone()
            conn.commit()
            conn.close()
            
            if created_feedback:
                return self._dict_to_obj(dict(created_feedback))
            return None
        except Exception as e:
            logger.error(f"Error upserting feedback: {e}")
            return None
    
    async def create_step(self, step: dict) -> Optional[Dict]:
        """Create a new step (message) - with FK check to prevent errors"""
        try:
            step_id = step.get("id")
            thread_id = step.get("threadId") or step.get("thread_id")
            parent_id = step.get("parentId") or step.get("parent_id")
            name = step.get("name")
            step_type = step.get("type")
            input_text = step.get("input")
            output_text = step.get("output")
            metadata = step.get("metadata", {})
            start_time = step.get("start") or step.get("startTime")
            end_time = step.get("end") or step.get("endTime")
            
            # Verify thread exists before creating step (prevent FK errors)
            if thread_id:
                thread = await self.get_thread(thread_id)
                if not thread:
                    # Thread not found - skip step creation
                    return None
            
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO chainlit_steps (id, thread_id, parent_id, name, type, input, output, metadata, start_time, end_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    output = EXCLUDED.output,
                    end_time = EXCLUDED.end_time,
                    metadata = EXCLUDED.metadata
                RETURNING *
                """,
                (step_id, thread_id, parent_id, name, step_type, input_text, output_text, Json(metadata), start_time, end_time)
            )
            created_step = cursor.fetchone()
            conn.commit()
            conn.close()
            
            if created_step:
                return self._dict_to_obj(dict(created_step))
            return None
        except Exception as e:
            # Log but don't fail - just skip this step silently
            return None
    
    async def update_step(self, step: dict) -> Optional[Dict]:
        """Update an existing step"""
        try:
            step_id = step.get("id")
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Build update query
            updates = []
            values = []
            for key in ['output', 'input', 'metadata', 'end_time']:
                if key in step:
                    db_key = key
                    value = step[key]
                    if key == 'metadata':
                        value = Json(value)
                    updates.append(f"{db_key} = %s")
                    values.append(value)
            
            if not updates:
                return None
            
            values.append(step_id)
            query = f"UPDATE chainlit_steps SET {', '.join(updates)} WHERE id = %s RETURNING *"
            cursor.execute(query, values)
            updated_step = cursor.fetchone()
            conn.commit()
            conn.close()
            
            if updated_step:
                return self._dict_to_obj(dict(updated_step))
            return None
        except Exception as e:
            logger.error(f"Error updating step: {e}")
            return None
    
    async def delete_step(self, step_id: str):
        """Delete a step"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chainlit_steps WHERE id = %s", (step_id,))
            conn.commit()
            conn.close()
            logger.info(f"✅ Step deleted: {step_id}")
        except Exception as e:
            logger.error(f"Error deleting step: {e}")
    
    async def get_element(self, thread_id: str, element_id: str) -> Optional[Dict]:
        """Get an element"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM chainlit_elements WHERE thread_id = %s AND id = %s",
                (thread_id, element_id)
            )
            element = cursor.fetchone()
            conn.close()
            if element:
                return self._dict_to_obj(dict(element))
            return None
        except Exception as e:
            logger.error(f"Error getting element: {e}")
            return None
    
    async def create_element(self, element: dict) -> Optional[Dict]:
        """Create an element"""
        try:
            element_id = element.get("id")
            thread_id = element.get("threadId") or element.get("thread_id")
            step_id = element.get("forId") or element.get("step_id")
            name = element.get("name")
            element_type = element.get("type")
            url = element.get("url")
            mime_type = element.get("mime") or element.get("mimeType")
            size = element.get("size")
            metadata = element.get("metadata", {})
            
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO chainlit_elements (id, thread_id, step_id, name, type, url, mime_type, size, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    url = EXCLUDED.url,
                    metadata = EXCLUDED.metadata
                RETURNING *
                """,
                (element_id, thread_id, step_id, name, element_type, url, mime_type, size, Json(metadata))
            )
            created_element = cursor.fetchone()
            conn.commit()
            conn.close()
            
            if created_element:
                return self._dict_to_obj(dict(created_element))
            return None
        except Exception as e:
            logger.error(f"Error creating element: {e}")
            return None
    
    async def delete_element(self, element_id: str):
        """Delete an element"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chainlit_elements WHERE id = %s", (element_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error deleting element: {e}")
    
    async def list_steps(self, thread_id: str, pagination: Optional[Dict] = None, **kwargs) -> Dict:
        """List all steps (messages) for a thread
        
        This is called by Chainlit when resuming a chat to load message history.
        Returns steps ordered by creation time (oldest first) for proper chat display.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Handle pagination - Chainlit may pass as dict or object
            limit = 100
            offset = 0
            if pagination:
                if isinstance(pagination, dict):
                    limit = pagination.get("first", 100)
                    cursor_val = pagination.get("cursor")
                else:
                    # It's an object, try to get attributes
                    limit = getattr(pagination, "first", 100)
                    cursor_val = getattr(pagination, "cursor", None)
                
                if cursor_val is not None:
                    try:
                        offset = int(cursor_val)
                    except (ValueError, TypeError):
                        offset = 0
            
            # Query steps for this thread, ordered by creation time (oldest first)
            cursor.execute(
                """
                SELECT * FROM chainlit_steps 
                WHERE thread_id = %s 
                ORDER BY created_at ASC 
                LIMIT %s OFFSET %s
                """,
                (thread_id, limit + 1, offset)  # Fetch one extra to check if there's more
            )
            steps = cursor.fetchall()
            conn.close()
            
            has_next_page = len(steps) > limit
            
            # Convert to AttrDict for attribute access
            data = []
            for s in steps[:limit]:
                step_dict = dict(s)
                step_attrdict = AttrDict(step_dict)
                data.append(step_attrdict)
            
            # Return in Chainlit's expected format
            return AttrDict({
                "data": data,
                "pageInfo": {
                    "hasNextPage": bool(has_next_page),
                    "endCursor": str(offset + limit) if has_next_page else None
                }
            })
        except Exception as e:
            logger.error(f"Error listing steps for thread {thread_id}: {e}")
            return AttrDict({"data": [], "pageInfo": {"hasNextPage": False, "endCursor": None}})
    
    def build_debug_url(self) -> str:
        """Build debug URL for the data layer"""
        return "postgresql://chainlit-debug"
    
    async def close(self):
        """Close connections (cleanup)"""
        # Connections are closed after each operation


# Export singleton instance
chainlit_data_layer = PostgreSQLDataLayer()

