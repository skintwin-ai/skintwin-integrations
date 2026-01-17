from database import db_sql
from database_models import (
    User, Client, Service, Appointment, Transaction, 
    Product, PurchaseOrder, Shift, ShiftBreak, PortfolioEntry
)
from werkzeug.security import generate_password_hash
from datetime import datetime
import json

# User functions
def create_user_sql(username, email, password, is_staff=False, is_admin=False):
    """Create a new user in the SQL database"""
    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        is_staff=is_staff,
        is_admin=is_admin,
        two_factor_enabled=False,
        two_factor_secret=None
    )
    db_sql.session.add(user)
    db_sql.session.commit()
    return user

def get_user_by_id_sql(user_id):
    """Get a user by ID from the SQL database"""
    return User.query.get(user_id)

def get_user_by_email_sql(email):
    """Get a user by email from the SQL database"""
    return User.query.filter_by(email=email).first()

def get_all_users_sql():
    """Get all users from the SQL database"""
    return User.query.all()

def update_user_sql(user_id, **kwargs):
    """Update a user in the SQL database"""
    user = User.query.get(user_id)
    if not user:
        return False
    
    if 'password' in kwargs:
        user.password_hash = generate_password_hash(kwargs.pop('password'))
    
    for key, value in kwargs.items():
        if hasattr(user, key):
            setattr(user, key, value)
    
    db_sql.session.commit()
    return True

def delete_user_sql(user_id):
    """Delete a user from the SQL database"""
    user = User.query.get(user_id)
    if not user:
        return False
    
    db_sql.session.delete(user)
    db_sql.session.commit()
    return True

# Client functions
def create_client_sql(name, email, phone):
    """Create a new client in the SQL database"""
    client = Client(
        name=name,
        email=email,
        phone=phone,
        loyalty_points=0,
        total_spent=0.0,
        tier='Bronze',
        hair_length='medium',
        style_preference='classic',
        color_preference='natural'
    )
    db_sql.session.add(client)
    db_sql.session.commit()
    return client

def get_client_sql(client_id):
    """Get a client by ID from the SQL database"""
    return Client.query.get(client_id)

def get_client_by_email_sql(email):
    """Get a client by email from the SQL database"""
    return Client.query.filter_by(email=email).first()

def get_all_clients_sql():
    """Get all clients from the SQL database"""
    return Client.query.all()

def update_client_sql(client_id, **kwargs):
    """Update a client in the SQL database"""
    client = Client.query.get(client_id)
    if not client:
        return False
    
    for key, value in kwargs.items():
        if hasattr(client, key):
            setattr(client, key, value)
    
    db_sql.session.commit()
    return True

def delete_client_sql(client_id):
    """Delete a client from the SQL database"""
    client = Client.query.get(client_id)
    if not client:
        return False
    
    db_sql.session.delete(client)
    db_sql.session.commit()
    return True

# Service functions
def create_service_sql(name, description, price, duration, category=None):
    """Create a new service in the SQL database"""
    service = Service(
        name=name,
        description=description,
        price=price,
        duration=duration,
        category=category,
        popularity=0
    )
    db_sql.session.add(service)
    db_sql.session.commit()
    return service

def get_service_sql(service_id):
    """Get a service by ID from the SQL database"""
    return Service.query.get(service_id)

def get_all_services_sql():
    """Get all services from the SQL database"""
    return Service.query.all()

def update_service_sql(service_id, **kwargs):
    """Update a service in the SQL database"""
    service = Service.query.get(service_id)
    if not service:
        return False
    
    for key, value in kwargs.items():
        if hasattr(service, key):
            setattr(service, key, value)
    
    db_sql.session.commit()
    return True

def delete_service_sql(service_id):
    """Delete a service from the SQL database"""
    service = Service.query.get(service_id)
    if not service:
        return False
    
    db_sql.session.delete(service)
    db_sql.session.commit()
    return True

# Appointment functions
def create_appointment_sql(client_id, stylist_id, service_id, date_time, status="scheduled"):
    """Create a new appointment in the SQL database"""
    appointment = Appointment(
        client_id=client_id,
        stylist_id=stylist_id,
        service_id=service_id,
        date_time=date_time,
        status=status
    )
    db_sql.session.add(appointment)
    db_sql.session.commit()
    return appointment

def get_appointment_sql(appointment_id):
    """Get an appointment by ID from the SQL database"""
    return Appointment.query.get(appointment_id)

def get_all_appointments_sql():
    """Get all appointments from the SQL database"""
    return Appointment.query.all()

