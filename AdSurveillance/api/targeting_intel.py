"""
Targeting Intelligence API for AdSurveillance
Flask Blueprint Version for Unified Deployment
Provides audience insights, targeting data, and demographic analysis
"""
import os
import sys
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from supabase import create_client, Client
import traceback
import random

# Create Flask Blueprint
targeting_intel_bp = Blueprint('targeting_intel', __name__)

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

@targeting_intel_bp.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'targeting_intel',
        'timestamp': datetime.now().isoformat(),
        'supabase_configured': bool(supabase)
    })

@targeting_intel_bp.route('/audience-insights', methods=['GET'])
@token_required
def get_audience_insights():
    """Get audience insights for the user's competitors"""
    try:
        if not supabase:
            return jsonify({'error': 'Database not configured'}), 500
            
        user_id = request.user_id
        
        # Get user's competitors
        competitors_response = supabase.table("competitors")\
            .select("id,name,industry,platform")\
            .eq("user_id", user_id)\
            .eq("is_active", True)\
            .execute()
        
        if not competitors_response.data:
            return jsonify({
                'success': True,
                'data': generate_default_audience_insights(),
                'message': 'No competitors found. Using default insights.'
            }), 200
        
        competitor_ids = [c['id'] for c in competitors_response.data]
        competitor_names = [c['name'] for c in competitors_response.data]
        industries = list(set([c.get('industry') for c in competitors_response.data if c.get('industry')]))
        
        # Get ads data from daily_metrics to analyze targeting
        ads_response = supabase.table("daily_metrics")\
            .select("competitor_id, platform, creative")\
            .in_("competitor_id", competitor_ids)\
            .limit(50)\
            .execute()
        
        ads_data = ads_response.data if ads_response.data else []
        
        # Analyze creatives for keywords (simple text analysis)
        all_keywords = analyze_creatives_for_keywords([ad.get('creative', '') for ad in ads_data])
        
        # Get platform distribution
        platforms = {}
        for ad in ads_data:
            platform = ad.get('platform', 'unknown')
            platforms[platform] = platforms.get(platform, 0) + 1
        
        # Generate audience insights
        insights = {
            'primary_audiences': generate_primary_audiences(industries, all_keywords),
            'demographics': generate_demographics(industries),
            'interests': generate_interests(all_keywords, industries),
            'behavioral_patterns': generate_behavioral_patterns(platforms),
            'top_keywords': all_keywords[:10],
            'platform_distribution': platforms,
            'competitors_analyzed': competitor_names,
            'sample_size': len(ads_data),
            'industries_targeted': industries,
            'confidence_score': calculate_confidence_score(len(ads_data), len(competitor_ids))
        }
        
        return jsonify({
            'success': True,
            'data': insights,
            'competitor_count': len(competitor_ids),
            'ads_analyzed': len(ads_data)
        }), 200
        
    except Exception as e:
        print(f"❌ Error getting audience insights: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': True,
            'data': generate_default_audience_insights(),
            'error': str(e),
            'message': 'Could not generate insights. Using default data.'
        }), 200

def analyze_creatives_for_keywords(creatives):
    """Simple keyword extraction from creative texts"""
    keywords = []
    common_words = ['the', 'and', 'for', 'with', 'this', 'that', 'your', 'you', 'are', 'get', 'free', 'now', 'best', 'new']
    
    for creative in creatives:
        if not creative:
            continue
        
        # Convert to lowercase and split
        words = creative.lower().split()
        for word in words:
            # Remove punctuation and check if meaningful
            word = word.strip('.,!?;:"\'()[]{}')
            if (len(word) > 3 and 
                word not in common_words and 
                word.isalpha() and 
                word not in keywords):
                keywords.append(word)
    
    # Count frequency and return top keywords
    from collections import Counter
    if keywords:
        keyword_counts = Counter(keywords)
        return [{'keyword': k, 'frequency': v} for k, v in keyword_counts.most_common(20)]
    
    return [
        {'keyword': 'technology', 'frequency': 15},
        {'keyword': 'business', 'frequency': 12},
        {'keyword': 'solution', 'frequency': 10},
        {'keyword': 'growth', 'frequency': 8},
        {'keyword': 'innovation', 'frequency': 7}
    ]

