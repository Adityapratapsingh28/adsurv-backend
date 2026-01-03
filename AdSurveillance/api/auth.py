"""
Authentication API for AdSurveillance - Flask Blueprint Version
"""
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import datetime
import jwt
import os

# Create Flask Blueprint
auth_bp = Blueprint('auth', __name__)

# Load secret key from environment or generate one
SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)

# Initialize Supabase client
supabase_url = os.environ.get('SUPABASE_URL')
supabase_key = os.environ.get('SUPABASE_KEY')

if supabase_url and supabase_key:
    supabase: Client = create_client(supabase_url, supabase_key)
else:
    print("⚠️  Warning: Supabase credentials not found. Some features may not work.")
    supabase = None

@auth_bp.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'auth',
        'timestamp': datetime.datetime.now().isoformat()
    })

@auth_bp.route('/verify', methods=['POST'])
def verify():
    """Verify JWT token"""
    try:
        if not supabase:
            return jsonify({
                'success': False,
                'error': 'Database not configured'
            }), 500
            
        data = request.get_json()
        token = data.get('token', '')
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'Token is required'
            }), 400
        
        # Decode token
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        
        # Get user from database
        user_response = (
            supabase.table('users')
            .select('*')
            .eq("user_id", payload['user_id'])
            .execute()
        )
        
        if not user_response.data:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        user_data = user_response.data[0]
        
        return jsonify({
            'success': True,
            'user': {
                'user_id': user_data['user_id'],
                'name': user_data['name'],
                'email': user_data['email'],
                'onboarding_completed': user_data.get('onboarding_completed', False)
            }
        }), 200
        
    except jwt.ExpiredSignatureError:
        return jsonify({
            'success': False,
            'error': 'Token has expired'
        }), 401
    except jwt.InvalidTokenError as e:
        return jsonify({
            'success': False,
            'error': f'Invalid token: {str(e)}'
        }), 401
    except Exception as e:
        print(f"Error in verify: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'Token verification failed'
        }), 500

@auth_bp.route('/signup', methods=['POST'])
@cross_origin()
def signup():
    """User registration"""
    try:
        if not supabase:
            return jsonify({
                'success': False,
                'error': 'Database not configured'
            }), 500
            
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': "No data provided"
            }), 400
        
        name = data.get("name")
        email = data.get("email")
        password = data.get("password")
        confirm_password = data.get("confirmPassword")

        # Validate all fields are present
        if not name or not email or not password or not confirm_password:
            return jsonify({
                'success': False,
                'error': 'Fill all the details before proceeding'
            }), 400
        
        # Validate password match
        if password != confirm_password:
            return jsonify({
                'success': False,
                'error': 'Passwords do not match'
            }), 400
        
        # Validate password length
        if len(password) < 8:
            return jsonify({
                'success': False,
                'error': 'Password must be at least 8 characters long'
            }), 400
        
        # Convert email to lowercase for consistency
        email = email.lower().strip()
        
        # Check if user already exists
        existing_user = (
            supabase.table('users')
            .select('*')
            .eq("email", email)
            .execute()
        )

        if existing_user.data:
            return jsonify({
                'success': False,
                'error': 'Email already exists'
            }), 409
        
        # Hash the password
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        
        # Insert new user into database with onboarding_completed flag
        response = (
            supabase.table("users")
            .insert({
                "name": name,
                "email": email,
                "password_hash": hashed_password,
                "onboarding_completed": False
            })
            .execute()
        )

        if response.data:
            user_data = response.data[0]

            # Create JWT token
            token = jwt.encode(
                {
                    'user_id': user_data['user_id'],
                    'email': user_data['email'],
                    'name': user_data['name'],
                    'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30)
                },
                SECRET_KEY,
                algorithm="HS256"
            )
            
            return jsonify({
                'success': True,
                'message': "Account Created Successfully",
                'token': token,
                'user': {
                    'user_id': user_data['user_id'],
                    'name': user_data['name'],
                    'email': user_data['email'],
                    'onboarding_completed': False
                }
            }), 201
        else:
            raise Exception("Failed to create user")

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': "Invalid Data Format"
        }), 400

    except KeyError as e:
        return jsonify({
            'success': False,
            'error': f'Missing key: {str(e)}'
        }), 400
        
    except Exception as e:
        print(f"Error in signup: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'An internal server error occurred'
        }), 500

