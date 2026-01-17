"""
Script to create test client milestones for demonstration purposes
"""
from datetime import datetime, timedelta
import random
from database_models import Client, db_sql
from database_models_ai import ClientMilestone

def create_test_milestones():
    """
    Create test milestones for all clients based on their existing data
    """
    print("Creating test client milestones...")
    
    # Get all clients
    clients = Client.query.all()
    
    # For each client, create 2-5 milestones
    milestone_count = 0
    for client in clients:
        # Determine how many milestones to create for this client (2-5)
        num_milestones = random.randint(2, 5)
        
        # Create the milestones
        create_first_visit_milestone(client)
        milestone_count += 1
        
        if client.total_spent > 250 and random.random() > 0.3:
            create_spending_milestone(client)
            milestone_count += 1
            num_milestones -= 1
        
        if client.loyalty_points > 100 and random.random() > 0.3:
            create_loyalty_tier_milestone(client)
            milestone_count += 1
            num_milestones -= 1
        
        # Create random milestones for the remaining count
        for _ in range(max(0, num_milestones - 1)):
            milestone_type = random.choice([
                'special_service', 
                'anniversary', 
                'treatment_change', 
                'custom'
            ])
            
            if milestone_type == 'special_service':
                create_special_service_milestone(client)
            elif milestone_type == 'anniversary':
                create_anniversary_milestone(client)
            elif milestone_type == 'treatment_change':
                create_treatment_change_milestone(client)
            else:
                create_custom_milestone(client)
                
            milestone_count += 1
    
    # Commit all milestone additions to the database
    db_sql.session.commit()
    print(f"Created {milestone_count} test milestones across {len(clients)} clients")


def create_milestone(client_id, title, description, milestone_type, date, importance, icon, metadata_dict):
    """
    Helper function to create a milestone with the given parameters
    """
    milestone = ClientMilestone(
        client_id=client_id,
        title=title,
        description=description,
        milestone_type=milestone_type,
        date=date,
        importance=importance,
        icon=icon,
        milestone_metadata=metadata_dict
    )
    
    db_sql.session.add(milestone)
    return milestone


def create_first_visit_milestone(client):
    """Create a first visit milestone"""
    # Use client creation date or a bit after
    client_created = client.created_at
    days_offset = random.randint(0, 10)
    milestone_date = client_created + timedelta(days=days_offset)
    
    title = "First Visit"
    description = f"Welcome {client.name} to our skin care spa! First impressions are important, and we're excited to begin this skin care journey together."
    milestone_type = "first_visit"
    importance = random.randint(7, 10)  # First visits are important
    icon = "fas fa-star"
    
    metadata = {
        "esthetician_notes": random.choice([
            "Client seemed nervous but was happy with results",
            "Very friendly and open to suggestions",
            "Specific about skin concerns but open to guidance",
            "Referred by another client",
            "Found us through social media"
        ]),
        "service_booked": random.choice([
            "Basic facial",
            "Skin consultation",
            "Hydrating treatment",
            "Full skin analysis",
            "Express facial"
        ])
    }
    
    return create_milestone(
        client.id, title, description, milestone_type, 
        milestone_date, importance, icon, metadata
    )


def create_spending_milestone(client):
    """Create a spending milestone"""
    # Use a date between client creation and now
    client_created = client.created_at
    days_since_creation = max((datetime.now() - client_created).days, 30)  # Ensure at least 30 days
    days_offset = random.randint(int(days_since_creation/2), max(days_since_creation-10, int(days_since_creation/2)+1))
    milestone_date = client_created + timedelta(days=days_offset)
    
    spend_thresholds = [100, 250, 500, 1000, 2500]
    closest_threshold = min(spend_thresholds, key=lambda x: abs(x - client.total_spent))
    
    if closest_threshold > client.total_spent:
        closest_threshold = max([t for t in spend_thresholds if t < client.total_spent], default=100)
    
    title = f"${closest_threshold} Spending Milestone"
    description = f"Congratulations to {client.name} for reaching the ${closest_threshold} spending milestone with our skin care spa!"
    milestone_type = "spending_milestone"
    importance = random.randint(5, 8)
    icon = "fas fa-dollar-sign"
    
    metadata = {
        "threshold_reached": closest_threshold,
        "total_spent_at_milestone": round(client.total_spent * random.uniform(0.8, 0.95), 2),
        "reward_given": random.choice([
            "Complimentary product",
            "Service discount",
            "Special treatment upgrade",
            "Loyalty points bonus",
            "Gift card"
        ])
    }
    
    return create_milestone(
        client.id, title, description, milestone_type, 
        milestone_date, importance, icon, metadata
    )