def generate_primary_audiences(industries, keywords):
    """Generate primary audience segments"""
    audiences = []
    
    if industries:
        for industry in industries[:3]:  # Top 3 industries
            audiences.append({
                'segment': f'{industry} Professionals',
                'size': random.randint(10000, 500000),
                'growth_rate': round(random.uniform(0.1, 0.3), 2),
                'key_characteristics': [
                    f'Interest in {industry} solutions',
                    'Decision makers',
                    'Industry-specific pain points'
                ]
            })
    else:
        audiences = [
            {
                'segment': 'Business Decision Makers',
                'size': 250000,
                'growth_rate': 0.15,
                'key_characteristics': ['C-level executives', 'Budget holders', 'Strategic planners']
            },
            {
                'segment': 'Marketing Professionals',
                'size': 180000,
                'growth_rate': 0.22,
                'key_characteristics': ['Digital marketing experience', 'ROI-focused', 'Platform savvy']
            }
        ]
    
    return audiences

def generate_demographics(industries):
    """Generate demographic data"""
    demographics = {
        'age_distribution': {
            '18-24': random.randint(5, 15),
            '25-34': random.randint(25, 40),
            '35-44': random.randint(20, 35),
            '45-54': random.randint(10, 25),
            '55+': random.randint(5, 15)
        },
        'gender_distribution': {
            'male': random.randint(40, 60),
            'female': random.randint(35, 55),
            'other': random.randint(1, 5)
        },
        'income_levels': {
            'low': random.randint(10, 20),
            'middle': random.randint(50, 70),
            'high': random.randint(20, 40)
        },
        'education_levels': {
            'high_school': random.randint(10, 25),
            'bachelors': random.randint(40, 60),
            'masters_plus': random.randint(20, 40)
        }
    }
    
    # Adjust based on industries if available
    if industries and any('tech' in str(ind).lower() for ind in industries):
        demographics['age_distribution']['25-34'] = random.randint(35, 50)
        demographics['income_levels']['high'] = random.randint(30, 50)
        demographics['education_levels']['masters_plus'] = random.randint(30, 50)
    
    return demographics

def generate_interests(keywords, industries):
    """Generate interest categories"""
    interests = []
    
    # Convert keywords to interests
    tech_keywords = ['tech', 'software', 'ai', 'digital', 'cloud', 'data']
    business_keywords = ['business', 'growth', 'solution', 'strategy', 'enterprise']
    
    tech_count = sum(1 for kw in keywords if any(tk in kw['keyword'].lower() for tk in tech_keywords))
    business_count = sum(1 for kw in keywords if any(bk in kw['keyword'].lower() for bk in business_keywords))
    
    if tech_count > 0:
        interests.append({
            'category': 'Technology',
            'affinity_score': min(95, 60 + tech_count * 5),
            'related_competitors': random.randint(3, 8)
        })
    
    if business_count > 0:
        interests.append({
            'category': 'Business & Entrepreneurship',
            'affinity_score': min(90, 55 + business_count * 5),
            'related_competitors': random.randint(2, 6)
        })
    
    # Add default interests if none found
    if not interests:
        interests = [
            {
                'category': 'Digital Marketing',
                'affinity_score': 75,
                'related_competitors': 5
            },
            {
                'category': 'Business Solutions',
                'affinity_score': 68,
                'related_competitors': 4
            }
        ]
    
    return interests

