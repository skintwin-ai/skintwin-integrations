import os
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import exc
from flask import current_app
import time

# Create a separate SQLAlchemy instance outside of app
db_sql = SQLAlchemy()

def init_db(app):
    # Ensure instance directory exists
    instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
    os.makedirs(instance_path, exist_ok=True)
    
    # Configure SQLite database path
    db_path = os.path.join(instance_path, 'salon.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db_sql.init_app(app)
    
    # Initialize database if it doesn't exist
    with app.app_context():
        db_sql.create_all()

# Define a function to handle database operations with automatic retries
def db_operation_with_retry(operation, max_retries=3, retry_delay=0.5):
    """
    Execute a database operation with automatic retries on connection errors

    Args:
        operation: A callable that performs the database operation
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds

    Returns:
        The result of the operation if successful

    Raises:
        The last encountered exception if all retries fail
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            return operation()
        except (exc.DatabaseError, exc.OperationalError, exc.DisconnectionError) as e:
            last_error = e
            if attempt < max_retries - 1:  # Don't sleep on the last attempt
                if current_app:  # Check if we're in a Flask app context
                    current_app.logger.warning(
                        f"Database operation failed (attempt {attempt+1}/{max_retries}): {str(e)}. Retrying..."
                    )
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff

                # If it's a connection issue, try to ping the database to check connection
                try:
                    db_sql.session.execute("SELECT 1")
                    db_sql.session.commit()
                except Exception:
                    # If ping fails, remove the session and create a new one
                    db_sql.session.remove()

    # If we get here, all retries failed
    if current_app:
        current_app.logger.error(f"Database operation failed after {max_retries} attempts: {str(last_error)}")

    # Re-raise the last error
    raise last_error