def update_appointment_sql(appointment_id, **kwargs):
    """Update an appointment in the SQL database"""
    appointment = Appointment.query.get(appointment_id)
    if not appointment:
        return False
    
    for key, value in kwargs.items():
        if hasattr(appointment, key):
            setattr(appointment, key, value)
    
    db_sql.session.commit()
    return True

def delete_appointment_sql(appointment_id):
    """Delete an appointment from the SQL database"""
    appointment = Appointment.query.get(appointment_id)
    if not appointment:
        return False
    
    db_sql.session.delete(appointment)
    db_sql.session.commit()
    return True

# Transaction functions
def create_transaction_sql(client_id, amount, description, payment_method_id=None, payment_intent_id=None, points_used=0, payment_provider='stripe'):
    """Create a new transaction in the SQL database with payment provider details"""
    # Calculate points earned based on ConfigManager.get_points_per_dollar or default to 1 point per dollar
    points_per_dollar = 1 # Default fallback
    try:
        from utils.config_utils import ConfigManager
        points_per_dollar = ConfigManager.get_points_per_dollar()
    except:
        pass  # Use default if ConfigManager is not available
    
    points_earned = int(amount * points_per_dollar)
    
    transaction = Transaction(
        client_id=client_id,
        amount=amount,
        description=description,
        points_earned=points_earned,
        points_used=points_used,
        payment_method_id=payment_method_id,
        payment_intent_id=payment_intent_id,
        payment_provider=payment_provider,
        payment_status='completed' if payment_intent_id else 'pending'
    )
    db_sql.session.add(transaction)
    
    # Update client loyalty info
    client = Client.query.get(client_id)
    if client:
        client.loyalty_points = client.loyalty_points + points_earned - points_used
        client.total_spent = client.total_spent + amount
        
        # Determine tier based on total spent
        if client.total_spent >= 1000:
            client.tier = 'Gold'
        elif client.total_spent >= 500:
            client.tier = 'Silver'
        else:
            client.tier = 'Bronze'
    
    db_sql.session.commit()
    return transaction

def get_transaction_sql(transaction_id):
    """Get a transaction by ID from the SQL database"""
    return Transaction.query.get(transaction_id)

def get_all_transactions_sql():
    """Get all transactions from the SQL database"""
    return Transaction.query.all()

# Product functions
def create_product_sql(name, description, price, quantity, reorder_level, category=None, supplier=None):
    """Create a new product in the SQL database"""
    product = Product(
        name=name,
        description=description,
        price=price,
        quantity=quantity,
        reorder_level=reorder_level,
        category=category,
        supplier=supplier
    )
    db_sql.session.add(product)
    db_sql.session.commit()
    return product

def get_product_sql(product_id):
    """Get a product by ID from the SQL database"""
    return Product.query.get(product_id)

def get_all_products_sql():
    """Get all products from the SQL database"""
    return Product.query.all()

def update_product_sql(product_id, **kwargs):
    """Update a product in the SQL database"""
    product = Product.query.get(product_id)
    if not product:
        return False
    
    for key, value in kwargs.items():
        if hasattr(product, key):
            setattr(product, key, value)
    
    product.updated_at = datetime.utcnow()
    db_sql.session.commit()
    return True

def delete_product_sql(product_id):
    """Delete a product from the SQL database"""
    product = Product.query.get(product_id)
    if not product:
        return False
    
    db_sql.session.delete(product)
    db_sql.session.commit()
    return True

def get_low_stock_products_sql():
    """Get all products that are low in stock"""
    return Product.query.filter(Product.quantity <= Product.reorder_level).all()

def get_product_categories_sql():
    """Get all unique product categories"""
    categories = db_sql.session.query(Product.category).distinct().all()
    return [c[0] for c in categories if c[0]]

# Purchase Order functions
def create_purchase_order_sql(product_id, quantity, supplier=None):
    """Create a new purchase order in the SQL database"""
    product = Product.query.get(product_id)
    if not product:
        return None
    
    po = PurchaseOrder(
        product_id=product_id,
        quantity=quantity,
        supplier=supplier or product.supplier,
        status='pending'
    )
    db_sql.session.add(po)
    db_sql.session.commit()
    return po

def get_purchase_order_sql(po_id):
    """Get a purchase order by ID from the SQL database"""
    return PurchaseOrder.query.get(po_id)

def get_all_purchase_orders_sql():
    """Get all purchase orders from the SQL database"""
    return PurchaseOrder.query.all()

def update_purchase_order_status_sql(po_id, status):
    """Update a purchase order status in the SQL database"""
    po = PurchaseOrder.query.get(po_id)
    if not po:
        return False
    
    po.status = status
    db_sql.session.commit()
    return True