def generate_behavioral_patterns(platforms):
    """Generate behavioral patterns based on platform usage"""
    patterns = []
    
    platform_behavior_map = {
        'meta': ['Social media engagement', 'Visual content consumption', 'Mobile-first usage'],
        'facebook': ['Community participation', 'News consumption', 'Event engagement'],
        'instagram': ['Visual storytelling', 'Influencer following', 'Discovery mode'],
        'linkedin': ['Professional networking', 'Industry news', 'B2B engagement'],
        'google': ['Search-driven', 'Problem-solving', 'Research-oriented'],
        'tiktok': ['Short-form content', 'Trend participation', 'Entertainment focus']
    }
    
    for platform, count in platforms.items():
        if platform.lower() in platform_behavior_map:
            patterns.append({
                'platform': platform,
                'primary_behavior': platform_behavior_map[platform.lower()][0],
                'engagement_level': 'high' if count > 10 else 'medium' if count > 5 else 'low',
                'behavioral_traits': platform_behavior_map[platform.lower()]
            })
    
    # Add default patterns if none found
    if not patterns:
        patterns = [
            {
                'platform': 'Meta',
                'primary_behavior': 'Social media engagement',
                'engagement_level': 'high',
                'behavioral_traits': ['Community building', 'Content sharing', 'Brand interaction']
            },
            {
                'platform': 'LinkedIn',
                'primary_behavior': 'Professional networking',
                'engagement_level': 'medium',
                'behavioral_traits': ['Industry discussions', 'Professional development', 'B2B networking']
            }
        ]
    
    return patterns

def calculate_confidence_score(ads_count, competitor_count):
    """Calculate confidence score based on data quality"""
    if ads_count == 0:
        return 0.3  # Low confidence with no ads data
    
    base_score = min(0.9, 0.3 + (ads_count * 0.01))
    
    # Adjust based on competitor count
    if competitor_count >= 5:
        base_score = min(0.95, base_score + 0.1)
    
    return round(base_score, 2)

def generate_default_audience_insights():
    """Generate default audience insights when no data is available"""
    return {
        'primary_audiences': [
            {
                'segment': 'Business Decision Makers',
                'size': 250000,
                'growth_rate': 0.15,
                'key_characteristics': ['C-level executives', 'Budget holders', 'Strategic planners']
            },
            {
                'segment': 'Marketing Professionals',
                'size': 180000,
                'growth_rate': 0.22,
                'key_characteristics': ['Digital marketing experience', 'ROI-focused', 'Platform savvy']
            }
        ],
        'demographics': {
            'age_distribution': {'18-24': 12, '25-34': 35, '35-44': 28, '45-54': 18, '55+': 7},
            'gender_distribution': {'male': 52, 'female': 45, 'other': 3},
            'income_levels': {'low': 15, 'middle': 60, 'high': 25},
            'education_levels': {'high_school': 20, 'bachelors': 50, 'masters_plus': 30}
        },
        'interests': [
            {
                'category': 'Digital Marketing',
                'affinity_score': 75,
                'related_competitors': 5
            },
            {
                'category': 'Business Solutions',
                'affinity_score': 68,
                'related_competitors': 4
            }
        ],
        'behavioral_patterns': [
            {
                'platform': 'Meta',
                'primary_behavior': 'Social media engagement',
                'engagement_level': 'high',
                'behavioral_traits': ['Community building', 'Content sharing', 'Brand interaction']
            },
            {
                'platform': 'LinkedIn',
                'primary_behavior': 'Professional networking',
                'engagement_level': 'medium',
                'behavioral_traits': ['Industry discussions', 'Professional development', 'B2B networking']
            }
        ],
        'top_keywords': [
            {'keyword': 'business', 'frequency': 15},
            {'keyword': 'solution', 'frequency': 12},
            {'keyword': 'growth', 'frequency': 10},
            {'keyword': 'digital', 'frequency': 8},
            {'keyword': 'marketing', 'frequency': 7}
        ],
        'platform_distribution': {'meta': 8, 'linkedin': 5, 'google': 3},
        'competitors_analyzed': ['Sample Competitors'],
        'sample_size': 0,
        'industries_targeted': ['General Business'],
        'confidence_score': 0.3,
        'is_default_data': True
    }

