from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from database_models import User
from database import db_sql
# Import SQLAlchemy models and functions
from database_utils import get_user_by_email_sql, create_user_sql, update_user_sql
import pyotp
from functools import wraps
# Import Replit DB function for legacy support
from models import get_user, update_user

auth_bp = Blueprint('auth', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You need to be an admin to access this page.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def ensure_admin_user():
    # Create a dummy admin user for development purposes
    admin_email = 'admin@salon.dev'
    admin_password = 'admin123'
    
    # Try to get admin user from SQL database
    admin_user_sql = get_user_by_email_sql(admin_email)
    
    if not admin_user_sql:
        # Try legacy database
        admin_user = get_user(f"user_{admin_email}")
        
        if not admin_user:
            # Create new admin user in SQL database
            create_user_sql('Admin', admin_email, admin_password, is_staff=True, is_admin=True)
            print(f"Dev admin user created - Email: {admin_email}, Password: {admin_password}")
        else:
            # Migrate legacy user to SQL database
            create_user_sql('Admin', admin_email, admin_password, is_staff=True, is_admin=True)
            print(f"Dev admin user migrated from legacy DB - Email: {admin_email}, Password: {admin_password}")
    else:
        # Update existing SQL admin user
        admin_user_sql.is_admin = True
        admin_user_sql.is_staff = True
        admin_user_sql.username = 'Admin'
        admin_user_sql.set_password(admin_password)
        update_user_sql(admin_user_sql.id, is_admin=True, is_staff=True, username='Admin', 
                      password_hash=admin_user_sql.password_hash)
        print(f"Dev admin user updated - Email: {admin_email}, Password: {admin_password}")

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Check SQL database first
        existing_user_sql = get_user_by_email_sql(email)
        if existing_user_sql:
            flash('Email address already exists')
            return redirect(url_for('auth.register'))
            
        # Check legacy database as well
        existing_user = get_user(f"user_{email}")
        if existing_user:
            flash('Email address already exists')
            return redirect(url_for('auth.register'))

        # Create user in SQL database
        user_id = create_user_sql(username, email, password)

        flash('Registration successful. Please log in.')
        return redirect(url_for('auth.login'))

    return render_template('register.html')

@auth_bp.route('/register_admin', methods=['GET', 'POST'])
def register_admin():
    # Check if any admin exists
    if User.query.filter_by(is_admin=True).first():
        return "Admin already exists", 403

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if not username or not email or not password:
            flash('Please fill all fields')
            return redirect(url_for('auth.register_admin'))

        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            is_admin=True
        )

        db_sql.session.add(user)
        db_sql.session.commit()

        login_user(user)
        return redirect(url_for('index'))

    return render_template('register_admin.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))

        flash('Invalid credentials')
    return render_template('login.html')

@auth_bp.route('/setup-2fa')
@login_required
def setup_2fa():
    # Check if the user is a SQLAlchemy model or legacy
    if hasattr(current_user, 'id') and isinstance(current_user.id, int):
        # SQL user
        if not current_user.two_factor_secret:
            secret = pyotp.random_base32()
            # Update in SQL database
            current_user.two_factor_secret = secret
            update_user_sql(current_user.id, two_factor_secret=secret)
            totp = pyotp.TOTP(secret)
            provisioning_uri = totp.provisioning_uri(current_user.email, issuer_name="Salon Management")
            return render_template('2fa_setup.html', secret=secret, qr_uri=provisioning_uri)
    else:
        # Legacy user
        if not current_user.two_factor_secret:
            secret = pyotp.random_base32()
            update_user(f"user_{current_user.email}", two_factor_secret=secret)
            totp = pyotp.TOTP(secret)
            provisioning_uri = totp.provisioning_uri(current_user.email, issuer_name="Salon Management")
            return render_template('2fa_setup.html', secret=secret, qr_uri=provisioning_uri)
    
    return redirect(url_for('index'))

@auth_bp.route('/verify-2fa', methods=['POST'])
@login_required
def verify_2fa():
    code = request.form.get('code')
    
    # Check if the user is a SQLAlchemy model or legacy
    if hasattr(current_user, 'id') and isinstance(current_user.id, int):
        # SQL user
        totp = pyotp.TOTP(current_user.two_factor_secret)
        
        if totp.verify(code):
            current_user.two_factor_enabled = True
            update_user_sql(current_user.id, two_factor_enabled=True)
            flash('Two-factor authentication enabled successfully!')
            return redirect(url_for('index'))
    else:
        # Legacy user
        user = get_user(f"user_{current_user.email}")
        totp = pyotp.TOTP(user['two_factor_secret'])
        
        if totp.verify(code):
            update_user(f"user_{current_user.email}", two_factor_enabled=True)
            flash('Two-factor authentication enabled successfully!')
            return redirect(url_for('index'))

    flash('Invalid verification code')
    return redirect(url_for('auth.setup_2fa'))

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/admin_dashboard')
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html')