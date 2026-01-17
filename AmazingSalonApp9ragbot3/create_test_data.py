import os
from app import app, db_sql
from database_models import (
    User, Client, Service, Appointment, Transaction, 
    Product, PurchaseOrder, Shift, ShiftBreak, PortfolioEntry
)
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import random

def create_test_data():
    """
    Create test data for all entities in the database
    """
    with app.app_context():
        # Create additional staff users
        create_staff_users()
        # Create test clients
        clients = create_test_clients()
        # Create services
        services = create_test_services()
        # Create products
        products = create_test_products()
        # Create purchase orders
        create_test_purchase_orders(products)
        # Create shifts for staff
        create_test_shifts()
        # Create appointments
        create_test_appointments(clients, services)
        # Create transactions
        create_test_transactions(clients)
        # Create portfolio entries
        create_test_portfolio_entries(clients, services)

def create_staff_users():
    """Create test staff users"""
    # Check if users already exist
    if User.query.count() <= 1:  # If only admin exists
        staff_users = [
            {
                "username": "Jennifer",
                "email": "jennifer@salon.dev",
                "password": "staff123",
                "is_staff": True,
                "is_admin": False
            },
            {
                "username": "Michael",
                "email": "michael@salon.dev",
                "password": "staff123",
                "is_staff": True,
                "is_admin": False
            },
            {
                "username": "Sarah",
                "email": "sarah@salon.dev",
                "password": "staff123",
                "is_staff": True,
                "is_admin": False
            }
        ]
        
        for user_data in staff_users:
            user = User(
                username=user_data["username"],
                email=user_data["email"],
                password_hash=generate_password_hash(user_data["password"]),
                is_staff=user_data["is_staff"],
                is_admin=user_data["is_admin"]
            )
            db_sql.session.add(user)
        
        db_sql.session.commit()
        print(f"Created {len(staff_users)} staff users")

def create_test_clients():
    """Create test clients"""
    # Check if clients already exist
    if Client.query.count() == 0:
        clients_data = [
            {
                "name": "Emma Johnson",
                "email": "emma@example.com",
                "phone": "555-1234",
                "skin_type": "dry",
                "skin_concern": "aging",
                "sensitivity_level": "medium"
            },
            {
                "name": "James Smith",
                "email": "james@example.com",
                "phone": "555-2345",
                "skin_type": "oily",
                "skin_concern": "acne",
                "sensitivity_level": "low"
            },
            {
                "name": "Sophia Williams",
                "email": "sophia@example.com",
                "phone": "555-3456",
                "skin_type": "combination",
                "skin_concern": "pigmentation",
                "sensitivity_level": "medium"
            },
            {
                "name": "Oliver Brown",
                "email": "oliver@example.com",
                "phone": "555-4567",
                "skin_type": "normal",
                "skin_concern": "texture",
                "sensitivity_level": "low"
            },
            {
                "name": "Ava Jones",
                "email": "ava@example.com",
                "phone": "555-5678",
                "skin_type": "sensitive",
                "skin_concern": "redness",
                "sensitivity_level": "high"
            },
            {
                "name": "Liam Wilson",
                "email": "liam@example.com",
                "phone": "555-6789",
                "skin_type": "combination",
                "skin_concern": "acne",
                "sensitivity_level": "medium"
            },
            {
                "name": "Charlotte Miller",
                "email": "charlotte@example.com",
                "phone": "555-7890",
                "skin_type": "dry",
                "skin_concern": "hydration",
                "sensitivity_level": "high"
            },
            {
                "name": "Ethan Davis",
                "email": "ethan@example.com",
                "phone": "555-8901",
                "skin_type": "oily",
                "skin_concern": "texture",
                "sensitivity_level": "low"
            },
            {
                "name": "Amelia Garcia",
                "email": "amelia@example.com",
                "phone": "555-9012",
                "skin_type": "sensitive",
                "skin_concern": "sensitivity",
                "sensitivity_level": "high"
            },
            {
                "name": "Noah Rodriguez",
                "email": "noah@example.com",
                "phone": "555-0123",
                "skin_type": "combination",
                "skin_concern": "aging",
                "sensitivity_level": "medium"
            }
        ]
        
        created_clients = []
        for client_data in clients_data:
            client = Client(
                name=client_data["name"],
                email=client_data["email"],
                phone=client_data["phone"],
                skin_type=client_data["skin_type"],
                skin_concern=client_data["skin_concern"],
                sensitivity_level=client_data["sensitivity_level"],
                loyalty_points=random.randint(0, 500),
                total_spent=random.uniform(0.0, 1000.0),
                tier="Bronze" if random.random() < 0.6 else ("Silver" if random.random() < 0.8 else "Gold")
            )
            db_sql.session.add(client)
            created_clients.append(client)
        
        db_sql.session.commit()
        print(f"Created {len(clients_data)} clients")
        return created_clients
    
    return Client.query.all()

