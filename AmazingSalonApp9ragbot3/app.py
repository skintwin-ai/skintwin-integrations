import os
from flask import Flask, request, send_file, jsonify
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from replit import db
import io
import csv
from database import db_sql
from io import BytesIO # Added BytesIO import for CSV export fix

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("FLASK_SECRET_KEY") or "a secret key"
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///salon.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'pool_timeout': 30,
    'pool_size': 10,
    'max_overflow': 5
}

# Initialize extensions
db_sql.init_app(app)
migrate = Migrate(app, db_sql)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)
login_manager = LoginManager()
csrf = CSRFProtect()

login_manager.init_app(app)
csrf.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    from database_models import User as SQLUser
    try:
        # Try SQL database first
        user = SQLUser.query.get(int(user_id))
        if user:
            return user

        # Fallback to Replit db
        user_data = db.get(user_id)
        if user_data and isinstance(user_data, dict):
            user_obj = type('User', (), {
                'id': user_id,
                'is_authenticated': True,
                'is_active': True,
                'is_anonymous': False,
                'get_id': lambda: str(user_id),
                **user_data
            })
            return user_obj
    except Exception as e:
        print(f"Error loading user: {e}")
    return None


# Import and register blueprints after app creation
with app.app_context():
    # Create database tables
    db_sql.create_all()

    # Import and register blueprints
    from routes import auth, appointments, clients, pos, staff, reports, inventory, services, booking, analytics, recommendations, smart_booking, portfolio, voice_assistant, chat_assistant, memory_timeline, journey_map, settings, trends, skill_playground
    app.register_blueprint(auth.auth_bp)
    app.register_blueprint(appointments.bp)
    app.register_blueprint(clients.bp)
    app.register_blueprint(pos.bp)
    app.register_blueprint(staff.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(inventory.bp)
    app.register_blueprint(services.bp)
    app.register_blueprint(booking.bp)
    app.register_blueprint(analytics.bp)
    app.register_blueprint(recommendations.bp)
    app.register_blueprint(smart_booking.bp)
    app.register_blueprint(portfolio.bp)
    app.register_blueprint(voice_assistant.bp)
    app.register_blueprint(chat_assistant.bp)
    app.register_blueprint(memory_timeline.memory_timeline, url_prefix='/memory-timeline')
    app.register_blueprint(journey_map.journey_map, url_prefix='/journey-map')
    app.register_blueprint(settings.bp)
    
    # Register skill playground routes
    skill_playground.register_routes(app)
    
    # Register functional routes (non-blueprint)
    from routes import trends
    trends.register_routes(app)

@app.route('/')
def index():
    from flask import render_template, redirect, url_for
    from flask_login import current_user

    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    return render_template('index.html')





if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)