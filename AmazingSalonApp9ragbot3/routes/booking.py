
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user
from models import get_all_services, get_all_users, create_appointment
from datetime import datetime

bp = Blueprint('booking', __name__)

@bp.route('/booking')
def index():
    services = get_all_services()
    stylists = [user for user in get_all_users() if user.get('is_staff', False)]
    return render_template('booking.html', services=services, stylists=stylists)

@bp.route('/booking/create', methods=['POST'])
def create():
    try:
        service = request.form['service']
        stylist_id = request.form['stylist_id']
        date_time = datetime.strptime(request.form['date_time'], '%Y-%m-%dT%H:%M')
        client_email = request.form['email']
        client_name = request.form['name']
        
        appointment = create_appointment(client_email, stylist_id, service, date_time)
        flash('Appointment booked successfully!')
        return redirect(url_for('booking.confirmation'))
    except Exception as e:
        flash('Error booking appointment: ' + str(e))
        return redirect(url_for('booking.index'))

@bp.route('/booking/confirmation')
def confirmation():
    return render_template('booking_confirmation.html')
