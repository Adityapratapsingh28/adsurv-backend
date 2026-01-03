"""
Ads Refresh API - Handles refresh button clicks from frontend
Flask Blueprint Version for Unified Deployment
"""
from flask import Blueprint, request, jsonify
import jwt
import uuid
import time
import os
import sys
import threading
from datetime import datetime, timezone
from supabase import create_client, Client
import traceback

# Create Flask Blueprint
ads_refresh_bp = Blueprint('ads_refresh', __name__)

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

# Initialize Supabase
try:
    supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
except Exception as e:
    print(f"❌ Supabase initialization error: {e}")
    supabase = None

# ========== ADS FETCHER IMPORT ==========
FETCHER_AVAILABLE = False
ads_fetcher = None

# Try to import AdsFetcher
try:
    # Try to find ad_fetch_service directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    service_path = os.path.join(project_root, 'ad_fetch_service')
    
    if os.path.exists(service_path):
        if service_path not in sys.path:
            sys.path.insert(0, service_path)
        
        try:
            from ads_fetcher import AdsFetcher
            ads_fetcher = AdsFetcher()
            FETCHER_AVAILABLE = True
            print("✅ AdsFetcher loaded successfully")
        except ImportError as e:
            print(f"❌ Could not import AdsFetcher: {e}")
        except Exception as e:
            print(f"❌ Error initializing AdsFetcher: {e}")
    else:
        print(f"❌ ad_fetch_service directory not found: {service_path}")
except Exception as e:
    print(f"❌ Unexpected error loading AdsFetcher: {e}")

if not FETCHER_AVAILABLE:
    print("🚫 AdsFetcher not available - ads fetching will fail")
# ========== END ADS FETCHER IMPORT ==========

def verify_token(token):
    """Verify JWT token and return user_id"""
    try:
        if not token:
            return None
        
        # Remove 'Bearer ' prefix if present
        if token.startswith('Bearer '):
            token = token[7:]
        
        payload = jwt.decode(token, Config.SECRET_KEY, algorithms=[Config.JWT_ALGORITHM])
        return payload.get('user_id')
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError as e:
        print(f"Invalid token error: {e}")
        return None
    except Exception as e:
        print(f"Token verification error: {e}")
        return None

def get_user_competitors(user_id):
    """Get all competitors for a user"""
    try:
        if not supabase:
            return []
            
        response = supabase.table(Config.DB_TABLES['competitors'])\
            .select('id,name,domain,platform')\
            .eq('user_id', user_id)\
            .eq('is_active', True)\
            .execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error getting competitors: {e}")
        return []

def create_job_record(user_id, job_id, platform="all"):
    """Create a new job record in database"""
    try:
        if not supabase:
            print("❌ Supabase not available")
            return False
            
        competitors = get_user_competitors(user_id)
        
        job_data = {
            'user_id': user_id,
            'job_id': job_id,
            'status': 'pending',
            'platform': platform,
            'total_competitors': len(competitors),
            'ads_fetched': 0,
            'start_time': datetime.now(timezone.utc).isoformat(),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        response = supabase.table('ads_fetch_jobs').insert(job_data).execute()
        
        if response.data:
            print(f"✅ Job record created: {job_id} for user {user_id}")
            return True
        else:
            print(f"❌ Failed to create job record: {response}")
            return False
            
    except Exception as e:
        print(f"Error creating job record: {e}")
        return False

def run_background_fetch(job_id, user_id, platform):
    """Run ads fetching in background thread"""
    try:
        print(f"🚀 Starting background fetch for job {job_id}")
        
        if not supabase:
            print("❌ Supabase not available for job update")
            return
            
        # Update job status to running
        supabase.table('ads_fetch_jobs')\
            .update({
                'status': 'running',
                'updated_at': datetime.now(timezone.utc).isoformat()
            })\
            .eq('job_id', job_id)\
            .execute()
        
        # Run the ads fetcher if available
        success = False
        logs = ""
        ads_count = 0
        
        if FETCHER_AVAILABLE and ads_fetcher:
            success, logs, ads_count = ads_fetcher.run_for_user(user_id, platform)
        else:
            logs = "=== ADS FETCHING DISABLED ===\n"
            logs += f"AdsFetcher not properly configured\n"
            ads_count = 0
        
        # Update job with results
        end_time = datetime.now(timezone.utc).isoformat()
        update_data = {
            'status': 'completed' if success else 'failed',
            'ads_fetched': ads_count,
            'end_time': end_time,
            'updated_at': end_time
        }
        
        # Add logs if available (truncate if too long)
        if logs:
            if len(logs) > 10000:  # Limit to 10KB
                logs = logs[:10000] + "\n...[truncated]"
            update_data['logs'] = logs
        
        # Add error message if failed
        if not success and logs:
            error_msg = logs[:500] if len(logs) > 500 else logs
            update_data['error_message'] = error_msg
        
        # Update database
        supabase.table('ads_fetch_jobs')\
            .update(update_data)\
            .eq('job_id', job_id)\
            .execute()
        
        print(f"✅ Background fetch completed for job {job_id}: {'success' if success else 'failed'}")
        
    except Exception as e:
        print(f"❌ Error in background fetch for job {job_id}: {e}")
        traceback.print_exc()

@ads_refresh_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'ads_refresh',
        'fetcher_available': FETCHER_AVAILABLE,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'supabase_configured': bool(supabase)
    }), 200