def create_test_services():
    """Create test services"""
    # Check if services already exist
    if Service.query.count() == 0:
        services_data = [
            {
                "name": "Basic European Facial",
                "description": "Traditional deep cleansing, exfoliation, and extraction for all skin types",
                "price": 65.0,
                "duration": 45,
                "category": "Essential Facial"
            },
            {
                "name": "Hydrating Hyaluronic Treatment",
                "description": "Intensive multi-layer hydration protocol for dry or dehydrated skin",
                "price": 85.0,
                "duration": 60,
                "category": "Specialized Facial"
            },
            {
                "name": "Anti-Aging Collagen Treatment",
                "description": "Targets fine lines and wrinkles with peptides and growth factors",
                "price": 110.0,
                "duration": 75,
                "category": "Anti-Aging"
            },
            {
                "name": "Clinical Acne Management",
                "description": "Medical-grade treatment with salicylic acid and targeted extraction for acne-prone skin",
                "price": 95.0,
                "duration": 60,
                "category": "Clinical Treatment"
            },
            {
                "name": "Chemical Peel - Glycolic",
                "description": "Alpha hydroxy acid exfoliation for cellular renewal and texture improvement",
                "price": 90.0,
                "duration": 45,
                "category": "Chemical Peel"
            },
            {
                "name": "Chemical Peel - TCA",
                "description": "Medium-depth trichloroacetic acid peel for pigmentation and visible skin concerns",
                "price": 120.0,
                "duration": 60,
                "category": "Chemical Peel"
            },
            {
                "name": "Diamond Microdermabrasion",
                "description": "Controlled physical exfoliation for smoother skin texture and tone",
                "price": 100.0,
                "duration": 45,
                "category": "Exfoliation"
            },
            {
                "name": "LED Phototherapy",
                "description": "Multi-spectrum light treatment for acne, inflammation, or collagen stimulation",
                "price": 75.0,
                "duration": 30,
                "category": "Advanced Treatment"
            },
            {
                "name": "Dermaplaning",
                "description": "Physical exfoliation with surgical blade to remove dead skin cells and peach fuzz",
                "price": 85.0,
                "duration": 45,
                "category": "Exfoliation"
            },
            {
                "name": "Oxygen Infusion Facial",
                "description": "Pressurized oxygen treatment to deliver specialized serums deep into the skin",
                "price": 95.0,
                "duration": 60,
                "category": "Specialized Facial"
            },
            {
                "name": "Microneedling",
                "description": "Collagen induction therapy with fine needles to stimulate skin regeneration",
                "price": 200.0,
                "duration": 90,
                "category": "Advanced Treatment"
            },
            {
                "name": "HydraFacial Treatment",
                "description": "Multi-step cleansing, exfoliation, extraction, and hydration with vortex technology",
                "price": 150.0,
                "duration": 60,
                "category": "Signature Treatment"
            },
            {
                "name": "Skin Analysis & Consultation",
                "description": "In-depth computerized skin analysis and personalized treatment planning",
                "price": 45.0,
                "duration": 30,
                "category": "Consultation"
            },
            {
                "name": "Skin Transformation Package",
                "description": "Comprehensive 4-treatment protocol with custom home care regimen",
                "price": 550.0,
                "duration": 240,
                "category": "Treatment Package"
            }
        ]
        
        created_services = []
        for service_data in services_data:
            service = Service(
                name=service_data["name"],
                description=service_data["description"],
                price=service_data["price"],
                duration=service_data["duration"],
                category=service_data["category"],
                popularity=random.randint(0, 100)
            )
            db_sql.session.add(service)
            created_services.append(service)
        
        db_sql.session.commit()
        print(f"Created {len(services_data)} services")
        return created_services
    
    return Service.query.all()

