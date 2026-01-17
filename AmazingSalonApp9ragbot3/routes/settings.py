"""
Routes for system settings and configuration
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from database import db_sql
from database_models_config import SystemConfig
from database_models import Transaction
from utils.config_utils import ConfigManager
import sqlalchemy as sa
from functools import wraps
from datetime import datetime

bp = Blueprint('settings', __name__, url_prefix='/settings')

# Decorator to require admin access
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('You need administrator privileges to access this page.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/')
@login_required
@admin_required
def index():
    """Settings overview page"""
    # Get all system configurations
    all_configs = ConfigManager.get_all()
    
    # Get business information
    business_info = ConfigManager.get_business_info()
    
    # Check if Stripe is configured
    stripe_configured = bool(ConfigManager.get_stripe_public_key() and ConfigManager.get_stripe_secret_key())
    
    # Get loyalty program settings
    points_to_dollar_ratio = ConfigManager.get_loyalty_points_ratio()
    points_per_dollar = ConfigManager.get_points_per_dollar()
    
    # Gather loyalty program statistics
    stats = {}
    try:
        # Get total points issued (sum of points_earned column)
        total_points = db_sql.session.query(sa.func.sum(Transaction.points_earned)).scalar() or 0
        stats['total_points'] = total_points
        
        # Get points redeemed (sum of points_used column)
        points_redeemed = db_sql.session.query(sa.func.sum(Transaction.points_used)).scalar() or 0
        stats['points_redeemed'] = points_redeemed
        
        # Calculate discount value
        stats['discount_value'] = points_redeemed * points_to_dollar_ratio
        
        # Calculate redemption rate (if total points is 0, use 0 to avoid division by zero)
        if total_points > 0:
            stats['redemption_rate'] = round((points_redeemed / total_points) * 100)
        else:
            stats['redemption_rate'] = 0
    except Exception as e:
        # Handle database errors
        print(f"Error calculating loyalty statistics: {str(e)}")
        stats = {
            'total_points': 0,
            'points_redeemed': 0,
            'discount_value': 0,
            'redemption_rate': 0
        }
    
    return render_template('settings/index.html',
                          all_configs=all_configs,
                          business_info=business_info,
                          stripe_configured=stripe_configured,
                          points_to_dollar_ratio=points_to_dollar_ratio,
                          points_per_dollar=points_per_dollar,
                          stats=stats)

@bp.route('/payment')
@login_required
@admin_required
def payment_settings():
    """Payment settings page"""
    # Get Stripe API keys
    stripe_public_key = ConfigManager.get_stripe_public_key()
    stripe_secret_key = ConfigManager.get_stripe_secret_key()
    
    # Get Paystack API keys
    paystack_public_key = ConfigManager.get_paystack_public_key()
    paystack_secret_key = ConfigManager.get_paystack_secret_key()
    
    # Get default payment provider
    default_payment_provider = ConfigManager.get_default_payment_provider()
    
    # Get business information
    business_info = ConfigManager.get_business_info()
    
    # Get current datetime for receipt preview
    now = datetime.utcnow()
    
    return render_template('settings/payment_settings.html',
                          stripe_public_key=stripe_public_key,
                          stripe_secret_key=stripe_secret_key,
                          paystack_public_key=paystack_public_key,
                          paystack_secret_key=paystack_secret_key,
                          default_payment_provider=default_payment_provider,
                          business_info=business_info,
                          now=now)

@bp.route('/loyalty')
@login_required
@admin_required
def loyalty_settings():
    """Loyalty program settings page"""
    # Get loyalty program settings
    points_to_dollar_ratio = ConfigManager.get_loyalty_points_ratio()
    points_per_dollar = ConfigManager.get_points_per_dollar()
    
    # Gather loyalty program statistics
    stats = {}
    try:
        # Get total points issued (sum of points_earned column)
        total_points = db_sql.session.query(sa.func.sum(Transaction.points_earned)).scalar() or 0
        stats['total_points'] = total_points
        
        # Get points redeemed (sum of points_used column)
        points_redeemed = db_sql.session.query(sa.func.sum(Transaction.points_used)).scalar() or 0
        stats['points_redeemed'] = points_redeemed
        
        # Calculate discount value
        stats['discount_value'] = points_redeemed * points_to_dollar_ratio
        
        # Calculate redemption rate (if total points is 0, use 0 to avoid division by zero)
        if total_points > 0:
            stats['redemption_rate'] = round((points_redeemed / total_points) * 100)
        else:
            stats['redemption_rate'] = 0
    except Exception as e:
        # Handle database errors
        print(f"Error calculating loyalty statistics: {str(e)}")
        stats = {
            'total_points': 0,
            'points_redeemed': 0,
            'discount_value': 0,
            'redemption_rate': 0
        }
    
    return render_template('settings/loyalty_settings.html',
                          points_to_dollar_ratio=points_to_dollar_ratio,
                          points_per_dollar=points_per_dollar,
                          stats=stats)

@bp.route('/update', methods=['POST'])
@login_required
@admin_required
def update_settings():
    """Update settings"""
    section = request.form.get('section')
    
    if section == 'business':
        # Update business information
        business_name = request.form.get('business_name')
        business_email = request.form.get('business_email')
        business_phone = request.form.get('business_phone')
        
        # Validate inputs
        if not business_name or not business_email:
            flash('Business name and email are required', 'error')
            return redirect(url_for('settings.payment_settings'))
        
        # Save to configuration
        ConfigManager.set('business_name', business_name, 'Business name', 'business', False, current_user.id)
        ConfigManager.set('business_email', business_email, 'Business email address', 'business', False, current_user.id)
        ConfigManager.set('business_phone', business_phone, 'Business phone number', 'business', False, current_user.id)
        
        flash('Business information updated successfully', 'success')
        return redirect(url_for('settings.payment_settings') + '#business')
    
    elif section == 'loyalty':
        # Update loyalty program settings
        points_per_dollar = request.form.get('loyalty_points_per_dollar')
        points_to_dollar_ratio = request.form.get('points_to_dollar_ratio')
        
        # Validate inputs
        try:
            points_per_dollar = int(points_per_dollar)
            if points_per_dollar < 0:
                raise ValueError("Points per dollar must be non-negative")
        except (ValueError, TypeError):
            flash('Points per dollar must be a valid non-negative integer', 'error')
            return redirect(url_for('settings.loyalty_settings'))
        
        try:
            points_to_dollar_ratio = float(points_to_dollar_ratio)
            if points_to_dollar_ratio <= 0 or points_to_dollar_ratio > 1:
                raise ValueError("Points to dollar ratio must be between 0 and 1")
        except (ValueError, TypeError):
            flash('Points to dollar ratio must be a valid decimal between 0 and 1', 'error')
            return redirect(url_for('settings.loyalty_settings'))
        
        # Save to configuration
        ConfigManager.set('loyalty_points_per_dollar', str(points_per_dollar), 
                         'Loyalty points earned per dollar spent', 'loyalty', False, current_user.id)
        ConfigManager.set('points_to_dollar_ratio', str(points_to_dollar_ratio), 
                         'Loyalty points to dollar conversion ratio', 'loyalty', False, current_user.id)
        
        flash('Loyalty program settings updated successfully', 'success')
        return redirect(url_for('settings.loyalty_settings'))
    
    # Default fallback
    flash('Invalid settings section', 'error')
    return redirect(url_for('settings.index'))

@bp.route('/update-stripe-keys', methods=['POST'])
@login_required
@admin_required
def update_stripe_keys():
    """Update Stripe API keys"""
    stripe_public_key = request.form.get('stripe_public_key')
    stripe_secret_key = request.form.get('stripe_secret_key')
    
    # Basic validation
    if not stripe_public_key or not stripe_public_key.startswith(('pk_test_', 'pk_live_')):
        flash('Invalid Stripe publishable key format', 'error')
        return redirect(url_for('settings.payment_settings'))
    
    if not stripe_secret_key or not stripe_secret_key.startswith(('sk_test_', 'sk_live_')):
        flash('Invalid Stripe secret key format', 'error')
        return redirect(url_for('settings.payment_settings'))
    
    # Ensure both keys are from the same environment (test or live)
    if ('test' in stripe_public_key and 'live' in stripe_secret_key) or \
       ('live' in stripe_public_key and 'test' in stripe_secret_key):
        flash('Stripe keys must both be from the same environment (test or live)', 'error')
        return redirect(url_for('settings.payment_settings'))
    
    # Save the keys
    success = ConfigManager.set_stripe_keys(stripe_public_key, stripe_secret_key, current_user.id)
    
    # Set as default payment provider if checkbox is checked
    if request.form.get('default_payment_provider') == 'stripe':
        ConfigManager.set_default_payment_provider('stripe', current_user.id)
    
    if success:
        flash('Stripe API keys updated successfully', 'success')
    else:
        flash('Error updating Stripe API keys', 'error')
    
    return redirect(url_for('settings.payment_settings'))

@bp.route('/update-paystack-keys', methods=['POST'])
@login_required
@admin_required
def update_paystack_keys():
    """Update Paystack API keys"""
    paystack_public_key = request.form.get('paystack_public_key')
    paystack_secret_key = request.form.get('paystack_secret_key')
    
    # Basic validation
    if not paystack_public_key or not paystack_public_key.startswith(('pk_test_', 'pk_live_')):
        flash('Invalid Paystack public key format', 'error')
        return redirect(url_for('settings.payment_settings'))
    
    if not paystack_secret_key or not paystack_secret_key.startswith(('sk_test_', 'sk_live_')):
        flash('Invalid Paystack secret key format', 'error')
        return redirect(url_for('settings.payment_settings'))
    
    # Ensure both keys are from the same environment (test or live)
    if ('test' in paystack_public_key and 'live' in paystack_secret_key) or \
       ('live' in paystack_public_key and 'test' in paystack_secret_key):
        flash('Paystack keys must both be from the same environment (test or live)', 'error')
        return redirect(url_for('settings.payment_settings'))
    
    # Save the keys
    success = ConfigManager.set_paystack_keys(paystack_public_key, paystack_secret_key, current_user.id)
    
    # Set as default payment provider if checkbox is checked
    if request.form.get('default_payment_provider') == 'paystack':
        ConfigManager.set_default_payment_provider('paystack', current_user.id)
    
    if success:
        flash('Paystack API keys updated successfully', 'success')
    else:
        flash('Error updating Paystack API keys', 'error')
    
    return redirect(url_for('settings.payment_settings'))

@bp.route('/reset/<string:setting_key>')
@login_required
@admin_required
def reset_setting(setting_key):
    """Reset a setting to its default value"""
    # Get all default values for each known setting
    defaults = {
        'business_name': 'Salon Management System',
        'business_email': 'contact@salon-management.app',
        'business_phone': '+1-555-123-4567',
        'loyalty_points_per_dollar': '1',
        'points_to_dollar_ratio': '0.1',
        'default_payment_provider': 'stripe',
    }
    
    # Check if the setting exists in our defaults
    if setting_key in defaults:
        # Get the existing setting to determine category
        setting = db_sql.session.query(SystemConfig).filter_by(key=setting_key).first()
        
        if setting:
            # Update with default value
            setting.value = defaults[setting_key]
            db_sql.session.commit()
            
            # Update the cache
            ConfigManager._cache[setting_key] = {
                'value': defaults[setting_key],
                'description': setting.description,
                'category': setting.category,
                'is_sensitive': setting.is_sensitive,
                'updated_at': setting.updated_at
            }
            
            flash(f'Setting "{setting_key}" reset to default value', 'success')
        else:
            # Not found in database - unlikely but handle anyway
            flash(f'Setting "{setting_key}" not found', 'error')
    else:
        # Not a known default setting
        flash(f'No default value defined for "{setting_key}"', 'error')
    
    return redirect(url_for('settings.index'))