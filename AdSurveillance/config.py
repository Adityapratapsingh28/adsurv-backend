"""
Unified configuration for AdSurveillance
For Railway/Production Deployment
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ========== FLASK CONFIG ==========
    DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-super-secret-jwt-key-change-in-production')
    
    # ========== SUPABASE CONFIGURATION ==========
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY', SUPABASE_KEY)  # Fallback
    
    # ========== JWT CONFIGURATION ==========
    JWT_ALGORITHM = 'HS256'
    JWT_EXPIRATION_DAYS = 30
    
    # ========== ADS FETCHING CONFIG ==========
    # Path to your TypeScript ads fetching module
    ADS_FETCH_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src')
    
    # Node.js command to run (default: 'npm start')
    NODE_SCRIPT = os.getenv('NODE_SCRIPT', 'npm start')
    
    # Timeout for ads fetching in seconds (default: 5 minutes)
    ADS_FETCH_TIMEOUT = int(os.getenv('ADS_FETCH_TIMEOUT', 300))
    
    # ========== CORS CONFIG ==========
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')
    CORS_SUPPORTS_CREDENTIALS = True
    
    # ========== DATABASE TABLES ==========
    DB_TABLES = {
        'users': 'users',
        'competitors': 'competitors',
        'advertisements': 'advertisements',
        'daily_metrics': 'daily_metrics',
        'summary_metrics': 'summary_metrics',
        'data_source_logs': 'data_source_logs',
        'ads_fetch_jobs': 'ads_fetch_jobs'
    }
    
    # ========== API VERSION ==========
    API_VERSION = 'v1'
    API_PREFIX = f'/api/{API_VERSION}'
    
    # ========== ENVIRONMENT ==========
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
    IS_PRODUCTION = ENVIRONMENT == 'production'
    IS_DEVELOPMENT = ENVIRONMENT == 'development'

# Create global instance
config = Config()