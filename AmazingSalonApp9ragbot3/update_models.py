"""
This script updates the models.py functions to use the SQLAlchemy database
instead of Replit DB. It keeps the same function signatures but changes the
implementation to use the SQL database.
"""

# Import these when function is called to avoid circular imports
import models
from database_models import User, Client, Service, Appointment, Transaction, Product, PurchaseOrder, Shift, ShiftBreak, PortfolioEntry
from database_utils import (
    get_all_products_sql, get_low_stock_products_sql, get_product_categories_sql,
    get_all_users_sql, get_user_by_id_sql, get_user_by_email_sql,
    get_all_clients_sql, get_client_sql, get_client_by_email_sql,
    get_all_services_sql, get_service_sql,
    get_all_appointments_sql, get_appointment_sql,
    get_all_transactions_sql, get_transaction_sql,
    get_all_purchase_orders_sql, get_purchase_order_sql,
    get_all_portfolio_entries_sql, get_client_portfolio_entries_sql
)
import models

def apply_sql_functions_to_models():
    """
    Replace the Replit DB functions in models.py with SQL functions
    """
    # Import inside function to avoid circular imports
    from app import app, db_sql
    from database_utils import (
        get_all_products_sql, get_low_stock_products_sql, get_product_categories_sql,
        get_all_users_sql, get_user_by_id_sql, get_user_by_email_sql,
        get_all_clients_sql, get_client_sql, get_client_by_email_sql,
        get_all_services_sql, get_service_sql,
        get_all_appointments_sql, get_appointment_sql,
        get_all_transactions_sql, get_transaction_sql,
        get_all_purchase_orders_sql, get_purchase_order_sql,
        get_all_portfolio_entries_sql, get_client_portfolio_entries_sql
    )
    import models
    
    print("Updating models.py to use SQL functions...")
    
    # Replace product functions
    models.get_all_products = get_all_products_wrapper
    models.get_low_stock_products = get_low_stock_products_wrapper
    models.get_product_categories = get_product_categories_wrapper
    models.get_product = get_product_wrapper
    models.update_product = update_product_wrapper
    models.delete_product = delete_product_wrapper
    
    # Replace user functions
    models.get_all_users = get_all_users_wrapper
    models.get_user = get_user_wrapper
    
    # Replace client functions
    models.get_all_clients = get_all_clients_wrapper
    models.get_client = get_client_wrapper
    
    # Replace service functions
    models.get_all_services = get_all_services_wrapper
    models.get_service = get_service_wrapper
    
    # Replace appointment functions
    models.get_all_appointments = get_all_appointments_wrapper
    models.get_appointment = get_appointment_wrapper
    
    # Replace transaction functions
    models.get_all_transactions = get_all_transactions_wrapper
    models.get_transaction = get_transaction_wrapper
    
    # Replace purchase order functions
    models.get_all_purchase_orders = get_all_purchase_orders_wrapper
    models.get_purchase_order = get_purchase_order_wrapper
    
    # Replace portfolio functions
    models.get_all_portfolio_entries = get_all_portfolio_entries_wrapper
    models.get_client_portfolio_entries = get_client_portfolio_entries_wrapper
    
    print("Updates completed. The application will now use SQL database for these functions.")

# Product wrappers
def get_all_products_wrapper():
    """Wrapper for get_all_products_sql that ensures backward compatibility"""
    products = get_all_products_sql()
    return [product_to_dict(p) for p in products]

def get_product_wrapper(product_id):
    """Wrapper for get_product_sql that ensures backward compatibility"""
    from database_utils import get_product_sql
    product = get_product_sql(product_id)
    if product:
        return product_to_dict(product)
    return None

def update_product_wrapper(product_id, **kwargs):
    """Wrapper for update_product_sql that ensures backward compatibility"""
    from database_utils import update_product_sql
    return update_product_sql(product_id, **kwargs)

def delete_product_wrapper(product_id):
    """Wrapper for delete_product_sql that ensures backward compatibility"""
    from database_utils import delete_product_sql
    return delete_product_sql(product_id)

def get_low_stock_products_wrapper():
    """Wrapper for get_low_stock_products_sql that ensures backward compatibility"""
    products = get_low_stock_products_sql()
    return [product_to_dict(p) for p in products]

def get_product_categories_wrapper():
    """Wrapper for get_product_categories_sql that ensures backward compatibility"""
    return get_product_categories_sql()

# User wrappers
def get_all_users_wrapper():
    """Wrapper for get_all_users_sql that ensures backward compatibility"""
    users = get_all_users_sql()
    return [user_to_dict(u) for u in users]

def get_user_wrapper(user_id):
    """Wrapper for get_user_by_id_sql that ensures backward compatibility"""
    user = get_user_by_id_sql(user_id)
    if user:
        return user_to_dict(user)
    return None

# Client wrappers
def get_all_clients_wrapper():
    """Wrapper for get_all_clients_sql that ensures backward compatibility"""
    clients = get_all_clients_sql()
    return [client_to_dict(c) for c in clients]

def get_client_wrapper(client_id):
    """Wrapper for get_client_sql that ensures backward compatibility"""
    client = get_client_sql(client_id)
    if client:
        return client_to_dict(client)
    return None

# Service wrappers
def get_all_services_wrapper():
    """Wrapper for get_all_services_sql that ensures backward compatibility"""
    services = get_all_services_sql()
    return [service_to_dict(s) for s in services]

def get_service_wrapper(service_id):
    """Wrapper for get_service_sql that ensures backward compatibility"""
    service = get_service_sql(service_id)
    if service:
        return service_to_dict(service)
    return None

# Appointment wrappers
def get_all_appointments_wrapper():
    """Wrapper for get_all_appointments_sql that ensures backward compatibility"""
    appointments = get_all_appointments_sql()
    return [appointment_to_dict(a) for a in appointments]

