import os
import json
from datetime import datetime, timedelta
from app.utils.supabase_client import supabase, supabase_admin, url, key
from supabase import create_client

def init_db():
    """
    No-op for Supabase as tables are created via SQL Editor.
    Kept for compatibility with app startup.
    """
    pass

def save_user(google_id, channel_id, access_token, refresh_token, expires_in):
    """
    Legacy function signature compatibility.
    In the new flow, we should use save_user_tokens with the Supabase User ID.
    If this is called, it means we are still using the old flow somewhere.
    """
    print("WARNING: save_user (legacy) called. This should be replaced by save_user_tokens.")
    pass 

def save_user_tokens(user_id, google_id, channel_id, access_token, refresh_token, token_expiry, jwt=None):
    """
    Saves tokens to public.user_tokens table.
    user_id: Supabase UUID
    jwt: Optional Supabase JWT for RLS authentication (not needed if using admin client)
    """
    data = {
        "user_id": user_id,
        "google_id": google_id,
        "channel_id": channel_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_expiry": token_expiry,
        "updated_at": datetime.utcnow().isoformat()
    }
    
    # Use Admin Client (Service Role) if available to bypass RLS
    client = supabase_admin if supabase_admin else supabase
    
    # Fallback to JWT impersonation if no admin client and JWT provided
    if not supabase_admin and jwt:
        client = create_client(url, key)
        client.postgrest.auth(jwt)

    # Upsert
    try:
        response = client.table("user_tokens").upsert(data).execute()
        return user_id
    except Exception as e:
        print(f"Error saving user tokens: {e}")
        return None

def get_user(user_id):
    """
    Retrieves user tokens from public.user_tokens.
    """
    # Use Admin Client to bypass RLS for reading
    client = supabase_admin if supabase_admin else supabase
    
    try:
        response = client.table("user_tokens").select("*").eq("user_id", user_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error getting user: {e}")
        return None

def log_reply(user_id, video_id, comment_id, original_comment, ai_suggestion, final_reply):
    """
    Logs a reply to the database for future learning.
    Determines if the reply was edited by comparing ai_suggestion and final_reply.
    """
    is_edited = (ai_suggestion != final_reply) if ai_suggestion else True
    
    data = {
        "user_id": user_id,
        "video_id": video_id,
        "comment_id": comment_id,
        "original_comment": original_comment,
        "ai_suggestion": ai_suggestion,
        "final_reply": final_reply,
        "is_edited": is_edited
    }
    try:
        # Logging usually allows INSERT by authenticated user, but backend might need admin if doing it offline
        # For now, let's try admin if available
        client = supabase_admin if supabase_admin else supabase
        client.table("reply_logs").insert(data).execute()
    except Exception as e:
        print(f"Error logging reply: {e}")

def log_usage(user_id, input_tokens, output_tokens, model_name):
    """
    Logs usage to public.usage_logs.
    """
    data = {
        "user_id": user_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "model_name": model_name
    }
    try:
        client = supabase_admin if supabase_admin else supabase
        client.table("usage_logs").insert(data).execute()
    except Exception as e:
        print(f"Error logging usage: {e}")

def get_few_shot_examples(user_id, limit=3):
    """
    Retrieves recent EDITED replies to use as few-shot examples.
    Only returns examples where the user actually changed the AI's suggestion (or wrote it manually).
    """
    try:
        client = supabase_admin if supabase_admin else supabase
        response = client.table("reply_logs")\
            .select("original_comment, final_reply")\
            .eq("user_id", user_id)\
            .eq("is_edited", True)\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        
        examples = []
        for row in response.data:
            examples.append({
                "input": row['original_comment'],
                "output": row['final_reply']
            })
        return examples
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error fetching examples: {e}")
        return []

def get_daily_reply_count(user_id):
    """
    Counts replies made in the last 24 hours.
    """
    try:
        # Supabase (Postgres) query
        # We can use a filter for created_at
        one_day_ago = (datetime.utcnow() - timedelta(days=1)).isoformat()
        
        client = supabase_admin if supabase_admin else supabase
        response = client.table("reply_logs")\
            .select("id", count="exact")\
            .eq("user_id", user_id)\
            .gte("created_at", one_day_ago)\
            .execute()
            
        return response.count if response.count is not None else 0
    except Exception as e:
        print(f"Error counting daily replies: {e}")
        return 0

def mark_thread_complete(user_id, comment_id, status='completed', jwt=None):
    """
    Marks a thread as complete (or other status) in thread_states table.
    """
    data = {
        "user_id": user_id,
        "comment_id": comment_id,
        "status": status,
        "updated_at": datetime.utcnow().isoformat()
    }
    try:
        client = supabase_admin if supabase_admin else supabase
        
        # If no admin client and JWT provided, authenticate as user
        if not supabase_admin and jwt:
            client = create_client(url, key)
            client.postgrest.auth(jwt)

        # We use upsert to handle re-marking or status changes
        client.table("thread_states").upsert(data, on_conflict="user_id, comment_id").execute()
        return True
    except Exception as e:
        # Suppress "table not found" error
        error_msg = str(e)
        if "PGRST205" in error_msg or "Could not find the table" in error_msg:
            print(f"[WARN] Thread states table missing. Skipping mark complete.")
        else:
            print(f"Error marking thread complete: {e}")
        return False

def delete_thread_state(user_id, comment_id, jwt=None):
    """
    Deletes a thread state (un-marks completion) from thread_states table.
    """
    try:
        client = supabase_admin if supabase_admin else supabase
        
        # If no admin client and JWT provided, authenticate as user
        if not supabase_admin and jwt:
            client = create_client(url, key)
            client.postgrest.auth(jwt)

        response = client.table("thread_states")\
            .delete()\
            .eq("user_id", user_id)\
            .eq("comment_id", comment_id)\
            .execute()
            
        if not response.data:
            print(f"[WARN] No thread state deleted for {comment_id}. Possible RLS issue or ID mismatch.")
            return False
            
        return True
    except Exception as e:
        # Suppress "table not found" error
        error_msg = str(e)
        if "PGRST205" in error_msg or "Could not find the table" in error_msg:
            pass
        else:
            print(f"Error deleting thread state: {e}")
        return False

def get_completed_threads(user_id, jwt=None):
    """
    Returns a list of comment_ids that are marked as completed for the user.
    """
    try:
        client = supabase_admin if supabase_admin else supabase
        
        # If no admin client and JWT provided, authenticate as user
        if not supabase_admin and jwt:
            client = create_client(url, key)
            client.postgrest.auth(jwt)

        response = client.table("thread_states")\
            .select("comment_id")\
            .eq("user_id", user_id)\
            .eq("status", "completed")\
            .execute()
        
        return [row['comment_id'] for row in response.data]
    except Exception as e:
        # Suppress "table not found" error to avoid log spam
        error_msg = str(e)
        if "PGRST205" in error_msg or "Could not find the table" in error_msg:
            pass # Silent fail for missing table
        else:
            print(f"Error getting completed threads: {e}")
        return []