@ads_refresh_bp.route('/refresh', methods=['POST'])
def refresh_ads():
    """
    Endpoint called when user clicks refresh button
    Returns: { status, job_id, message, estimated_time }
    """
    # Get authorization header
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'Missing authorization header'}), 401
    
    user_id = verify_token(auth_header)
    
    if not user_id:
        return jsonify({'error': 'Invalid or expired token'}), 401
    
    # Check if fetcher is available
    if not FETCHER_AVAILABLE:
        return jsonify({
            'error': 'Ads fetching is currently disabled',
            'code': 'FETCHER_NOT_AVAILABLE',
            'message': 'The ads fetcher is not properly configured.'
        }), 503
    
    if not supabase:
        return jsonify({
            'error': 'Database not configured'
        }), 500
    
    # Get request data
    try:
        data = request.get_json() or {}
    except:
        data = {}
    
    platform = data.get('platform', 'all')
    force = data.get('force', False)
    
    # Check if user already has a running job
    if not force:
        running_jobs = supabase.table('ads_fetch_jobs')\
            .select('id')\
            .eq('user_id', user_id)\
            .eq('status', 'running')\
            .execute()
        
        if running_jobs.data and len(running_jobs.data) > 0:
            return jsonify({
                'error': 'You already have an ads fetch in progress',
                'code': 'JOB_ALREADY_RUNNING'
            }), 409
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    # Create job record in database
    if not create_job_record(user_id, job_id, platform):
        return jsonify({'error': 'Failed to create job record in database'}), 500
    
    # Get user's competitors count for estimation
    competitors = get_user_competitors(user_id)
    competitors_count = len(competitors)
    
    # Calculate estimated time
    estimated_time = competitors_count * 30
    if platform == 'all':
        estimated_time *= 4
    estimated_time = min(estimated_time, 300)
    
    # Start ads fetching in background thread
    thread = threading.Thread(
        target=run_background_fetch,
        args=(job_id, user_id, platform),
        daemon=True
    )
    thread.start()
    
    # Return immediate response
    response_data = {
        'status': 'started',
        'job_id': job_id,
        'message': f'Started fetching ads from {platform} for {competitors_count} competitors',
        'estimated_time': estimated_time,
        'competitors_count': competitors_count,
        'platform': platform,
        'start_time': datetime.now(timezone.utc).isoformat()
    }
    
    print(f"✅ Started ads fetch job {job_id} for user {user_id}")
    
    return jsonify(response_data), 202

@ads_refresh_bp.route('/user-jobs', methods=['GET'])
def get_user_jobs():
    """Get all jobs for the current user"""
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'Missing authorization header'}), 401
    
    user_id = verify_token(auth_header)
    
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401
    
    if not supabase:
        return jsonify({'error': 'Database not configured'}), 500
    
    try:
        # Get last 20 jobs for the user
        response = supabase.table('ads_fetch_jobs')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('created_at', desc=True)\
            .limit(20)\
            .execute()
        
        # Format jobs for display
        jobs = []
        for job in (response.data if response.data else []):
            formatted_job = job.copy()
            
            # Add status icon
            status = job.get('status', 'unknown')
            icons = {'completed': '✅', 'running': '🔄', 'failed': '❌', 'pending': '⏳'}
            formatted_job['status_icon'] = icons.get(status, '❓')
            
            # Format duration
            duration = job.get('duration_seconds')
            if duration:
                if duration < 60:
                    formatted_job['duration_formatted'] = f"{duration}s"
                elif duration < 3600:
                    minutes = duration // 60
                    seconds = duration % 60
                    formatted_job['duration_formatted'] = f"{minutes}m {seconds}s"
                else:
                    hours = duration // 3600
                    minutes = (duration % 3600) // 60
                    formatted_job['duration_formatted'] = f"{hours}h {minutes}m"
            else:
                formatted_job['duration_formatted'] = 'N/A'
            
            jobs.append(formatted_job)
        
        return jsonify({
            'jobs': jobs,
            'count': len(jobs),
            'has_active_jobs': any(j.get('status') == 'running' for j in jobs),
            'fetcher_available': FETCHER_AVAILABLE
        }), 200
    except Exception as e:
        print(f"Error getting user jobs: {e}")
        return jsonify({'error': str(e)}), 500

