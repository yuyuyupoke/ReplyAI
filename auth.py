import os
import google.oauth2.credentials
import google_auth_oauthlib.flow
from google.auth.transport.requests import Request

SCOPES = [
    'https://www.googleapis.com/auth/youtube.force-ssl',
    'https://www.googleapis.com/auth/yt-analytics.readonly'
]
CLIENT_SECRET_FILE = os.environ.get('CLIENT_SECRET_FILE', 'client_secret.json')

import json

def credentials_to_dict(credentials):
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

def get_client_config():
    # First try to get from environment variable (for cloud deployment)
    env_secret = os.environ.get('GOOGLE_CLIENT_SECRET_JSON')
    if env_secret:
        try:
            data = json.loads(env_secret)
            return data.get('web') or data.get('installed')
        except json.JSONDecodeError:
            print("Error decoding GOOGLE_CLIENT_SECRET_JSON")
            pass
            
    # Fallback to file (for local development)
    if os.path.exists(CLIENT_SECRET_FILE):
        with open(CLIENT_SECRET_FILE, 'r') as f:
            data = json.load(f)
            return data.get('web') or data.get('installed')
    
    raise FileNotFoundError(f"Client secret not found. Set GOOGLE_CLIENT_SECRET_JSON env var or create {CLIENT_SECRET_FILE}")

def get_flow(redirect_uri):
    # First try to get from environment variable
    env_secret = os.environ.get('GOOGLE_CLIENT_SECRET_JSON')
    if env_secret:
        try:
            client_config = json.loads(env_secret)
            flow = google_auth_oauthlib.flow.Flow.from_client_config(
                client_config, scopes=SCOPES)
            flow.redirect_uri = redirect_uri
            return flow
        except json.JSONDecodeError:
            print("Error decoding GOOGLE_CLIENT_SECRET_JSON")
            pass

    # Fallback to file
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE, scopes=SCOPES)
    flow.redirect_uri = redirect_uri
    return flow

from datetime import datetime

def get_credentials_from_user(user):
    client_config = get_client_config()
    
    expiry = None
    if user['expires_in']:
        try:
            expiry = datetime.fromisoformat(user['expires_in'])
        except ValueError:
            pass

    creds = google.oauth2.credentials.Credentials(
        token=user['access_token'],
        refresh_token=user['refresh_token'],
        token_uri='https://oauth2.googleapis.com/token',
        client_id=client_config['client_id'],
        client_secret=client_config['client_secret'],
        scopes=SCOPES,
        expiry=expiry
    )
    return creds