@targeting_intel_bp.route('/competitive-analysis', methods=['GET'])
@token_required
def get_competitive_analysis():
    """Get competitive analysis based on ads data"""
    try:
        if not supabase:
            return jsonify({'error': 'Database not configured'}), 500
            
        user_id = request.user_id
        
        # Get user's competitors
        competitors_response = supabase.table("competitors")\
            .select("id,name,industry")\
            .eq("user_id", user_id)\
            .eq("is_active", True)\
            .execute()
        
        if not competitors_response.data:
            return jsonify({
                'success': True,
                'data': generate_default_competitive_analysis(),
                'message': 'No competitors found'
            }), 200
        
        competitor_ids = [c['id'] for c in competitors_response.data]
        
        # Get ads data for analysis
        ads_response = supabase.table("daily_metrics")\
            .select("competitor_id, platform, daily_spend, daily_impressions, daily_ctr, creative, date")\
            .in_("competitor_id", competitor_ids)\
            .gte("date", (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))\
            .execute()
        
        ads_data = ads_response.data if ads_response.data else []
        
        # Analyze competitive landscape
        analysis = {
            'market_coverage': analyze_market_coverage(competitors_response.data, ads_data),
            'spending_patterns': analyze_spending_patterns(ads_data),
            'creative_strategies': analyze_creative_strategies(ads_data),
            'platform_effectiveness': analyze_platform_effectiveness(ads_data),
            'opportunity_areas': identify_opportunity_areas(ads_data, competitors_response.data),
            'competitive_intensity': calculate_competitive_intensity(ads_data),
            'trends': identify_trends(ads_data)
        }
        
        return jsonify({
            'success': True,
            'data': analysis,
            'competitors_analyzed': len(competitor_ids),
            'ads_analyzed': len(ads_data),
            'time_period': '30 days'
        }), 200
        
    except Exception as e:
        print(f"❌ Error getting competitive analysis: {str(e)}")
        return jsonify({
            'success': True,
            'data': generate_default_competitive_analysis(),
            'error': str(e)
        }), 200

def analyze_market_coverage(competitors, ads_data):
    """Analyze market coverage by competitors"""
    return {
        'total_market_presence': len(competitors),
        'active_competitors': len(set(ad['competitor_id'] for ad in ads_data)),
        'market_segments': list(set(c.get('industry', 'General') for c in competitors if c.get('industry'))),
        'coverage_score': round(min(100, len(competitors) * 10), 1)
    }

def analyze_spending_patterns(ads_data):
    """Analyze spending patterns"""
    if not ads_data:
        return {
            'total_spend': 0,
            'avg_daily_spend': 0,
            'spending_distribution': {'low': 100, 'medium': 0, 'high': 0},
            'trend': 'stable'
        }
    
    total_spend = sum(float(ad.get('daily_spend', 0) or 0) for ad in ads_data)
    avg_spend = total_spend / len(ads_data) if ads_data else 0
    
    # Categorize spending
    spends = [float(ad.get('daily_spend', 0) or 0) for ad in ads_data]
    low = sum(1 for s in spends if s < 100)
    medium = sum(1 for s in spends if 100 <= s < 1000)
    high = sum(1 for s in spends if s >= 1000)
    
    total = len(spends)
    distribution = {
        'low': round(low / total * 100, 1) if total > 0 else 0,
        'medium': round(medium / total * 100, 1) if total > 0 else 0,
        'high': round(high / total * 100, 1) if total > 0 else 0
    }
    
    return {
        'total_spend': round(total_spend, 2),
        'avg_daily_spend': round(avg_spend, 2),
        'spending_distribution': distribution,
        'trend': 'increasing' if total_spend > 10000 else 'stable' if total_spend > 5000 else 'low'
    }

def analyze_creative_strategies(ads_data):
    """Analyze creative strategies from ads"""
    strategies = {
        'value_proposition': 0,
        'urgency': 0,
        'social_proof': 0,
        'educational': 0
    }
    
    keywords_map = {
        'value_proposition': ['save', 'get', 'free', 'offer', 'deal', 'discount'],
        'urgency': ['now', 'today', 'limited', 'hurry', 'expire', 'last'],
        'social_proof': ['testimonial', 'review', 'rating', 'popular', 'trusted', 'award'],
        'educational': ['guide', 'how', 'tips', 'learn', 'master', 'understand']
    }
    
    for ad in ads_data:
        creative = str(ad.get('creative', '')).lower()
        for strategy, keywords in keywords_map.items():
            if any(keyword in creative for keyword in keywords):
                strategies[strategy] += 1
    
    total = len(ads_data)
    if total > 0:
        for key in strategies:
            strategies[key] = round(strategies[key] / total * 100, 1)
    
    return strategies

