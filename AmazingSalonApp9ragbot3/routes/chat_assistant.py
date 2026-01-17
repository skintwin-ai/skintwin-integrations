from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
import os
import json
from datetime import datetime

from database import db_sql, db_operation_with_retry
from database_models_ai import ChatConversation, ChatMessage, ClientMemory
from database_models import User
from utils.ai_utils import RAGAssistant, extract_client_insights
from utils.openai_config import openai_api_key_required, has_openai_api_key, set_openai_api_key, get_openai_api_key
import models

bp = Blueprint('chat_assistant', __name__, url_prefix='/chat_assistant')

@bp.route('/')
@login_required
def index():
    """Chat assistant landing page showing conversation history"""
    # Check if OpenAI API key is configured
    api_key_configured = has_openai_api_key()
    
    conversations = ChatConversation.query.filter_by(user_id=current_user.id).order_by(ChatConversation.updated_at.desc()).all()
    return render_template('chat_assistant.html', conversations=conversations, api_key_configured=api_key_configured)

@bp.route('/setup-api-key', methods=['GET', 'POST'])
@login_required
def setup_api_key():
    """Setup or update OpenAI API key"""
    # Check if API key is already configured
    api_key_configured = has_openai_api_key()
    
    if request.method == 'POST':
        api_key = request.form.get('api_key', '').strip()
        if not api_key:
            flash('API key cannot be empty', 'danger')
            return redirect(url_for('chat_assistant.setup_api_key'))
        
        # Set the API key
        set_openai_api_key(api_key)
        
        # If this is the first time setting up the API key, create an initial conversation
        if not api_key_configured:
            # Determine user role for the conversation
            if current_user.is_admin:
                user_role = 'admin'
            elif current_user.is_staff:
                user_role = 'staff'
            else:
                user_role = 'client'
                
            # Create the first conversation with appropriate role
            assistant = RAGAssistant(api_key=api_key, user_role=user_role)
            try:
                conversation = assistant.create_conversation(
                    current_user.id, 
                    f"Welcome to Salon Assistant ({user_role.capitalize()} mode)"
                )
                
                # Add an initial system message explaining the capabilities
                welcome_message = "Welcome to your role-based salon assistant! "
                if user_role == 'admin':
                    welcome_message += "As an admin, you have full access to salon information including clients, inventory, staff schedules, and business analytics."
                elif user_role == 'staff':
                    welcome_message += "As a staff member, you can view client information, service details, inventory levels, and appointment schedules."
                else:
                    welcome_message += "You can ask about services, check your appointments, and learn about our products."
                
                assistant.add_message(conversation.id, "assistant", welcome_message)
                
                flash('OpenAI API key configured successfully and your first conversation has been created!', 'success')
            except Exception as e:
                current_app.logger.error(f"Error creating initial conversation: {str(e)}")
                flash('OpenAI API key configured successfully', 'success')
        else:
            flash('OpenAI API key updated successfully', 'success')
            
        return redirect(url_for('chat_assistant.index'))
    
    return render_template('chat_api_key_setup.html', api_key_configured=api_key_configured)

@bp.route('/conversation/<int:id>')
@login_required
@openai_api_key_required
def view_conversation(id):
    """View a specific conversation"""
    conversation = ChatConversation.query.get_or_404(id)
    
    # Security check - only the owner can view the conversation
    if conversation.user_id != current_user.id and not current_user.is_admin:
        flash('You don\'t have permission to view this conversation', 'danger')
        return redirect(url_for('chat_assistant.index'))
    
    messages = ChatMessage.query.filter_by(conversation_id=id).order_by(ChatMessage.created_at).all()
    
    return render_template('chat_conversation.html', conversation=conversation, messages=messages)

@bp.route('/create', methods=['POST'])
@login_required
@openai_api_key_required
def create_conversation():
    """Create a new conversation"""
    title = request.form.get('title', f"New conversation {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}")
    
    try:
        # Determine user role for the conversation
        if current_user.is_admin:
            user_role = 'admin'
        elif current_user.is_staff:
            user_role = 'staff'
        else:
            user_role = 'client'
            
        # Initialize RAG Assistant with the appropriate role
        assistant = RAGAssistant(user_role=user_role)
        conversation = assistant.create_conversation(current_user.id, title)
        
        return redirect(url_for('chat_assistant.view_conversation', id=conversation.id))
    except ValueError as e:
        flash(f"Error creating conversation: {str(e)}", 'danger')
        return redirect(url_for('chat_assistant.index'))