def create_loyalty_tier_milestone(client):
    """Create a loyalty tier upgrade milestone"""
    # Use a date between client creation and now
    client_created = client.created_at
    days_since_creation = max((datetime.now() - client_created).days, 45)  # Ensure at least 45 days
    days_offset = random.randint(int(days_since_creation/3), max(days_since_creation-15, int(days_since_creation/3)+1))
    milestone_date = client_created + timedelta(days=days_offset)
    
    # Determine tier upgrade based on current tier
    current_tier = client.tier
    if current_tier == "Gold":
        previous_tier = "Silver"
    elif current_tier == "Silver":
        previous_tier = "Bronze"
    else:
        previous_tier = "New Client"
    
    title = f"{current_tier} Tier Achievement"
    description = f"Congratulations! {client.name} has been upgraded from {previous_tier} to {current_tier} tier, unlocking new rewards and benefits."
    milestone_type = "loyalty_tier"
    importance = random.randint(6, 9)
    
    if current_tier == "Gold":
        icon = "fas fa-crown"
    elif current_tier == "Silver":
        icon = "fas fa-award"
    else:
        icon = "fas fa-gem"
    
    metadata = {
        "previous_tier": previous_tier,
        "new_tier": current_tier,
        "points_at_upgrade": client.loyalty_points - random.randint(10, 50),
        "benefits_unlocked": random.choice([
            "Priority booking",
            "Complimentary add-ons",
            "Birthday gift",
            "Exclusive event invitations",
            "Higher points earning rate"
        ])
    }
    
    return create_milestone(
        client.id, title, description, milestone_type, 
        milestone_date, importance, icon, metadata
    )


def create_special_service_milestone(client):
    """Create a special service milestone"""
    # Use a date between client creation and now
    client_created = client.created_at
    days_since_creation = max((datetime.now() - client_created).days, 30)  # Ensure at least 30 days
    days_offset = random.randint(15, max(days_since_creation-5, 16))
    milestone_date = client_created + timedelta(days=days_offset)
    
    special_services = [
        {"name": "Bridal Skin Prep", "icon": "fas fa-heart"},
        {"name": "Complete Skin Transformation", "icon": "fas fa-magic"},
        {"name": "Special Event Facial", "icon": "fas fa-glass-cheers"},
        {"name": "Advanced Anti-Aging Treatment", "icon": "fas fa-clock"},
        {"name": "VIP Spa Package", "icon": "fas fa-gem"}
    ]
    
    service = random.choice(special_services)
    
    title = f"{service['name']} Experience"
    description = f"{client.name} enjoyed our premium {service['name']} service, a significant milestone in their journey with us."
    milestone_type = "special_service"
    importance = random.randint(5, 9)
    icon = service['icon']
    
    metadata = {
        "service_name": service['name'],
        "duration": f"{random.randint(90, 240)} minutes",
        "esthetician_notes": random.choice([
            "Client was thrilled with the skin results",
            "Significant skin improvement that built trust",
            "Client referred friends after this treatment",
            "Shared before/after photos on social media",
            "Booked follow-up treatments immediately"
        ])
    }
    
    return create_milestone(
        client.id, title, description, milestone_type, 
        milestone_date, importance, icon, metadata
    )


def create_anniversary_milestone(client):
    """Create an anniversary milestone"""
    # Use a date about 1 year after client creation
    client_created = client.created_at
    days_since_creation = max((datetime.now() - client_created).days, 120)  # Ensure at least 120 days
    
    # Always create a check-in milestone
    if days_since_creation < 355 or random.random() < 0.7:  # Most will be quarterly check-ins
        safe_days = max(days_since_creation-5, 90)
        milestone_date = client_created + timedelta(days=random.randint(90, min(safe_days, 180)))
        title = "Quarterly Check-in"
        description = f"We've enjoyed having {client.name} as a client for {random.randint(3, 6)} months now! Looking forward to many more visits."
        importance = random.randint(3, 6)
    else:
        # Calculate a date near the 1 year anniversary
        offset = random.randint(-5, 5)
        milestone_date = client_created + timedelta(days=365+offset)
        title = "One Year Anniversary"
        description = f"Celebrating one year of {client.name}'s skin care journey with our spa! Thank you for your continued loyalty."
        importance = random.randint(6, 9)
    
    milestone_type = "anniversary"
    icon = "fas fa-calendar-alt"
    
    metadata = {
        "years_as_client": "1" if days_since_creation >= 355 else "<1",
        "celebration_note": random.choice([
            "Sent a thank you card",
            "Provided a complimentary service add-on",
            "Offered anniversary discount",
            "Gave a small gift with service",
            "Celebrated with the team"
        ])
    }
    
    return create_milestone(
        client.id, title, description, milestone_type, 
        milestone_date, importance, icon, metadata
    )


