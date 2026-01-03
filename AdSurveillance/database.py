"""
Database configuration for AdSurveillance
Simplified for Supabase-only usage
"""
import os
from supabase import create_client, Client
from config import Config

# Initialize Supabase client
def init_supabase():
    """Initialize Supabase client"""
    try:
        if Config.SUPABASE_URL and Config.SUPABASE_KEY:
            supabase_client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
            print(f"✅ Supabase connected: {Config.SUPABASE_URL[:30]}...")
            return supabase_client
        else:
            print("❌ Supabase credentials missing")
            print(f"   SUPABASE_URL: {'Set' if Config.SUPABASE_URL else 'Missing'}")
            print(f"   SUPABASE_KEY: {'Set' if Config.SUPABASE_KEY else 'Missing'}")
            return None
    except Exception as e:
        print(f"❌ Failed to connect to Supabase: {e}")
        return None

# Global Supabase client
supabase: Client = init_supabase()

# Helper functions
def get_supabase():
    """Get Supabase client instance"""
    return supabase

def is_supabase_connected():
    """Check if Supabase is connected"""
    return supabase is not None

# Database table references (for convenience)
def get_table(table_name):
    """Get Supabase table reference"""
    if not supabase:
        raise Exception("Supabase not connected")
    return supabase.table(table_name)

# Specific table references
users_table = lambda: get_table('users')
competitors_table = lambda: get_table('competitors')
daily_metrics_table = lambda: get_table('daily_metrics')
ads_fetch_jobs_table = lambda: get_table('ads_fetch_jobs')