
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
import models
from datetime import datetime
import json
import random
from sqlalchemy.exc import OperationalError, DatabaseError

bp = Blueprint('portfolio', __name__, url_prefix='/portfolio')

@bp.route('/')
def index():
    """Client Portfolio landing page"""
    try:
        clients = models.get_all_clients()
        return render_template('portfolio_index.html', clients=clients)
    except (OperationalError, DatabaseError) as e:
        # Log the error
        current_app.logger.error(f"Database error in portfolio.index: {str(e)}")
        
        # Try to recover the connection
        db_sql = current_app.extensions['sqlalchemy'].db
        db_sql.session.rollback()
        db_sql.session.remove()
        
        # Try once more
        try:
            clients = models.get_all_clients()
            return render_template('portfolio_index.html', clients=clients)
        except Exception as retry_error:
            current_app.logger.error(f"Failed to reconnect: {str(retry_error)}")
            flash("Database connection error. Please try again later.", "error")
            return render_template('portfolio_index.html', clients=[])

@bp.route('/<client_id>')
def view_client_portfolio(client_id):
    """View a specific client's style portfolio"""
    try:
        client = models.get_client(client_id)
        if not client:
            flash('Client not found', 'error')
            return redirect(url_for('portfolio.index'))
        
        # Get client portfolio entries
        portfolio_entries = models.get_client_portfolio_entries(client_id)
        
        # Get all services for adding new portfolio entries
        services = models.get_all_services()
        
        return render_template('client_portfolio.html', 
                              client=client, 
                              portfolio_entries=portfolio_entries,
                              services=services)
    except (OperationalError, DatabaseError) as e:
        # Log the error
        current_app.logger.error(f"Database error in portfolio.view_client_portfolio: {str(e)}")
        
        # Try to recover the connection
        db_sql = current_app.extensions['sqlalchemy'].db
        db_sql.session.rollback()
        db_sql.session.remove()
        
        # Try once more
        try:
            client = models.get_client(client_id)
            if not client:
                flash('Client not found', 'error')
                return redirect(url_for('portfolio.index'))
            
            portfolio_entries = models.get_client_portfolio_entries(client_id)
            services = models.get_all_services()
            
            return render_template('client_portfolio.html', 
                                  client=client, 
                                  portfolio_entries=portfolio_entries,
                                  services=services)
        except Exception as retry_error:
            current_app.logger.error(f"Failed to reconnect: {str(retry_error)}")
            flash("Database connection error. Please try again later.", "error")
            return redirect(url_for('portfolio.index'))

@bp.route('/<client_id>/add', methods=['POST'])
@login_required
def add_portfolio_entry(client_id):
    """Add a new entry to client's portfolio"""
    client = models.get_client(client_id)
    if not client:
        flash('Client not found', 'error')
        return redirect(url_for('portfolio.index'))
    
    # Process form data
    service_id = request.form.get('service_id')
    notes = request.form.get('notes', '')
    stylist_id = request.form.get('stylist_id', current_user.get_id())
    
    # For a real implementation, handle photo upload
    # Here we're just simulating it
    photo_url = request.form.get('photo_url', '/static/img/default_style.jpg')
    
    # Create portfolio entry
    entry_id = models.create_portfolio_entry(
        client_id=client_id,
        service_id=service_id,
        stylist_id=stylist_id,
        photo_url=photo_url,
        notes=notes
    )
    
    if entry_id:
        flash('Portfolio entry added successfully!', 'success')
    else:
        flash('Failed to add portfolio entry', 'error')
        
    return redirect(url_for('portfolio.view_client_portfolio', client_id=client_id))

@bp.route('/<client_id>/entry/<entry_id>/delete', methods=['POST'])
@login_required
def delete_portfolio_entry(client_id, entry_id):
    """Delete a portfolio entry"""
    if models.delete_portfolio_entry(entry_id):
        flash('Portfolio entry deleted', 'success')
    else:
        flash('Failed to delete entry', 'error')
        
    return redirect(url_for('portfolio.view_client_portfolio', client_id=client_id))