def create_treatment_change_milestone(client):
    """Create a skin treatment change milestone"""
    # Use a date between client creation and now
    client_created = client.created_at
    days_since_creation = max((datetime.now() - client_created).days, 40)  # Ensure at least 40 days
    days_offset = random.randint(20, max(days_since_creation-10, 21))
    milestone_date = client_created + timedelta(days=days_offset)
    
    treatment_changes = [
        {"from": "basic", "to": "advanced", "desc": "transition to advanced treatments"},
        {"from": "hydration", "to": "anti-aging", "desc": "focus shift to anti-aging concerns"},
        {"from": "acne", "to": "maintenance", "desc": "successful acne resolution"},
        {"from": "sensitive", "to": "balanced", "desc": "skin sensitivity improvement"},
        {"from": "pigmentation", "to": "even tone", "desc": "hyperpigmentation reduction"}
    ]
    
    change = random.choice(treatment_changes)
    
    title = f"Treatment Plan Evolution"
    description = f"{client.name} experienced a {change['desc']}, marking a significant milestone in their skin care journey."
    milestone_type = "treatment_change"
    importance = random.randint(6, 9)
    icon = "fas fa-sync-alt"
    
    metadata = {
        "previous_focus": change["from"],
        "new_focus": change["to"],
        "transformation_type": change["desc"],
        "client_reaction": random.choice([
            "Extremely satisfied with visible results",
            "Initially skeptical but now convinced",
            "Very emotional about skin improvement",
            "Gained confidence with improved skin",
            "Committed to ongoing maintenance plan"
        ])
    }
    
    return create_milestone(
        client.id, title, description, milestone_type, 
        milestone_date, importance, icon, metadata
    )


def create_custom_milestone(client):
    """Create a custom milestone type"""
    # Use a date between client creation and now
    client_created = client.created_at
    days_since_creation = max((datetime.now() - client_created).days, 25)  # Ensure at least 25 days
    days_offset = random.randint(10, max(days_since_creation-5, 11))
    milestone_date = client_created + timedelta(days=days_offset)
    
    custom_milestones = [
        {
            "title": "Skin Care Product Enthusiast",
            "description": "CLIENT became a skin care product enthusiast, regularly purchasing our recommended professional skin care items.",
            "icon": "fas fa-shopping-bag",
            "importance": random.randint(4, 7),
            "metadata": {
                "favorite_products": random.choice([
                    "Advanced moisturizer and serum",
                    "Vitamin C brightening complex",
                    "Hyaluronic acid collection",
                    "Gentle exfoliation kit",
                    "Anti-aging routine set"
                ]),
                "purchase_frequency": random.choice([
                    "Monthly",
                    "Every visit",
                    "Quarterly stock-up",
                    "Seasonal refresh"
                ])
            }
        },
        {
            "title": "Brought Family Member",
            "description": "CLIENT introduced a family member to our skin care spa, expanding our relationship with their household.",
            "icon": "fas fa-users",
            "importance": random.randint(5, 8),
            "metadata": {
                "relationship": random.choice([
                    "Daughter",
                    "Son",
                    "Spouse",
                    "Parent",
                    "Sibling"
                ]),
                "potential_lifetime_value": "High"
            }
        },
        {
            "title": "Spa Event Participant",
            "description": "CLIENT attended our exclusive skin care spa event, engaging more deeply with our brand community.",
            "icon": "fas fa-glass-cheers",
            "importance": random.randint(4, 7),
            "metadata": {
                "event_type": random.choice([
                    "Skin care workshop",
                    "New product demonstration",
                    "Seasonal skin care education",
                    "Client appreciation night",
                    "Charity fundraiser"
                ]),
                "engagement_level": random.choice([
                    "Highly engaged",
                    "Brought friends",
                    "Asked detailed questions",
                    "Purchased recommended products",
                    "Requested follow-up consultation"
                ])
            }
        },
        {
            "title": "Featured in Spa Social Media",
            "description": "CLIENT's stunning skin transformation was featured on our spa's social media, showcasing our work.",
            "icon": "fas fa-camera",
            "importance": random.randint(6, 9),
            "metadata": {
                "platform": random.choice([
                    "Instagram",
                    "Facebook",
                    "TikTok",
                    "Pinterest",
                    "Website gallery"
                ]),
                "engagement": random.choice([
                    "High likes and shares",
                    "Brought in new clients",
                    "Client shared before/after photos",
                    "Featured in local publication",
                    "Used in promotional materials"
                ])
            }
        }
    ]
    
    milestone = random.choice(custom_milestones)
    title = milestone["title"]
    description = milestone["description"].replace("CLIENT", client.name)
    milestone_type = "custom"
    importance = milestone["importance"]
    icon = milestone["icon"]
    metadata = milestone["metadata"]
    
    return create_milestone(
        client.id, title, description, milestone_type, 
        milestone_date, importance, icon, metadata
    )


if __name__ == "__main__":
    from app import app
    with app.app_context():
        create_test_milestones()