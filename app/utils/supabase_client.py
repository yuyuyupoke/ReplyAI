import os
from supabase import create_client, Client

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("⚠️ WARNING: SUPABASE_URL or SUPABASE_KEY not found in environment variables.")

supabase: Client = create_client(url, key)

service_key: str = os.environ.get("SUPABASE_SERVICE_KEY")
supabase_admin: Client = None

if service_key:
    supabase_admin = create_client(url, service_key)
else:
    print("⚠️ WARNING: SUPABASE_SERVICE_KEY not found. Backend operations requiring admin privileges (bypassing RLS) will fail.")
