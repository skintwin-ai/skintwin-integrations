
from flask import Blueprint, render_template
from flask_login import login_required
from datetime import datetime, timedelta
from models import get_all_transactions, get_all_appointments, get_all_services, get_all_clients

bp = Blueprint('analytics', __name__)

@bp.route('/analytics')
@login_required
def index():
    # Get data for the last 30 days
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    # Get transactions and calculate revenue
    transactions = get_all_transactions()
    revenue_data = {}
    total_revenue = 0
    for transaction in transactions:
        date = datetime.fromisoformat(transaction['date_time']).strftime('%Y-%m-%d')
        amount = transaction['amount']
        revenue_data[date] = revenue_data.get(date, 0) + amount
        if start_date <= datetime.fromisoformat(transaction['date_time']) <= end_date:
            total_revenue += amount
    
    # Get appointments for service popularity and staff performance
    appointments = get_all_appointments()
    service_popularity = {}
    staff_performance = {}
    recent_appointments = []
    for appointment in appointments:
        # Service popularity
        service = appointment['service']
        service_popularity[service] = service_popularity.get(service, 0) + 1
        
        # Staff performance
        stylist = appointment['stylist_id']
        if stylist in staff_performance:
            staff_performance[stylist]['appointments'] += 1
        else:
            staff_performance[stylist] = {'appointments': 1, 'revenue': 0}
            
        # Recent appointments for retention
        appt_date = datetime.fromisoformat(appointment['date_time'])
        if start_date <= appt_date <= end_date:
            recent_appointments.append(appointment)
    
    # Calculate client retention
    clients = get_all_clients()
    total_clients = len(clients)
    returning_clients = len(set(appt['client_id'] for appt in recent_appointments))
    retention_rate = (returning_clients / total_clients * 100) if total_clients > 0 else 0
    
    # Calculate average revenue per client
    avg_revenue = total_revenue / returning_clients if returning_clients > 0 else 0
    
    return render_template('analytics.html',
                         revenue_data=revenue_data,
                         service_popularity=service_popularity,
                         staff_performance=staff_performance,
                         retention_rate=retention_rate,
                         total_revenue=total_revenue,
                         avg_revenue=avg_revenue,
                         total_clients=total_clients,
                         returning_clients=returning_clients)