@bp.route('/rename/<int:id>', methods=['POST'])
@login_required
def rename_conversation(id):
    """Rename an existing conversation"""
    conversation = ChatConversation.query.get_or_404(id)
    
    # Security check
    if conversation.user_id != current_user.id and not current_user.is_admin:
        return jsonify({"success": False, "message": "Permission denied"}), 403
    
    new_title = request.form.get('title', '').strip()
    if not new_title:
        return jsonify({"success": False, "message": "Title cannot be empty"}), 400
    
    conversation.title = new_title
    db_sql.session.commit()
    
    return jsonify({"success": True})

@bp.route('/message/<int:conversation_id>', methods=['POST'])
@login_required
@openai_api_key_required
def send_message(conversation_id):
    """Send a message to the AI assistant"""
    try:
        conversation = ChatConversation.query.get_or_404(conversation_id)
        
        # Security check
        if conversation.user_id != current_user.id and not current_user.is_admin:
            return jsonify({"success": False, "message": "Permission denied"}), 403
        
        message_content = request.form.get('message', '').strip()
        if not message_content:
            return jsonify({"success": False, "message": "Message cannot be empty"}), 400
        
        # Check for duplicate/repeated messages
        last_message = ChatMessage.query.filter_by(
            conversation_id=conversation_id, 
            role='user'
        ).order_by(ChatMessage.created_at.desc()).first()
        
        if last_message and last_message.content == message_content:
            # If this is a repeated message, add a small variation to avoid repetition issues
            message_content += " (clarification)"
            current_app.logger.info(f"Detected duplicate message, adding variation")
        
        try:
            # Determine user role for the conversation
            if current_user.is_admin:
                user_role = 'admin'
            elif current_user.is_staff:
                user_role = 'staff'
            else:
                user_role = 'client'
                
            # Initialize RAG Assistant with the appropriate role
            assistant = RAGAssistant(user_role=user_role)
            
            # Generate response
            result = assistant.generate_response(conversation_id, message_content)
            
            # Update conversation timestamp
            conversation.updated_at = datetime.utcnow()
            db_sql.session.commit()
            
            # Process for client insights in a way that won't break the main flow
            try:
                # Determine the appropriate role for insight processing
                # Pass the user role to ensure proper permission handling
                if current_user.is_admin:
                    insight_role = 'admin'
                elif current_user.is_staff:
                    insight_role = 'staff'
                else:
                    insight_role = 'client'
                
                process_client_insights(conversation_id, user_role=insight_role)
            except Exception as insight_error:
                # Just log the error but don't fail the main request
                current_app.logger.error(f"Error processing client insights: {str(insight_error)}")
            
            return jsonify({
                "success": True,
                "response": result["response"],
                "context": result.get("context", [])
            })
        
        except Exception as e:
            current_app.logger.error(f"Error generating response: {str(e)}")
            return jsonify({
                "success": False, 
                "message": f"Error generating response: {str(e)}"
            }), 500
            
    except Exception as outer_e:
        current_app.logger.error(f"Database or server error in message endpoint: {str(outer_e)}")
        return jsonify({
            "success": False, 
            "message": "Server error processing your message. Please try again or refresh the page."
        }), 500

@bp.route('/delete/<int:conversation_id>', methods=['POST'])
@login_required
def delete_conversation(conversation_id):
    """Delete a conversation"""
    conversation = ChatConversation.query.get_or_404(conversation_id)
    
    # Security check
    if conversation.user_id != current_user.id and not current_user.is_admin:
        flash('You don\'t have permission to delete this conversation', 'danger')
        return redirect(url_for('chat_assistant.index'))
    
    db_sql.session.delete(conversation)
    db_sql.session.commit()
    
    flash('Conversation deleted successfully', 'success')
    return redirect(url_for('chat_assistant.index'))

@bp.route('/process-insights/<int:conversation_id>/<int:client_id>', methods=['GET'])
@login_required
@openai_api_key_required
def process_insights_route(conversation_id, client_id):
    """Process insights from a conversation about a specific client"""
    result = manually_process_insights(conversation_id, client_id)
    return result

