from flask import Blueprint, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from models import get_all_appointments, get_all_transactions, get_all_clients, get_all_users
from datetime import datetime, timedelta
from flask_mail import Message, Mail
try:
    from app import mail
except ImportError:
    # Mock mail for testing if not available
    mail = None

bp = Blueprint('reports', __name__)

@bp.route('/reports')
@login_required
def index():
    # Get date range for reports (last 30 days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    # Appointments report
    all_appointments = get_all_appointments()
    appointments = [
        appointment for appointment in all_appointments
        if start_date <= datetime.fromisoformat(appointment['date_time']) <= end_date
    ]
    appointment_count = len(appointments)
    
    # Revenue report
    all_transactions = get_all_transactions()
    transactions = [
        transaction for transaction in all_transactions
        if start_date <= datetime.fromisoformat(transaction['date_time']) <= end_date
    ]
    revenue = sum(transaction['amount'] for transaction in transactions)
    
    # Popular services report
    service_count = {}
    for appointment in appointments:
        service = appointment['service']
        service_count[service] = service_count.get(service, 0) + 1
    popular_services = sorted(service_count.items(), key=lambda x: x[1], reverse=True)[:5]
    
    return render_template('reports.html', 
                           appointments=appointment_count, 
                           revenue=revenue, 
                           popular_services=popular_services,
                           start_date=start_date,
                           end_date=end_date)
@bp.route('/generate_monthly_report')
@login_required
def generate_monthly_report():
    from utils.email_utils import send_monthly_report
    
    # Get first and last day of previous month
    today = datetime.now()
    first_day = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    last_day = today.replace(day=1) - timedelta(days=1)
    
    # Get all appointments for previous month
    appointments = [
        appt for appt in get_all_appointments()
        if first_day <= datetime.fromisoformat(appt['date_time']) <= last_day
    ]
    
    # Calculate metrics
    total_revenue = sum(float(appt.get('amount', 0)) for appt in appointments)
    total_appointments = len(appointments)
    
    # Calculate service popularity
    service_count = {}
    for appt in appointments:
        service = appt['service']
        service_count[service] = service_count.get(service, 0) + 1
    
    popular_services = [
        {'name': service, 'count': count}
        for service, count in sorted(service_count.items(), key=lambda x: x[1], reverse=True)[:5]
    ]
    
    # Get client metrics
    all_clients = get_all_clients()
    new_clients = len([
        client for client in all_clients
        if first_day <= datetime.fromisoformat(client.get('created_at', '')) <= last_day
    ])
    
    # Calculate retention rate
    total_clients = len(all_clients)
    returning_clients = len(set(appt['client_id'] for appt in appointments))
    retention_rate = (returning_clients / total_clients * 100) if total_clients > 0 else 0
    
    report_data = {
        'total_revenue': total_revenue,
        'total_appointments': total_appointments,
        'new_clients': new_clients,
        'retention_rate': retention_rate,
        'popular_services': popular_services,
        'period': {
            'start': first_day.strftime("%B %d, %Y"),
            'end': last_day.strftime("%B %d, %Y")
        }
    }
    
    # Send report to admin
    admin_email = current_user.email
    
    try:
        send_monthly_report(admin_email, report_data)
        flash('Monthly report has been generated and sent to your email.')
    except Exception as e:
        flash(f'Failed to send monthly report: {str(e)}')
    
    # Also send to all staff
    try:
        # Set date range for staff reports (last 30 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        # Get all transactions in date range
        transactions = [t for t in get_all_transactions() 
                      if start_date <= datetime.fromisoformat(t['date_time']) <= end_date]
        
        # Calculate additional metrics
        avg_transaction = total_revenue / len(transactions) if transactions else 0
        
        # Send to all staff emails
        staff = [u for u in get_all_users() if u.get('is_staff', False)]
        for user in staff:
            if user['email'] != admin_email:  # Avoid duplicate emails
                msg = Message(
                    f'Monthly Salon Report - {end_date.strftime("%B %Y")}',
                    recipients=[user['email']],
                    html=f'''
                        <h2>Monthly Report</h2>
                        <p>Period: {first_day.strftime("%B %d")} - {last_day.strftime("%B %d, %Y")}</p>
                        <h3>Key Metrics:</h3>
                        <ul>
                            <li>Total Revenue: ${total_revenue:.2f}</li>
                            <li>Number of Transactions: {len(transactions)}</li>
                            <li>Average Transaction: ${avg_transaction:.2f}</li>
                            <li>Total Appointments: {len(appointments)}</li>
                        </ul>
                    '''
                )
                mail.send(msg)
    except Exception as e:
        # Log error but don't disrupt user experience
        print(f"Error sending staff reports: {str(e)}")
        
    return redirect(url_for('reports.index'))