@ads_refresh_bp.route('/estimate-time', methods=['POST'])
def estimate_time():
    """Estimate how long ads fetching will take"""
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'Missing authorization header'}), 401
    
    user_id = verify_token(auth_header)
    
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401
    
    try:
        data = request.get_json() or {}
    except:
        data = {}
    
    platform = data.get('platform', 'all')
    
    competitors = get_user_competitors(user_id)
    count = len(competitors)
    
    # Estimation logic
    base_time_per_competitor = 30
    if platform == 'all':
        platforms_count = 4
    else:
        platforms_count = 1
    
    estimated_seconds = count * base_time_per_competitor * platforms_count
    estimated_seconds = min(estimated_seconds, 300)
    
    return jsonify({
        'estimated_seconds': estimated_seconds,
        'estimated_minutes': round(estimated_seconds / 60, 1),
        'competitors_count': count,
        'platform': platform,
        'platforms_count': platforms_count,
        'fetcher_available': FETCHER_AVAILABLE
    }), 200

@ads_refresh_bp.route('/cancel-job/<job_id>', methods=['POST'])
def cancel_job(job_id):
    """Cancel a running job"""
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'Missing authorization header'}), 401
    
    user_id = verify_token(auth_header)
    
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401
    
    if not supabase:
        return jsonify({'error': 'Database not configured'}), 500
    
    try:
        # Verify job belongs to user
        job_response = supabase.table('ads_fetch_jobs')\
            .select('user_id, status')\
            .eq('job_id', job_id)\
            .execute()
        
        if not job_response.data:
            return jsonify({'error': 'Job not found'}), 404
        
        job = job_response.data[0]
        
        if job['user_id'] != user_id:
            return jsonify({'error': 'Unauthorized to cancel this job'}), 403
        
        if job['status'] not in ['pending', 'running']:
            return jsonify({'error': f'Job cannot be cancelled (current status: {job["status"]})'}), 400
        
        # Update job status
        update_response = supabase.table('ads_fetch_jobs')\
            .update({
                'status': 'failed',
                'error_message': 'Cancelled by user',
                'end_time': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            })\
            .eq('job_id', job_id)\
            .execute()
        
        return jsonify({
            'success': True,
            'message': 'Job cancelled successfully',
            'job_id': job_id
        }), 200
        
    except Exception as e:
        print(f"Error cancelling job {job_id}: {e}")
        return jsonify({'error': str(e)}), 500

@ads_refresh_bp.route('/config', methods=['GET'])
def get_ads_fetch_config():
    """Get ads fetching configuration"""
    env_ok = False
    node_version = "Unknown"
    npm_version = "Unknown"
    
    if FETCHER_AVAILABLE and ads_fetcher:
        try:
            test_results = ads_fetcher.test_connection()
            env_ok = test_results.get('environment_ok', False)
            node_version = test_results.get('node_version', 'Unknown')
            npm_version = test_results.get('npm_version', 'Unknown')
        except:
            pass
    
    return jsonify({
        'fetcher_available': FETCHER_AVAILABLE,
        'environment_ok': env_ok,
        'node_version': node_version,
        'npm_version': npm_version,
        'supported_platforms': ['meta', 'google', 'linkedin', 'tiktok', 'all'],
        'mock_mode': False
    }), 200

@ads_refresh_bp.route('/stats', methods=['GET'])
def get_stats():
    """Get statistics about ads fetching"""
    if not supabase:
        return jsonify({'error': 'Database not configured'}), 500
    
    try:
        # Total jobs
        total_jobs = supabase.table('ads_fetch_jobs')\
            .select('id', count='exact')\
            .execute()
        
        # Completed jobs
        completed_jobs = supabase.table('ads_fetch_jobs')\
            .select('id', count='exact')\
            .eq('status', 'completed')\
            .execute()
        
        # Total ads fetched
        ads_response = supabase.table('ads_fetch_jobs')\
            .select('ads_fetched')\
            .eq('status', 'completed')\
            .execute()
        
        total_ads = sum([job['ads_fetched'] for job in ads_response.data]) if ads_response.data else 0
        
        return jsonify({
            'total_jobs': total_jobs.count if total_jobs.count else 0,
            'completed_jobs': completed_jobs.count if completed_jobs.count else 0,
            'success_rate': (completed_jobs.count / total_jobs.count * 100) if total_jobs.count and total_jobs.count > 0 else 0,
            'total_ads_fetched': total_ads,
            'fetcher_available': FETCHER_AVAILABLE
        }), 200
    except Exception as e:
        print(f"Error getting stats: {e}")
        return jsonify({'error': str(e)}), 500

# For backward compatibility
if __name__ == '__main__':
    from flask import Flask
    from flask_cors import CORS
    
    app = Flask(__name__)
    CORS(app)
    app.register_blueprint(ads_refresh_bp, url_prefix='/api/ads')
    app.run(port=5005, debug=True)