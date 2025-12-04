import sqlite3
import os

DB_NAME = 'sakusaku.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # User table (Reverted to 'user' singular)
    c.execute('''
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            google_id TEXT UNIQUE NOT NULL,
            channel_id TEXT,
            access_token TEXT,
            refresh_token TEXT,
            expires_in TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Usage logs table
    c.execute('''
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            input_tokens INTEGER,
            output_tokens INTEGER,
            model_name TEXT,
            FOREIGN KEY (user_id) REFERENCES user (id)
        )
    ''')

    # Reply logs table for AI Personalization (Few-Shot Learning)
    c.execute('''
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
    ''')
    
    conn.commit()
    conn.close()
    print(f"Database {DB_NAME} initialized.")

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def save_user(google_id, channel_id, access_token, refresh_token, expires_in):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO user (google_id, channel_id, access_token, refresh_token, expires_in)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(google_id) DO UPDATE SET
                access_token = excluded.access_token,
                refresh_token = excluded.refresh_token,
                expires_in = excluded.expires_in
        ''', (google_id, channel_id, access_token, refresh_token, expires_in))
        conn.commit()
        
        # Get the user ID
        c.execute('SELECT id FROM user WHERE google_id = ?', (google_id,))
        user_id = c.fetchone()['id']
        return user_id
    finally:
        conn.close()

def get_user(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    user = c.execute('SELECT * FROM user WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return user

def log_usage(user_id, input_tokens, output_tokens, model_name):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO usage_logs (user_id, input_tokens, output_tokens, model_name)
        VALUES (?, ?, ?, ?)
    ''', (user_id, input_tokens, output_tokens, model_name))
    conn.commit()
    conn.close()

def log_reply(user_id, video_id, comment_id, original_comment, ai_suggestion, final_reply):
    """
    Logs a reply to the database for future learning.
    Determines if the reply was edited by comparing ai_suggestion and final_reply.
    """
    is_edited = (ai_suggestion != final_reply) if ai_suggestion else True
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO reply_logs (user_id, video_id, comment_id, original_comment, ai_suggestion, final_reply, is_edited)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, video_id, comment_id, original_comment, ai_suggestion, final_reply, is_edited))
    conn.commit()
    conn.close()

def get_few_shot_examples(user_id, limit=3):
    """
    Retrieves recent EDITED replies to use as few-shot examples.
    Only returns examples where the user actually changed the AI's suggestion (or wrote it manually).
    """
    conn = get_db_connection()
    c = conn.cursor()
    rows = c.execute('''
        SELECT original_comment, final_reply 
        FROM reply_logs 
        WHERE user_id = ? AND is_edited = 1
        ORDER BY created_at DESC 
        LIMIT ?
    ''', (user_id, limit)).fetchall()
    conn.close()
    
    examples = []
    for row in rows:
        examples.append({
            'comment': row['original_comment'],
            'reply': row['final_reply']
        })
    return examples

def get_daily_reply_count(user_id):
    conn = get_db_connection()
    # Count replies in the last 24 hours
    count = conn.execute('''
        SELECT COUNT(*) FROM reply_logs 
        WHERE user_id = ? AND created_at > datetime('now', '-1 day')
    ''', (user_id,)).fetchone()[0]
    conn.close()
    return count

if __name__ == '__main__':
    init_db()