def create_test_products():
    """Create test products"""
    # Check if products already exist
    if Product.query.count() == 0:
        products_data = [
            {
                "name": "Gentle Cream Cleanser",
                "description": "pH-balanced cream cleanser for sensitive skin types",
                "price": 28.99,
                "quantity": 50,
                "reorder_level": 10,
                "category": "Cleanser",
                "supplier": "Pure Skin Labs"
            },
            {
                "name": "Foaming Enzyme Cleanser",
                "description": "Papaya enzyme cleanser for normal to oily skin",
                "price": 32.99,
                "quantity": 45,
                "reorder_level": 10,
                "category": "Cleanser",
                "supplier": "Pure Skin Labs"
            },
            {
                "name": "Micellar Cleansing Water",
                "description": "No-rinse cleansing solution for all skin types",
                "price": 24.99,
                "quantity": 38,
                "reorder_level": 8,
                "category": "Cleanser",
                "supplier": "Advanced Skincare Inc."
            },
            {
                "name": "Hyaluronic Acid Moisturizer",
                "description": "Multi-weight hyaluronic acid complex for deep hydration",
                "price": 42.99,
                "quantity": 45,
                "reorder_level": 10,
                "category": "Moisturizer",
                "supplier": "Pure Skin Labs"
            },
            {
                "name": "Ceramide Barrier Cream",
                "description": "Barrier-repair moisturizer for compromised skin",
                "price": 46.99,
                "quantity": 30,
                "reorder_level": 8,
                "category": "Moisturizer",
                "supplier": "Advanced Skincare Inc."
            },
            {
                "name": "Oil-Free Mattifying Lotion",
                "description": "Lightweight hydration with sebum control for oily skin",
                "price": 38.99,
                "quantity": 35,
                "reorder_level": 8,
                "category": "Moisturizer",
                "supplier": "Advanced Skincare Inc."
            },
            {
                "name": "20% Vitamin C + E Serum",
                "description": "Stabilized L-ascorbic acid with ferulic acid for brightening",
                "price": 68.99,
                "quantity": 25,
                "reorder_level": 6,
                "category": "Serum",
                "supplier": "Advanced Skincare Inc."
            },
            {
                "name": "Tranexamic Acid Serum",
                "description": "Targets hyperpigmentation and uneven skin tone",
                "price": 56.99,
                "quantity": 22,
                "reorder_level": 5,
                "category": "Serum",
                "supplier": "Advanced Skincare Inc."
            },
            {
                "name": "0.3% Retinol Night Treatment",
                "description": "Encapsulated retinol with peptides for overnight renewal",
                "price": 72.99,
                "quantity": 20,
                "reorder_level": 5,
                "category": "Treatment",
                "supplier": "Advanced Skincare Inc."
            },
            {
                "name": "Mineral SPF 50 Sunscreen",
                "description": "Zinc oxide and titanium dioxide broad-spectrum protection",
                "price": 36.99,
                "quantity": 40,
                "reorder_level": 12,
                "category": "Sun Protection",
                "supplier": "Pure Skin Labs"
            },
            {
                "name": "Tinted SPF 40 Moisturizer",
                "description": "Light coverage with mineral sun protection",
                "price": 42.99,
                "quantity": 25,
                "reorder_level": 8,
                "category": "Sun Protection",
                "supplier": "Pure Skin Labs"
            },
            {
                "name": "Kaolin Clay Detox Mask",
                "description": "Deep pore cleansing with charcoal for congested skin",
                "price": 34.99,
                "quantity": 25,
                "reorder_level": 7,
                "category": "Mask",
                "supplier": "Natural Beauty Co."
            },
            {
                "name": "Hydrojelly Mask",
                "description": "Professional-grade alginate mask for intense hydration",
                "price": 12.99,
                "quantity": 48,
                "reorder_level": 15,
                "category": "Mask",
                "supplier": "Natural Beauty Co."
            },
            {
                "name": "AHA/BHA Exfoliating Toner",
                "description": "Multi-acid exfoliation with hydrating ingredients",
                "price": 32.99,
                "quantity": 30,
                "reorder_level": 8,
                "category": "Toner",
                "supplier": "Advanced Skincare Inc."
            },
            {
                "name": "Cica Peptide Eye Cream",
                "description": "Centella asiatica and peptides for eye area rejuvenation",
                "price": 48.99,
                "quantity": 20,
                "reorder_level": 5,
                "category": "Eye Care",
                "supplier": "Advanced Skincare Inc."
            },
            {
                "name": "10% Niacinamide Serum",
                "description": "Pore-refining and oil control with zinc PCA",
                "price": 42.99,
                "quantity": 28,
                "reorder_level": 7,
                "category": "Serum",
                "supplier": "Natural Beauty Co."
            },
            {
                "name": "Professional Treatment Spatulas",
                "description": "Stainless steel application tools for estheticians",
                "price": 18.99,
                "quantity": 15,
                "reorder_level": 5,
                "category": "Tools",
                "supplier": "Esthetician Supply Co."
            },
            {
                "name": "Extraction Tools Kit",
                "description": "Professional-grade stainless steel extraction instruments",
                "price": 34.99,
                "quantity": 10,
                "reorder_level": 3,
                "category": "Tools",
                "supplier": "Esthetician Supply Co."
            }
        ]
        
        created_products = []
        for product_data in products_data:
            product = Product(
                name=product_data["name"],
                description=product_data["description"],
                price=product_data["price"],
                quantity=product_data["quantity"],
                reorder_level=product_data["reorder_level"],
                category=product_data["category"],
                supplier=product_data["supplier"]
            )
            db_sql.session.add(product)
            created_products.append(product)
        
        db_sql.session.commit()
        print(f"Created {len(products_data)} products")
        return created_products
    
    return Product.query.all()

