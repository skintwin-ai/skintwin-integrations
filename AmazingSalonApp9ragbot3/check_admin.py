from database_models import User
from app import app
from werkzeug.security import generate_password_hash

with app.app_context():
    admin = User.query.filter_by(email='admin@salon.com').first()
    print(f"Admin user found: {admin}")
    
    if not admin:
        print("Creating admin user...")
        from database_utils import create_user_sql
        create_user_sql('Admin', 'admin@salon.com', 'admin123', is_staff=True, is_admin=True)
        print("Admin user created")
    else:
        # Check if password matches 'admin123'
        if admin.check_password('admin123'):
            print("Password is correct")
        else:
            print("Password is incorrect, updating password...")
            admin.set_password('admin123')
            from database import db_sql
            db_sql.session.commit()
            print("Password updated")