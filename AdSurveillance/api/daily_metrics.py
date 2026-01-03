"""
Competitors management endpoints for AdSurveillance
Flask Blueprint Version for Unified Deployment
"""
import os
import sys
from flask import Blueprint, request, jsonify
from datetime import datetime
from supabase import create_client, Client
import traceback

# Create Flask Blueprint
competitors_bp = Blueprint('competitors', __name__)

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

# Initialize Supabase
try:
    supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
except Exception as e:
    print(f"❌ Supabase initialization error: {e}")
    supabase = None

# Import auth middleware
try:
    from AdSurveillance.middleware.auth import token_required
    print("✅ Middleware auth imported successfully")
except ImportError as e:
    print(f"❌ Could not import middleware.auth: {e}")
    
    # Fallback to basic auth decorator
    import jwt
    from functools import wraps
    
    SECRET_KEY = os.environ.get("SECRET_KEY", "fallback-secret-key")
    
    def token_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = None
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
            
            if not token:
                return jsonify({'error': 'Token missing'}), 401
            
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
                request.user_id = payload.get('user_id')
            except:
                return jsonify({'error': 'Invalid token'}), 401
            
            return f(*args, **kwargs)
        return decorated

@competitors_bp.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'competitors',
        'timestamp': datetime.now().isoformat(),
        'supabase_configured': bool(supabase)
    })

@competitors_bp.route('/', methods=['GET'])
@token_required
def get_user_competitors():
    """Get all competitors for the logged-in user"""
    try:
        if not supabase:
            return jsonify({'error': 'Database not configured'}), 500
            
        user_id = request.user_id
        print(f"📊 Fetching competitors for user: {user_id}")
        
        # Get competitors from database
        response = supabase.table("competitors")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("is_active", True)\
            .order("created_at", desc=True)\
            .execute()
        
        competitors = response.data if response.data else []
        print(f"✅ Found {len(competitors)} competitors for user {user_id}")
        
        return jsonify({
            'success': True,
            'data': competitors,
            'count': len(competitors),
            'user_id': user_id
        }), 200
        
    except Exception as e:
        print(f"❌ Error getting competitors: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to fetch competitors'
        }), 500

