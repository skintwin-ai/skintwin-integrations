"""
Script to initialize the skin care salon database
"""

from app import app
from database import db_sql
from create_test_data import (
    create_staff_users, create_test_clients, create_test_services,
    create_test_products, create_test_purchase_orders, create_test_shifts,
    create_test_appointments, create_test_transactions, create_test_portfolio_entries
)
import time

def init_db():
    """Initialize the database structure"""
    with app.app_context():
        print("Resetting database structure...")
        db_sql.drop_all()
        db_sql.create_all()
        print("Database structure reset successfully!")

def create_users():
    """Create staff user accounts"""
    with app.app_context():
        print("Creating staff users...")
        create_staff_users()
        print("Staff users created successfully!")

def create_clients():
    """Create client records"""
    with app.app_context():
        print("Creating clients...")
        create_test_clients()
        print("Clients created successfully!")

def create_services():
    """Create service offerings"""
    with app.app_context():
        print("Creating services...")
        create_test_services()
        print("Services created successfully!")

def create_products():
    """Create product inventory"""
    with app.app_context():
        print("Creating products...")
        create_test_products()
        print("Products created successfully!")

def create_purchase_orders():
    """Create purchase orders"""
    with app.app_context():
        print("Creating purchase orders...")
        products = create_test_products()  # Get products directly within this context
        create_test_purchase_orders(products)
        print("Purchase orders created successfully!")

def create_shifts():
    """Create staff shifts"""
    with app.app_context():
        print("Creating staff shifts...")
        create_test_shifts()
        print("Staff shifts created successfully!")

def create_appointments():
    """Create client appointments"""
    with app.app_context():
        print("Creating appointments...")
        clients = create_test_clients()
        services = create_test_services()
        create_test_appointments(clients, services)
        print("Appointments created successfully!")

def create_transactions():
    """Create client transactions"""
    with app.app_context():
        print("Creating transactions...")
        clients = create_test_clients()
        create_test_transactions(clients)
        print("Transactions created successfully!")

def create_portfolio_entries():
    """Create portfolio entries"""
    with app.app_context():
        print("Creating portfolio entries...")
        clients = create_test_clients()
        services = create_test_services()
        create_test_portfolio_entries(clients, services)
        print("Portfolio entries created successfully!")

if __name__ == "__main__":
    # Initialize database
    init_db()
    
    # Create basic data
    create_users()
    create_clients()
    create_services()
    create_products()
    
    # Create relational data
    create_purchase_orders()
    create_shifts()
    create_appointments()
    create_transactions()
    create_portfolio_entries()
    
    print("Skin care salon database initialization complete!")