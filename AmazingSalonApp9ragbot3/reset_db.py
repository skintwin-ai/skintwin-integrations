"""
Script to reset and re-initialize the database with skin care salon test data
"""

from app import app
from database import db_sql
from create_test_data import (
    create_staff_users, create_test_clients, create_test_services,
    create_test_products, create_test_purchase_orders, create_test_shifts,
    create_test_appointments, create_test_transactions, create_test_portfolio_entries
)

def reset_db():
    """Reset and initialize the database"""
    with app.app_context():
        # Drop all tables
        print("Dropping all tables...")
        db_sql.drop_all()
        
        # Create all tables
        print("Creating all tables...")
        db_sql.create_all()
        
        print("Database structure reset successfully!")

def populate_base_data():
    """Populate the database with basic test data"""
    with app.app_context():
        # Create users and clients first
        print("Creating staff users...")
        staff = create_staff_users()
        
        print("Creating clients...")
        clients = create_test_clients()
        
        print("Creating services...")
        services = create_test_services()
        
        print("Creating products...")
        products = create_test_products()
        
        print("Base data created successfully!")
        return clients, services, products, staff

def populate_relational_data(clients, services, products):
    """Populate relational data that depends on other entities"""
    with app.app_context():
        print("Creating purchase orders...")
        create_test_purchase_orders(products)
        
        print("Creating staff shifts...")
        create_test_shifts()
        
        print("Creating appointments...")
        create_test_appointments(clients, services)
        
        print("Creating transactions...")
        create_test_transactions(clients)
        
        print("Creating portfolio entries...")
        create_test_portfolio_entries(clients, services)
        
        print("Relational data created successfully!")

if __name__ == "__main__":
    # Step 1: Reset the database
    reset_db()
    
    # Step 2: Create base data
    clients, services, products, staff = populate_base_data()
    
    # Step 3: Create relational data
    populate_relational_data(clients, services, products)
    
    print("Database reset and populated with skin care salon data successfully!")