@competitors_bp.route('/', methods=['POST'])
@token_required
def add_competitor():
    """Add a new competitor for the logged-in user"""
    try:
        if not supabase:
            return jsonify({'error': 'Database not configured'}), 500
            
        user_id = request.user_id
        data = request.get_json() or {}
        
        name = data.get('name', '').strip()
        domain = data.get('domain', '').strip()
        industry = data.get('industry', '').strip()
        estimated_monthly_spend = data.get('estimated_monthly_spend', 0)
        
        if not name:
            return jsonify({
                'success': False,
                'error': 'Competitor name is required'
            }), 400
        
        print(f"➕ Adding competitor '{name}' for user {user_id}")
        
        # Check if competitor already exists for this user
        existing_response = supabase.table("competitors")\
            .select("id")\
            .eq("user_id", user_id)\
            .eq("name", name)\
            .eq("is_active", True)\
            .execute()
        
        if existing_response.data and len(existing_response.data) > 0:
            return jsonify({
                'success': False,
                'error': f'Competitor "{name}" already exists',
                'competitor_id': existing_response.data[0]['id']
            }), 409
        
        # Create competitor data
        competitor_data = {
            "user_id": user_id,
            "name": name,
            "domain": domain if domain else None,
            "industry": industry if industry else None,
            "estimated_monthly_spend": float(estimated_monthly_spend) if estimated_monthly_spend else 0.00,
            "is_active": True,
            "ads_count": 0,
            "last_fetch_status": "pending",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        # Insert competitor
        response = supabase.table("competitors")\
            .insert(competitor_data)\
            .execute()
        
        if response.data and len(response.data) > 0:
            print(f"✅ Competitor added: {response.data[0]['id']}")
            return jsonify({
                'success': True,
                'message': 'Competitor added successfully',
                'data': response.data[0]
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to add competitor'
            }), 500
            
    except Exception as e:
        print(f"❌ Error adding competitor: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@competitors_bp.route('/<competitor_id>', methods=['DELETE'])
@token_required
def delete_competitor(competitor_id):
    """Delete a competitor for the logged-in user"""
    try:
        if not supabase:
            return jsonify({'error': 'Database not configured'}), 500
            
        user_id = request.user_id
        
        print(f"🗑️ Deleting competitor {competitor_id} for user {user_id}")
        
        # Verify competitor belongs to user
        competitor_response = supabase.table("competitors")\
            .select("id, name")\
            .eq("id", competitor_id)\
            .eq("user_id", user_id)\
            .eq("is_active", True)\
            .execute()
        
        if not competitor_response.data:
            return jsonify({
                'success': False,
                'error': 'Competitor not found or unauthorized'
            }), 404
        
        competitor_name = competitor_response.data[0].get('name', 'Unknown')
        
        # Soft delete (set is_active to False)
        response = supabase.table("competitors")\
            .update({
                "is_active": False,
                "updated_at": datetime.now().isoformat()
            })\
            .eq("id", competitor_id)\
            .eq("user_id", user_id)\
            .execute()
        
        if response.data:
            print(f"✅ Competitor '{competitor_name}' deleted")
            return jsonify({
                'success': True,
                'message': f'Competitor "{competitor_name}" deleted successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to delete competitor'
            }), 500
        
    except Exception as e:
        print(f"❌ Error deleting competitor: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@competitors_bp.route('/<competitor_id>', methods=['PUT'])
@token_required
def update_competitor(competitor_id):
    """Update a competitor"""
    try:
        if not supabase:
            return jsonify({'error': 'Database not configured'}), 500
            
        user_id = request.user_id
        data = request.get_json() or {}
        
        # Verify competitor belongs to user
        check_response = supabase.table("competitors")\
            .select("id")\
            .eq("id", competitor_id)\
            .eq("user_id", user_id)\
            .eq("is_active", True)\
            .execute()
        
        if not check_response.data:
            return jsonify({
                'success': False,
                'error': 'Competitor not found or unauthorized'
            }), 404
        
        # Prepare update data
        update_data = {}
        if 'name' in data:
            update_data['name'] = data['name'].strip()
        if 'domain' in data:
            update_data['domain'] = data['domain'].strip() if data['domain'] else None
        if 'industry' in data:
            update_data['industry'] = data['industry'].strip() if data['industry'] else None
        if 'estimated_monthly_spend' in data:
            update_data['estimated_monthly_spend'] = float(data['estimated_monthly_spend']) if data['estimated_monthly_spend'] else 0.00
        
        if not update_data:
            return jsonify({
                'success': False,
                'error': 'No valid fields to update'
            }), 400
        
        update_data['updated_at'] = datetime.now().isoformat()
        
        # Update competitor
        response = supabase.table("competitors")\
            .update(update_data)\
            .eq("id", competitor_id)\
            .eq("user_id", user_id)\
            .execute()
        
        if response.data:
            return jsonify({
                'success': True,
                'message': 'Competitor updated successfully',
                'data': response.data[0]
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to update competitor'
            }), 500
            
    except Exception as e:
        print(f"❌ Error updating competitor: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@competitors_bp.route('/stats', methods=['GET'])
@token_required
def get_competitor_stats():
    """Get competitor statistics for the user"""
    try:
        if not supabase:
            return jsonify({'error': 'Database not configured'}), 500
            
        user_id = request.user_id
        
        # Get total active competitors
        total_response = supabase.table("competitors")\
            .select("*", count='exact')\
            .eq("user_id", user_id)\
            .eq("is_active", True)\
            .execute()
        
        total_count = total_response.count if total_response.count else 0
        
        # Get competitors with ads
        with_ads_response = supabase.table("competitors")\
            .select("*", count='exact')\
            .eq("user_id", user_id)\
            .eq("is_active", True)\
            .gt("ads_count", 0)\
            .execute()
        
        with_ads_count = with_ads_response.count if with_ads_response.count else 0
        
        # Get fetch status counts
        status_response = supabase.table("competitors")\
            .select("last_fetch_status")\
            .eq("user_id", user_id)\
            .eq("is_active", True)\
            .execute()
        
        status_counts = {
            'success': 0,
            'failed': 0,
            'pending': 0,
            'no_ads': 0
        }
        
        for comp in (status_response.data or []):
            status = comp.get('last_fetch_status', 'pending')
            if status in status_counts:
                status_counts[status] += 1
            else:
                status_counts['pending'] += 1
        
        # Calculate success rate
        success_rate = round((status_counts['success'] / total_count) * 100, 1) if total_count > 0 else 0
        
        return jsonify({
            'success': True,
            'data': {
                'total_competitors': total_count,
                'competitors_with_ads': with_ads_count,
                'competitors_without_ads': total_count - with_ads_count,
                'fetch_status': status_counts,
                'success_rate': success_rate
            }
        }), 200
        
    except Exception as e:
        print(f"❌ Error getting competitor stats: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@competitors_bp.route('/platforms', methods=['GET'])
@token_required
def get_competitor_platforms():
    """Get platforms for all competitors"""
    try:
        if not supabase:
            return jsonify({'error': 'Database not configured'}), 500
            
        user_id = request.user_id
        
        # Get competitors with platforms
        response = supabase.table("competitors")\
            .select("platform, name")\
            .eq("user_id", user_id)\
            .eq("is_active", True)\
            .execute()
        
        platforms = {}
        for comp in (response.data or []):
            platform = comp.get('platform', 'unknown')
            if platform not in platforms:
                platforms[platform] = []
            platforms[platform].append(comp['name'])
        
        # Calculate platform distribution
        distribution = {}
        for platform, names in platforms.items():
            distribution[platform] = len(names)
        
        return jsonify({
            'success': True,
            'data': {
                'platforms': platforms,
                'distribution': distribution,
                'total_by_platform': distribution
            }
        }), 200
        
    except Exception as e:
        print(f"❌ Error getting competitor platforms: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# For backward compatibility
if __name__ == '__main__':
    from flask import Flask
    from flask_cors import CORS
    
    app = Flask(__name__)
    CORS(app)
    app.register_blueprint(competitors_bp, url_prefix='/api/competitors')
    app.run(port=5009, debug=True)