def get_appointment_wrapper(appointment_id):
    """Wrapper for get_appointment_sql that ensures backward compatibility"""
    appointment = get_appointment_sql(appointment_id)
    if appointment:
        return appointment_to_dict(appointment)
    return None

# Transaction wrappers
def get_all_transactions_wrapper():
    """Wrapper for get_all_transactions_sql that ensures backward compatibility"""
    transactions = get_all_transactions_sql()
    return [transaction_to_dict(t) for t in transactions]

def get_transaction_wrapper(transaction_id):
    """Wrapper for get_transaction_sql that ensures backward compatibility"""
    transaction = get_transaction_sql(transaction_id)
    if transaction:
        return transaction_to_dict(transaction)
    return None

# Purchase order wrappers
def get_all_purchase_orders_wrapper():
    """Wrapper for get_all_purchase_orders_sql that ensures backward compatibility"""
    purchase_orders = get_all_purchase_orders_sql()
    return [purchase_order_to_dict(po) for po in purchase_orders]

def get_purchase_order_wrapper(po_id):
    """Wrapper for get_purchase_order_sql that ensures backward compatibility"""
    po = get_purchase_order_sql(po_id)
    if po:
        return purchase_order_to_dict(po)
    return None

# Portfolio wrappers
def get_all_portfolio_entries_wrapper():
    """Wrapper for get_all_portfolio_entries_sql that ensures backward compatibility"""
    entries = get_all_portfolio_entries_sql()
    return [portfolio_entry_to_dict(e) for e in entries]

def get_client_portfolio_entries_wrapper(client_id):
    """Wrapper for get_client_portfolio_entries_sql that ensures backward compatibility"""
    entries = get_client_portfolio_entries_sql(client_id)
    return [portfolio_entry_to_dict(e) for e in entries]

# Dictionary conversion functions
def product_to_dict(product):
    """Convert a SQLAlchemy Product model to a dictionary"""
    return {
        'id': product.id,
        'name': product.name,
        'description': product.description,
        'price': product.price,
        'quantity': product.quantity,
        'reorder_level': product.reorder_level,
        'category': product.category,
        'supplier': product.supplier,
        'created_at': product.created_at.isoformat() if product.created_at else None,
        'updated_at': product.updated_at.isoformat() if product.updated_at else None
    }

def user_to_dict(user):
    """Convert a SQLAlchemy User model to a dictionary"""
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'is_staff': user.is_staff,
        'is_admin': user.is_admin,
        'two_factor_enabled': user.two_factor_enabled,
        'created_at': user.created_at.isoformat() if user.created_at else None
    }

def client_to_dict(client):
    """Convert a SQLAlchemy Client model to a dictionary"""
    return {
        'id': client.id,
        'name': client.name,
        'email': client.email,
        'phone': client.phone,
        'loyalty_points': client.loyalty_points,
        'total_spent': client.total_spent,
        'tier': client.tier,
        'created_at': client.created_at.isoformat() if client.created_at else None,
        'hair_length': client.hair_length,
        'style_preference': client.style_preference,
        'color_preference': client.color_preference
    }

def service_to_dict(service):
    """Convert a SQLAlchemy Service model to a dictionary"""
    return {
        'id': service.id,
        'name': service.name,
        'description': service.description,
        'price': service.price,
        'duration': service.duration,
        'category': service.category,
        'popularity': service.popularity,
        'created_at': service.created_at.isoformat() if service.created_at else None
    }

def appointment_to_dict(appointment):
    """Convert a SQLAlchemy Appointment model to a dictionary"""
    return {
        'id': appointment.id,
        'client_id': appointment.client_id,
        'stylist_id': appointment.stylist_id, 
        'service_id': appointment.service_id,
        'date_time': appointment.date_time.isoformat() if appointment.date_time else None,
        'status': appointment.status,
        'created_at': appointment.created_at.isoformat() if appointment.created_at else None,
        'client_name': appointment.client.name if appointment.client else None,
        'stylist_name': appointment.stylist.username if appointment.stylist else None,
        'service_name': appointment.service_rel.name if appointment.service_rel else None
    }

def transaction_to_dict(transaction):
    """Convert a SQLAlchemy Transaction model to a dictionary"""
    return {
        'id': transaction.id,
        'client_id': transaction.client_id,
        'amount': transaction.amount,
        'date_time': transaction.date_time.isoformat() if transaction.date_time else None,
        'description': transaction.description,
        'points_earned': transaction.points_earned,
        'points_used': transaction.points_used,
        'client_name': transaction.client.name if transaction.client else None
    }

def purchase_order_to_dict(po):
    """Convert a SQLAlchemy PurchaseOrder model to a dictionary"""
    return {
        'id': po.id,
        'product_id': po.product_id,
        'quantity': po.quantity,
        'supplier': po.supplier,
        'status': po.status,
        'created_at': po.created_at.isoformat() if po.created_at else None,
        'product_name': po.product.name if po.product else None
    }

def portfolio_entry_to_dict(entry):
    """Convert a SQLAlchemy PortfolioEntry model to a dictionary"""
    return {
        'id': entry.id,
        'client_id': entry.client_id,
        'service_id': entry.service_id,
        'stylist_id': entry.stylist_id,
        'photo_url': entry.photo_url,
        'notes': entry.notes,
        'date_time': entry.date_time.isoformat() if entry.date_time else None,
        'client_name': entry.client.name if entry.client else None,
        'service_name': entry.service_rel.name if entry.service_rel else None,
        'stylist_name': entry.stylist.username if entry.stylist else None
    }

if __name__ == '__main__':
    with app.app_context():
        apply_sql_functions_to_models()