def analyze_platform_effectiveness(ads_data):
    """Analyze which platforms are most effective"""
    platform_data = {}
    
    for ad in ads_data:
        platform = ad.get('platform', 'unknown')
        if platform not in platform_data:
            platform_data[platform] = {
                'spend': 0,
                'impressions': 0,
                'clicks': 0,
                'count': 0
            }
        
        platform_data[platform]['spend'] += float(ad.get('daily_spend', 0) or 0)
        platform_data[platform]['impressions'] += int(ad.get('daily_impressions', 0) or 0)
        platform_data[platform]['count'] += 1
    
    # Calculate effectiveness scores
    effectiveness = []
    for platform, data in platform_data.items():
        if data['impressions'] > 0:
            cpm = (data['spend'] / data['impressions']) * 1000
            score = max(1, min(100, 100 - cpm))  # Lower CPM = higher score
        else:
            score = 50
        
        effectiveness.append({
            'platform': platform,
            'effectiveness_score': round(score, 1),
            'spend_share': round(data['spend'] / sum(d['spend'] for d in platform_data.values()) * 100, 1) if sum(d['spend'] for d in platform_data.values()) > 0 else 0,
            'ads_count': data['count']
        })
    
    return sorted(effectiveness, key=lambda x: x['effectiveness_score'], reverse=True)

def identify_opportunity_areas(ads_data, competitors):
    """Identify opportunity areas based on gaps"""
    opportunities = []
    
    # Check for underserved platforms
    all_platforms = ['meta', 'facebook', 'instagram', 'linkedin', 'google', 'tiktok']
    used_platforms = set(ad.get('platform', '').lower() for ad in ads_data)
    unused_platforms = [p for p in all_platforms if p not in used_platforms]
    
    if unused_platforms:
        opportunities.append({
            'type': 'platform_gap',
            'description': f'Opportunity on {", ".join(unused_platforms).title()} platform(s)',
            'potential_impact': 'high',
            'difficulty': 'medium'
        })
    
    # Check for creative strategy gaps
    if len(ads_data) < 10:
        opportunities.append({
            'type': 'content_gap',
            'description': 'Limited creative variety in current ads',
            'potential_impact': 'medium',
            'difficulty': 'low'
        })
    
    return opportunities

def calculate_competitive_intensity(ads_data):
    """Calculate competitive intensity score"""
    if not ads_data:
        return {'score': 30, 'level': 'low', 'description': 'Limited competition detected'}
    
    # Simple scoring based on ad volume and diversity
    unique_competitors = len(set(ad.get('competitor_id') for ad in ads_data))
    total_ads = len(ads_data)
    
    score = min(100, (unique_competitors * 15) + (total_ads / 10))
    
    if score >= 70:
        level = 'high'
        desc = 'Highly competitive landscape'
    elif score >= 40:
        level = 'medium'
        desc = 'Moderate competition'
    else:
        level = 'low'
        desc = 'Limited competition'
    
    return {'score': round(score, 1), 'level': level, 'description': desc}

def identify_trends(ads_data):
    """Identify trends in advertising"""
    if not ads_data or len(ads_data) < 5:
        return {
            'emerging_formats': ['Video content', 'Interactive ads'],
            'content_themes': ['Value-driven messaging', 'Problem-solution approach'],
            'predicted_shifts': ['Increased video adoption', 'More personalized content']
        }
    
    # Simple trend analysis (in a real app, this would be more sophisticated)
    return {
        'emerging_formats': ['Short-form video', 'Interactive stories', 'Carousel ads'],
        'content_themes': ['Authentic storytelling', 'User-generated content', 'Educational value'],
        'predicted_shifts': [
            'Higher video ad spend',
            'Increased AR/VR experimentation',
            'More personalized retargeting'
        ],
        'data_based': len(ads_data) >= 10
    }

