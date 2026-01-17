from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from models import create_transaction, get_transaction, get_all_transactions, get_client, get_all_clients
import stripe
import os
import json
import requests
from datetime import datetime
from database_utils import create_transaction_sql, get_transaction_sql, get_all_transactions_sql
from database_utils import get_client_sql, get_all_clients_sql, update_client_sql
from utils.email_utils import send_appointment_reminder as send_email
from database import db_operation_with_retry, db_sql
from database_models import Transaction, Client
from utils.config_utils import ConfigManager

bp = Blueprint('pos', __name__)

# Initialize Stripe with the API key from ConfigManager or fallback to environment variable
stripe_secret_key = ConfigManager.get_stripe_secret_key() or os.environ.get('STRIPE_SECRET_KEY')
if stripe_secret_key:
    stripe.api_key = stripe_secret_key

# Get Paystack secret key
paystack_secret_key = ConfigManager.get_paystack_secret_key() or os.environ.get('PAYSTACK_SECRET_KEY')

# Get default payment provider
default_payment_provider = ConfigManager.get_default_payment_provider()

@bp.route('/pos')
@login_required
def index():
    # Use the SQL database functions with fallback to old functions
    try:
        transactions = get_all_transactions_sql()
        clients = get_all_clients_sql()
    except Exception as e:
        # Fallback to older functions if SQL fails
        transactions = get_all_transactions()
        clients = get_all_clients()
    
    # Get Stripe public key from ConfigManager or fallback to environment variable
    stripe_public_key = ConfigManager.get_stripe_public_key() or os.environ.get('STRIPE_PUBLIC_KEY')
    
    # Get Paystack public key from ConfigManager or fallback to environment variable
    paystack_public_key = ConfigManager.get_paystack_public_key() or os.environ.get('PAYSTACK_PUBLIC_KEY')
    
    # Get default payment provider
    default_payment_provider = ConfigManager.get_default_payment_provider()
    
    # Get loyalty points conversion ratio from ConfigManager
    points_to_dollar_ratio = ConfigManager.get_loyalty_points_ratio()
    
    return render_template('pos.html', 
                         transactions=transactions, 
                         clients=clients,
                         stripe_public_key=stripe_public_key,
                         paystack_public_key=paystack_public_key,
                         default_payment_provider=default_payment_provider,
                         points_to_dollar_ratio=points_to_dollar_ratio)

@bp.route('/pos/initialize-paystack', methods=['POST'])
@login_required
def initialize_paystack():
    """Initialize a Paystack payment"""
    if not request.is_json:
        return jsonify({'error': 'Invalid request format'}), 400
    
    data = request.json
    client_id = data.get('client_id')
    amount = float(data.get('amount'))
    description = data.get('description')
    points_to_redeem = int(data.get('points_to_redeem', 0))
    email = data.get('email')
    
    if not client_id or not amount or not email:
        return jsonify({'error': 'Missing required parameters'}), 400
    
    # Get loyalty points conversion ratio from configuration
    points_to_dollar_ratio = ConfigManager.get_loyalty_points_ratio()
    
    # Get the client from SQL database
    try:
        client = get_client_sql(client_id)
        
        # Check if client has enough points to redeem
        if client and points_to_redeem > 0:
            if points_to_redeem > client.loyalty_points:
                return jsonify({'error': 'Not enough loyalty points'}), 400
            
            # Convert points to dollars using the configured ratio
            discount = points_to_redeem * points_to_dollar_ratio
            amount = max(0, amount - discount)
    except Exception as e:
        # Fall back to old client method
        client = get_client(client_id)
        if client and points_to_redeem > 0:
            if points_to_redeem > client.get('loyalty_points', 0):
                return jsonify({'error': 'Not enough loyalty points'}), 400
            
            # Convert points to dollars using the configured ratio
            discount = points_to_redeem * points_to_dollar_ratio
            amount = max(0, amount - discount)
    
    # Get Paystack secret key
    paystack_secret = ConfigManager.get_paystack_secret_key()
    if not paystack_secret:
        return jsonify({'error': 'Paystack API key not configured'}), 500
    
    # Prepare Paystack request
    url = "https://api.paystack.co/transaction/initialize"
    headers = {
        'Authorization': f'Bearer {paystack_secret}',
        'Content-Type': 'application/json'
    }
    
    # Paystack expects amount in kobo (100 kobo = 1 Naira)
    # For USD we'll use cents (100 cents = 1 USD)
    payload = {
        'email': email,
        'amount': int(amount * 100),
        'currency': 'USD',
        'reference': f'salon-{client_id}-{int(datetime.utcnow().timestamp())}',
        'callback_url': url_for('pos.verify_paystack', _external=True),
        'metadata': {
            'client_id': client_id,
            'description': description,
            'points_redeemed': points_to_redeem,
            'custom_fields': [
                {
                    'display_name': 'Client ID',
                    'variable_name': 'client_id',
                    'value': client_id
                },
                {
                    'display_name': 'Description',
                    'variable_name': 'description',
                    'value': description
                }
            ]
        }
    }
    
    try:
        # Make request to Paystack
        response = requests.post(url, headers=headers, json=payload)
        response_data = response.json()
        
        if response.status_code == 200 and response_data['status']:
            # Return authorization URL for redirect
            return jsonify({
                'success': True,
                'authorization_url': response_data['data']['authorization_url'],
                'reference': response_data['data']['reference']
            })
        else:
            # Return error from Paystack
            return jsonify({
                'error': response_data.get('message', 'Failed to initialize Paystack payment')
            }), 400
    except Exception as e:
        return jsonify({'error': f'Error initializing Paystack payment: {str(e)}'}), 500

