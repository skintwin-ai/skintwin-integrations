from database import db_sql
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB

class ChatConversation(db_sql.Model):
    """Model to store chat conversations between users and the AI assistant"""
    __tablename__ = 'chat_conversations'
    
    id = db_sql.Column(db_sql.Integer, primary_key=True)
    user_id = db_sql.Column(db_sql.Integer, db_sql.ForeignKey('users.id'), nullable=False)
    title = db_sql.Column(db_sql.String(255), nullable=True)
    created_at = db_sql.Column(db_sql.DateTime, default=datetime.utcnow)
    updated_at = db_sql.Column(db_sql.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    messages = db_sql.relationship('ChatMessage', backref='conversation', lazy=True, cascade="all, delete-orphan")
    user = db_sql.relationship('User', backref='chat_conversations', lazy=True)
    
    def __repr__(self):
        return f'<ChatConversation {self.id}>'


class ChatMessage(db_sql.Model):
    """Model to store individual messages in a conversation"""
    __tablename__ = 'chat_messages'
    
    id = db_sql.Column(db_sql.Integer, primary_key=True)
    conversation_id = db_sql.Column(db_sql.Integer, db_sql.ForeignKey('chat_conversations.id'), nullable=False)
    role = db_sql.Column(db_sql.String(50), nullable=False)  # 'user', 'assistant', 'system'
    content = db_sql.Column(db_sql.Text, nullable=False)
    message_metadata = db_sql.Column(JSONB, nullable=True)  # For storing things like citations, tokens used, etc.
    created_at = db_sql.Column(db_sql.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ChatMessage {self.id} ({self.role})>'


class DocumentChunk(db_sql.Model):
    """Model to store document chunks for the RAG system"""
    __tablename__ = 'document_chunks'
    
    id = db_sql.Column(db_sql.Integer, primary_key=True)
    document_type = db_sql.Column(db_sql.String(100), nullable=False)  # e.g., 'service', 'client', 'product', etc.
    document_id = db_sql.Column(db_sql.Integer, nullable=False)  # ID of the original document
    content = db_sql.Column(db_sql.Text, nullable=False)  # The chunk text
    embedding = db_sql.Column(db_sql.LargeBinary, nullable=True)  # Vector embedding for similarity search
    chunk_metadata = db_sql.Column(JSONB, nullable=True)  # Additional metadata
    created_at = db_sql.Column(db_sql.DateTime, default=datetime.utcnow)
    updated_at = db_sql.Column(db_sql.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<DocumentChunk {self.id} ({self.document_type})>'


class ClientMemory(db_sql.Model):
    """Model to store long-term memory about clients for personalized interactions"""
    __tablename__ = 'client_memories'
    
    id = db_sql.Column(db_sql.Integer, primary_key=True)
    client_id = db_sql.Column(db_sql.Integer, db_sql.ForeignKey('clients.id'), nullable=False)
    memory_type = db_sql.Column(db_sql.String(100), nullable=False)  # e.g., 'preference', 'history', 'feedback'
    content = db_sql.Column(db_sql.Text, nullable=False)
    importance = db_sql.Column(db_sql.Integer, default=1)  # 1-10 scale of importance
    created_at = db_sql.Column(db_sql.DateTime, default=datetime.utcnow)
    last_accessed = db_sql.Column(db_sql.DateTime, nullable=True)
    
    # Relationships
    client = db_sql.relationship('Client', backref='memories', lazy=True)
    
    def __repr__(self):
        return f'<ClientMemory {self.id} ({self.memory_type})>'


class ClientMilestone(db_sql.Model):
    """Model to store important milestones in a client's journey with the salon"""
    __tablename__ = 'client_milestones'
    
    id = db_sql.Column(db_sql.Integer, primary_key=True)
    client_id = db_sql.Column(db_sql.Integer, db_sql.ForeignKey('clients.id'), nullable=False)
    title = db_sql.Column(db_sql.String(255), nullable=False)
    description = db_sql.Column(db_sql.Text, nullable=True)
    milestone_type = db_sql.Column(db_sql.String(100), nullable=False)  # e.g., 'first_visit', 'loyalty_tier_upgrade', 'special_event'
    date = db_sql.Column(db_sql.DateTime, default=datetime.utcnow)
    importance = db_sql.Column(db_sql.Integer, default=5)  # 1-10 scale of importance
    icon = db_sql.Column(db_sql.String(100), nullable=True)  # CSS icon class
    milestone_metadata = db_sql.Column(JSONB, nullable=True)  # Additional data like related appointments, services, etc.
    created_at = db_sql.Column(db_sql.DateTime, default=datetime.utcnow)
    
    # Relationships
    client = db_sql.relationship('Client', backref='milestones', lazy=True)
    
    def __repr__(self):
        return f'<ClientMilestone {self.id} ({self.milestone_type}): {self.title}>'