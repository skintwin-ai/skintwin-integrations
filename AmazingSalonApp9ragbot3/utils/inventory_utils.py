
from models import get_low_stock_products, create_purchase_order
from .email_utils import send_inventory_alert

def check_and_reorder_inventory():
    low_stock_items = get_low_stock_products()
    
    for item in low_stock_items:
        # Create purchase order for items below reorder level
        if item['quantity'] <= item['reorder_level']:
            reorder_quantity = max(
                item['reorder_level'] * 2 - item['quantity'],
                10  # Minimum reorder quantity
            )
            
            create_purchase_order(
                product_id=item['id'],
                quantity=reorder_quantity,
                supplier=item.get('supplier')
            )
    
    # Send alert to manager if any items are low
    if low_stock_items:
        send_inventory_alert(low_stock_items, 'manager@salon.com')
def check_and_reorder_inventory():
    from models import get_low_stock_products, create_purchase_order
    
    # Check all products with low stock
    low_stock = get_low_stock_products()
    
    for product in low_stock:
        # Create purchase order for twice the reorder level
        reorder_quantity = product['reorder_level'] * 2
        po_id = create_purchase_order(
            product_id=product['id'],
            quantity=reorder_quantity,
            supplier=product.get('supplier')
        )
