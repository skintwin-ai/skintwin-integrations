
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import create_service, get_service, update_service, delete_service, get_all_services

bp = Blueprint('services', __name__)

@bp.route('/services')
@login_required
def index():
    services = get_all_services()
    return render_template('services.html', services=services)

@bp.route('/services/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        duration = int(request.form['duration'])
        
        create_service(name, description, price, duration)
        flash('Service created successfully')
        return redirect(url_for('services.index'))
    
    return render_template('services_form.html')

@bp.route('/services/edit/<string:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    service = get_service(id)
    if not service:
        flash('Service not found')
        return redirect(url_for('services.index'))
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        duration = int(request.form['duration'])
        
        update_service(id, name=name, description=description, price=price, duration=duration)
        flash('Service updated successfully')
        return redirect(url_for('services.index'))
    
    return render_template('services_form.html', service=service)

@bp.route('/services/delete/<string:id>', methods=['POST'])
@login_required
def delete(id):
    if delete_service(id):
        flash('Service deleted successfully')
    else:
        flash('Service not found')
    return redirect(url_for('services.index'))
