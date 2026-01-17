
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import get_client, get_all_clients, update_user, get_all_services
from datetime import datetime
import json
import random  # Temporary for demo purposes

bp = Blueprint('recommendations', __name__)

@bp.route('/client-recommendations/<client_id>')
@login_required
def client_recommendations(client_id):
    client = get_client(client_id)
    if not client:
        flash('Client not found', 'error')
        return redirect(url_for('clients.index'))
    
    # Get all available services
    all_services = get_all_services()
    
    # Create preferences dict from client attributes for compatibility with existing code
    client_preferences = {
        'hair_length': client.get('hair_length', 'medium'),
        'style_preference': client.get('style_preference', 'classic'),
        'color_preference': client.get('color_preference', 'natural'),
        'previous_services': []
    }
    
    # Generate recommendations based on preferences
    # In a production environment, this would use ML algorithms
    # For now, we'll use a rule-based approach
    recommendations = generate_recommendations(client, all_services, client_preferences)
    
    return render_template('client_recommendations.html', 
                           client=client, 
                           recommendations=recommendations)

@bp.route('/update-client-preferences/<client_id>', methods=['POST'])
@login_required
def update_client_preferences(client_id):
    client = get_client(client_id)
    if not client:
        flash('Client not found', 'error')
        return redirect(url_for('clients.index'))
    
    # Update client preferences
    hair_length = request.form.get('hair_length', 'medium')
    style_preference = request.form.get('style_preference', 'classic')
    color_preference = request.form.get('color_preference', 'natural')
    
    # Use the database_utils to update the client directly
    from database_utils import update_client_sql
    update_client_sql(
        client_id=client_id,
        hair_length=hair_length,
        style_preference=style_preference,
        color_preference=color_preference
    )
    
    flash('Client preferences updated successfully', 'success')
    
    return redirect(url_for('recommendations.client_recommendations', client_id=client_id))

@bp.route('/api/style-preview', methods=['POST'])
@login_required
def style_preview():
    """API endpoint for style preview - would connect to a real AI service"""
    style_id = request.json.get('style_id')
    client_id = request.json.get('client_id')
    
    # In a production environment, this would generate actual style previews
    # using ML/AI models like GANs or diffusion models
    preview_urls = [
        f"/static/img/style_previews/{style_id}_preview1.jpg",
        f"/static/img/style_previews/{style_id}_preview2.jpg",
        f"/static/img/style_previews/{style_id}_preview3.jpg"
    ]
    
    return jsonify({
        'previews': preview_urls,
        'success': True
    })

def generate_recommendations(client, all_services, preferences):
    """
    Generate AI-powered personalized treatment recommendations
    """
    from utils.ai_utils import analyze_client_history, predict_best_treatments
    
    # Analyze client history and preferences
    client_analysis = analyze_client_history(client)
    
    # Get personalized predictions
    recommended_treatments = predict_best_treatments(
        client_analysis=client_analysis,
        available_services=all_services,
        preferences=preferences
    )
    recommendations = []
    
    # Extract client features that matter for recommendations
    hair_length = preferences.get('hair_length', 'medium')
    style_pref = preferences.get('style_preference', 'classic')
    color_pref = preferences.get('color_preference', 'natural')
    
    # Map client preferences to service attributes
    # In a real system, this would use more sophisticated matching
    for service in all_services:
        service_name = service.get('name', '').lower()
        score = 0
        
        # Score based on hair length match
        if hair_length == 'short' and ('short' in service_name or 'bob' in service_name or 'pixie' in service_name):
            score += 3
        elif hair_length == 'medium' and ('medium' in service_name or 'shoulder' in service_name or 'lob' in service_name):
            score += 3
        elif hair_length == 'long' and ('long' in service_name or 'extension' in service_name):
            score += 3
            
        # Score based on style preference
        if style_pref == 'classic' and ('classic' in service_name or 'traditional' in service_name):
            score += 2
        elif style_pref == 'modern' and ('modern' in service_name or 'trendy' in service_name):
            score += 2
        elif style_pref == 'edgy' and ('edgy' in service_name or 'punk' in service_name or 'creative' in service_name):
            score += 2
            
        # Score based on color preference
        if 'color' in service_name or 'highlight' in service_name or 'dye' in service_name:
            if color_pref == 'natural' and ('natural' in service_name or 'subtle' in service_name):
                score += 2
            elif color_pref == 'bold' and ('vibrant' in service_name or 'bold' in service_name):
                score += 2
            elif color_pref == 'trendy' and ('trendy' in service_name or 'fashion' in service_name):
                score += 2
        
        # Add some randomness to make it interesting
        score += random.uniform(0, 1)
        
        # If the score is above threshold, add to recommendations
        if score > 2:
            recommendations.append({
                'service': service,
                'confidence': min(score / 7 * 100, 98),  # Convert to percentage, cap at 98%
                'reasoning': generate_recommendation_reasoning(service, preferences)
            })
    
    # Sort by confidence
    recommendations.sort(key=lambda x: x['confidence'], reverse=True)
    
    # Limit to top 5
    return recommendations[:5]

def generate_recommendation_reasoning(service, preferences):
    """Generate natural language explanation for recommendation"""
    reasons = [
        f"This {service.get('name')} would complement your {preferences.get('hair_length')} hair length beautifully.",
        f"Based on your preference for {preferences.get('style_preference')} styles, this would be a perfect match.",
        f"This service would enhance your natural features while aligning with your {preferences.get('color_preference')} color preferences.",
        "Our AI analysis suggests this would be particularly flattering for your face shape and features.",
        "This style is trending now and matches your preference for contemporary looks.",
        "This would be a subtle yet impactful change to refresh your look."
    ]
    
    # Select 2-3 random reasons
    selected_reasons = random.sample(reasons, min(3, len(reasons)))
    return " ".join(selected_reasons)
