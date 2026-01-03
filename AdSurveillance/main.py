"""
AdSurveillance - Unified Flask API
Main entry point for Railway/Production Deployment
"""
import os
import sys
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime

# Import config
from config import Config

# Import blueprints
from AdSurveillance.api.auth import auth_bp
from AdSurveillance.api.ads_refresh import ads_refresh_bp
from AdSurveillance.api.ads_status import ads_status_bp
from AdSurveillance.api.competitors import competitors_bp
from AdSurveillance.api.daily_metrics import daily_metrics_bp
from AdSurveillance.api.targeting_intel import targeting_intel_bp
from AdSurveillance.api.user_analytics import user_analytics_bp

# Check for main_dashboard blueprint (optional)
try:
    from AdSurveillance.api.main_dashboard import main_dashboard_bp
    HAS_DASHBOARD = True
except ImportError:
    HAS_DASHBOARD = False
    print("⚠️  main_dashboard.py not found - skipping dashboard blueprint")

def create_app():
    """Create and configure the Flask application"""
    # Create Flask app
    app = Flask(__name__)
    
    # Configure app
    app.config['SECRET_KEY'] = Config.SECRET_KEY
    app.config['DEBUG'] = Config.DEBUG
    
    # Enable CORS
    CORS(app, 
         origins=Config.CORS_ORIGINS,
         supports_credentials=Config.CORS_SUPPORTS_CREDENTIALS)
    
    # ========== REGISTER BLUEPRINTS ==========
    # Authentication
    app.register_blueprint(auth_bp, url_prefix=f'{Config.API_PREFIX}/auth')
    
    # Ads Management
    app.register_blueprint(ads_refresh_bp, url_prefix=f'{Config.API_PREFIX}/ads')
    app.register_blueprint(ads_status_bp, url_prefix=f'{Config.API_PREFIX}/ads/status')
    
    # Competitors
    app.register_blueprint(competitors_bp, url_prefix=f'{Config.API_PREFIX}/competitors')
    
    # Analytics & Metrics
    app.register_blueprint(daily_metrics_bp, url_prefix=f'{Config.API_PREFIX}/metrics')
    app.register_blueprint(user_analytics_bp, url_prefix=f'{Config.API_PREFIX}/analytics')
    
    # Targeting Intelligence
    app.register_blueprint(targeting_intel_bp, url_prefix=f'{Config.API_PREFIX}/targeting')
    
    # Dashboard (optional)
    if HAS_DASHBOARD:
        app.register_blueprint(main_dashboard_bp, url_prefix=f'{Config.API_PREFIX}/dashboard')
    
    # ========== GLOBAL ENDPOINTS ==========
    @app.route('/')
    def root():
        """Root endpoint with service information"""
        return jsonify({
            'service': 'AdSurveillance API',
            'version': Config.API_VERSION,
            'status': 'running',
            'timestamp': datetime.now().isoformat(),
            'environment': Config.ENVIRONMENT,
            'endpoints': {
                'auth': f'{Config.API_PREFIX}/auth',
                'ads': f'{Config.API_PREFIX}/ads',
                'competitors': f'{Config.API_PREFIX}/competitors',
                'metrics': f'{Config.API_PREFIX}/metrics',
                'analytics': f'{Config.API_PREFIX}/analytics',
                'targeting': f'{Config.API_PREFIX}/targeting',
                'health': '/health'
            }
        })
    
    @app.route('/health')
    def health():
        """Health check endpoint (required for Railway)"""
        from AdSurveillance.database import is_supabase_connected
        
        checks = {
            'api': 'healthy',
            'supabase': 'healthy' if is_supabase_connected() else 'unhealthy',
            'environment': Config.ENVIRONMENT
        }
        
        status = 200 if all(v == 'healthy' for k, v in checks.items() if k != 'environment') else 503
        
        return jsonify({
            'status': 'healthy' if status == 200 else 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'checks': checks,
            'service': 'AdSurveillance'
        }), status
    
    @app.route('/api')
    def api_root():
        """API root endpoint"""
        return jsonify({
            'message': 'AdSurveillance API',
            'version': Config.API_VERSION,
            'documentation': 'See / endpoint for available endpoints'
        })
    
    # ========== ERROR HANDLERS ==========
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'error': 'Not found',
            'message': 'The requested endpoint does not exist',
            'status': 404
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred',
            'status': 500
        }), 500
    
    # ========== PRINT STARTUP INFO ==========
    @app.before_first_request
    def print_startup_info():
        print("\n" + "="*80)
        print("🚀 AD SURVEILLANCE API")
        print("="*80)
        print(f"📦 Version: {Config.API_VERSION}")
        print(f"🌍 Environment: {Config.ENVIRONMENT}")
        print(f"🔧 Debug: {Config.DEBUG}")
        print(f"🔐 Supabase: {'Connected' if is_supabase_connected() else 'Not connected'}")
        print(f"🔗 API Prefix: {Config.API_PREFIX}")
        print("\n📋 Registered Blueprints:")
        print(f"  • Authentication: {Config.API_PREFIX}/auth")
        print(f"  • Ads Management: {Config.API_PREFIX}/ads")
        print(f"  • Competitors: {Config.API_PREFIX}/competitors")
        print(f"  • Metrics: {Config.API_PREFIX}/metrics")
        print(f"  • Analytics: {Config.API_PREFIX}/analytics")
        print(f"  • Targeting: {Config.API_PREFIX}/targeting")
        if HAS_DASHBOARD:
            print(f"  • Dashboard: {Config.API_PREFIX}/dashboard")
        print("\n🌐 Endpoints:")
        print(f"  • Root: /")
        print(f"  • Health: /health")
        print(f"  • API Info: /api")
        print("="*80 + "\n")
    
    return app

# Create the app instance
app = create_app()

# For local development
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting AdSurveillance API on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=Config.DEBUG)