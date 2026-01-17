
from datetime import datetime
from models import get_all_clients, get_all_transactions
from .email_utils import mail, render_template_string, Message

PROMOTION_TEMPLATE = """
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
    <h2>Special Offer Just for You!</h2>
    <p>Dear {{ client_name }},</p>
    <p>As a valued {{ tier }} member, you've earned a special reward:</p>
    <div style="margin: 20px; padding: 15px; background: #f5f5f5;">
        <h3>{{ promotion_text }}</h3>
        <p>Valid until: {{ expiry_date.strftime('%B %d, %Y') }}</p>
    </div>
</body>
</html>
"""

def check_and_send_promotions():
    clients = get_all_clients()
    for client in clients:
        total_spent = float(client.get('total_spent', 0))
        loyalty_points = int(client.get('loyalty_points', 0))
        
        # Define promotion based on spending and points
        promotion = None
        if total_spent >= 1000 and loyalty_points >= 500:
            promotion = {
                'text': '50% off your next premium service',
                'expiry_days': 30
            }
        elif total_spent >= 500 and loyalty_points >= 200:
            promotion = {
                'text': '25% off your next visit',
                'expiry_days': 14
            }
        
        if promotion:
            msg = Message(
                'Special Offer from Your Salon',
                recipients=[client['email']],
                html=render_template_string(
                    PROMOTION_TEMPLATE,
                    client_name=client['name'],
                    tier=client.get('tier', 'Valued'),
                    promotion_text=promotion['text'],
                    expiry_date=datetime.now() + timedelta(days=promotion['expiry_days'])
                )
            )
            mail.send(msg)
