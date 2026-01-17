"""
Routes for AI-powered service trend prediction dashboard
"""
from flask import render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import json

from database import db_sql
from database_models import Service, Appointment, Transaction, User
from salon_math.trend_prediction import TrendPredictor
from routes.auth import admin_required

def register_routes(app):
    """Register trend prediction routes with the Flask app"""
    
    @app.route('/trends')
    @login_required
    def trend_dashboard():
        """Service trend prediction dashboard"""
        return render_template('trends/dashboard.html')
    
    @app.route('/trends/service_popularity')
    @login_required
    def service_popularity_trends():
        """Get service popularity trends data"""
        time_period = request.args.get('time_period', 'month')
        
        # Get services
        services = Service.query.all()
        
        # Get appointment data
        appointments = []
        appointment_records = Appointment.query.all()
        for appointment in appointment_records:
            appointments.append({
                'service_id': appointment.service_id,
                'date_time': appointment.date_time,
                'status': appointment.status
            })
            
        # Get transaction data with service info from appointments
        transactions = []
        transaction_records = Transaction.query.all()
        for transaction in transaction_records:
            # For simplicity, associate transactions with appointments based on client
            # In a real system, you'd have a direct link between transactions and services
            client_appointments = Appointment.query.filter_by(client_id=transaction.client_id).all()
            if client_appointments:
                for appointment in client_appointments:
                    if abs((appointment.date_time - transaction.date_time).total_seconds()) < 86400:  # Within 24h
                        transactions.append({
                            'service_id': appointment.service_id,
                            'amount': transaction.amount,
                            'date_time': transaction.date_time,
                            'created_at': transaction.date_time
                        })
                        break
        
        # Combine appointments and transactions for analysis
        service_data = appointments + transactions
        
        # Get trend predictions
        service_trends = TrendPredictor.predict_service_popularity(service_data, time_period)
        
        # Map service IDs to names and add service details
        result = {}
        for service_id, trend_data in service_trends.items():
            service = Service.query.get(service_id)
            if service:
                result[service_id] = {
                    **trend_data,
                    'service_name': service.name,
                    'service_price': service.price,
                    'service_category': service.category
                }
        
        return jsonify(result)
    
    @app.route('/trends/peak_times')
    @login_required
    def peak_times_analysis():
        """Get peak appointment time analysis"""
        granularity = request.args.get('granularity', 'day_of_week')
        
        # Get appointments
        appointments = []
        appointment_records = Appointment.query.all()
        for appointment in appointment_records:
            appointments.append({
                'service_id': appointment.service_id,
                'date_time': appointment.date_time,
                'status': appointment.status
            })
        
        # Get peak time predictions
        peak_times_data = TrendPredictor.predict_peak_times(appointments, granularity)
        
        return jsonify(peak_times_data)
    
    @app.route('/trends/recommendations')
    @login_required
    def optimization_recommendations():
        """Get business optimization recommendations"""
        
        # Get service trend data
        time_period = request.args.get('time_period', 'month')
        
        # Get services
        services = Service.query.all()
        
        # Get appointment data
        appointments = []
        appointment_records = Appointment.query.all()
        for appointment in appointment_records:
            appointments.append({
                'service_id': appointment.service_id,
                'date_time': appointment.date_time,
                'status': appointment.status
            })
            
        # Get transaction data with service info from appointments
        transactions = []
        transaction_records = Transaction.query.all()
        for transaction in transaction_records:
            # For simplicity, associate transactions with appointments based on client
            client_appointments = Appointment.query.filter_by(client_id=transaction.client_id).all()
            if client_appointments:
                for appointment in client_appointments:
                    if abs((appointment.date_time - transaction.date_time).total_seconds()) < 86400:  # Within 24h
                        transactions.append({
                            'service_id': appointment.service_id,
                            'amount': transaction.amount,
                            'date_time': transaction.date_time,
                            'created_at': transaction.date_time
                        })
                        break
        
        # Combine appointments and transactions for analysis
        service_data = appointments + transactions
        
        # Get trend predictions
        service_trends = TrendPredictor.predict_service_popularity(service_data, time_period)
        
        # Get peak times data
        granularity = request.args.get('granularity', 'day_of_week')
        peak_times_data = TrendPredictor.predict_peak_times(appointments, granularity)
        
        # Generate recommendations
        recommendations = TrendPredictor.generate_optimization_recommendations(service_trends, peak_times_data)
        
        # Enhance recommendations with service details
        for rec in recommendations:
            if 'service_id' in rec:
                service = Service.query.get(rec['service_id'])
                if service:
                    rec['service_name'] = service.name
                    rec['service_category'] = service.category
        
        return jsonify(recommendations)