@bp.route('/pos/verify-paystack')
@login_required
def verify_paystack():
    """Verify and process a Paystack payment callback"""
    reference = request.args.get('reference')
    if not reference:
        flash('Invalid payment reference', 'error')
        return redirect(url_for('pos.index'))
    
    # Get Paystack secret key
    paystack_secret = ConfigManager.get_paystack_secret_key()
    if not paystack_secret:
        flash('Paystack API key not configured', 'error')
        return redirect(url_for('pos.index'))
    
    # Verify the transaction
    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {
        'Authorization': f'Bearer {paystack_secret}',
        'Content-Type': 'application/json'
    }
    
    try:
        # Make request to Paystack
        response = requests.get(url, headers=headers)
        response_data = response.json()
        
        if response.status_code == 200 and response_data['status'] and response_data['data']['status'] == 'success':
            # Get transaction details from Paystack response
            metadata = response_data['data'].get('metadata', {})
            client_id = metadata.get('client_id')
            description = metadata.get('description', 'Paystack Payment')
            points_redeemed = int(metadata.get('points_redeemed', 0))
            
            # Get amount in dollars
            amount = float(response_data['data']['amount']) / 100  # Convert from kobo/cents to dollars
            
            # Get loyalty points configuration
            points_per_dollar = ConfigManager.get_points_per_dollar()
            
            # Calculate points earned
            points_earned = int(amount * points_per_dollar)
            
            # Create transaction
            try:
                # Try SQL database first
                transaction = create_transaction_sql(
                    client_id=client_id,
                    amount=amount,
                    description=description,
                    payment_provider='paystack',
                    payment_intent_id=reference,  # Use Paystack reference as payment_intent_id
                    payment_method_id=response_data['data'].get('authorization', {}).get('authorization_code'),
                    points_used=points_redeemed
                )
                transaction_id = transaction.id
                
                # Update client's loyalty points
                def update_client_loyalty():
                    # Find client
                    client = db_sql.session.query(Client).get(client_id)
                    if client:
                        # Deduct redeemed points
                        client.loyalty_points -= points_redeemed
                        # Add new points
                        client.loyalty_points += points_earned
                        # Update total spent
                        client.total_spent += amount
                        
                        # Update tier based on total spent
                        if client.total_spent >= 1000:
                            client.tier = 'Gold'
                        elif client.total_spent >= 500:
                            client.tier = 'Silver'
                        else:
                            client.tier = 'Bronze'
                        
                        db_sql.session.commit()
                        return client
                
                # Update client with retry for transient issues
                updated_client = db_operation_with_retry(update_client_loyalty)
                
                # Get client for receipt
                client = updated_client
                client_email = client.email
                client_name = client.name
                
            except Exception as e:
                # Fall back to old method
                transaction_id = create_transaction(
                    client_id=client_id,
                    amount=amount,
                    description=description,
                    points_used=points_redeemed
                )
                
                # Update client's loyalty points in old system
                try:
                    client = get_client(client_id)
                    # Subtract redeemed points
                    client['loyalty_points'] = client.get('loyalty_points', 0) - points_redeemed
                    # Add new points
                    client['loyalty_points'] = client.get('loyalty_points', 0) + points_earned
                    # Update total spent
                    client['total_spent'] = client.get('total_spent', 0) + amount
                    # Update tier
                    if client.get('total_spent', 0) >= 1000:
                        client['tier'] = 'Gold'
                    elif client.get('total_spent', 0) >= 500:
                        client['tier'] = 'Silver'
                    else:
                        client['tier'] = 'Bronze'
                    
                    client_email = client.get('email')
                    client_name = client.get('name')
                except Exception as client_error:
                    print(f"Error updating client points: {str(client_error)}")
                    client_email = None
                    client_name = "Customer"
            
            # Send receipt email
            try:
                if client_email:
                    # Get business information from ConfigManager
                    business_info = ConfigManager.get_business_info()
                    
                    receipt_html = render_template('email/receipt.html',
                                                transaction_id=transaction_id,
                                                client_name=client_name,
                                                amount=amount,
                                                description=description,
                                                date=datetime.utcnow(),
                                                loyalty_points_earned=points_earned,
                                                points_redeemed=points_redeemed,
                                                payment_provider='Paystack',
                                                business_name=business_info.get('name'),
                                                business_email=business_info.get('email'),
                                                business_phone=business_info.get('phone'))
                    
                    send_email(client_email, 'Your Receipt', receipt_html)
            except Exception as e:
                # Log error but don't fail the transaction
                print(f"Error sending receipt: {str(e)}")
            
            flash('Payment processed successfully!', 'success')
            return redirect(url_for('pos.index', success=True, transaction_id=transaction_id))
        else:
            # Payment verification failed
            flash(f'Payment verification failed: {response_data.get("message", "Unknown error")}', 'error')
            return redirect(url_for('pos.index'))
    except Exception as e:
        flash(f'Error verifying payment: {str(e)}', 'error')
        return redirect(url_for('pos.index'))