def create_test_purchase_orders(products):
    """Create test purchase orders"""
    # Check if purchase orders already exist
    if PurchaseOrder.query.count() == 0 and products:
        # Create purchase orders for some products
        for _ in range(5):
            product = random.choice(products)
            purchase_order = PurchaseOrder(
                product_id=product.id,
                quantity=random.randint(10, 30),
                supplier=product.supplier,
                status=random.choice(['pending', 'ordered', 'received'])
            )
            db_sql.session.add(purchase_order)
        
        db_sql.session.commit()
        print("Created 5 purchase orders")

def create_test_shifts():
    """Create test shifts for staff"""
    # Check if shifts already exist
    if Shift.query.count() == 0:
        # Get staff users
        staff_users = User.query.filter_by(is_staff=True).all()
        if staff_users:
            # Start date for shifts (today)
            start_date = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
            
            # Create shifts for the next 7 days
            for day in range(7):
                day_date = start_date + timedelta(days=day)
                
                for staff in staff_users:
                    # Morning shift
                    if random.random() < 0.7:  # 70% chance to have a shift
                        shift_start = day_date
                        shift_end = day_date.replace(hour=17)  # 9 AM to 5 PM
                        
                        shift = Shift(
                            staff_id=staff.id,
                            start_time=shift_start,
                            end_time=shift_end,
                            status='scheduled'
                        )
                        db_sql.session.add(shift)
                        
                        # Add breaks
                        if random.random() < 0.8:  # 80% chance to have a lunch break
                            break_start = shift_start.replace(hour=12)  # 12 PM
                            break_end = shift_start.replace(hour=13)    # 1 PM
                            
                            shift_break = ShiftBreak(
                                shift=shift,
                                start_time=break_start,
                                end_time=break_end
                            )
                            db_sql.session.add(shift_break)
            
            db_sql.session.commit()
            print(f"Created shifts for {len(staff_users)} staff members over 7 days")