def determine_journey_stage(client_id):
    """Determine the client's journey stage based on their data"""
    try:
        client = models.get_client(client_id)
        if not client:
            return "Unknown"
            
        # Use the analyze_client_history utility to determine journey stage
        from utils.ai_utils import analyze_client_history
        analysis = analyze_client_history(client)
        return analysis.get('journey_stage', 'Unknown')
    except Exception as e:
        print(f"Error determining journey stage: {str(e)}")
        return "Unknown"

def retrieve_client_context(client_id):
    """Retrieve comprehensive client context including journey and memories"""
    from routes.journey_map import get_client_milestones
    try:
        # Avoid circular import by importing inside function
        from routes.memory_timeline import get_client_memories
        memories = get_client_memories(client_id)
    except Exception as e:
        print(f"Error getting client memories: {str(e)}")
        memories = []
    
    journey_stage = determine_journey_stage(client_id)
    
    context = {
        'milestones': get_client_milestones(client_id),
        'memories': memories,
        'journey_stage': journey_stage
    }
    return context

def manually_process_insights(conversation_id, client_id):
    """Manually process a conversation for insights about a specific client"""
    conversation = ChatConversation.query.get_or_404(conversation_id)
    
    # Security check
    if conversation.user_id != current_user.id and not current_user.is_admin:
        flash('You don\'t have permission to process this conversation', 'danger')
        return redirect(url_for('chat_assistant.index'))
    
    # Check if client exists
    client = models.get_client(client_id)
    if not client:
        flash(f'Client with ID {client_id} not found', 'danger')
        return redirect(url_for('chat_assistant.view_conversation', id=conversation_id))
    
    # Get conversation messages
    messages = ChatMessage.query.filter_by(conversation_id=conversation_id)\
        .order_by(ChatMessage.created_at).all()
    
    # Format for insight extraction
    conversation_history = []
    for message in messages:
        if message.role != 'system':  # Skip system messages
            conversation_history.append({
                "role": message.role,
                "content": message.content
            })
    
    # Extract insights
    insights = extract_client_insights(conversation_history, client_id)
    
    # Store new insights as client memories with a lower threshold for testing
    stored_count = 0
    
    # Determine appropriate role for insight processing
    if current_user.is_admin:
        insight_role = 'admin'
    elif current_user.is_staff:
        insight_role = 'staff'
    else:
        insight_role = 'client'
    
    # Use determined role for memory processing 
    assistant = RAGAssistant(user_role=insight_role)
    
    # Set threshold based on role
    min_importance = 2 if current_user.is_admin else (3 if current_user.is_staff else 4)
    
    for insight in insights:
        if insight['importance'] >= min_importance:
            try:
                assistant.create_client_memory(
                    client_id=client_id,
                    memory_type=insight['type'],
                    content=insight['content'],
                    importance=insight['importance']
                )
                stored_count += 1
            except Exception as e:
                current_app.logger.error(f"Error storing client memory: {str(e)}")
    
    flash(f'Processed conversation and stored {stored_count} memories for client {client["name"]}', 'success')
    return redirect(url_for('chat_assistant.view_conversation', id=conversation_id))

@bp.route('/api/conversation/<int:conversation_id>', methods=['GET'])
@login_required
def api_get_conversation(conversation_id):
    """API endpoint to get conversation messages"""
    try:
        # Using retry function for database operations
        def get_conversation():
            return ChatConversation.query.get_or_404(conversation_id)
        
        conversation = db_operation_with_retry(get_conversation)
        
        # Security check
        if conversation.user_id != current_user.id and not current_user.is_admin:
            return jsonify({"success": False, "message": "Permission denied"}), 403
        
        # Using retry function for database operations
        def get_messages():
            return ChatMessage.query.filter_by(conversation_id=conversation_id)\
                .order_by(ChatMessage.created_at).all()
        
        messages = db_operation_with_retry(get_messages)
        
        result = []
        for message in messages:
            if message.role != 'system':  # Don't include system messages
                result.append({
                    "id": message.id,
                    "role": message.role,
                    "content": message.content,
                    "timestamp": message.created_at.strftime('%Y-%m-%d %H:%M:%S')
                })
        
        return jsonify({
            "success": True,
            "conversation_id": conversation_id,
            "title": conversation.title,
            "messages": result
        })
    except Exception as e:
        current_app.logger.error(f"Error retrieving conversation: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Error retrieving conversation. Please refresh the page."
        }), 500

