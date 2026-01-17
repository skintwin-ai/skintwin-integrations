"""
Script to create test client memories for demonstration purposes
"""

from app import app
from database import db_sql
from database_models import Client
from database_models_ai import ClientMemory
from datetime import datetime, timedelta
import random

def create_test_memories():
    """Create test client memories for all clients"""
    clients = Client.query.all()
    
    if not clients:
        print("No clients found. Please run create_test_data.py first.")
        return
    
    print(f"Creating test memories for {len(clients)} clients...")
    
    # Define memory types and sample content
    memory_types = {
        'skin_condition': [
            "Has occasional hormonal breakouts on chin",
            "Experiences redness around nose area",
            "Has some hyperpigmentation on cheeks",
            "Shows early signs of fine lines around eyes",
            "Has combination skin with T-zone oiliness",
            "Experiences seasonal dryness in winter",
            "Has some acne scarring on cheeks",
            "Shows signs of sun damage on forehead",
            "Has enlarged pores on nose",
            "Experiences slight rosacea flare-ups"
        ],
        'preference': [
            "Prefers appointments in the morning",
            "Likes to chat during treatments",
            "Prefers quiet, relaxing facials",
            "Always brings ingredient lists to discuss",
            "Likes to be offered herbal tea during appointment",
            "Prefers female estheticians",
            "Always books weekend appointments",
            "Likes to have detailed skin analysis explanations",
            "Prefers quick, efficient facial services",
            "Enjoys personalized product recommendations"
        ],
        'history': [
            "Previously had a bad reaction to retinol",
            "Has been a skin care client for over 5 years",
            "Recently moved from another medical spa",
            "Had a skin allergy reaction last year",
            "Has sensitive skin due to medical condition",
            "Recently recovered from severe skin dehydration",
            "Has tried microneedling in the past",
            "Had professional chemical peels for many years",
            "Previously used drugstore skincare exclusively",
            "Has visited 3 times in the last month for acne treatment"
        ],
        'feedback': [
            "Was very happy with the hydrating facial",
            "Mentioned skin felt more balanced after treatment",
            "Loved the lymphatic drainage massage techniques",
            "Said the vitamin C serum recommendation worked wonders",
            "Found the gentle cleanser recommendation helpful",
            "Appreciated esthetician listening to skin concerns",
            "Mentioned some products were a bit expensive",
            "Loved the hydrojelly mask treatment results",
            "Said the extractions were thorough but gentle",
            "Really enjoyed the aromatherapy experience"
        ],
        'request': [
            "Asked about dermaplaning treatments",
            "Inquired about vegan skin care options",
            "Requested information on mineral sunscreen types",
            "Asked for special event prep facial options",
            "Requested gentler options for sensitive skin",
            "Asked about anti-aging starting routine",
            "Inquired about hyperpigmentation treatments",
            "Asked for travel-sized skin care recommendations",
            "Requested product samples to try at home",
            "Asked about subscription service for personalized skin care"
        ],
        'skin_progress': [
            "Significant improvement in acne after 3 treatments",
            "Reduction in fine lines around eyes since starting regimen",
            "Hyperpigmentation has faded by approximately 40%",
            "Skin texture greatly improved after microdermabrasion series",
            "Hydration levels increased according to skin analysis device",
            "Sebum production has normalized after oily skin treatment plan",
            "Redness associated with rosacea has decreased notably",
            "Pore size visibly reduced after consistent treatment",
            "Skin elasticity improved following collagen-boosting treatments",
            "Melasma has shown moderate improvement with current protocol"
        ],
        'home_care': [
            "Consistently follows recommended cleansing routine",
            "Has difficulty remembering to apply sunscreen daily",
            "Successfully incorporated retinol without irritation",
            "Reports using mask treatments twice weekly as advised",
            "Struggled with multilayer skincare routine - simplified version provided",
            "Very dedicated to following AM and PM routines exactly",
            "Sometimes overuses exfoliating products despite guidance",
            "Successfully transitioned to medical-grade skin care products",
            "Follows hydration protocol perfectly during dry seasons",
            "Has integrated facial massage techniques into home routine"
        ]
    }
    
    # Generate memories for each client
    for client in clients:
        # Random number of memories per client (3-15)
        num_memories = random.randint(3, 15)
        
        # Calculate a base date (between 1-6 months ago)
        days_ago = random.randint(30, 180)
        base_date = datetime.utcnow() - timedelta(days=days_ago)
        
        for i in range(num_memories):
            # Random memory type
            memory_type = random.choice(list(memory_types.keys()))
            
            # Random content from that type
            content = random.choice(memory_types[memory_type])
            
            # Importance rating between 1-10
            importance = random.randint(1, 10)
            
            # Date between base_date and now
            random_days = random.randint(0, days_ago)
            created_at = base_date + timedelta(days=random_days)
            
            # Create memory
            memory = ClientMemory(
                client_id=client.id,
                memory_type=memory_type,
                content=content,
                importance=importance,
                created_at=created_at
            )
            
            # 70% chance of having accessed the memory
            if random.random() < 0.7:
                days_since_create = (datetime.utcnow() - created_at).days
                if days_since_create > 0:
                    access_days_ago = random.randint(0, days_since_create)
                    memory.last_accessed = datetime.utcnow() - timedelta(days=access_days_ago)
            
            db_sql.session.add(memory)
        
        print(f"Created {num_memories} memories for {client.name}")
    
    db_sql.session.commit()
    print("Test memories created successfully!")

if __name__ == '__main__':
    with app.app_context():
        create_test_memories()