# Shift functions
def create_shift_sql(staff_id, start_time, end_time, status='scheduled'):
    """Create a new shift in the SQL database"""
    shift = Shift(
        staff_id=staff_id,
        start_time=start_time,
        end_time=end_time,
        status=status
    )
    db_sql.session.add(shift)
    db_sql.session.commit()
    return shift

def add_break_to_shift_sql(shift_id, break_start, break_end):
    """Add a break to a shift in the SQL database"""
    shift = Shift.query.get(shift_id)
    if not shift:
        return False
    
    # Validate break times
    if not (shift.start_time <= break_start < break_end <= shift.end_time):
        return False
    
    # Check for overlapping breaks
    for existing_break in shift.breaks:
        if (break_start < existing_break.end_time and break_end > existing_break.start_time):
            return False
    
    shift_break = ShiftBreak(
        shift_id=shift_id,
        start_time=break_start,
        end_time=break_end
    )
    db_sql.session.add(shift_break)
    db_sql.session.commit()
    return True

# Portfolio functions
def create_portfolio_entry_sql(client_id, service_id, stylist_id, photo_url, notes=""):
    """Create a new portfolio entry in the SQL database"""
    entry = PortfolioEntry(
        client_id=client_id,
        service_id=service_id,
        stylist_id=stylist_id,
        photo_url=photo_url,
        notes=notes
    )
    db_sql.session.add(entry)
    db_sql.session.commit()
    return entry

def get_client_portfolio_entries_sql(client_id):
    """Get all portfolio entries for a specific client"""
    return PortfolioEntry.query.filter_by(client_id=client_id).order_by(PortfolioEntry.date_time.desc()).all()

def delete_portfolio_entry_sql(entry_id):
    """Delete a portfolio entry from the SQL database"""
    entry = PortfolioEntry.query.get(entry_id)
    if not entry:
        return False
    
    db_sql.session.delete(entry)
    db_sql.session.commit()
    return True

def get_all_portfolio_entries_sql():
    """Get all portfolio entries from the SQL database"""
    return PortfolioEntry.query.order_by(PortfolioEntry.date_time.desc()).all()

# Migration functions to help transition from Replit DB to SQL
def migrate_users_to_sql():
    """Migrate users from Replit DB to SQL database"""
    from models import get_all_users
    from replit import db
    
    users_migrated = 0
    for replit_user in get_all_users():
        user_id = replit_user.get('id', '')
        if not user_id.startswith('user_'):
            continue
            
        email = replit_user.get('email', '')
        # Check if user already exists in SQL
        existing_user = get_user_by_email_sql(email)
        if existing_user:
            continue
            
        # Create user in SQL
        new_user = User(
            username=replit_user.get('username', ''),
            email=email,
            password_hash=replit_user.get('password_hash', ''),
            is_staff=replit_user.get('is_staff', False),
            is_admin=replit_user.get('is_admin', False),
            two_factor_enabled=replit_user.get('two_factor_enabled', False),
            two_factor_secret=replit_user.get('two_factor_secret', None)
        )
        db_sql.session.add(new_user)
        users_migrated += 1
    
    db_sql.session.commit()
    return users_migrated

def migrate_clients_to_sql():
    """Migrate clients from Replit DB to SQL database"""
    from models import get_all_clients
    
    clients_migrated = 0
    for replit_client in get_all_clients():
        email = replit_client.get('email', '')
        # Check if client already exists in SQL
        existing_client = get_client_by_email_sql(email)
        if existing_client:
            continue
            
        # Create client in SQL
        new_client = Client(
            name=replit_client.get('name', ''),
            email=email,
            phone=replit_client.get('phone', ''),
            loyalty_points=replit_client.get('loyalty_points', 0),
            total_spent=replit_client.get('total_spent', 0.0),
            tier=replit_client.get('tier', 'Bronze'),
            hair_length=replit_client.get('preferences', {}).get('hair_length', 'medium'),
            style_preference=replit_client.get('preferences', {}).get('style_preference', 'classic'),
            color_preference=replit_client.get('preferences', {}).get('color_preference', 'natural')
        )
        db_sql.session.add(new_client)
        clients_migrated += 1
    
    db_sql.session.commit()
    return clients_migrated

def migrate_data():
    """Migrate data from Replit DB to SQL database"""
    try:
        # Migrate users
        users_migrated = migrate_users_to_sql()
        print(f"Migrated {users_migrated} users to SQL database")
        
        # Migrate clients
        clients_migrated = migrate_clients_to_sql()
        print(f"Migrated {clients_migrated} clients to SQL database")
        
        # More migrations can be added here as needed
        
        return True
    except Exception as e:
        print(f"Error during migration: {e}")
        return False
