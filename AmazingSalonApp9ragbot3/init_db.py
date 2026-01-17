import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, upgrade

def init_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db = SQLAlchemy(app)
    migrate = Migrate(app, db)
    
    return app, db, migrate

def init_db():
    """Initialize the database with tables and initial data"""
    from app import app, db_sql
    
    with app.app_context():
        # Create all tables
        db_sql.create_all()
        
        # Import models after app context is established
        from database_models import User
        from werkzeug.security import generate_password_hash
        
        # Create admin user if it doesn't exist
        admin = User.query.filter_by(email='admin@salon.dev').first()
        if not admin:
            admin = User(
                username='Admin',
                email='admin@salon.dev',
                password_hash=generate_password_hash('admin123'),
                is_staff=True,
                is_admin=True
            )
            db_sql.session.add(admin)
            db_sql.session.commit()
            print("Admin user created.")
        else:
            print("Admin user already exists.")

def run_migrations():
    """Run database migrations"""
    app, db, migrate = init_app()
    
    # Import models to ensure they're registered
    from database_models import User, Client, Service, Appointment, Transaction
    from database_models import Product, PurchaseOrder, Shift, ShiftBreak, PortfolioEntry
    from database_models_ai import ChatConversation, ChatMessage, DocumentChunk, ClientMemory, ClientMilestone
    from database_models_skills import AISkill, AITrainingSession, AIAchievement, AIModel, AISkillProgress
    from database_models_config import SystemConfig
    
    with app.app_context():
        # Run migrations using Flask-Migrate
        # Note: This assumes migrations directory already exists
        # If not, run 'flask db init' first
        try:
            # Using the command function from Flask-Migrate
            from flask_migrate import upgrade as migrate_upgrade
            migrate_upgrade()
            print("Database migrations completed successfully.")
        except Exception as e:
            print(f"Error running migrations: {e}")

def migrate_data():
    """Migrate data from Replit DB to SQL database"""
    from app import app
    
    with app.app_context():
        from database_utils import migrate_users_to_sql, migrate_clients_to_sql
        
        users_count = migrate_users_to_sql()
        clients_count = migrate_clients_to_sql()
        
        print(f"Data migration completed: {users_count} users and {clients_count} clients migrated.")

if __name__ == "__main__":
    # Run all database initialization steps
    print("Initializing database...")
    init_db()
    
    print("Running migrations...")
    run_migrations()
    
    print("Migrating data from Replit DB to SQL database...")
    migrate_data()