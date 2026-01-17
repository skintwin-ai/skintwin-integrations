from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from models import create_product, get_product, update_product, delete_product, get_all_products, get_low_stock_products, get_product_categories, get_all_users, create_purchase_order, get_all_purchase_orders
from io import BytesIO, StringIO

bp = Blueprint('inventory', __name__)

ITEMS_PER_PAGE = 10

@bp.route('/inventory')
@login_required
def index():
    search_query = request.args.get('search', '')
    category_filter = request.args.get('category', '')
    stock_status = request.args.get('stock_status', '')
    page = int(request.args.get('page', 1))

    products = get_all_products()

    if search_query:
        products = [p for p in products if search_query.lower() in p['name'].lower() or search_query.lower() in p['description'].lower()]
    if category_filter:
        products = [p for p in products if p.get('category') == category_filter]
    if stock_status == 'low':
        products = [p for p in products if p['quantity'] <= p['reorder_level']]
    elif stock_status == 'normal':
        products = [p for p in products if p['quantity'] > p['reorder_level']]

    total_products = len(products)
    total_pages = (total_products + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

    start_index = (page - 1) * ITEMS_PER_PAGE
    end_index = start_index + ITEMS_PER_PAGE
    products_page = products[start_index:end_index]

    low_stock_products = get_low_stock_products()
    categories = get_product_categories()

    return render_template('inventory.html', 
                           products=products_page, 
                           low_stock_products=low_stock_products, 
                           search_query=search_query, 
                           categories=categories, 
                           selected_category=category_filter,
                           stock_status=stock_status,
                           current_page=page,
                           total_pages=total_pages)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        quantity = int(request.form['quantity'])
        reorder_level = int(request.form['reorder_level'])
        category = request.form['category']

        create_product(name, description, price, quantity, reorder_level, category)

        if quantity <= reorder_level:
            from utils.email_utils import send_inventory_alert
            try:
                manager_email = current_user.email
                send_inventory_alert([{'name': name, 'quantity': quantity}], manager_email)
                flash('Product created successfully and low stock alert sent', 'success')
            except Exception as e:
                flash('Product created successfully but email notification failed', 'warning')
        else:
            flash('Product created successfully', 'success')
        return redirect(url_for('inventory.index'))

    return render_template('inventory_form.html', product=None, categories=get_product_categories())

@bp.route('/purchase_orders')
@login_required
def purchase_orders():
    pos = get_all_purchase_orders()
    return render_template('purchase_orders.html', purchase_orders=pos)

@bp.route('/auto_reorder', methods=['POST'])
@login_required
def auto_reorder():
    low_stock = get_low_stock_products()
    created_pos = []

    for product in low_stock:
        reorder_quantity = (product['reorder_level'] - product['quantity']) * 2
        if reorder_quantity > 0:
            po_id = create_purchase_order(product['id'], reorder_quantity)
            if po_id:
                created_pos.append(po_id)

    if created_pos:
        flash(f'Created {len(created_pos)} purchase orders for low stock items', 'success')
    else:
        flash('No purchase orders needed at this time', 'info')

    return redirect(url_for('inventory.purchase_orders'))

@bp.route('/edit/<string:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    product = get_product(id)
    if not product:
        flash('Product not found', 'error')
        return redirect(url_for('inventory.index'))

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        quantity = int(request.form['quantity'])
        reorder_level = int(request.form['reorder_level'])
        category = request.form['category']

        update_product(id, name=name, description=description, price=price, quantity=quantity, reorder_level=reorder_level, category=category)

        flash('Product updated successfully')

        # Check for low stock after update
        low_stock_items = get_low_stock_products()
        if low_stock_items:
            admin_users = [user for user in get_all_users() if user.get('is_admin')]
            from utils.email_utils import send_low_inventory_alert
            for admin in admin_users:
                try:
                    send_low_inventory_alert(admin['email'], low_stock_items)
                except Exception as e:
                    flash(f"Low stock alert failed to send to {admin['email']}: {e}", 'error')


        return redirect(url_for('inventory.index'))

    return render_template('inventory_form.html', product=product, categories=get_product_categories())

@bp.route('/delete/<string:id>', methods=['POST'])
@login_required
def delete(id):
    if delete_product(id):
        flash('Product deleted successfully', 'success')
    else:
        flash('Product not found', 'error')
    return redirect(url_for('inventory.index'))

@bp.route('/bulk_update', methods=['POST'])
@login_required
def bulk_update():
    product_ids = request.form.getlist('product_ids[]')
    action = request.form.get('action')

    if action == 'update_quantity':
        new_quantity = request.form.get('new_quantity', '')
        if new_quantity.strip():
            try:
                new_quantity = int(new_quantity)
                for product_id in product_ids:
                    update_product(product_id, quantity=new_quantity)
                flash('Products quantity updated successfully', 'success')
            except ValueError:
                flash('Invalid quantity value', 'error')
        else:
            flash('No quantity value provided', 'error')

    elif action == 'update_price':
        price_change = request.form.get('price_change', '')
        price_change_type = request.form.get('price_change_type')
        if price_change.strip():
            try:
                price_change = float(price_change)
                for product_id in product_ids:
                    product = get_product(product_id)
                    if price_change_type == 'fixed':
                        new_price = product['price'] + price_change
                    else:  # percentage
                        new_price = product['price'] * (1 + price_change / 100)
                    update_product(product_id, price=round(new_price, 2))
                flash('Products price updated successfully', 'success')
            except ValueError:
                flash('Invalid price change value', 'error')
        else:
            flash('No price change value provided', 'error')

    elif action == 'delete':
        for product_id in product_ids:
            delete_product(product_id)
        flash('Selected products deleted successfully', 'success')

    return redirect(url_for('inventory.index'))

@bp.route('/export_csv')
@login_required
def export_csv():
    products = get_all_products()
    output = BytesIO()

    # Write BOM for Excel compatibility
    output.write(b'\xef\xbb\xbf')

    # Write header
    header = 'ID,Name,Description,Price,Quantity,Reorder Level,Category\n'
    output.write(header.encode('utf-8'))

    # Write data
    for product in products:
        row = [
            str(product.get('id', '')),
            str(product.get('name', '')).replace(',', ';'),
            str(product.get('description', '')).replace(',', ';'),
            str(product.get('price', '')),
            str(product.get('quantity', '')),
            str(product.get('reorder_level', '')),
            str(product.get('category', '')).replace(',', ';')
        ]
        line = ','.join(row) + '\n'
        output.write(line.encode('utf-8'))

    output.seek(0)
    return send_file(
        output,
        mimetype='text/csv',
        as_attachment=True,
        download_name='inventory_report.csv'
    )