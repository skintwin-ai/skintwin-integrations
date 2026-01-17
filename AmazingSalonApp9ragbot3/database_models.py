from database import db_sql
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

class User(db_sql.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db_sql.Column(db_sql.Integer, primary_key=True)
    username = db_sql.Column(db_sql.String(100), nullable=False)
    email = db_sql.Column(db_sql.String(100), unique=True, nullable=False)
    password_hash = db_sql.Column(db_sql.String(255), nullable=False)
    is_staff = db_sql.Column(db_sql.Boolean, default=False)
    is_admin = db_sql.Column(db_sql.Boolean, default=False)
    two_factor_enabled = db_sql.Column(db_sql.Boolean, default=False)
    two_factor_secret = db_sql.Column(db_sql.String(255), nullable=True)
    openai_api_key = db_sql.Column(db_sql.String(255), nullable=True)
    created_at = db_sql.Column(db_sql.DateTime, default=datetime.utcnow)
    
    # Relationships
    shifts = db_sql.relationship('Shift', backref='staff', lazy=True)
    appointments_as_esthetician = db_sql.relationship('Appointment', backref='esthetician', lazy=True, foreign_keys='Appointment.esthetician_id')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Client(db_sql.Model):
    __tablename__ = 'clients'
    
    id = db_sql.Column(db_sql.Integer, primary_key=True)
    name = db_sql.Column(db_sql.String(100), nullable=False)
    email = db_sql.Column(db_sql.String(100), unique=True, nullable=False)
    phone = db_sql.Column(db_sql.String(20), nullable=False)
    loyalty_points = db_sql.Column(db_sql.Integer, default=0)
    total_spent = db_sql.Column(db_sql.Float, default=0.0)
    tier = db_sql.Column(db_sql.String(20), default='Bronze')
    created_at = db_sql.Column(db_sql.DateTime, default=datetime.utcnow)
    
    # Client preferences
    skin_type = db_sql.Column(db_sql.String(20), default='normal')
    skin_concern = db_sql.Column(db_sql.String(50), default='hydration')
    sensitivity_level = db_sql.Column(db_sql.String(20), default='low')
    
    # Relationships
    appointments = db_sql.relationship('Appointment', backref='client', lazy=True)
    transactions = db_sql.relationship('Transaction', backref='client', lazy=True)
    portfolio_entries = db_sql.relationship('PortfolioEntry', backref='client', lazy=True)
    
    def __repr__(self):
        return f'<Client {self.name}>'

class Service(db_sql.Model):
    __tablename__ = 'services'
    
    id = db_sql.Column(db_sql.Integer, primary_key=True)
    name = db_sql.Column(db_sql.String(100), nullable=False)
    description = db_sql.Column(db_sql.Text, nullable=True)
    price = db_sql.Column(db_sql.Float, nullable=False)
    duration = db_sql.Column(db_sql.Integer, nullable=False)  # in minutes
    category = db_sql.Column(db_sql.String(50), nullable=True)
    popularity = db_sql.Column(db_sql.Integer, default=0)
    created_at = db_sql.Column(db_sql.DateTime, default=datetime.utcnow)
    
    # Relationships
    appointments = db_sql.relationship('Appointment', backref='service_rel', lazy=True)
    portfolio_entries = db_sql.relationship('PortfolioEntry', backref='service_rel', lazy=True)

    def __repr__(self):
        return f'<Service {self.name}>'

class Appointment(db_sql.Model):
    __tablename__ = 'appointments'
    
    id = db_sql.Column(db_sql.Integer, primary_key=True)
    client_id = db_sql.Column(db_sql.Integer, db_sql.ForeignKey('clients.id'), nullable=False)
    esthetician_id = db_sql.Column(db_sql.Integer, db_sql.ForeignKey('users.id'), nullable=False)
    service_id = db_sql.Column(db_sql.Integer, db_sql.ForeignKey('services.id'), nullable=False)
    date_time = db_sql.Column(db_sql.DateTime, nullable=False)
    status = db_sql.Column(db_sql.String(20), default='scheduled')  # scheduled, completed, cancelled, no-show
    created_at = db_sql.Column(db_sql.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Appointment {self.id} - {self.date_time}>'

class Transaction(db_sql.Model):
    __tablename__ = 'transactions'
    
    id = db_sql.Column(db_sql.Integer, primary_key=True)
    client_id = db_sql.Column(db_sql.Integer, db_sql.ForeignKey('clients.id'), nullable=False)
    amount = db_sql.Column(db_sql.Float, nullable=False)
    date_time = db_sql.Column(db_sql.DateTime, default=datetime.utcnow)
    description = db_sql.Column(db_sql.Text, nullable=True)
    points_earned = db_sql.Column(db_sql.Integer, default=0)
    points_used = db_sql.Column(db_sql.Integer, default=0)
    
    # Payment fields
    payment_provider = db_sql.Column(db_sql.String(50), default='stripe')  # stripe, paystack
    payment_intent_id = db_sql.Column(db_sql.String(255), nullable=True)  # Stripe payment_intent_id or Paystack reference
    payment_method_id = db_sql.Column(db_sql.String(255), nullable=True)  # Stripe payment_method_id or Paystack authorization code
    payment_status = db_sql.Column(db_sql.String(50), default='pending')  # pending, completed, failed, refunded
    
    def __repr__(self):
        return f'<Transaction {self.id} - {self.amount}>'

class Product(db_sql.Model):
    __tablename__ = 'products'
    
    id = db_sql.Column(db_sql.Integer, primary_key=True)
    name = db_sql.Column(db_sql.String(100), nullable=False)
    description = db_sql.Column(db_sql.Text, nullable=True)
    price = db_sql.Column(db_sql.Float, nullable=False)
    quantity = db_sql.Column(db_sql.Integer, default=0)
    reorder_level = db_sql.Column(db_sql.Integer, default=10)
    category = db_sql.Column(db_sql.String(50), nullable=True)
    supplier = db_sql.Column(db_sql.String(100), nullable=True)
    created_at = db_sql.Column(db_sql.DateTime, default=datetime.utcnow)
    updated_at = db_sql.Column(db_sql.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    purchase_orders = db_sql.relationship('PurchaseOrder', backref='product', lazy=True)

    def __repr__(self):
        return f'<Product {self.name}>'

class PurchaseOrder(db_sql.Model):
    __tablename__ = 'purchase_orders'
    
    id = db_sql.Column(db_sql.Integer, primary_key=True)
    product_id = db_sql.Column(db_sql.Integer, db_sql.ForeignKey('products.id'), nullable=False)
    quantity = db_sql.Column(db_sql.Integer, nullable=False)
    supplier = db_sql.Column(db_sql.String(100), nullable=True)
    status = db_sql.Column(db_sql.String(20), default='pending')  # pending, ordered, received, cancelled
    created_at = db_sql.Column(db_sql.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<PurchaseOrder {self.id} - {self.product.name if self.product else "Unknown"}>'

class Shift(db_sql.Model):
    __tablename__ = 'shifts'
    
    id = db_sql.Column(db_sql.Integer, primary_key=True)
    staff_id = db_sql.Column(db_sql.Integer, db_sql.ForeignKey('users.id'), nullable=False)
    start_time = db_sql.Column(db_sql.DateTime, nullable=False)
    end_time = db_sql.Column(db_sql.DateTime, nullable=False)
    status = db_sql.Column(db_sql.String(20), default='scheduled')  # scheduled, completed, cancelled
    
    # Relationships
    breaks = db_sql.relationship('ShiftBreak', backref='shift', lazy=True)
    
    def __repr__(self):
        return f'<Shift {self.id} - {self.start_time} to {self.end_time}>'

class ShiftBreak(db_sql.Model):
    __tablename__ = 'shift_breaks'
    
    id = db_sql.Column(db_sql.Integer, primary_key=True)
    shift_id = db_sql.Column(db_sql.Integer, db_sql.ForeignKey('shifts.id'), nullable=False)
    start_time = db_sql.Column(db_sql.DateTime, nullable=False)
    end_time = db_sql.Column(db_sql.DateTime, nullable=False)
    
    def __repr__(self):
        return f'<ShiftBreak {self.id} - {self.start_time} to {self.end_time}>'

class PortfolioEntry(db_sql.Model):
    __tablename__ = 'portfolio_entries'
    
    id = db_sql.Column(db_sql.Integer, primary_key=True)
    client_id = db_sql.Column(db_sql.Integer, db_sql.ForeignKey('clients.id'), nullable=False)
    service_id = db_sql.Column(db_sql.Integer, db_sql.ForeignKey('services.id'), nullable=False)
    esthetician_id = db_sql.Column(db_sql.Integer, db_sql.ForeignKey('users.id'), nullable=False)
    photo_url = db_sql.Column(db_sql.String(255), nullable=False)
    notes = db_sql.Column(db_sql.Text, nullable=True)
    date_time = db_sql.Column(db_sql.DateTime, default=datetime.utcnow)
    
    # Relationship to esthetician
    esthetician = db_sql.relationship('User', backref='portfolio_entries', foreign_keys=[esthetician_id])
    
    def __repr__(self):
        return f'<PortfolioEntry {self.id} - {self.client.name if self.client else "Unknown"} - {self.service_rel.name if self.service_rel else "Unknown"}>'