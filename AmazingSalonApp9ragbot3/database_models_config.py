"""
Database models for system configuration
"""
from database import db_sql
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB

class SystemConfig(db_sql.Model):
    """Model to store system configuration settings"""
    __tablename__ = 'system_config'
    
    id = db_sql.Column(db_sql.Integer, primary_key=True)
    key = db_sql.Column(db_sql.String(255), unique=True, nullable=False)
    value = db_sql.Column(db_sql.Text, nullable=True)
    description = db_sql.Column(db_sql.Text, nullable=True)
    category = db_sql.Column(db_sql.String(50), nullable=False, default='general')
    is_sensitive = db_sql.Column(db_sql.Boolean, default=False)  # For API keys and sensitive data
    created_at = db_sql.Column(db_sql.DateTime, default=datetime.utcnow)
    updated_at = db_sql.Column(db_sql.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db_sql.Column(db_sql.Integer, db_sql.ForeignKey('users.id'), nullable=True)
    
    def __repr__(self):
        return f"<SystemConfig {self.key}={self.value[:20] + '...' if self.value and len(self.value) > 20 else self.value}>"