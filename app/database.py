import sqlite3
import os
import datetime

# Try to import psycopg2 for PostgreSQL support
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

DB_NAME = 'sakusaku.db'

# Check if we are running on Render (or any env with DATABASE_URL)
DATABASE_URL = os.environ.get('DATABASE_URL')
IS_POSTGRES = DATABASE_URL is not None

def get_db_connection():
    if IS_POSTGRES:
        if not psycopg2:
            raise ImportError("psycopg2 is required for PostgreSQL connections but not installed.")
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        return conn

def execute_query(conn, query, params=(), fetch_one=False, fetch_all=False, commit=False):
    """
    Wrapper to execute queries on either SQLite or PostgreSQL.
    Handles placeholder differences (? vs %s).
    """
    if IS_POSTGRES:
        # PostgreSQL uses %s for placeholders
        query = query.replace('?', '%s')
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            
            if fetch_one:
                return cur.fetchone()
            if fetch_all:
                return cur.fetchall()
            if commit:
                conn.commit()
                # For INSERT ... RETURNING, we might want to fetch
                if 'RETURNING' in query.upper():
                    return cur.fetchone()
                return cur
    else:
        # SQLite uses ? for placeholders
        cur = conn.cursor()
        cur.execute(query, params)
        
        if fetch_one:
            result = cur.fetchone()
            return result
        if fetch_all:
            result = cur.fetchall()
            return result
        if commit:
            conn.commit()
            if 'RETURNING' in query.upper():
                 # SQLite doesn't support RETURNING in older versions, but let's assume standard behavior
                 # Actually, standard SQLite doesn't return from execute.
                 # We handle ID retrieval separately for SQLite usually.
                 pass
            return cur

