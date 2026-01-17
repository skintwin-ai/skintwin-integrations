from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import get_all_appointments, get_appointment, get_user, get_client, get_all_users, get_all_clients, update_appointment, delete_appointment
from database_utils import (
    create_appointment_sql, get_appointment_sql, update_appointment_sql, delete_appointment_sql,
    get_all_appointments_sql, get_all_users_sql, get_all_clients_sql, get_service_sql
)
from utils.email_utils import send_appointment_reminder
from datetime import datetime

bp = Blueprint('appointments', __name__)

@bp.route('/appointments')
@login_required
def index():
    appointments = get_all_appointments()
    return render_template('appointments.html', appointments=appointments)

@bp.route('/appointments/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        client_id = int(request.form['client_id'])
        stylist_id = int(request.form['stylist_id'])
        service_id = int(request.form['service_id'])
        date_time_str = request.form['date_time']
        date_time = datetime.strptime(date_time_str, '%Y-%m-%dT%H:%M')
        
        appointment_id = create_appointment_sql(
            client_id=client_id,
            stylist_id=stylist_id,
            service_id=service_id,
            date_time=date_time
        )
        
        appointment = get_appointment_sql(appointment_id)
        client = appointment.client
        stylist = appointment.stylist
        
        try:
            send_appointment_reminder(
                appointment_to_dict(appointment),
                client.name,
                stylist.username
            )
            flash('Appointment created successfully and confirmation email sent')
        except Exception as e:
            flash(f'Appointment created successfully but email notification failed: {str(e)}')
        return redirect(url_for('appointments.index'))
    
    clients = get_all_clients()
    stylists = [user for user in get_all_users() if user.get('is_staff', False)]
    from models import get_all_services
    services = get_all_services()
    return render_template('appointments.html', clients=clients, stylists=stylists, services=services)

@bp.route('/appointments/update/<int:id>', methods=['GET', 'POST'])
@login_required
def update(id):
    appointment = get_appointment(id)
    
    if request.method == 'POST':
        client_id = int(request.form['client_id'])
        stylist_id = int(request.form['stylist_id'])
        service_id = int(request.form['service_id'])
        date_time_str = request.form['date_time']
        date_time = datetime.strptime(date_time_str, '%Y-%m-%dT%H:%M')
        status = request.form['status']
        
        update_appointment_sql(
            id,
            client_id=client_id,
            stylist_id=stylist_id,
            service_id=service_id,
            date_time=date_time,
            status=status
        )
        
        flash('Appointment updated successfully')
        return redirect(url_for('appointments.index'))
    
    clients = get_all_clients()
    stylists = [user for user in get_all_users() if user.get('is_staff', False)]
    from models import get_all_services
    services = get_all_services()
    return render_template('appointments.html', appointment=appointment, clients=clients, stylists=stylists, services=services)

@bp.route('/appointments/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    appointment = get_appointment(id)
    if appointment:
        client = get_client(appointment['client_id'])
        try:
            from utils.email_utils import send_cancellation_notice
            send_cancellation_notice(appointment, client['name'])
            delete_appointment_sql(id)
            flash('Appointment cancelled and notification sent')
        except Exception as e:
            delete_appointment_sql(id)
            flash(f'Appointment cancelled but notification failed: {str(e)}')
    else:
        flash('Appointment not found')
    return redirect(url_for('appointments.index'))

def appointment_to_dict(appointment):
    """Convert a SQLAlchemy appointment to a dictionary for legacy email functions"""
    return {
        'id': appointment.id,
        'client_id': appointment.client_id,
        'stylist_id': appointment.stylist_id,
        'service_id': appointment.service_id,
        'date_time': appointment.date_time,
        'status': appointment.status,
        'client': appointment.client.name if appointment.client else '',
        'stylist': appointment.stylist.username if appointment.stylist else '',
        'service': appointment.service_rel.name if appointment.service_rel else '',
        'client_name': appointment.client.name if appointment.client else '',
        'stylist_name': appointment.stylist.username if appointment.stylist else '',
        'service_name': appointment.service_rel.name if appointment.service_rel else ''
    }
