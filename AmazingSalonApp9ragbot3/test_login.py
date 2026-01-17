from flask import Flask, session
from app import app
from database_models import User
import requests

def test_login():
    """Test login functionality with admin credentials"""
    print("Testing login functionality with admin credentials...")
    
    with app.app_context():
        # Check if admin user exists
        admin = User.query.filter_by(email='admin@salon.com').first()
        if not admin:
            print("Admin user not found in database")
            return False
        
        print(f"Found admin user: {admin.username} ({admin.email})")
        
        # Test if password works
        if admin.check_password('admin123'):
            print("Password verification successful!")
        else:
            print("Password verification failed!")
            return False
        
    print("Login functionality test passed!")
    return True

if __name__ == "__main__":
    test_login()