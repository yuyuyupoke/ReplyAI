import os
from flask import Flask
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')

if not app.secret_key:
    import secrets
    print("⚠️ WARNING: SECRET_KEY not found in environment. Generating a temporary one. Sessions will be lost on restart.")
    app.secret_key = secrets.token_hex(16)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' # For dev only

# Fix for ngrok (https -> http)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# --- Dev Mode Configuration ---
USE_MOCK_DATA = os.environ.get('USE_MOCK_DATA', 'False').lower() == 'true'

if USE_MOCK_DATA:
    print("⚠️ RUNNING IN DEV MODE WITH MOCK DATA ⚠️")
    # We will import the service in routes or where needed, 
    # but we can set a config here if we want to be cleaner.
    # For now, let's keep the logic similar to original but accessible.
    app.config['USE_MOCK_DATA'] = True
else:
    app.config['USE_MOCK_DATA'] = False

@app.context_processor
def inject_dev_mode():
    return dict(is_dev_mode=app.config['USE_MOCK_DATA'])

from app import routes
from app import database

# Initialize DB on startup (creates tables if not exist)
with app.app_context():
    database.init_db()