def process_client_insights(conversation_id, user_role='client'):
    """Process conversation for client insights and store them as memories
    
    Args:
        conversation_id: ID of the conversation to process
        user_role: User role ('client', 'staff', 'admin') for role-based memory access
    """
    # Get conversation history
    messages = ChatMessage.query.filter_by(conversation_id=conversation_id)\
        .order_by(ChatMessage.created_at).all()
    
    # Format for insight extraction
    conversation_history = []
    for message in messages:
        if message.role != 'system':  # Skip system messages
            conversation_history.append({
                "role": message.role,
                "content": message.content
            })
    
    # Look for client mentions in messages with metadata
    client_id = None
    client_name = None
    
    # First check the most recent message metadata for client references
    if messages and messages[-1].message_metadata:
        try:
            metadata = messages[-1].message_metadata
            if 'retrieved_docs' in metadata:
                for doc in metadata['retrieved_docs']:
                    if doc['type'] == 'client':
                        client_id = doc['id']
                        
                        # Try to get client name
                        client = models.get_client(client_id)
                        if client:
                            client_name = client.get('name')
                        break
        except Exception as e:
            current_app.logger.error(f"Error extracting client info from metadata: {str(e)}")
    
    # If we still don't have a client, check all messages
    if not client_id:
        for message in messages:
            if message.message_metadata:
                try:
                    metadata = message.message_metadata
                    if 'retrieved_docs' in metadata:
                        for doc in metadata['retrieved_docs']:
                            if doc['type'] == 'client':
                                client_id = doc['id']
                                
                                # Try to get client name
                                client = models.get_client(client_id)
                                if client:
                                    client_name = client.get('name')
                                break
                except Exception as e:
                    current_app.logger.error(f"Error extracting client info from metadata: {str(e)}")
                    
            if client_id:
                break
    
    # Also check for appointment references that might contain client info
    if not client_id:
        for message in messages:
            if message.message_metadata:
                try:
                    metadata = message.message_metadata
                    if 'retrieved_docs' in metadata:
                        for doc in metadata['retrieved_docs']:
                            if doc['type'] == 'appointment':
                                # Get the appointment and extract client
                                appointment_id = doc['id']
                                appointment = models.get_appointment(appointment_id)
                                if appointment:
                                    client_id = appointment.get('client_id')
                                    if client_id:
                                        client = models.get_client(client_id)
                                        if client:
                                            client_name = client.get('name')
                                        break
                except Exception as e:
                    current_app.logger.error(f"Error extracting client from appointment: {str(e)}")
            
            if client_id:
                break
    
    if client_id:
        # Extract insights about this client
        insights = extract_client_insights(conversation_history, client_id)
        
        # Log the extraction for debugging
        current_app.logger.info(f"Extracted {len(insights)} insights for client {client_name or client_id}")
        
        # Store new insights as client memories, but only if they're important enough
        stored_count = 0
        
        # Get the conversation to find its owner
        conversation = ChatConversation.query.get(conversation_id)
        if conversation:
            # Get the user role of the person who owns this conversation
            conversation_owner = User.query.get(conversation.user_id)
            if conversation_owner:
                # Determine appropriate user role for memory access
                # Use staff permissions for clients to enable memory creation
                # Admin and staff already have appropriate permissions
                if conversation_owner.is_admin:
                    assistant_role = 'admin' 
                else:
                    # For both staff and clients, use staff role to ensure proper memory access
                    assistant_role = 'staff'
                    
                assistant = RAGAssistant(user_role=assistant_role)
                
                for insight in insights:
                    # Different threshold based on user role - admin/staff can create memories with lower importance
                    min_importance = 3 if conversation_owner.is_admin or conversation_owner.is_staff else 4
                    if insight['importance'] >= min_importance:
                        try:
                            assistant.create_client_memory(
                                client_id=client_id,
                                memory_type=insight['type'],
                                content=insight['content'],
                                importance=insight['importance']
                            )
                            stored_count += 1
                        except Exception as e:
                            current_app.logger.error(f"Error storing client memory: {str(e)}")
        
        current_app.logger.info(f"Stored {stored_count} new client memories for {client_name or client_id}")
        return stored_count
    
    return 0