def create_test_appointments(clients, services):
    """Create test appointments"""
    # Check if appointments already exist
    if Appointment.query.count() == 0 and clients and services:
        # Get staff users
        staff_users = User.query.filter_by(is_staff=True).all()
        if staff_users:
            # Start date for appointments (today)
            start_date = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
            
            # Define skin care specific service categories for intelligent booking
            facial_services = [s for s in services if "Facial" in s.category or "facial" in s.name.lower()]
            peel_services = [s for s in services if "Peel" in s.category or "peel" in s.name.lower()]
            treatment_services = [s for s in services if "Treatment" in s.category]
            advanced_services = [s for s in services if "Advanced" in s.category]
            
            # Create appointments for the next 7 days
            for day in range(7):
                day_date = start_date + timedelta(days=day)
                
                # Create 3-5 appointments per day
                for _ in range(random.randint(3, 5)):
                    client = random.choice(clients)
                    staff = random.choice(staff_users)
                    
                    # If the client has a specific skin concern, match them with an appropriate service
                    if hasattr(client, 'skin_concern') and client.skin_concern:
                        if client.skin_concern == 'acne':
                            # Client has acne concerns, prioritize acne treatments
                            relevant_services = [s for s in services if "acne" in s.name.lower() or "clarifying" in s.description.lower()]
                            service = random.choice(relevant_services) if relevant_services else random.choice(services)
                        elif client.skin_concern == 'aging':
                            # Client has aging concerns, prioritize anti-aging treatments
                            relevant_services = [s for s in services if "anti-aging" in s.name.lower() or "wrinkle" in s.description.lower() or "collagen" in s.description.lower()]
                            service = random.choice(relevant_services) if relevant_services else random.choice(services)
                        elif client.skin_concern == 'hydration':
                            # Client has hydration concerns, prioritize hydrating treatments
                            relevant_services = [s for s in services if "hydra" in s.name.lower() or "moisturizing" in s.description.lower() or "dry" in s.description.lower()]
                            service = random.choice(relevant_services) if relevant_services else random.choice(services)
                        elif client.skin_concern == 'pigmentation':
                            # Client has pigmentation concerns, prioritize brightening treatments
                            relevant_services = [s for s in services if "bright" in s.name.lower() or "pigment" in s.description.lower() or "even" in s.description.lower()]
                            service = random.choice(relevant_services) if relevant_services else random.choice(services)
                        elif client.skin_concern == 'sensitivity':
                            # Client has sensitive skin, prioritize gentle treatments
                            relevant_services = [s for s in services if "gentle" in s.name.lower() or "calm" in s.description.lower() or "sensitive" in s.description.lower()]
                            service = random.choice(relevant_services) if relevant_services else random.choice(services)
                        elif client.skin_concern == 'texture':
                            # Client has texture concerns, prioritize exfoliating treatments
                            relevant_services = [s for s in services if "texture" in s.name.lower() or "exfol" in s.description.lower() or "smooth" in s.description.lower()]
                            service = random.choice(relevant_services) if relevant_services else random.choice(services)
                        elif client.skin_concern == 'redness':
                            # Client has redness concerns, prioritize soothing treatments
                            relevant_services = [s for s in services if "sooth" in s.name.lower() or "calm" in s.description.lower() or "redness" in s.description.lower()]
                            service = random.choice(relevant_services) if relevant_services else random.choice(services)
                        else:
                            # Default to a random service if no specific concern matching
                            service = random.choice(services)
                    else:
                        # No specific skin concern data, choose random service
                        service = random.choice(services)
                    
                    # Random hour between 9 AM and 4 PM
                    hour = random.randint(9, 16)
                    minute = random.choice([0, 15, 30, 45])
                    
                    appointment_time = day_date.replace(hour=hour, minute=minute)
                    
                    # Determine status based on date
                    if day_date.date() < datetime.now().date():
                        status = random.choice(['completed', 'no-show'])
                    else:
                        status = 'scheduled'
                    
                    appointment = Appointment(
                        client_id=client.id,
                        esthetician_id=staff.id,
                        service_id=service.id,
                        date_time=appointment_time,
                        status=status
                    )
                    db_sql.session.add(appointment)
            
            db_sql.session.commit()
            print("Created appointments for the next 7 days")

