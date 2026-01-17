
from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required, current_user
import models
from datetime import datetime
import json
import random
import re

bp = Blueprint('voice_assistant', __name__, url_prefix='/voice')

@bp.route('/')
@login_required
def index():
    """Voice assistant interface landing page"""
    return render_template('voice_assistant.html')

@bp.route('/process', methods=['POST'])
@login_required
def process_command():
    """Process voice commands with advanced intent recognition"""
    command = request.json.get('command', '').lower()
    
    # Intent recognition - identify what the user is trying to do
    response = {
        'success': True,
        'message': '',
        'action': None,
        'data': None
    }
    
    # Enhanced client search with fuzzy matching
    if any(keyword in command for keyword in ['client', 'customer', 'person']) and any(keyword in command for keyword in ['find', 'search', 'lookup', 'information', 'details', 'profile']):
        # Extract potential client names - would use NLP in production
        clients = models.get_all_clients()
        matched_clients = []
        
        # More sophisticated matching
        for client in clients:
            client_name = client['name'].lower()
            name_parts = client_name.split()
            
            # Check if any part of the client name is in the command
            if any(part in command for part in name_parts) or client_name in command:
                matched_clients.append(client)
        
        if matched_clients:
            response['message'] = f"Found {len(matched_clients)} matching clients."
            response['action'] = 'showClients'
            response['data'] = matched_clients
        else:
            response['message'] = "No clients found matching that name. Try using the client's full name or check if they exist in the system."
    
    # Enhanced appointment scheduling
    elif any(keyword in command for keyword in ['appointment', 'booking', 'schedule', 'reservation']):
        # Determine specific intent
        if any(keyword in command for keyword in ['today', 'upcoming', 'show', 'view', 'list']):
            # Show appointments
            today = datetime.now().strftime('%Y-%m-%d')
            appointments = models.get_all_appointments()
            
            # Filter appointments for today
            today_appointments = [apt for apt in appointments if apt.get('date_time', '').startswith(today)]
            
            response['message'] = f"Found {len(today_appointments)} appointments scheduled for today."
            response['action'] = 'showAppointments'
            response['data'] = today_appointments
        else:
            # Create a new appointment
            response['message'] = "I can help you schedule an appointment. What client and service would you like to book?"
            response['action'] = 'startBooking'
            
            # Extract potential client and service information
            clients = models.get_all_clients()
            services = models.get_all_services()
            extracted_data = {'client': None, 'service': None, 'time': None}
            
            # Simple extraction - would use more sophisticated NLP in production
            for client in clients:
                if client['name'].lower() in command:
                    extracted_data['client'] = client
                    break
                    
            for service in services:
                if service['name'].lower() in command:
                    extracted_data['service'] = service
                    break
            
            # Try to extract time using simple pattern matching
            # Look for patterns like "at 3pm" or "at 3:00"
            time_patterns = [r"at (\d+)(?::(\d+))?\s*(am|pm)?", r"(\d+)(?::(\d+))?\s*(am|pm)"]
            for pattern in time_patterns:
                matches = re.search(pattern, command)
                if matches:
                    extracted_data['time'] = matches.group(0)
                    break
            
            if any(extracted_data.values()):
                response['data'] = extracted_data
    
    # Enhanced service information
    elif any(keyword in command for keyword in ['service', 'treatment', 'haircut', 'color', 'style']):
        services = models.get_all_services()
        
        if any(keyword in command for keyword in ['list', 'all', 'available', 'offer']):
            # List all services
            response['message'] = f"We offer {len(services)} different services."
            response['action'] = 'showAllServices'
            response['data'] = services
        else:
            # Look for specific service
            matched_services = []
            
            for service in services:
                service_name = service['name'].lower()
                if service_name in command or any(word in command for word in service_name.split()):
                    matched_services.append(service)
            
            if matched_services:
                response['message'] = f"Found information about {matched_services[0]['name']}."
                response['action'] = 'showService'
                response['data'] = matched_services[0]
            else:
                response['message'] = "I couldn't find details for that service. Would you like to see a list of all available services?"
    
    # Enhanced inventory management
    elif any(keyword in command for keyword in ['inventory', 'stock', 'product', 'supplies']):
        products = models.get_all_products()
        
        if any(keyword in command for keyword in ['low', 'need', 'order', 'reorder']):
            low_stock = models.get_low_stock_products()
            response['message'] = f"Found {len(low_stock)} products with low stock levels that need to be reordered."
            response['action'] = 'showLowStock'
            response['data'] = low_stock
        elif any(keyword in command for keyword in ['add', 'new', 'create']):
            response['message'] = "I can help you add a new product to inventory. What details would you like to provide?"
            response['action'] = 'startAddProduct'
        elif any(keyword in command for keyword in ['search', 'find']) and any(part in command for part in [cat.lower() for cat in models.get_product_categories()]):
            # Search for products by category
            category_matches = []
            for category in models.get_product_categories():
                if category.lower() in command:
                    category_matches = [p for p in products if p.get('category') == category]
                    break
                    
            if category_matches:
                response['message'] = f"Found {len(category_matches)} products in that category."
                response['action'] = 'showCategoryProducts'
                response['data'] = category_matches
            else:
                response['message'] = "I couldn't find products in that category."
        else:
            response['message'] = f"Currently tracking {len(products)} products in inventory."
            response['action'] = 'showInventory'
            response['data'] = products[:5]  # Just show top 5 for simplicity
    
    # Staff schedule commands
    elif any(keyword in command for keyword in ['staff', 'stylist', 'employee']) and any(keyword in command for keyword in ['schedule', 'shift', 'working', 'available']):
        response['message'] = "Here's the current staff schedule."
        response['action'] = 'showStaffSchedule'
        
        # In a real implementation, we would query the staff schedule database
        # For now, we'll return a placeholder
        response['data'] = {'message': 'Staff schedule would be displayed here'}
    
    # Analytics and reports
    elif any(keyword in command for keyword in ['report', 'analytics', 'stats', 'statistics', 'performance']):
        report_type = None
        
        if 'revenue' in command or 'sales' in command:
            report_type = 'revenue'
            response['message'] = "Here's the latest revenue report."
        elif 'service' in command and 'popular' in command:
            report_type = 'popular_services'
            response['message'] = "Here are our most popular services."
        elif 'client' in command:
            report_type = 'clients'
            response['message'] = "Here's the latest client activity report."
        else:
            report_type = 'general'
            response['message'] = "Here's a general performance overview."
            
        response['action'] = 'showAnalytics'
        response['data'] = {'report_type': report_type}
        
    # Default response with suggestions
    else:
        response['message'] = "I'm not sure how to help with that request. Try asking about:"
        response['data'] = {
            'suggestions': [
                "Find client Sarah Johnson",
                "Schedule an appointment for tomorrow",
                "Show today's appointments",
                "What services do we offer?",
                "Check inventory stock levels",
                "Show products with low stock",
                "Show staff schedule for this week",
                "Show revenue report"
            ]
        }
    
    return jsonify(response)