@bp.route('/pos/create', methods=['POST'])
@login_required
def create_transaction_route():
    # For JSON requests from payment providers
    if request.is_json:
        data = request.json
        client_id = data.get('client_id')
        amount = float(data.get('amount'))
        description = data.get('description')
        payment_method_id = data.get('payment_method_id')
        points_to_redeem = int(data.get('points_to_redeem', 0))
        payment_provider = data.get('payment_provider', 'stripe')  # Default to stripe if not specified
    else:
        # For form submissions
        client_id = request.form.get('client_id')
        amount = float(request.form.get('amount'))
        description = request.form.get('description')
        payment_method_id = request.form.get('payment_method_id')
        points_to_redeem = int(request.form.get('points_to_redeem', 0))
        payment_provider = request.form.get('payment_provider', 'stripe')
    
    # Get loyalty points conversion ratio from configuration
    points_to_dollar_ratio = ConfigManager.get_loyalty_points_ratio()
    points_per_dollar = ConfigManager.get_points_per_dollar()
    
    # Get the client from SQL database
    try:
        client = get_client_sql(client_id)
        
        # Check if client has enough points to redeem
        if client and points_to_redeem > 0:
            if points_to_redeem > client.loyalty_points:
                if request.is_json:
                    return jsonify({'error': 'Not enough loyalty points'}), 400
                flash('Not enough loyalty points', 'error')
                return redirect(url_for('pos.index'))
            
            # Convert points to dollars using the configured ratio
            discount = points_to_redeem * points_to_dollar_ratio
            amount = max(0, amount - discount)
    except Exception as e:
        # Fall back to old client method
        client = get_client(client_id)
        if client and points_to_redeem > 0:
            if points_to_redeem > client.get('loyalty_points', 0):
                if request.is_json:
                    return jsonify({'error': 'Not enough loyalty points'}), 400
                flash('Not enough loyalty points', 'error')
                return redirect(url_for('pos.index'))
            
            # Convert points to dollars using the configured ratio
            discount = points_to_redeem * points_to_dollar_ratio
            amount = max(0, amount - discount)
    
    # Create a Stripe PaymentIntent
    try:
        # Create the payment intent
        payment_intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Stripe expects amounts in cents
            currency='usd',
            description=description,
            payment_method=payment_method_id,
            confirm=True,  # Confirm the payment immediately
            return_url=url_for('pos.index', _external=True)  # Redirect after payment
        )
        
        # Handle successful payment
        if payment_intent.status == 'succeeded':
            # Calculate loyalty points earned - use configured points per dollar
            points_earned = int(amount * points_per_dollar)
            
            # Try to use SQL transaction creation first
            try:
                transaction = create_transaction_sql(
                    client_id=client_id, 
                    amount=amount, 
                    description=description,
                    payment_method_id=payment_method_id,
                    payment_intent_id=payment_intent.id,
                    points_used=points_to_redeem,
                    payment_provider=payment_provider
                )
                transaction_id = transaction.id
                
                # Update client's loyalty points
                def update_client_loyalty():
                    # Find client
                    client = db_sql.session.query(Client).get(client_id)
                    if client:
                        # Deduct redeemed points
                        client.loyalty_points -= points_to_redeem
                        # Add new points
                        client.loyalty_points += points_earned
                        # Update total spent (important for tier calculation)
                        client.total_spent += amount
                        
                        # Update tier based on total spent
                        if client.total_spent >= 1000:
                            client.tier = 'Gold'
                        elif client.total_spent >= 500:
                            client.tier = 'Silver'
                        else:
                            client.tier = 'Bronze'
                        
                        db_sql.session.commit()
                        return client
                
                # Update client with retry for transient issues
                updated_client = db_operation_with_retry(update_client_loyalty)
                
            except Exception as e:
                # Fall back to old method
                transaction_id = create_transaction(
                    client_id=client_id, 
                    amount=amount, 
                    description=description,
                    points_used=points_to_redeem
                )
                
                # Update client's loyalty points in old system
                try:
                    client = get_client(client_id)
                    # Subtract redeemed points
                    client['loyalty_points'] = client.get('loyalty_points', 0) - points_to_redeem
                    # Add new points
                    client['loyalty_points'] = client.get('loyalty_points', 0) + points_earned
                    # Update total spent
                    client['total_spent'] = client.get('total_spent', 0) + amount
                    # Update tier
                    if client.get('total_spent', 0) >= 1000:
                        client['tier'] = 'Gold'
                    elif client.get('total_spent', 0) >= 500:
                        client['tier'] = 'Silver'
                    else:
                        client['tier'] = 'Bronze'
                except Exception as client_error:
                    print(f"Error updating client points: {str(client_error)}")
            
            # Generate and send receipt
            try:
                client_email = client.email if hasattr(client, 'email') else client.get('email')
                client_name = client.name if hasattr(client, 'name') else client.get('name')
                
                # Get business information from ConfigManager
                business_info = ConfigManager.get_business_info()
                
                receipt_html = render_template('email/receipt.html',
                                            transaction_id=transaction_id,
                                            client_name=client_name,
                                            amount=amount,
                                            description=description,
                                            date=datetime.utcnow(),
                                            loyalty_points_earned=points_earned,
                                            points_redeemed=points_to_redeem,
                                            payment_provider=payment_provider.capitalize(),
                                            business_name=business_info.get('name'),
                                            business_email=business_info.get('email'),
                                            business_phone=business_info.get('phone'))
                
                if client_email:
                    send_email(client_email, 'Your Receipt', receipt_html)
            except Exception as e:
                # Log error but don't fail the transaction
                print(f"Error sending receipt: {str(e)}")
            
            if request.is_json:
                return jsonify({'success': True, 'transaction_id': transaction_id})
            
            flash('Payment processed successfully')
            return redirect(url_for('pos.index'))
        else:
            # Handle payment requiring additional actions
            if payment_intent.status == 'requires_action':
                if request.is_json:
                    return jsonify({
                        'requires_action': True,
                        'payment_intent_client_secret': payment_intent.client_secret
                    })
                
                flash('Additional authentication required. Please try again.')
                return redirect(url_for('pos.index'))
            
            # Handle other payment statuses
            error_message = f"Payment failed with status: {payment_intent.status}"
            if request.is_json:
                return jsonify({'error': error_message}), 400
            
            flash(error_message, 'error')
            return redirect(url_for('pos.index'))
            
    except stripe.error.CardError as e:
        # Card was declined
        error_message = e.error.message
        if request.is_json:
            return jsonify({'error': error_message}), 400
        
        flash(f'Card error: {error_message}', 'error')
        return redirect(url_for('pos.index'))
        
    except stripe.error.StripeError as e:
        # Generic Stripe error
        error_message = str(e)
        if request.is_json:
            return jsonify({'error': error_message}), 400
        
        flash(f'Payment processing error: {error_message}', 'error')
        return redirect(url_for('pos.index'))
        
    except Exception as e:
        # Catch any other errors
        error_message = str(e)
        if request.is_json:
            return jsonify({'error': error_message}), 500
        
        flash(f'An unexpected error occurred: {error_message}', 'error')
        return redirect(url_for('pos.index'))

