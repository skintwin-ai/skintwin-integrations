"""
A script to run all database migrations in sequence
"""
import os
from flask import Flask
from flask_migrate import Migrate, upgrade
from database import init_db, db_sql

def run_all_migrations():
    """Run all database migrations to latest version"""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize database
    init_db(app)
    
    # Import models to ensure they're registered with SQLAlchemy
    from database_models import User, Client, Service, Appointment, Transaction
    from database_models import Product, PurchaseOrder, Shift, ShiftBreak, PortfolioEntry
    from database_models_ai import ChatConversation, ChatMessage, DocumentChunk, ClientMemory, ClientMilestone
    from database_models_config import SystemConfig
    
    # Setup migrations
    migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
    migrate = Migrate(app, db_sql, directory=migrations_dir)
    
    # Run upgrades
    with app.app_context():
        upgrade(directory=migrations_dir)
    
    print("All migrations completed successfully")

if __name__ == '__main__':
    run_all_migrations()