def create_test_transactions(clients):
    """Create test transactions"""
    # Check if transactions already exist
    if Transaction.query.count() == 0 and clients:
        # Create transactions for clients
        for client in clients:
            # 1-3 transactions per client
            for _ in range(random.randint(1, 3)):
                amount = random.uniform(30.0, 200.0)
                points_earned = int(amount / 10)  # 1 point per $10 spent
                
                transaction = Transaction(
                    client_id=client.id,
                    amount=amount,
                    date_time=datetime.now() - timedelta(days=random.randint(1, 30)),
                    description=f"Service and/or product purchase",
                    points_earned=points_earned,
                    points_used=0
                )
                db_sql.session.add(transaction)
        
        db_sql.session.commit()
        print(f"Created transactions for {len(clients)} clients")

def create_test_portfolio_entries(clients, services):
    """Create test portfolio entries"""
    # Check if portfolio entries already exist
    if PortfolioEntry.query.count() == 0 and clients and services:
        # Get staff users
        staff_users = User.query.filter_by(is_staff=True).all()
        if staff_users:
            # Create 1-2 portfolio entries per client
            for client in clients:
                if random.random() < 0.7:  # 70% chance to have a portfolio entry
                    for _ in range(random.randint(1, 2)):
                        service = random.choice(services)
                        staff = random.choice(staff_users)
                        
                        # Use a placeholder image URL
                        photo_url = "/static/img/default_style.jpg"
                        
                        # Create more detailed skin care focused notes
                        skin_descriptions = [
                            "Improved texture and tone",
                            "Reduction in congestion and breakouts",
                            "Visible improvement in hydration levels",
                            "Significant reduction in hyperpigmentation",
                            "Decreased redness and irritation",
                            "Enhanced skin barrier function",
                            "Diminished appearance of fine lines",
                            "Noticeable improvement in skin firmness",
                            "Reduced pore visibility",
                            "Balanced oil production"
                        ]
                        
                        treatment_details = [
                            "using gentle extraction technique",
                            "incorporating LED therapy for enhanced results",
                            "followed by cooling cryotherapy",
                            "with specialized massage techniques",
                            "using medical-grade ingredients",
                            "with customized serum infusion",
                            "combined with ultrasonic technology",
                            "adapting protocol for sensitive areas",
                            "with progressive treatment intensity",
                            "using cutting-edge peptide technology"
                        ]
                        
                        outcome_notes = [
                            "Client extremely satisfied with results",
                            "Treatment exceeded expectations",
                            "Client has booked a series of follow-up treatments",
                            "Recommended modified home care regimen",
                            "No adverse reactions during or post-treatment",
                            "Will progress to more intensive treatment next session",
                            "Photos document significant improvement from baseline",
                            "Client reported receiving compliments on skin appearance",
                            "Marked improvement compared to previous treatment",
                            "Skin analysis shows measurable improvement in hydration metrics"
                        ]
                        
                        notes = f"Client received {service.name} with {random.choice(treatment_details)}. Results show {random.choice(skin_descriptions).lower()}. {random.choice(outcome_notes)}."
                        
                        portfolio_entry = PortfolioEntry(
                            client_id=client.id,
                            service_id=service.id,
                            esthetician_id=staff.id,
                            photo_url=photo_url,
                            notes=notes,
                            date_time=datetime.now() - timedelta(days=random.randint(1, 60))
                        )
                        db_sql.session.add(portfolio_entry)
            
            db_sql.session.commit()
            print("Created portfolio entries for clients")

if __name__ == "__main__":
    create_test_data()
    print("Test data creation completed!")