@bp.route('/pos/confirm-payment', methods=['POST'])
@login_required
def confirm_payment():
    """
    Confirm a payment after additional authentication steps (like 3D Secure)
    """
    if not request.is_json:
        return jsonify({'error': 'Invalid request format'}), 400
    
    data = request.json
    payment_intent_id = data.get('payment_intent_id')
    client_id = data.get('client_id')
    payment_provider = data.get('payment_provider', 'stripe')
    
    if not payment_intent_id or not client_id:
        return jsonify({'error': 'Missing required data'}), 400
    
    # Get loyalty points configuration
    points_per_dollar = ConfigManager.get_points_per_dollar()
    
    try:
        # Retrieve the payment intent from Stripe
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        
        # Verify that payment was successful
        if payment_intent.status != 'succeeded':
            return jsonify({
                'error': f'Payment not successful. Status: {payment_intent.status}'
            }), 400
        
        # Get payment details
        amount = payment_intent.amount / 100  # Convert from cents to dollars
        description = payment_intent.description or 'Payment'
        payment_method_id = payment_intent.payment_method
        
        # Calculate loyalty points earned
        points_earned = int(amount * points_per_dollar)
        
        # Create transaction in database
        try:
            # Try SQL database first
            transaction = create_transaction_sql(
                client_id=client_id,
                amount=amount,
                description=description,
                payment_method_id=payment_method_id,
                payment_intent_id=payment_intent_id,
                points_used=0,  # Cannot redeem points at this stage
                payment_provider=payment_provider
            )
            transaction_id = transaction.id
            
            # Update client's loyalty points
            def update_client_loyalty():
                # Find client
                client = db_sql.session.query(Client).get(client_id)
                if client:
                    # Add new points
                    client.loyalty_points += points_earned
                    # Update total spent
                    client.total_spent += amount
                    
                    # Update tier based on total spent
                    if client.total_spent >= 1000:
                        client.tier = 'Gold'
                    elif client.total_spent >= 500:
                        client.tier = 'Silver'
                    
                    db_sql.session.commit()
                    return client
            
            # Update client with retry for transient issues
            updated_client = db_operation_with_retry(update_client_loyalty)
            
        except Exception as e:
            # Fall back to old method
            transaction_id = create_transaction(
                client_id=client_id,
                amount=amount,
                description=description,
                points_used=0
            )
            
            # Update client's loyalty points in old system
            try:
                client = get_client(client_id)
                # Add new points
                client['loyalty_points'] = client.get('loyalty_points', 0) + points_earned
                # Update total spent
                client['total_spent'] = client.get('total_spent', 0) + amount
                # Update tier
                if client.get('total_spent', 0) >= 1000:
                    client['tier'] = 'Gold'
                elif client.get('total_spent', 0) >= 500:
                    client['tier'] = 'Silver'
            except Exception as client_error:
                print(f"Error updating client points: {str(client_error)}")
            
        # Send receipt email
        try:
            # Try both client models
            try:
                client = get_client_sql(client_id)
                client_email = client.email
                client_name = client.name
            except Exception:
                client = get_client(client_id)
                client_email = client.get('email')
                client_name = client.get('name')
            
            # Get business information from ConfigManager
            business_info = ConfigManager.get_business_info()
            
            receipt_html = render_template('email/receipt.html',
                                        transaction_id=transaction_id,
                                        client_name=client_name,
                                        amount=amount,
                                        description=description,
                                        date=datetime.utcnow(),
                                        loyalty_points_earned=points_earned,
                                        points_redeemed=0,
                                        payment_provider=payment_provider.capitalize(),
                                        business_name=business_info.get('name'),
                                        business_email=business_info.get('email'),
                                        business_phone=business_info.get('phone'))
            
            if client_email:
                send_email(client_email, 'Your Receipt', receipt_html)
        except Exception as e:
            # Log error but don't fail the transaction
            print(f"Error sending receipt: {str(e)}")
        
        return jsonify({
            'success': True,
            'transaction_id': transaction_id
        })
    except stripe.error.StripeError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/pos/refund/<string:id>', methods=['POST'])