def init_db():
    conn = get_db_connection()
    
    # Define table schemas based on DB type
    if IS_POSTGRES:
        # PostgreSQL
        user_table = '''
            CREATE TABLE IF NOT EXISTS "user" (
                id SERIAL PRIMARY KEY,
                google_id TEXT UNIQUE NOT NULL,
                channel_id TEXT,
                access_token TEXT,
                refresh_token TEXT,
                expires_in TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''
        usage_logs_table = '''
            CREATE TABLE IF NOT EXISTS usage_logs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES "user" (id),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                input_tokens INTEGER,
                output_tokens INTEGER,
                model_name TEXT
            )
        '''
        reply_logs_table = '''
            CREATE TABLE IF NOT EXISTS reply_logs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES "user" (id),
                video_id TEXT,
                comment_id TEXT,
                original_comment TEXT,
                ai_suggestion TEXT,
                final_reply TEXT,
                is_edited BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''
    else:
        # SQLite
        user_table = '''
            CREATE TABLE IF NOT EXISTS user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                google_id TEXT UNIQUE NOT NULL,
                channel_id TEXT,
                access_token TEXT,
                refresh_token TEXT,
                expires_in TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''
        usage_logs_table = '''
            CREATE TABLE IF NOT EXISTS usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                input_tokens INTEGER,
                output_tokens INTEGER,
                model_name TEXT,
                FOREIGN KEY (user_id) REFERENCES user (id)
            )
        '''
        reply_logs_table = '''
            CREATE TABLE IF NOT EXISTS reply_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                video_id TEXT,
                comment_id TEXT,
                original_comment TEXT,
                ai_suggestion TEXT,
                final_reply TEXT,
                is_edited BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES user (id)
            )
        '''

    try:
        if IS_POSTGRES:
            with conn.cursor() as cur:
                cur.execute(user_table)
                cur.execute(usage_logs_table)
                cur.execute(reply_logs_table)
            conn.commit()
        else:
            conn.execute(user_table)
            conn.execute(usage_logs_table)
            conn.execute(reply_logs_table)
            conn.commit()
            
        print(f"Database initialized ({'PostgreSQL' if IS_POSTGRES else 'SQLite'}).")
    finally:
        conn.close()

def save_user(google_id, channel_id, access_token, refresh_token, expires_in):
    conn = get_db_connection()
    try:
        # Upsert query
        query = '''
            INSERT INTO "user" (google_id, channel_id, access_token, refresh_token, expires_in)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(google_id) DO UPDATE SET
                access_token = excluded.access_token,
                refresh_token = excluded.refresh_token,
                expires_in = excluded.expires_in
        '''
        
        # Note: "user" is a reserved word in Postgres, so we quote it. 
        # SQLite handles quotes fine too.
        
        execute_query(conn, query, (google_id, channel_id, access_token, refresh_token, expires_in), commit=True)
        
        # Get the user ID
        # For Postgres we could have used RETURNING id in the INSERT, but for compatibility let's select.
        select_query = 'SELECT id FROM "user" WHERE google_id = ?'
        result = execute_query(conn, select_query, (google_id,), fetch_one=True)
        
        return result['id']
    finally:
        conn.close()

def get_user(user_id):
    conn = get_db_connection()
    try:
        query = 'SELECT * FROM "user" WHERE id = ?'
        return execute_query(conn, query, (user_id,), fetch_one=True)
    finally:
        conn.close()

def log_usage(user_id, input_tokens, output_tokens, model_name):
    conn = get_db_connection()
    try:
        query = '''
            INSERT INTO usage_logs (user_id, input_tokens, output_tokens, model_name)
            VALUES (?, ?, ?, ?)
        '''
        execute_query(conn, query, (user_id, input_tokens, output_tokens, model_name), commit=True)
    finally:
        conn.close()

def log_reply(user_id, video_id, comment_id, original_comment, ai_suggestion, final_reply):
    """
    Logs a reply to the database for future learning.
    Determines if the reply was edited by comparing ai_suggestion and final_reply.
    """
    is_edited = (ai_suggestion != final_reply) if ai_suggestion else True
    
    conn = get_db_connection()
    try:
        query = '''
            INSERT INTO reply_logs (user_id, video_id, comment_id, original_comment, ai_suggestion, final_reply, is_edited)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        '''
        execute_query(conn, query, (user_id, video_id, comment_id, original_comment, ai_suggestion, final_reply, is_edited), commit=True)
    finally:
        conn.close()

def get_few_shot_examples(user_id, limit=3):
    """
    Retrieves recent EDITED replies to use as few-shot examples.
    Only returns examples where the user actually changed the AI's suggestion (or wrote it manually).
    """
    conn = get_db_connection()
    try:
        query = '''
            SELECT original_comment, final_reply 
            FROM reply_logs 
            WHERE user_id = ? AND is_edited = 1
            ORDER BY created_at DESC 
            LIMIT ?
        '''
        # SQLite stores booleans as 1/0, Postgres as true/false.
        # However, in SQL query '1' usually works for Postgres boolean too, or 'TRUE'.
        # Let's try to be safe.
        if IS_POSTGRES:
             query = query.replace('is_edited = 1', 'is_edited = TRUE')

        rows = execute_query(conn, query, (user_id, limit), fetch_all=True)
        
        examples = []
        if rows:
            for row in rows:
                examples.append({
                    'comment': row['original_comment'],
                    'reply': row['final_reply']
                })
        return examples
    finally:
        conn.close()

def get_daily_reply_count(user_id):
    conn = get_db_connection()
    try:
        # SQLite: datetime('now', '-1 day')
        # Postgres: NOW() - INTERVAL '1 day'
        if IS_POSTGRES:
            query = '''
                SELECT COUNT(*) as count FROM reply_logs 
                WHERE user_id = ? AND created_at > NOW() - INTERVAL '1 day'
            '''
        else:
            query = '''
                SELECT COUNT(*) as count FROM reply_logs 
                WHERE user_id = ? AND created_at > datetime('now', '-1 day')
            '''
            
        result = execute_query(conn, query, (user_id,), fetch_one=True)
        # result is a dict or Row
        return result['count'] if result else 0
    finally:
        conn.close()

if __name__ == '__main__':
    init_db()
