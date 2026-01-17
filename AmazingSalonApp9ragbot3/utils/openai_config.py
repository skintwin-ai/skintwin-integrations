import os
from functools import wraps
from flask import request, redirect, url_for, flash
from flask_login import current_user
from database import db_sql

def get_openai_api_key():
    """Get the OpenAI API key from user model or environment variables"""
    # First check if the current user has an API key stored in their profile
    if current_user and current_user.is_authenticated and hasattr(current_user, 'openai_api_key') and current_user.openai_api_key:
        return current_user.openai_api_key
    
    # Fall back to environment variable if not in user profile
    return os.environ.get('OPENAI_API_KEY')

def set_openai_api_key(api_key):
    """Set the OpenAI API key in the user model and as a fallback in environment variables"""
    # Store in the user model if user is logged in
    if current_user and current_user.is_authenticated:
        current_user.openai_api_key = api_key
        db_sql.session.commit()
    
    # Also store in environment variables as a fallback
    os.environ['OPENAI_API_KEY'] = api_key
    return True

def has_openai_api_key():
    """Check if the OpenAI API key is set"""
    return bool(get_openai_api_key())

def openai_api_key_required(f):
    """Decorator to check if OpenAI API key is available before executing a function"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not has_openai_api_key():
            flash('OpenAI API key is required to use the AI assistant. Please configure it in the settings.', 'warning')
            return redirect(url_for('chat_assistant.setup_api_key'))
        return f(*args, **kwargs)
    return decorated_function