def generate_default_competitive_analysis():
    """Generate default competitive analysis"""
    return {
        'market_coverage': {
            'total_market_presence': 0,
            'active_competitors': 0,
            'market_segments': ['General'],
            'coverage_score': 0
        },
        'spending_patterns': {
            'total_spend': 0,
            'avg_daily_spend': 0,
            'spending_distribution': {'low': 100, 'medium': 0, 'high': 0},
            'trend': 'stable'
        },
        'creative_strategies': {
            'value_proposition': 40,
            'urgency': 25,
            'social_proof': 20,
            'educational': 15
        },
        'platform_effectiveness': [
            {'platform': 'Meta', 'effectiveness_score': 75, 'spend_share': 40, 'ads_count': 8},
            {'platform': 'LinkedIn', 'effectiveness_score': 65, 'spend_share': 30, 'ads_count': 5},
            {'platform': 'Google', 'effectiveness_score': 60, 'spend_share': 30, 'ads_count': 3}
        ],
        'opportunity_areas': [
            {
                'type': 'platform_gap',
                'description': 'Opportunity on TikTok and Instagram platforms',
                'potential_impact': 'high',
                'difficulty': 'medium'
            }
        ],
        'competitive_intensity': {
            'score': 30,
            'level': 'low',
            'description': 'Limited competition detected'
        },
        'trends': {
            'emerging_formats': ['Video content', 'Interactive ads'],
            'content_themes': ['Value-driven messaging', 'Problem-solution approach'],
            'predicted_shifts': ['Increased video adoption', 'More personalized content'],
            'data_based': False
        },
        'is_default_data': True
    }

@targeting_intel_bp.route('/recommendations', methods=['GET'])
@token_required
def get_recommendations():
    """Get targeting recommendations based on analysis"""
    try:
        user_id = request.user_id
        
        # In a real app, this would use ML models or more sophisticated analysis
        recommendations = {
            'audience_expansion': [
                {
                    'segment': 'Lookalike Audiences',
                    'description': 'Target users similar to your current converters',
                    'expected_reach': '2-3x current audience',
                    'implementation_difficulty': 'low'
                },
                {
                    'segment': 'Interest-based Expansion',
                    'description': 'Expand to related interest categories',
                    'expected_reach': '1.5-2x current audience',
                    'implementation_difficulty': 'medium'
                }
            ],
            'creative_optimization': [
                {
                    'type': 'Video Content',
                    'description': 'Incorporate short-form video in ad creatives',
                    'expected_impact': 'Increase CTR by 15-25%',
                    'priority': 'high'
                },
                {
                    'type': 'Social Proof',
                    'description': 'Add testimonials and ratings to ads',
                    'expected_impact': 'Increase conversion by 10-20%',
                    'priority': 'medium'
                }
            ],
            'budget_allocation': [
                {
                    'platform': 'Meta',
                    'recommended_increase': '15-20%',
                    'rationale': 'High engagement and proven ROI',
                    'expected_roi_improvement': '12-18%'
                },
                {
                    'platform': 'LinkedIn',
                    'recommended_increase': '10-15%',
                    'rationale': 'Strong B2B conversion rates',
                    'expected_roi_improvement': '8-12%'
                }
            ],
            'testing_priorities': [
                {
                    'test_type': 'Audience Segment',
                    'description': 'Test new interest-based audience segments',
                    'duration': '2-3 weeks',
                    'budget_required': 'low'
                },
                {
                    'test_type': 'Creative Format',
                    'description': 'Test video vs. image vs. carousel formats',
                    'duration': '3-4 weeks',
                    'budget_required': 'medium'
                }
            ]
        }
        
        return jsonify({
            'success': True,
            'data': recommendations,
            'generated_at': datetime.now().isoformat(),
            'time_horizon': 'Next 30-60 days'
        }), 200
        
    except Exception as e:
        print(f"❌ Error getting recommendations: {str(e)}")
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
    app.register_blueprint(targeting_intel_bp, url_prefix='/api/targeting')
    app.run(port=5010, debug=True)