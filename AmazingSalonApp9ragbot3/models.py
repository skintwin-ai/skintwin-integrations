from replit import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

def create_user(username, email, password, is_staff=False, is_admin=False):
    user_id = f"user_{email}"
    db[user_id] = {
        "username": username,
        "email": email,
        "password_hash": generate_password_hash(password),
        "is_staff": is_staff,
        "is_admin": is_admin,
        "two_factor_enabled": False,
        "two_factor_secret": None
    }
    return user_id

def get_user(user_id):
    user = db.get(user_id)
    if user:
        user['id'] = user_id
    return user

def get_all_users():
    return [db[key] for key in db.prefix("user_")]

def update_user(user_id, **kwargs):
    user = db.get(user_id)
    if user:
        if 'password' in kwargs:
            kwargs['password_hash'] = generate_password_hash(kwargs.pop('password'))
        user.update(kwargs)
        db[user_id] = user
        return True
    return False

def delete_user(user_id):
    if user_id in db:
        del db[user_id]
        return True
    return False

def create_client(name, email, phone):
    client_id = f"client_{email}"
    db[client_id] = {
        'name': name,
        'email': email,
        'phone': phone,
        'loyalty_points': 0,
        'total_spent': 0.0,
        'preferences': {
            'hair_length': 'medium',
            'style_preference': 'classic',
            'color_preference': 'natural',
            'previous_services': []
        },
        'id': client_id  # Include ID for easier access
    }
    return client_id

def get_client(client_id):
    client = db.get(client_id)
    if client:
        client['id'] = client_id
    return client

def get_all_clients():
    clients = []
    for key in db.prefix("client_"):
        client = db[key]
        client['id'] = key
        clients.append(client)
    return clients

def create_appointment(client_id, stylist_id, service, date_time, status="scheduled"):
    appointment_id = f"appointment_{int(datetime.utcnow().timestamp())}"
    db[appointment_id] = {
        "client_id": client_id,
        "stylist_id": stylist_id,
        "service": service,
        "date_time": date_time.isoformat(),
        "status": status
    }
    return appointment_id

def get_appointment(appointment_id):
    return db.get(appointment_id)

def update_appointment(appointment_id, **kwargs):
    appointment = db.get(appointment_id)
    if appointment:
        appointment.update(kwargs)
        db[appointment_id] = appointment
        return True
    return False

def delete_appointment(appointment_id):
    if appointment_id in db:
        del db[appointment_id]
        return True
    return False

def create_transaction(client_id, amount, description, points_used=0):
    transaction_id = f"transaction_{int(datetime.utcnow().timestamp())}"

    # Calculate points earned (1 point per dollar)
    points_earned = int(amount)

    # Update client loyalty info
    client = get_client(client_id)
    if client:
        current_points = client.get('loyalty_points', 0)
        total_spent = client.get('total_spent', 0)

        # Update points and spending
        new_points = current_points + points_earned - points_used
        new_total = total_spent + amount

        # Determine tier based on total spent
        tier = "Bronze"
        if new_total >= 1000:
            tier = "Gold"
        elif new_total >= 500:
            tier = "Silver"

        client.update({
            'loyalty_points': new_points,
            'total_spent': new_total,
            'tier': tier
        })
        db[client_id] = client

    db[transaction_id] = {
        "client_id": client_id,
        "amount": amount,
        "date_time": datetime.utcnow().isoformat(),
        "description": description,
        "points_earned": points_earned,
        "points_used": points_used
    }
    return transaction_id

def get_transaction(transaction_id):
    return db.get(transaction_id)

def get_all_transactions():
    return [db[key] for key in db.prefix("transaction_")]

