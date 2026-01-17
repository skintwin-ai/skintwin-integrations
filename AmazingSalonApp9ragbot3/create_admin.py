"""
Script to create an admin user
"""
from app import app
from database import db_sql
from database_models import User
from werkzeug.security import generate_password_hash
from datetime import datetime

def create_admin():
    """Create an admin user"""
    with app.app_context():
        # Check if admin already exists
        admin = User.query.filter_by(email='admin@salon.com').first()
        if not admin:
            # Create admin user
            admin = User(
                username='admin',
                email='admin@salon.com', 
                password_hash=generate_password_hash('admin123'),
                is_staff=True,
                is_admin=True,
                created_at=datetime.utcnow()
            )
            db_sql.session.add(admin)
            db_sql.session.commit()
            print('Admin user created successfully!')
        else:
            print('Admin user already exists')

if __name__ == '__main__':
    create_admin()