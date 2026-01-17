
from app import app, db_sql
from database_utils import migrate_data
from init_db import init_db, run_migrations
import os

def initialize_app():
    # Ensure instance folder exists
    os.makedirs('instance', exist_ok=True)
    
    with app.app_context():
        # Initialize database
        init_db()
        
        try:
            # Run migrations
            run_migrations()
            
            # Migrate any existing data
            migrate_data()
        except Exception as e:
            print(f"Migration error: {e}")
            # Create all tables if migrations fail
            db_sql.create_all()

if __name__ == "__main__":
    try:
        # Initialize the application
        initialize_app()
        print("Database initialized successfully")
        
        # Run the application
        app.run(host="0.0.0.0", port=5000, debug=True)
    except Exception as e:
        print(f"Error during initialization: {e}")
        raise