@login_required
def refund_transaction(id):
    # Try to get transaction from SQL database first
    try:
        transaction = get_transaction_sql(id)
        if transaction is None:
            # Fall back to old method
            transaction = get_transaction(id)
            
        if not transaction:
            flash('Transaction not found')
            return redirect(url_for('pos.index'))
            
        # Get payment details based on model type
        if hasattr(transaction, 'payment_intent_id'):
            payment_intent_id = transaction.payment_intent_id
            payment_provider = transaction.payment_provider if hasattr(transaction, 'payment_provider') else 'stripe'
        else:
            payment_intent_id = transaction.get('payment_intent_id') or transaction.get('stripe_payment_intent_id')
            payment_provider = transaction.get('payment_provider', 'stripe')
            
        if not payment_intent_id:
            flash('This transaction has no associated payment to refund')
            return redirect(url_for('pos.index'))
        
        # Process the refund through the appropriate payment provider
        if payment_provider == 'stripe':
            # Process refund through Stripe
            refund = stripe.Refund.create(
                payment_intent=payment_intent_id
            )
        elif payment_provider == 'paystack':
            # Get Paystack secret key
            paystack_secret = ConfigManager.get_paystack_secret_key()
            if not paystack_secret:
                flash('Paystack API key not configured', 'error')
                return redirect(url_for('pos.index'))
                
            # Make refund request to Paystack API
            url = "https://api.paystack.co/refund"
            headers = {
                'Authorization': f'Bearer {paystack_secret}',
                'Content-Type': 'application/json'
            }
            payload = {
                'transaction': payment_intent_id
            }
            
            response = requests.post(url, headers=headers, json=payload)
            refund_data = response.json()
            
            if not response.status_code == 200 or not refund_data.get('status'):
                flash(f'Paystack refund failed: {refund_data.get("message", "Unknown error")}', 'error')
                return redirect(url_for('pos.index'))
        else:
            flash(f'Unsupported payment provider: {payment_provider}', 'error')
            return redirect(url_for('pos.index'))
        
        # Update the transaction status in the database
        if hasattr(transaction, 'payment_status'):
            # SQL model
            def update_transaction_status():
                transaction.payment_status = 'refunded'
                db_sql.session.commit()
                
                # Also refund the loyalty points - return redeemed points and deduct earned points
                client = db_sql.session.query(Client).get(transaction.client_id)
                if client:
                    # Return redeemed points
                    client.loyalty_points += transaction.points_used
                    # Deduct earned points
                    client.loyalty_points -= transaction.points_earned
                    # Deduct from total spent
                    client.total_spent -= transaction.amount
                    
                    # Re-evaluate tier based on adjusted total spent
                    if client.total_spent >= 1000:
                        client.tier = 'Gold'
                    elif client.total_spent >= 500:
                        client.tier = 'Silver'
                    else:
                        client.tier = 'Bronze'
                    
                    db_sql.session.commit()
                
            db_operation_with_retry(update_transaction_status)
        else:
            # Replit DB model
            from replit import db
            transaction['status'] = 'refunded'
            db[id] = transaction
            
            # Also try to handle points for old model
            try:
                client = get_client(transaction.get('client_id'))
                if client:
                    # Return redeemed points
                    client['loyalty_points'] = client.get('loyalty_points', 0) + transaction.get('points_used', 0)
                    # Deduct earned points
                    client['loyalty_points'] = client.get('loyalty_points', 0) - transaction.get('points_earned', 0)
                    # Deduct from total spent
                    client['total_spent'] = client.get('total_spent', 0) - transaction.get('amount', 0)
                    
                    # Re-evaluate tier
                    if client.get('total_spent', 0) >= 1000:
                        client['tier'] = 'Gold'
                    elif client.get('total_spent', 0) >= 500:
                        client['tier'] = 'Silver'
                    else:
                        client['tier'] = 'Bronze'
            except Exception as client_error:
                print(f"Error refunding client points: {str(client_error)}")
            
        flash('Transaction refunded successfully')
    except stripe.error.StripeError as e:
        flash(f'Error processing refund: {str(e)}')
    except Exception as e:
        flash(f'Error processing refund: {str(e)}')
        
    return redirect(url_for('pos.index'))