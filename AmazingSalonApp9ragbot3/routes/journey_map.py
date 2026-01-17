"""
Routes for the Client Journey Map feature
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required
from datetime import datetime

import json
from database_models import Client, Appointment, Transaction, db_sql
from database_models_ai import ClientMemory, ClientMilestone
import database_utils
from utils.ai_utils import RAGAssistant, analyze_client_history # Added import

journey_map = Blueprint('journey_map', __name__)

@journey_map.route('/')
@login_required
def index():
    """Journey map landing page showing client selection"""
    clients = Client.query.all()
    return render_template('journey_map/index.html', clients=clients)

@journey_map.route('/client/<int:client_id>')
@login_required
def view_journey_map(client_id):
    """View the journey map for a specific client"""
    client = Client.query.get_or_404(client_id)
    journey_insights = generate_journey_insights(client_id) # Integrate AI insights
    return render_template('journey_map/journey.html', client=client, journey_insights=journey_insights)

@journey_map.route('/api/milestones/<int:client_id>')
@login_required
def get_client_milestones(client_id):
    """API endpoint to get milestone data for journey map visualization"""
    client = Client.query.get_or_404(client_id)

    # Get all milestones for the client
    milestones = ClientMilestone.query.filter_by(client_id=client_id).all()

    # Get client memories
    memories = ClientMemory.query.filter_by(client_id=client_id).all()

    # Get client appointments
    appointments = Appointment.query.filter_by(client_id=client_id).all()

    # Get client transactions
    transactions = Transaction.query.filter_by(client_id=client_id).all()

    # Format the data for the frontend
    milestone_data = []
    for milestone in milestones:
        milestone_data.append({
            'id': milestone.id,
            'title': milestone.title,
            'description': milestone.description,
            'type': milestone.milestone_type,
            'date': milestone.date.isoformat(),
            'importance': milestone.importance,
            'icon': milestone.icon or 'fas fa-star',
            'metadata': milestone.milestone_metadata
        })

    memory_data = []
    for memory in memories:
        memory_data.append({
            'id': memory.id,
            'type': memory.memory_type,
            'content': memory.content,
            'importance': memory.importance,
            'date': memory.created_at.isoformat(),
        })

    appointment_data = []
    for appt in appointments:
        appointment_data.append({
            'id': appt.id,
            'date': appt.date_time.isoformat(),
            'status': appt.status,
            'service': appt.service_rel.name,
            'stylist': appt.stylist.username
        })

    transaction_data = []
    for trans in transactions:
        transaction_data.append({
            'id': trans.id,
            'date': trans.date_time.isoformat(),
            'amount': trans.amount,
            'description': trans.description
        })

    # Return the data as JSON
    return jsonify({
        'client': {
            'id': client.id,
            'name': client.name,
            'email': client.email,
            'tier': client.tier,
            'loyalty_points': client.loyalty_points,
            'total_spent': client.total_spent,
            'created_at': client.created_at.isoformat()
        },
        'milestones': milestone_data,
        'memories': memory_data,
        'appointments': appointment_data,
        'transactions': transaction_data
    })

@journey_map.route('/api/add-milestone/<int:client_id>', methods=['POST'])
@login_required
def add_milestone(client_id):
    """Add a new milestone to the client's journey"""
    client = Client.query.get_or_404(client_id)
    data = request.json

    try:
        # Create milestone with default values for any missing fields
        milestone = ClientMilestone(
            client_id=client_id,
            title=data.get('title'),
            description=data.get('description', ''),
            milestone_type=data.get('type', 'custom'),
            date=datetime.fromisoformat(data.get('date')) if data.get('date') else datetime.now(),
            importance=data.get('importance', 5),
            icon=data.get('icon', 'fas fa-star'),
            milestone_metadata={}  # Empty JSON object for new milestones
        )

        db_sql.session.add(milestone)
        db_sql.session.commit()

        return jsonify({
            'id': milestone.id,
            'title': milestone.title,
            'description': milestone.description,
            'type': milestone.milestone_type,
            'date': milestone.date.isoformat(),
            'importance': milestone.importance,
            'icon': milestone.icon
        })

    except Exception as e:
        db_sql.session.rollback()
        return jsonify({'error': str(e)}), 500

@journey_map.route('/api/delete-milestone/<int:milestone_id>', methods=['DELETE'])
@login_required
def delete_milestone(milestone_id):
    """Delete a milestone from the client's journey"""
    milestone = ClientMilestone.query.get_or_404(milestone_id)

    try:
        db_sql.session.delete(milestone)
        db_sql.session.commit()
        return jsonify({'success': True})

    except Exception as e:
        db_sql.session.rollback()
        return jsonify({'error': str(e)}), 500

def generate_journey_insights(client_id):
    """Generate AI-powered journey insights"""
    memories = ClientMemory.query.filter_by(client_id=client_id).order_by(ClientMemory.created_at).all()

    if not memories:
        return []

    # Analyze client history
    client = Client.query.get(client_id)
    analysis = analyze_client_history(client)

    # Create a conversation for memory analysis
    assistant = RAGAssistant(user_role='staff')
    conversation = assistant.create_conversation(1)  # Using admin user ID (1) for staff-level insights
    journey_points = []

    for memory in memories:
        if not memory.content:
            continue
            
        # Generate insight for important memories
        if memory.importance >= 5:
            try:
                response = assistant.generate_response(
                    conversation.id,
                    f"Analyze this client interaction for key journey milestones and insights: {memory.content}"
                )
                
                insight = response.get('response', '') if response else ''
            except Exception as e:
                insight = f"Error generating insight: {str(e)}"
                
            journey_points.append({
                'date': memory.created_at.strftime('%Y-%m-%d'),
                'type': memory.memory_type,
                'content': memory.content,
                'insight': insight,
                'importance': memory.importance
            })

    # Add journey stage from analysis
    if journey_points:
        journey_points.append({
            'date': 'Current',
            'type': 'journey_stage',
            'content': f"Current Journey Stage: {analysis.get('journey_stage', 'Unknown')}",
            'insight': "\n".join(analysis.get('recommendations', [])),
            'importance': 10
        })

    return journey_points