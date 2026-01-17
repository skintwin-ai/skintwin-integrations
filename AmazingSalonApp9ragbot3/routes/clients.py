from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from models import create_client, get_client, get_all_clients 
from database_utils import create_client_sql, get_client_sql, update_client_sql, delete_client_sql
from sqlalchemy.exc import OperationalError, DatabaseError

bp = Blueprint('clients', __name__)

@bp.route('/clients')
@login_required
def index():
    try:
        clients = get_all_clients()
        return render_template('clients.html', clients=clients)
    except (OperationalError, DatabaseError) as e:
        # Log the error
        current_app.logger.error(f"Database error in clients.index: {str(e)}")
        
        # Try to recover the connection
        db_sql = current_app.extensions['sqlalchemy'].db
        db_sql.session.rollback()
        db_sql.session.remove()
        
        # Try once more
        try:
            clients = get_all_clients()
            return render_template('clients.html', clients=clients)
        except Exception as retry_error:
            current_app.logger.error(f"Failed to reconnect: {str(retry_error)}")
            flash("Database connection error. Please try again later.", "error")
            return render_template('clients.html', clients=[])

@bp.route('/clients/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        
        client_id = create_client_sql(name, email, phone)
        
        flash('Client created successfully')
        return redirect(url_for('clients.index'))
    
    return render_template('clients.html')

@bp.route('/clients/update/<int:id>', methods=['GET', 'POST'])
@login_required
def update(id):
    client = get_client(id)
    
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        
        update_client_sql(id, name=name, email=email, phone=phone)
        flash('Client updated successfully')
        return redirect(url_for('clients.index'))
    
    return render_template('clients.html', client=client)

@bp.route('/clients/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    if delete_client_sql(id):
        flash('Client deleted successfully')
    else:
        flash('Client not found', 'error')
    return redirect(url_for('clients.index'))