@auth_bp.route('/complete-onboarding', methods=['POST'])
def complete_onboarding():
    """Complete user onboarding"""
    try:
        if not supabase:
            return jsonify({
                'success': False,
                'error': 'Database not configured'
            }), 500
            
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                'success': False,
                'error': 'No authorization token provided'
            }), 401
        
        token = auth_header.split(' ')[1]
        
        # Verify token
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            user_id = payload['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({
                'success': False,
                'error': 'Token has expired'
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                'success': False,
                'error': 'Invalid token'
            }), 401
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': "No data provided"
            }), 400
        
        business_type = data.get("businessType")
        industry = data.get("industry")
        goals = data.get("goals")
        
        # Validate required fields
        if not business_type or not industry or not goals:
            return jsonify({
                'success': False,
                'error': 'All onboarding questions must be answered'
            }), 400
        
        # Update user with onboarding data
        response = (
            supabase.table("users")
            .update({
                "business_type": business_type,
                "industry": industry,
                "goals": goals,
                "onboarding_completed": True
            })
            .eq("user_id", user_id)
            .execute()
        )
        
        if response.data:
            user_data = response.data[0]
            return jsonify({
                'success': True,
                'message': "Onboarding completed successfully",
                'user': {
                    'user_id': user_data['user_id'],
                    'name': user_data['name'],
                    'email': user_data['email'],
                    'business_type': user_data.get('business_type'),
                    'industry': user_data.get('industry'),
                    'goals': user_data.get('goals'),
                    'onboarding_completed': True
                }
            }), 200
        else:
            raise Exception("Failed to update user")
            
    except Exception as e:
        print(f"Error in complete_onboarding: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'An internal server error occurred'
        }), 500

@auth_bp.route('/login', methods=['POST', 'OPTIONS'])
@cross_origin()
def login():
    """User login"""
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
        
    try:
        if not supabase:
            return jsonify({
                'success': False,
                'error': 'Database not configured'
            }), 500
            
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': "No data provided"
            }), 400
        
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return jsonify({
                'success': False,
                'error': 'Email and password are required'
            }), 400
        
        # Convert email to lowercase
        email = email.lower().strip()
        
        # Find user by email
        user_response = (
            supabase.table('users')
            .select('*')
            .eq("email", email)
            .execute()
        )

        if not user_response.data:
            return jsonify({
                'success': False,
                'error': 'Invalid email or password'
            }), 401
        
        user_data = user_response.data[0]
        
        # Check if account is active
        if not user_data.get('is_active', True):
            return jsonify({
                'success': False,
                'error': 'Account has been deactivated'
            }), 403
        
        # Verify password
        if not check_password_hash(user_data['password_hash'], password):
            return jsonify({
                'success': False,
                'error': 'Invalid email or password'
            }), 401
        
        # Update last_login timestamp
        supabase.table('users').update({
            'last_login': datetime.datetime.utcnow().isoformat()
        }).eq('user_id', user_data['user_id']).execute()
        
        # Create JWT token
        token = jwt.encode(
            {
                'user_id': user_data['user_id'],
                'email': user_data['email'],
                'name': user_data['name'],
                'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30)
            },
            SECRET_KEY,
            algorithm="HS256"
        )
        
        return jsonify({
            'success': True,
            'message': "Login successful",
            'token': token,
            'user': {
                'user_id': user_data['user_id'],
                'name': user_data['name'],
                'email': user_data['email'],
                'onboarding_completed': user_data.get('onboarding_completed', False)
            }
        }), 200

    except Exception as e:
        print(f"Error in login: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'An internal server error occurred'
        }), 500

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Logout user (client-side token invalidation)"""
    return jsonify({
        'success': True,
        'message': 'Logout successful'
    }), 200

@auth_bp.route('/profile', methods=['GET'])
def get_profile():
    """Get user profile (requires Authorization header)"""
    try:
        if not supabase:
            return jsonify({
                'success': False,
                'error': 'Database not configured'
            }), 500
            
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                'success': False,
                'error': 'No authorization token provided'
            }), 401
        
        token = auth_header.split(' ')[1]
        
        # Verify token and get user_id
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            user_id = payload['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({
                'success': False,
                'error': 'Token has expired'
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                'success': False,
                'error': 'Invalid token'
            }), 401
        
        # Get user from database
        user_response = (
            supabase.table('users')
            .select('*')
            .eq("user_id", user_id)
            .execute()
        )
        
        if not user_response.data:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        user_data = user_response.data[0]
        
        return jsonify({
            'success': True,
            'user': {
                'user_id': user_data['user_id'],
                'name': user_data['name'],
                'email': user_data['email'],
                'onboarding_completed': user_data.get('onboarding_completed', False),
                'business_type': user_data.get('business_type'),
                'industry': user_data.get('industry'),
                'goals': user_data.get('goals'),
                'created_at': user_data.get('created_at')
            }
        }), 200
        
    except Exception as e:
        print(f"Error in get_profile: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get profile'
        }), 500

def _build_cors_preflight_response():
    """Build CORS preflight response"""
    response = jsonify()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add('Access-Control-Allow-Headers', "Content-Type,Authorization")
    response.headers.add('Access-Control-Allow-Methods', "GET,POST,PUT,DELETE,OPTIONS")
    response.headers.add('Access-Control-Allow-Credentials', "true")
    response.headers.add('Access-Control-Max-Age', "3600")
    return response

# For backward compatibility - if running this file directly
if __name__ == '__main__':
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.run(debug=True, port=5003, host='0.0.0.0')