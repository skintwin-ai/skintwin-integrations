from flask import Blueprint, render_template, jsonify, request, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import func
import importlib

# Try to import database-specific components
try:
    from utils.ai_utils import RAGAssistant, extract_client_insights
    from database_models_ai import ClientMemory
    from database_models import Client
    from database import db_sql
    USE_SQL_DB = True
except ImportError:
    from models import get_client_memories, get_client, create_client_memory, get_all_clients
    USE_SQL_DB = False

from routes.auth import admin_required

memory_timeline = Blueprint('memory_timeline', __name__)

@memory_timeline.route('/')
@login_required
def index():
    """Memory timeline landing page showing client selection"""
    # Get all clients for the dropdown
    if USE_SQL_DB:
        clients = Client.query.order_by(Client.name).all()
    else:
        clients = get_all_clients()
    
    return render_template('memory_timeline/index.html', clients=clients)

@memory_timeline.route('/view/<int:client_id>')
@login_required
def view_timeline(client_id):
    """View the memory timeline for a specific client"""
    if USE_SQL_DB:
        client = Client.query.get_or_404(client_id)
    else:
        client = get_client(client_id)
        if not client:
            return "Client not found", 404
    
    return render_template('memory_timeline/timeline.html', client=client)

@memory_timeline.route('/api/memories/<int:client_id>')
@login_required
def get_client_memories(client_id):
    """API endpoint to get memory data for timeline visualization"""
    if USE_SQL_DB:
        memories = ClientMemory.query.filter_by(client_id=client_id).order_by(ClientMemory.created_at).all()
        
        # Format memories for timeline display
        memory_data = []
        for memory in memories:
            memory_data.append({
                'id': memory.id,
                'type': memory.memory_type,
                'content': memory.content,
                'importance': memory.importance,
                'created_at': memory.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'last_accessed': memory.last_accessed.strftime('%Y-%m-%d %H:%M:%S') if memory.last_accessed else None,
                # Add icon based on memory type
                'icon': get_memory_icon(memory.memory_type)
            })
    else:
        # For non-SQL implementation
        memories = get_client_memories(client_id)
        memory_data = memories  # Assuming the non-SQL function returns formatted data
    
    return jsonify({
        'memories': memory_data
    })

@memory_timeline.route('/api/summarize/<int:client_id>')
@login_required
def get_client_summary(client_id):
    """Generate a narrative summary of client memories"""
    if not USE_SQL_DB:
        return jsonify({'summary': {}})
    
    memories = ClientMemory.query.filter_by(client_id=client_id).all()
    
    # Check if there are any memories
    if not memories:
        return jsonify({
            'summary': {}
        })
    
    # Group memories by type
    memory_by_type = {}
    for memory in memories:
        if memory.memory_type not in memory_by_type:
            memory_by_type[memory.memory_type] = []
        memory_by_type[memory.memory_type].append(memory)
    
    # Generate summary for each type
    summary = {}
    for memory_type, memories_list in memory_by_type.items():
        if memories_list:  # Additional check to ensure list is not empty
            content_list = [m.content for m in memories_list]
            summary[memory_type] = {
                'count': len(memories_list),
                'highlights': content_list[:3],  # Top 3 memories of this type
                'earliest': min(memories_list, key=lambda m: m.created_at).created_at.strftime('%Y-%m-%d'),
                'latest': max(memories_list, key=lambda m: m.created_at).created_at.strftime('%Y-%m-%d')
            }
    
    return jsonify({
        'summary': summary
    })

@memory_timeline.route('/delete/<int:memory_id>', methods=['POST'])
@login_required
def delete_memory(memory_id):
    """Delete a specific memory"""
    if not USE_SQL_DB:
        return jsonify({'success': False, 'message': 'SQL database required for this operation'}), 400
    
    memory = ClientMemory.query.get_or_404(memory_id)
    client_id = memory.client_id
    
    # Only admins can delete memories
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin privileges required'}), 403
    
    db_sql.session.delete(memory)
    db_sql.session.commit()
    
    return jsonify({'success': True, 'message': 'Memory deleted successfully'})

@memory_timeline.route('/api/memories/stats')
@login_required
def get_memory_stats():
    """Get memory statistics for the dashboard"""
    if not USE_SQL_DB:
        return jsonify({
            'total_memories': 0,
            'recent_memories': 0,
            'avg_per_client': 0,
            'type_distribution': {},
            'recent_items': []
        })
    
    # Get current date for "recent" calculations
    now = datetime.utcnow()
    one_week_ago = now - timedelta(days=7)
    
    # Calculate total memories
    total_memories = ClientMemory.query.count()
    
    # Calculate memories created in the last 7 days
    recent_memories = ClientMemory.query.filter(ClientMemory.created_at >= one_week_ago).count()
    
    # Calculate average memories per client
    client_count = Client.query.count()
    avg_per_client = total_memories / client_count if client_count > 0 else 0
    
    # Get memory type distribution
    memory_types = db_sql.session.query(
        ClientMemory.memory_type, 
        func.count(ClientMemory.id).label('count')
    ).group_by(ClientMemory.memory_type).all()
    
    type_distribution = {memory_type: count for memory_type, count in memory_types}
    
    # Get the most recent memories
    recent_items = ClientMemory.query.order_by(ClientMemory.created_at.desc()).limit(5).all()
    recent = []
    for memory in recent_items:
        client = Client.query.get(memory.client_id)
        recent.append({
            'id': memory.id,
            'type': memory.memory_type,
            'content': memory.content,
            'client_name': client.name if client else 'Unknown',
            'client_id': memory.client_id,
            'created_at': memory.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return jsonify({
        'total_memories': total_memories,
        'recent_memories': recent_memories,
        'avg_per_client': avg_per_client,
        'type_distribution': type_distribution,
        'recent_items': recent
    })

def process_memory_insights(memory_content):
    """Process memory content for insights using RAG assistant"""
    if USE_SQL_DB and 'RAGAssistant' in globals():
        assistant = RAGAssistant(user_role='staff')
        conversation = assistant.create_conversation(current_user.id)
        
        # Generate insights about the memory
        response = assistant.generate_response(
            conversation.id,
            f"Analyze this client interaction for key insights: {memory_content}"
        )
        
        return response.get('response', '')
    return ""

@memory_timeline.route('/api/memories/<client_id>', methods=['POST'])
@login_required
def add_memory(client_id):
    """Add a new memory with AI-generated insights"""
    content = request.json.get('content')
    memory_type = request.json.get('type', 'note')
    
    if not content:
        return jsonify({"error": "Content is required"}), 400
        
    # Process memory for insights
    insights = process_memory_insights(content)
    
    # Create memory with enhanced content
    if USE_SQL_DB and 'ClientMemory' in globals():
        memory = ClientMemory(
            client_id=client_id,
            memory_type=memory_type,
            content=content,
            importance=8 if insights else 5
        )
        db_sql.session.add(memory)
        db_sql.session.commit()
    else:
        memory = create_client_memory(
            client_id=client_id,
            memory_type=memory_type,
            content=content,
            importance=8 if insights else 5
        )
    
    return jsonify({
        "message": "Memory added successfully",
        "memory_id": memory.get('id', None) if isinstance(memory, dict) else memory.id,
        "insights": insights
    })

def get_memory_icon(memory_type):
    """Return the appropriate icon class for each memory type"""
    icons = {
        'style': 'fas fa-cut',
        'preference': 'fas fa-heart',
        'history': 'fas fa-history',
        'feedback': 'fas fa-comment',
        'request': 'fas fa-ticket-alt'
    }
    return icons.get(memory_type, 'fas fa-sticky-note')
