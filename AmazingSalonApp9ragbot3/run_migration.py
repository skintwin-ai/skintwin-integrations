"""
A script to run database migrations
"""
from flask import Flask
from flask_migrate import Migrate, upgrade
import os
from database import init_db, db_sql

def run_migrations():
    """Run database migrations"""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize database
    init_db(app)
    
    # Setup migrations
    migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
    migrate = Migrate(app, db_sql, directory=migrations_dir)
    
    # Run upgrades
    with app.app_context():
        upgrade(directory=migrations_dir)
    
    print("Migrations completed successfully")

if __name__ == '__main__':
    run_migrations()