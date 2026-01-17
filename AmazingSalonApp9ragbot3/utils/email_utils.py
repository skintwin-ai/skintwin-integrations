from flask_mail import Mail, Message
from flask import render_template_string
from datetime import datetime, timedelta

mail = Mail()

APPOINTMENT_REMINDER_TEMPLATE = """
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
    <h2>Appointment Reminder</h2>
    <p>Dear {{ client_name }},</p>
    <p>This is a reminder for your upcoming appointment:</p>
    <div style="margin: 20px; padding: 15px; background: #f5f5f5;">
        <p><strong>Service:</strong> {{ service }}</p>
        <p><strong>Date:</strong> {{ date_time.strftime('%B %d, %Y') }}</p>
        <p><strong>Time:</strong> {{ date_time.strftime('%I:%M %p') }}</p>
        <p><strong>Stylist:</strong> {{ stylist_name }}</p>
    </div>
    <p>Looking forward to seeing you!</p>
    <p>Best regards,<br>Your Salon Team</p>
</body>
</html>
"""

INVENTORY_ALERT_TEMPLATE = """
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
    <h2>Low Inventory Alert</h2>
    <p>The following items are running low:</p>
    <ul style="margin: 20px; padding: 15px; background: #f5f5f5;">
    {% for item in low_stock_items %}
        <li><strong>{{ item.name }}</strong> - Current quantity: {{ item.quantity }}</li>
    {% endfor %}
    </ul>
    <p>Please reorder soon.</p>
</body>
</html>
"""

def send_inventory_alert(low_stock_items, manager_email):
    msg = Message(
        'Low Inventory Alert',
        recipients=[manager_email],
        html=render_template_string(INVENTORY_ALERT_TEMPLATE, low_stock_items=low_stock_items)
    )
    mail.send(msg)

APPOINTMENT_CANCELLED_TEMPLATE = """
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
    <h2>Appointment Cancellation Notice</h2>
    <p>Dear {{ client_name }},</p>
    <p>Your appointment has been cancelled:</p>
    <div style="margin: 20px; padding: 15px; background: #f5f5f5;">
        <p><strong>Service:</strong> {{ service }}</p>
        <p><strong>Date:</strong> {{ date_time.strftime('%B %d, %Y') }}</p>
        <p><strong>Time:</strong> {{ date_time.strftime('%I:%M %p') }}</p>
    </div>
    <p>If you would like to reschedule, please contact us.</p>
</body>
</html>
"""

def send_appointment_reminder(appointment, client_name, stylist_name):
    msg = Message(
        'Appointment Reminder',
        recipients=[appointment['client_email']],
        html=render_template_string(
            APPOINTMENT_REMINDER_TEMPLATE,
            client_name=client_name,
            service=appointment['service'],
            date_time=datetime.fromisoformat(appointment['date_time']),
            stylist_name=stylist_name
        )
    )
    mail.send(msg)


def send_cancellation_notice(appointment, client_name):
    msg = Message(
        'Appointment Cancellation',
        recipients=[appointment['client_email']],
        html=render_template_string(
            APPOINTMENT_CANCELLED_TEMPLATE,
            client_name=client_name,
            service=appointment['service'],
            date_time=datetime.fromisoformat(appointment['date_time'])
        )
    )
    mail.send(msg)

# Added function based on the intention of the change request.  Assumes a send_email function exists.
def send_low_inventory_alert(admin_email, low_stock_items):
    subject = "Low Inventory Alert"
    #This assumes a template file named 'email/low_inventory_alert.html' exists.
    body = render_template_string(INVENTORY_ALERT_TEMPLATE, low_stock_items=low_stock_items) #Using existing template
    msg = Message(subject, recipients=[admin_email], html=body)
    mail.send(msg)
MONTHLY_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
    <h2>Monthly Salon Performance Report</h2>
    <div style="margin: 20px; padding: 15px; background: #f5f5f5;">
        <p><strong>Total Revenue:</strong> ${{ "%.2f"|format(total_revenue) }}</p>
        <p><strong>Total Appointments:</strong> {{ total_appointments }}</p>
        <p><strong>New Clients:</strong> {{ new_clients }}</p>
        <p><strong>Client Retention Rate:</strong> {{ "%.1f"|format(retention_rate) }}%</p>
        <p><strong>Most Popular Services:</strong></p>
        <ul>
        {% for service in popular_services %}
            <li>{{ service.name }} ({{ service.count }} bookings)</li>
        {% endfor %}
        </ul>
    </div>
</body>
</html>
"""

def send_monthly_report(admin_email, report_data):
    """Send monthly performance report"""
    msg = Message(
        'Monthly Salon Performance Report',
        recipients=[admin_email],
        html=render_template_string(MONTHLY_REPORT_TEMPLATE, **report_data)
    )
    mail.send(msg)