def create_product(name, description, price, quantity, reorder_level, category=None, supplier=None):
    product_id = f"product_{int(datetime.utcnow().timestamp())}"
    db[product_id] = {
        "id": product_id,  # Add this line
        "name": name,
        "description": description,
        "price": price,
        "quantity": quantity,
        "reorder_level": reorder_level,
        "category": category,
        "supplier": supplier,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    return product_id

def get_product(product_id):
    product = db.get(product_id)
    if product:
        product['id'] = product_id
    return product

def update_product(product_id, **kwargs):
    product = db.get(product_id)
    if product:
        product.update(kwargs)
        product["updated_at"] = datetime.utcnow().isoformat()
        db[product_id] = product
        return True
    return False

def delete_product(product_id):
    if product_id in db:
        del db[product_id]
        return True
    return False

def get_all_products():
    products = []
    for key in db.prefix("product_"):
        product = db[key]
        product['id'] = key
        products.append(product)
    return products

def create_purchase_order(product_id, quantity, supplier=None):
    po_id = f"po_{int(datetime.utcnow().timestamp())}"
    product = get_product(product_id)
    if not product:
        return None

    db[po_id] = {
        "product_id": product_id,
        "product_name": product["name"],
        "quantity": quantity,
        "supplier": supplier or product.get("supplier"),
        "status": "pending",
        "created_at": datetime.utcnow().isoformat()
    }
    return po_id

def get_purchase_order(po_id):
    return db.get(po_id)

def get_all_purchase_orders():
    return [db[key] for key in db.prefix("po_")]

def update_purchase_order_status(po_id, status):
    po = db.get(po_id)
    if po:
        po["status"] = status
        db[po_id] = po
        return True
    return False

def get_low_stock_products():
    return [product for product in get_all_products() if product["quantity"] <= product["reorder_level"]]

def get_all_appointments():
    return [db[key] for key in db.prefix("appointment_")]

def get_product_categories():
    categories = set()
    for product in get_all_products():
        if product.get('category'):
            categories.add(product['category'])
    return list(categories)

def create_service(name, description, price, duration):
    service_id = f"service_{int(datetime.utcnow().timestamp())}"
    db[service_id] = {
        "name": name,
        "description": description,
        "price": price,
        "duration": duration
    }
    return service_id

def get_service(service_id):
    service = db.get(service_id)
    if service:
        service['id'] = service_id
    return service

def get_all_services():
    services = []
    for key in db.prefix("service_"):
        service = db[key]
        service['id'] = key
        services.append(service)
    return services

def update_service(service_id, **kwargs):
    service = db.get(service_id)
    if service:
        service.update(kwargs)
        db[service_id] = service
        return True
    return False

def delete_service(service_id):
    if service_id in db:
        del db[service_id]
        return True
    return False

def create_shift(staff_id, start_time, end_time, breaks=None):
    shift_id = f"shift_{int(datetime.utcnow().timestamp())}"
    
    # Validate break times
    if breaks:
        shift_start = datetime.fromisoformat(start_time)
        shift_end = datetime.fromisoformat(end_time)
        for break_period in breaks:
            break_start = datetime.fromisoformat(break_period['start_time'])
            break_end = datetime.fromisoformat(break_period['end_time'])
            
            # Ensure breaks are within shift
            if not (shift_start <= break_start < break_end <= shift_end):
                raise ValueError("Break times must be within shift hours")
            
            # Ensure breaks don't overlap
            for other_break in breaks:
                if other_break != break_period:
                    other_start = datetime.fromisoformat(other_break['start_time'])
                    other_end = datetime.fromisoformat(other_break['end_time'])
                    if (break_start < other_end and break_end > other_start):
                        raise ValueError("Break times cannot overlap")
    
    db[shift_id] = {
        "staff_id": staff_id,
        "start_time": start_time,
        "end_time": end_time,
        "breaks": breaks or [],
        "status": "scheduled"
    }
    return shift_id

def add_break_to_shift(shift_id, break_start, break_end):
    shift = db.get(shift_id)
    if shift:
        breaks = shift.get('breaks', [])
        breaks.append({
            "start_time": break_start,
            "end_time": break_end
        })
        shift['breaks'] = breaks
        db[shift_id] = shift
        return True
    return False

#New functions for service recommendations
def get_services_by_category(category):
    return [service for service in get_all_services() if service.get('category') == category]

def get_services_by_keywords(keywords):
    keywords = keywords.lower().split()
    return [service for service in get_all_services() if any(keyword in service['name'].lower() or keyword in service['description'].lower() for keyword in keywords)]

def get_popular_services():
    #This would require additional data tracking on service popularity
    #Here's a placeholder that assumes a popularity field
    return sorted(get_all_services(), key=lambda service: service.get('popularity',0), reverse=True)

# Portfolio management functions
def create_portfolio_entry(client_id, service_id, stylist_id, photo_url, notes=""):
    """Create a new portfolio entry for a client"""
    entry_id = f"portfolio_{int(datetime.utcnow().timestamp())}"
    
    # Get service and stylist information
    service = get_service(service_id)
    stylist = get_user(stylist_id)
    
    if not service or not stylist:
        return None
        
    db[entry_id] = {
        "id": entry_id,
        "client_id": client_id,
        "service_id": service_id,
        "service_name": service.get('name', 'Unknown Service'),
        "stylist_id": stylist_id,
        "stylist_name": stylist.get('username', 'Unknown Stylist'),
        "photo_url": photo_url,
        "notes": notes,
        "date_time": datetime.utcnow().isoformat()
    }
    return entry_id

def get_client_portfolio_entries(client_id):
    """Get all portfolio entries for a specific client"""
    entries = []
    for key in db.prefix("portfolio_"):
        entry = db[key]
        if entry.get('client_id') == client_id:
            entries.append(entry)
    
    # Sort by date (newest first)
    return sorted(entries, key=lambda x: x.get('date_time', ''), reverse=True)

def delete_portfolio_entry(entry_id):
    """Delete a portfolio entry"""
    if entry_id in db:
        del db[entry_id]
        return True
    return False

def get_all_portfolio_entries():
    """Get all portfolio entries"""
    entries = []
    for key in db.prefix("portfolio_"):
        entry = db[key]
        entry['id'] = key
        entries.append(entry)
    return entries
def get_client_memories(client_id):
    """Get all memories for a specific client"""
    memories = []
    memory_prefix = f"memory_{client_id}_"
    
    for key in db.prefix(memory_prefix):
        memory = db[key]
        memory['id'] = key
        memories.append(memory)
    
    # Sort by date (newest first)
    return sorted(memories, key=lambda x: x.get('created_at', ''), reverse=True)

def create_client_memory(client_id, memory_type, content, importance=5):
    """Create a new memory for a client"""
    memory_id = f"memory_{client_id}_{int(datetime.utcnow().timestamp())}"
    
    db[memory_id] = {
        "client_id": client_id,
        "memory_type": memory_type,
        "content": content,
        "importance": importance,
        "created_at": datetime.utcnow().isoformat(),
        "last_accessed": None
    }
    
    return db[memory_id]
