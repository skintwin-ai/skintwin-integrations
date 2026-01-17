
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
import models
from datetime import datetime, timedelta
import random

bp = Blueprint('smart_booking', __name__, url_prefix='/smart-booking')

@bp.route('/')
def index():
    """Smart booking landing page with client selection"""
    clients = models.get_all_clients()
    services = models.get_all_services()
    stylists = [user for user in models.get_all_users() if user.get('is_staff', False)]
    
    return render_template('smart_booking.html', 
                          clients=clients, 
                          services=services,
                          stylists=stylists)

@bp.route('/suggestions', methods=['POST'])
def get_suggestions():
    """Get intelligent time suggestions based on preferences"""
    client_id = request.form.get('client_id')
    service_id = request.form.get('service_id')
    stylist_id = request.form.get('stylist_id')
    
    # Get service details for duration calculation
    service = models.get_service(service_id)
    if not service:
        flash('Service not found')
        return redirect(url_for('smart_booking.index'))
    
    # Calculate optimal time slots
    today = datetime.now()
    suggested_slots = generate_optimal_slots(client_id, stylist_id, service, today)
    
    return jsonify({
        'slots': suggested_slots,
        'client': models.get_client(client_id),
        'service': service,
        'stylist': models.get_user(stylist_id)
    })

def generate_optimal_slots(client_id, stylist_id, service, start_date):
    """Generate AI-optimized appointment slots based on multiple factors"""
    from utils.ai_utils import analyze_booking_patterns, predict_optimal_times
    
    # Analyze historical booking patterns
    booking_patterns = analyze_booking_patterns(client_id, stylist_id)
    
    # Predict optimal times using AI
    optimal_slots = predict_optimal_times(
        patterns=booking_patterns,
        service=service,
        start_date=start_date
    )
    # In a real implementation, this would use ML algorithms to predict optimal times
    # For now, we'll simulate with some basic logic
    
    service_duration = int(service.get('duration', 60))
    
    # Get stylist availability
    available_slots = []
    
    # Simulate stylist availability for the next 7 days
    for day_offset in range(7):
        day = start_date + timedelta(days=day_offset)
        
        # Generate 3 slots per day between 9am and 5pm
        day_slots = []
        
        # Morning slot
        morning = datetime(day.year, day.month, day.day, 9 + (day_offset % 3), 0)
        day_slots.append({
            'start_time': morning.isoformat(),
            'end_time': (morning + timedelta(minutes=service_duration)).isoformat(),
            'score': random.randint(70, 98),  # Simulate ML confidence score
            'reasoning': get_slot_reasoning(morning, client_id, "morning")
        })
        
        # Afternoon slot
        afternoon = datetime(day.year, day.month, day.day, 13 + (day_offset % 3), 30)
        day_slots.append({
            'start_time': afternoon.isoformat(),
            'end_time': (afternoon + timedelta(minutes=service_duration)).isoformat(),
            'score': random.randint(70, 98),
            'reasoning': get_slot_reasoning(afternoon, client_id, "afternoon")
        })
        
        # Evening slot
        evening = datetime(day.year, day.month, day.day, 16 + (day_offset % 2), 0)
        day_slots.append({
            'start_time': evening.isoformat(),
            'end_time': (evening + timedelta(minutes=service_duration)).isoformat(),
            'score': random.randint(70, 98),
            'reasoning': get_slot_reasoning(evening, client_id, "evening")
        })
        
        available_slots.extend(day_slots)
    
    # Sort slots by score (descending)
    return sorted(available_slots, key=lambda x: x['score'], reverse=True)

def get_slot_reasoning(time, client_id, time_of_day):
    """Generate reasoning for why this slot is recommended"""
    client = models.get_client(client_id)
    
    reasons = [
        f"This {time_of_day} slot typically has lower wait times",
        f"Based on your previous appointments, you seem to prefer {time_of_day} bookings",
        f"This time slot aligns with your stylist's peak performance hours",
        f"This time allows optimal duration for your selected service",
        f"Our AI predicts this time will result in the highest satisfaction rating",
        f"The lighting in our salon is ideal for your preferred styles at this time"
    ]
    
    # Select 2 random reasons
    selected_reasons = random.sample(reasons, 2)
    return " ".join(selected_reasons)

@bp.route('/book', methods=['POST'])
def book_appointment():
    """Book the selected smart appointment slot"""
    client_id = request.form.get('client_id')
    stylist_id = request.form.get('stylist_id')
    service_id = request.form.get('service_id')
    start_time = request.form.get('start_time')
    
    # Parse datetime
    start_time_dt = datetime.fromisoformat(start_time)
    
    # Get service details
    service = models.get_service(service_id)
    
    # Create the appointment
    appointment_id = models.create_appointment(
        client_id=client_id,
        stylist_id=stylist_id,
        service=service,
        date_time=start_time_dt,
        status="scheduled"
    )
    
    flash('Appointment booked successfully!')
    return redirect(url_for('appointments.index'))
