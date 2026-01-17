import os
import json
import requests
import base64
from io import BytesIO
from PIL import Image
from datetime import datetime
from flask import current_app, url_for
from sqlalchemy import func, desc
import numpy as np
from werkzeug.utils import secure_filename

from database import db_sql
from database_models_ai import ChatConversation, ChatMessage, DocumentChunk, ClientMemory
from database_models import User
import models

# Constants
MAX_CONVERSATION_HISTORY = 10  # Maximum number of messages to include in context

# Role-specific system prompts
CLIENT_SYSTEM_PROMPT = """You are an AI assistant for salon clients. 
You can help with viewing available services, booking appointments, and checking client history and loyalty points.
Be friendly, professional, and helpful. If you don't know something, say so clearly.
Always prioritize finding and sharing real information from the salon database.
Remember that as a client-facing assistant, you should not provide access to sensitive salon information like inventory levels, 
staff schedules, or other clients' data. Focus only on information relevant to the current client."""

STAFF_SYSTEM_PROMPT = """You are an AI assistant for salon staff members.
You can help with appointments, client information, services, inventory, and general salon operations.
Be professional, efficient, and thorough in your responses. If you don't know something, say so clearly.
Always prioritize finding and sharing real information from the salon database.
You can access client profiles, appointment details, and product inventory to help staff provide better service.
However, avoid sharing sensitive financial information or system administration details."""

ADMIN_SYSTEM_PROMPT = """You are an AI assistant for salon administrators.
You have full access to the salon management system including appointments, client information, 
services, inventory, staff schedules, financial reports, and system settings.
Be professional, comprehensive, and data-driven in your responses. If you don't know something, say so clearly.
Always prioritize finding and sharing real information from the salon database.
You can provide insights on business operations, suggest improvements, and help with administrative tasks."""

DEFAULT_SYSTEM_PROMPT = CLIENT_SYSTEM_PROMPT  # Default to client prompt if role is unknown

class RAGAssistant:
    """Retrieval-Augmented Generation (RAG) Assistant for the salon system"""
    
    def __init__(self, api_key=None, user_role='client'):
        """Initialize the RAG Assistant
        
        Args:
            api_key (str, optional): OpenAI API key. Defaults to None (will use env var).
            user_role (str, optional): Role of the user (client, staff, admin). Defaults to 'client'.
        """
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        # For testing only - allow initialization without API key
        # In production, uncomment the validation below
        # if not self.api_key:
        #     raise ValueError("OpenAI API key is required")
        
        # Set user role
        self.user_role = user_role.lower()
    
    def create_conversation(self, user_id, title=None):
        """Create a new conversation for a user"""
        conversation = ChatConversation(
            user_id=user_id,
            title=title or f"Conversation {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
        )
        db_sql.session.add(conversation)
        db_sql.session.commit()
        
        # Select the appropriate system prompt based on user role
        if self.user_role == 'admin':
            system_prompt = ADMIN_SYSTEM_PROMPT
        elif self.user_role == 'staff':
            system_prompt = STAFF_SYSTEM_PROMPT
        else:
            system_prompt = CLIENT_SYSTEM_PROMPT
        
        # Add system message
        system_message = ChatMessage(
            conversation_id=conversation.id,
            role="system",
            content=system_prompt
        )
        db_sql.session.add(system_message)
        db_sql.session.commit()
        
        return conversation
    
    def add_message(self, conversation_id, role, content, metadata=None):
        """Add a message to the conversation"""
        message = ChatMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            message_metadata=metadata
        )
        db_sql.session.add(message)
        db_sql.session.commit()
        return message
    
    def get_conversation_history(self, conversation_id, limit=MAX_CONVERSATION_HISTORY):
        """Get the conversation history"""
        messages = ChatMessage.query.filter_by(conversation_id=conversation_id).order_by(ChatMessage.created_at).all()
        
        # Find system message separately - we'll add this at the beginning
        system_messages = [m for m in messages if m.role == "system"]
        system_message = system_messages[0] if system_messages else None
        
        # Get user and assistant messages in chronological order (excluding system)
        conversation_messages = [m for m in messages if m.role != "system"]
        
        # Only keep the most recent messages up to the limit
        if len(conversation_messages) > limit:
            conversation_messages = conversation_messages[-limit:]
        
        # First add system prompt if it exists
        result = []
        if system_message:
            result.append({"role": system_message.role, "content": system_message.content})
        
        # Then add the conversation messages in order
        for message in conversation_messages:
            result.append({"role": message.role, "content": message.content})
            
        print(f"DEBUG - Final formatted conversation history: {result}")
        
        return result
    
    def retrieve_relevant_documents(self, query, limit=5, current_user_id=None, current_client_id=None):
        """
        Retrieve relevant documents based on the query
        Uses semantic keyword matching to find relevant information
        In a full production implementation, this would use vector similarity search
        
        Role-based access control is implemented here:
        - Clients: Can only access service information and their own appointments/profile
        - Staff: Can access all client information, services, appointments, and products
        - Admin: Full access to all information
        
        Args:
            query: The user's query string
            limit: Maximum number of documents to return
            current_user_id: ID of the current user (for role-specific filtering)
            current_client_id: ID of the client if the current user is a client
        """
        query_lower = query.lower()
        relevant_chunks = []
        
        # Extract potential intent and entities from the query
        query_words = set(query_lower.split())
        
        # Define intent keywords
        intent_keywords = {
            'service': ['service', 'treatment', 'haircut', 'color', 'style', 'manicure', 'pedicure', 'massage', 'facial', 'price'],
            'client': ['client', 'customer', 'person', 'profile', 'history', 'preferences'],
            'product': ['product', 'inventory', 'stock', 'item', 'brand', 'shampoo', 'conditioner', 'cream', 'supplies'],
            'appointment': ['appointment', 'schedule', 'booking', 'reservation', 'time', 'cancel', 'reschedule', 'today', 'tomorrow', 'date']
        }
        
        # Determine which entity types to search based on query and user role
        # Default search flags - will be modified based on user role
        search_services = any(word in query_words for word in intent_keywords['service']) or len(query_words.intersection(intent_keywords['service'])) > 0
        search_clients = any(word in query_words for word in intent_keywords['client']) or len(query_words.intersection(intent_keywords['client'])) > 0
        search_products = any(word in query_words for word in intent_keywords['product']) or len(query_words.intersection(intent_keywords['product'])) > 0
        search_appointments = any(word in query_words for word in intent_keywords['appointment']) or len(query_words.intersection(intent_keywords['appointment'])) > 0
        
        # If no specific intent is detected, search everything (role-based restrictions will still apply)
        if not any([search_services, search_clients, search_products, search_appointments]):
            search_services = search_clients = search_products = search_appointments = True
            
        # Apply role-based access restrictions
        if self.user_role == 'client':
            # Clients can only search for services and their own appointments
            # Restrict client and product searches for clients
            search_clients = False  # Will be selectively enabled for current client only
            search_products = False  # Clients don't need inventory details
        elif self.user_role == 'staff':
            # Staff can search everything except sensitive admin info
            pass  # Default search flags are fine
        # Admin has full access (default)
        
        # Search for relevant services
        if search_services:
            services = models.get_all_services()
            for service in services:
                service_name = service.get('name', '').lower()
                service_desc = service.get('description', '').lower()
                service_category = service.get('category', '').lower()
                
                # Check for any word match between query and service info
                name_words = set(service_name.split())
                desc_words = set(service_desc.split())
                category_words = set(service_category.split())
                
                if (query_lower in service_name or 
                    query_lower in service_desc or
                    query_words.intersection(name_words) or
                    query_words.intersection(desc_words) or
                    query_words.intersection(category_words)):
                    
                    chunk = {
                        'type': 'service',
                        'id': service.get('id'),
                        'content': f"Service: {service.get('name')}\nDescription: {service.get('description')}\nPrice: ${service.get('price')}\nDuration: {service.get('duration')} minutes\nCategory: {service.get('category')}"
                    }
                    relevant_chunks.append(chunk)
        
        # Search for relevant clients
        if search_clients:
            # For client role, we should only return their own client profile
            clients = []
            if self.user_role == 'client' and current_client_id is not None:
                # If user is a client, only get their own client record
                client_record = models.get_client(current_client_id)
                if client_record:
                    clients = [client_record]
            else:
                # For staff and admin, get all clients
                clients = models.get_all_clients()
                
            for client in clients:
                client_id = client.get('id')
                client_name = client.get('name', '').lower()
                client_email = client.get('email', '').lower()
                client_preferences = {
                    'hair_length': client.get('hair_length', '').lower(),
                    'style_preference': client.get('style_preference', '').lower(),
                    'color_preference': client.get('color_preference', '').lower()
                }
                
                # Check for direct name match or email match
                # For client role, always include their own profile regardless of query match
                is_own_profile = self.user_role == 'client' and client_id == current_client_id
                
                if is_own_profile or (
                    query_lower in client_name or client_name in query_lower or
                    query_lower in client_email):
                    
                    # Create the basic client profile info
                    chunk = {
                        'type': 'client',
                        'id': client.get('id'),
                        'content': (f"Client: {client.get('name')}\n"
                                   f"Email: {client.get('email')}\n"
                                   f"Phone: {client.get('phone')}\n"
                                   f"Loyalty Points: {client.get('loyalty_points')}\n"
                                   f"Tier: {client.get('tier')}")
                    }
                    
                    # Add styling preferences based on role
                    # Clients, staff and admins can all see styling preferences
                    chunk['content'] += (f"\nHair Length: {client.get('hair_length')}\n"
                                        f"Style Preference: {client.get('style_preference')}\n"
                                        f"Color Preference: {client.get('color_preference')}")
                    
                    relevant_chunks.append(chunk)
        
        # Search for relevant products
        if search_products:
            products = models.get_all_products()
            for product in products:
                product_name = product.get('name', '').lower()
                product_desc = product.get('description', '').lower()
                product_category = product.get('category', '').lower()
                product_supplier = product.get('supplier', '').lower()
                
                # Check for any word match between query and product info
                name_words = set(product_name.split())
                desc_words = set(product_desc.split())
                category_words = set(product_category.split())
                supplier_words = set(product_supplier.split())
                
                if (query_lower in product_name or 
                    query_lower in product_desc or
                    query_lower in product_category or
                    query_lower in product_supplier or
                    query_words.intersection(name_words) or
                    query_words.intersection(desc_words) or
                    query_words.intersection(category_words) or
                    query_words.intersection(supplier_words)):
                    
                    # Customize product content based on user role
                    product_content = f"Product: {product.get('name')}\nDescription: {product.get('description')}\nPrice: ${product.get('price')}"
                    
                    # Add inventory details for staff and admin only
                    if self.user_role in ['staff', 'admin']:
                        product_content += f"\nQuantity: {product.get('quantity')}"
                        
                        # Add supplier info for admin only
                        if self.user_role == 'admin':
                            product_content += f"\nSupplier: {product.get('supplier')}"
                            
                        # Add extra information for low stock products (staff and admin only)
                        if product.get('quantity', 0) <= product.get('reorder_level', 0):
                            reorder_info = "\n⚠️ LOW STOCK: This product is below the reorder level."
                            product_content += reorder_info
                    
                    # Everyone can see category
                    product_content += f"\nCategory: {product.get('category')}"
                    
                    chunk = {
                        'type': 'product',
                        'id': product.get('id'),
                        'content': product_content
                    }
                    relevant_chunks.append(chunk)
        
        # Search for relevant appointments
        if search_appointments:
            appointments = models.get_all_appointments()
            
            # For client role, we need the current user's client ID to filter appointments
            current_user_client_id = current_client_id  # Use the provided client ID parameter
            
            for appointment in appointments:
                # Convert appointment details to strings for searching
                client_id = appointment.get('client_id', 0)
                service_id = appointment.get('service_id', 0)
                stylist_id = appointment.get('stylist_id', 0)
                
                # Role-based filtering: if user is a client, only show their own appointments
                if self.user_role == 'client' and current_user_client_id is not None:
                    if client_id != current_user_client_id:
                        continue  # Skip appointments that don't belong to this client
                
                client = models.get_client(client_id)
                service = models.get_service(service_id)
                stylist = models.get_user(stylist_id)
                
                client_name = client.get('name', 'Unknown Client') if client else 'Unknown Client'
                service_name = service.get('name', 'Unknown Service') if service else 'Unknown Service'
                stylist_name = stylist.get('username', 'Unknown Stylist') if stylist else 'Unknown Stylist'
                
                date_time = str(appointment.get('date_time', ''))
                status = appointment.get('status', '')
                
                # Create combined text for keyword matching
                combined_text = f"{client_name} {service_name} {stylist_name} {date_time} {status}".lower()
                
                if (query_lower in combined_text or
                    query_lower in client_name.lower() or
                    query_lower in service_name.lower() or
                    query_lower in stylist_name.lower() or
                    query_lower in status.lower() or
                    any(date_term in date_time.lower() for date_term in ['today', 'tomorrow', 'next week'] if date_term in query_lower)):
                    
                    chunk = {
                        'type': 'appointment',
                        'id': appointment.get('id'),
                        'content': f"Appointment: {client_name} with {stylist_name}\nService: {service_name}\nDate/Time: {date_time}\nStatus: {status}"
                    }
                    relevant_chunks.append(chunk)
        
        # Sort chunks by relevance (more sophisticated implementations would use a better ranking algorithm)
        sorted_chunks = sorted(relevant_chunks, key=lambda x: self._calculate_relevance(x, query_lower), reverse=True)
        
        # Limit the number of chunks returned
        return sorted_chunks[:limit]
        
    def _calculate_relevance(self, chunk, query):
        """Calculate a simple relevance score based on content matching"""
        content = chunk['content'].lower()
        query_words = set(query.split())
        content_words = set(content.split())
        
        # Count word overlaps
        word_matches = len(query_words.intersection(content_words))
        
        # Direct phrase match bonus
        phrase_match = 3 if query in content else 0
        
        # Type-specific boosts
        type_boost = {
            'client': 2 if 'client' in query or 'customer' in query else 0,
            'service': 2 if 'service' in query or 'haircut' in query or 'treatment' in query else 0,
            'product': 2 if 'product' in query or 'inventory' in query else 0,
            'appointment': 2 if 'appointment' in query or 'schedule' in query or 'booking' in query else 0
        }.get(chunk['type'], 0)
        
        return word_matches + phrase_match + type_boost
    
    def retrieve_client_memories(self, client_id, limit=3):
        """Retrieve memories about a specific client with role-based access control"""
        # Admin and staff can see all memories
        # Clients can see limited memory types (no internal notes or sensitive information)
        if self.user_role == 'client':
            # Clients can only see preference and style memories
            client_accessible_types = ['preference', 'style', 'history', 'special_occasion']
            # Also filter by importance - clients only see public-facing important memories
            memories = ClientMemory.query.filter(
                ClientMemory.client_id == client_id,
                ClientMemory.memory_type.in_(client_accessible_types),
                ClientMemory.importance >= 5  # Higher threshold for client view
            ).order_by(desc(ClientMemory.importance), desc(ClientMemory.last_accessed)).limit(limit).all()
        else:
            # Staff and admin see all memories, prioritized by importance
            memories = ClientMemory.query.filter_by(
                client_id=client_id
            ).order_by(desc(ClientMemory.importance), desc(ClientMemory.last_accessed)).limit(limit).all()
        
        # Update last_accessed time for retrieved memories
        for memory in memories:
            memory.last_accessed = datetime.utcnow()
        db_sql.session.commit()
        
        # Format memories for return
        return [
            {"type": memory.memory_type, "content": memory.content, "importance": memory.importance}
            for memory in memories
        ]
    
    def create_client_memory(self, client_id, memory_type, content, importance=5):
        """Create a new memory for a client with role-based access control"""
        # Enforce role-based creation permissions
        if self.user_role == 'client':
            # Clients can only create memories of certain types and lower importance
            allowed_types = ['preference', 'style', 'history', 'special_occasion']
            if memory_type not in allowed_types:
                raise ValueError(f"Clients cannot create memories of type {memory_type}")
            
            # Cap importance for client-created memories
            capped_importance = min(importance, 6)
            
            memory = ClientMemory(
                client_id=client_id,
                memory_type=memory_type,
                content=content,
                importance=capped_importance,
                last_accessed=datetime.utcnow()
            )
        else:
            # Staff and admin can create any type of memory
            memory = ClientMemory(
                client_id=client_id,
                memory_type=memory_type,
                content=content,
                importance=importance,
                last_accessed=datetime.utcnow()
            )
            
        db_sql.session.add(memory)
        db_sql.session.commit()
        return memory
    
    def generate_response(self, conversation_id, query):
        """Generate a response to the user query using RAG"""
        # Debug: Print the conversation_id and query
        print(f"DEBUG - generate_response called with conversation_id={conversation_id}, query={query}")
        
        # 1. Get conversation history
        conversation_history = self.get_conversation_history(conversation_id)
        print(f"DEBUG - conversation_history length: {len(conversation_history)}")
        
        # 2. Retrieve relevant documents based on the query
        # First, try to find the client ID if this is a client user
        current_client_id = None
        current_user_name = None
        
        # Get conversation owner information for role-specific data access
        try:
            conversation = ChatConversation.query.get(conversation_id)
            if conversation:
                user_id = conversation.user_id
                user = User.query.get(user_id)
                if user:
                    current_user_name = user.username
                    
                    # If user is a client, find their client ID for filtering
                    if self.user_role == 'client':
                        clients = models.get_all_clients()
                        # Try to match by email first (most reliable)
                        for client in clients:
                            if client.get('email') == user.email:
                                current_client_id = client.get('id')
                                print(f"DEBUG - Matched client ID {current_client_id} by email")
                                break
                                
                        # If no match by email, try by name (less reliable but backup)
                        if not current_client_id:
                            for client in clients:
                                if user.username.lower() in client.get('name', '').lower():
                                    current_client_id = client.get('id')
                                    print(f"DEBUG - Matched client ID {current_client_id} by name")
                                    break
        except Exception as e:
            print(f"DEBUG - Error getting client ID: {str(e)}")
            
        print(f"DEBUG - User role: {self.user_role}, Client ID: {current_client_id}, User: {current_user_name}")
        
        # Now retrieve relevant docs with role-specific filtering
        relevant_docs = self.retrieve_relevant_documents(
            query=query,
            current_client_id=current_client_id
        )
        print(f"DEBUG - relevant_docs count: {len(relevant_docs)}")
        
        # 3. Construct the prompt with retrieved context
        context = "\n\n".join([doc['content'] for doc in relevant_docs])
        
        # Check if we have any client-specific query to add memories
        client_id = None
        client_name = None
        
        # Look for client information in the relevant documents
        for doc in relevant_docs:
            if doc['type'] == 'client':
                client_id = doc['id']
                # Extract client name from the content
                content_lines = doc['content'].split('\n')
                if content_lines and content_lines[0].startswith('Client:'):
                    client_name = content_lines[0].replace('Client:', '').strip()
                break
        
        # Also check for client mentions in appointments
        if not client_id:
            for doc in relevant_docs:
                if doc['type'] == 'appointment':
                    # Try to extract client name and find their ID
                    content_lines = doc['content'].split('\n')
                    if content_lines and content_lines[0].startswith('Appointment:'):
                        # Extract client name (format is typically "Appointment: {client_name} with {stylist_name}")
                        appointment_info = content_lines[0].replace('Appointment:', '').strip()
                        if ' with ' in appointment_info:
                            extracted_client_name = appointment_info.split(' with ')[0].strip()
                            # Find client ID using the name
                            clients = models.get_all_clients()
                            for client in clients:
                                if client.get('name', '').lower() == extracted_client_name.lower():
                                    client_id = client.get('id')
                                    client_name = client.get('name')
                                    break
        
        # If we found a client, retrieve their memories
        client_context = ""
        if client_id:
            from routes.chat_assistant import retrieve_client_context
            client_data = retrieve_client_context(client_id)
            
            client_context = f"Client Information for {client_name}:\n\n"
            
            # Add journey stage
            client_context += f"Journey Stage: {client_data['journey_stage']}\n\n"
            
            # Add key milestones
            if client_data['milestones']:
                client_context += "Key Milestones:\n"
                for milestone in client_data['milestones'][:3]:  # Show 3 most recent
                    client_context += f"- {milestone['title']}: {milestone['description']}\n"
                client_context += "\n"
            
            # Add important memories
            if client_data['memories']:
                client_context += "Important Client Memories:\n"
                for memory in client_data['memories']:
                    client_context += f"- {memory['content']}\n"
        
        # 4. Add user query to the conversation AFTER we get the history
        # This prevents us from having the same query appear twice in the messages
        user_message = {"role": "user", "content": query}
        self.add_message(conversation_id, "user", query)
        
        # 5. Prepare the messages for the API request
        # We'll create a fresh messages array with our structure
        messages = []
        
        # Select the appropriate system prompt based on user role
        if self.user_role == 'admin':
            system_content = ADMIN_SYSTEM_PROMPT
        elif self.user_role == 'staff':
            system_content = STAFF_SYSTEM_PROMPT
        else:
            system_content = CLIENT_SYSTEM_PROMPT
            
        # Add the role-specific system message
        system_message = {
            "role": "system", 
            "content": system_content
        }
        messages.append(system_message)
        
        # Add context information if available
        if context or client_context:
            context_message = "Here is relevant information from the salon database:\n\n"
            if context:
                context_message += context + "\n\n"
            if client_context:
                context_message += client_context + "\n\n"
            context_message += (
                "Use this information to answer the user's question accurately. "
                "You can reference this information in your response, but phrase it naturally as if you're having a conversation. "
                "Only mention details that are relevant to the current query."
            )
            
            # Add context as a system message
            messages.append({"role": "system", "content": context_message})
        
        # Add the conversation history first (excluding system messages)
        for message in conversation_history:
            if message["role"] != "system" and message["role"] != "user" or message["content"] != query:
                messages.append(message)
        
        # Then add the current user message
        messages.append(user_message)
                
        print(f"DEBUG - Final API messages structure: {messages}")
        
        # 6. Call OpenAI API
        try:
            print(f"DEBUG - Sending request to OpenAI API with {len(messages)} messages")
            
            # Debug logging messages - be careful not to log the API key
            request_data = {
                "model": "gpt-3.5-turbo",
                "messages": messages,
                "max_tokens": 500,
                "temperature": 0.7
            }
            print(f"DEBUG - Request data: {request_data}")
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=request_data
            )
            
            print(f"DEBUG - OpenAI API response status code: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"Error calling OpenAI API: {response.text}"
                print(f"DEBUG - API Error: {error_msg}")
                self.add_message(conversation_id, "assistant", error_msg)
                return {"response": error_msg, "metadata": None}
            
            result = response.json()
            print(f"DEBUG - API response: {result}")
            
            assistant_response = result["choices"][0]["message"]["content"]
            print(f"DEBUG - Assistant response: {assistant_response}")
            
            # 7. Store the assistant's response
            metadata = {
                "usage": result.get("usage", {}),
                "retrieved_docs": [{"type": doc["type"], "id": doc["id"]} for doc in relevant_docs]
            }
            
            self.add_message(conversation_id, "assistant", assistant_response, metadata)
            
            # 8. If this was a conversation about a client, process it for insights
            if client_id:
                # Get the most recent messages including this exchange
                recent_messages = self.get_conversation_history(conversation_id, limit=10)
                insights = extract_client_insights(recent_messages, client_id)
                
                # Store any high-importance insights (importance > 5)
                for insight in insights:
                    if insight['importance'] > 5:
                        self.create_client_memory(
                            client_id=client_id,
                            memory_type=insight['type'],
                            content=insight['content'],
                            importance=insight['importance']
                        )
            
            return {
                "response": assistant_response,
                "metadata": metadata,
                "context": relevant_docs
            }
            
        except Exception as e:
            error_msg = f"Error generating response: {str(e)}"
            self.add_message(conversation_id, "assistant", error_msg)
            return {"response": error_msg, "metadata": None}


def analyze_client_history(client):
    """Analyze client history to generate insights for journey mapping
    
    Args:
        client: Client object or dictionary with client information
        
    Returns:
        dict: Analysis results with journey stage and recommendations
    """
    # Extract key client data
    try:
        loyalty_points = client.get('loyalty_points', 0) if isinstance(client, dict) else client.loyalty_points
        total_spent = client.get('total_spent', 0) if isinstance(client, dict) else client.total_spent
        tier = client.get('tier', 'New') if isinstance(client, dict) else client.tier
        
        # Determine current journey stage
        if loyalty_points < 100 and total_spent < 200:
            journey_stage = "Acquisition"
            recommendations = [
                "Offer a welcome discount or complimentary service",
                "Collect preferences and style information",
                "Introduce loyalty program benefits"
            ]
        elif loyalty_points < 500 and total_spent < 1000:
            journey_stage = "Engagement"
            recommendations = [
                "Suggest service upgrades based on preferences",
                "Create personalized product recommendations",
                "Schedule regular appointment reminders"
            ]
        elif loyalty_points < 1000 and total_spent < 2000:
            journey_stage = "Retention"
            recommendations = [
                "Offer loyalty tier upgrade incentives",
                "Introduce referral program benefits",
                "Provide exclusive access to new services"
            ]
        else:
            journey_stage = "Advocacy"
            recommendations = [
                "Recognize VIP status with premium experiences",
                "Request testimonials or social media tags",
                "Offer early access to limited services"
            ]
            
        return {
            "journey_stage": journey_stage,
            "recommendations": recommendations,
            "loyalty_level": tier,
            "engagement_score": min(10, int(loyalty_points / 100)) 
        }
    except Exception as e:
        print(f"Error analyzing client history: {str(e)}")
        return {
            "journey_stage": "Unknown",
            "recommendations": ["Complete client profile to enable personalized recommendations"],
            "loyalty_level": "New",
            "engagement_score": 0
        }

def extract_client_insights(conversation_history, client_id):
    """Extract insights about clients from conversation history
    This would be enhanced with real NLP in production
    """
    # Simplified example implementation - in production would use more sophisticated NLP
    insights = []
    relevant_keywords = {
        'preference': ['like', 'prefer', 'favorite', 'enjoy', 'want', 'love', 'fond of'],
        'dislike': ['dislike', 'hate', 'don\'t like', 'don\'t want', 'avoid', 'allergic to', 'sensitive to'],
        'allergy': ['allergy', 'allergic', 'reaction', 'sensitive', 'irritation', 'rash', 'itchy'],
        'history': ['last time', 'previously', 'before', 'past', 'used to', 'had', 'appointment'],
        'style': ['style', 'haircut', 'color', 'length', 'blonde', 'brunette', 'red', 'highlights', 'short', 'long', 'bob', 'layers', 'bangs'],
        'frequency': ['every', 'monthly', 'weekly', 'biweekly', 'quarterly', 'often', 'regularly', 'seldom', 'rare'],
        'special_occasion': ['wedding', 'party', 'event', 'vacation', 'holiday', 'trip', 'celebration', 'anniversary', 'graduation']
    }
    
    # Track processed sentences to avoid duplicates
    processed_sentences = set()
    
    for message in conversation_history:
        if message['role'] != 'user':
            continue
            
        content = message['content'].lower()
        
        # Extract sentences that might contain client insights
        sentences = [s.strip() for s in content.split('.') if s.strip()]
        
        for sentence in sentences:
            # Skip if we've already processed this sentence
            if sentence in processed_sentences:
                continue
                
            processed_sentences.add(sentence)
            
            # Check each insight type
            for insight_type, keywords in relevant_keywords.items():
                # Calculate the importance based on multiple factors
                importance = 0
                matched_keywords = []
                
                for keyword in keywords:
                    if keyword in sentence:
                        importance += 1
                        matched_keywords.append(keyword)
                
                # If we found any keywords of this type
                if matched_keywords:
                    # Increase importance for sentences with personal pronouns
                    personal_pronouns = ['i', 'me', 'my', 'mine', 'myself']
                    if any(pronoun in sentence.split() for pronoun in personal_pronouns):
                        importance += 2
                    
                    # Add the insight if it's important enough (has at least one keyword)
                    if importance > 0:
                        # Cap importance at 10
                        importance = min(importance, 10)
                        
                        # Determine if this is factual or a preference
                        is_factual = insight_type in ['history', 'allergy']
                        
                        # Add a prefix based on the insight type to make it more usable
                        prefixed_content = sentence
                        if insight_type == 'preference':
                            prefixed_content = f"Client likes: {sentence}"
                        elif insight_type == 'dislike':
                            prefixed_content = f"Client dislikes: {sentence}"
                        elif insight_type == 'allergy':
                            prefixed_content = f"Client allergy/sensitivity: {sentence}"
                        elif insight_type == 'history':
                            prefixed_content = f"Client history: {sentence}"
                        elif insight_type == 'style':
                            prefixed_content = f"Client style preference: {sentence}"
                        elif insight_type == 'frequency':
                            prefixed_content = f"Client visit frequency: {sentence}"
                        elif insight_type == 'special_occasion':
                            prefixed_content = f"Client special occasion: {sentence}"
                        
                        insights.append({
                            'type': insight_type,
                            'content': prefixed_content,
                            'importance': importance
                        })
    
    # Sort by importance (highest first)
    insights.sort(key=lambda x: x['importance'], reverse=True)
    
    # Remove duplicate content (keep the one with highest importance)
    unique_insights = []
    seen_content = set()
    
    for insight in insights:
        if insight['content'] not in seen_content:
            seen_content.add(insight['content'])
            unique_insights.append(insight)
    
    return unique_insights
def generate_treatment_preview(image_file, treatment_type):
    """Generate a preview of treatment results using AI
    
    Args:
        image_file: uploaded file object
        treatment_type: type of treatment (anti_aging, acne, brightening, hydration)
    
    Returns:
        dict: Response containing either preview_url or error message
    """
    if not image_file:
        return {"error": "No image file provided"}
        
    if not treatment_type in ['anti_aging', 'acne', 'brightening', 'hydration']:
        return {"error": "Invalid treatment type"}
        
    try:
        # Validate image file
        if not image_file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            return {"error": "Invalid image format. Please use PNG or JPEG"}
            
        # Save original image
        img = Image.open(image_file)
        img_buffer = BytesIO()
        img.save(img_buffer, format="JPEG")
        img_str = base64.b64encode(img_buffer.getvalue()).decode()

        # Prepare the prompt based on treatment type
        prompts = {
            'anti_aging': "Show reduced appearance of fine lines and wrinkles, improved skin firmness",
            'acne': "Show clearer skin with reduced acne, smoother texture, less inflammation",
            'brightening': "Show more even skin tone, reduced dark spots, enhanced radiance",
            'hydration': "Show plumper, more hydrated skin with improved texture and glow"
        }

        # Call OpenAI's DALL-E API for image editing
        response = requests.post(
            "https://api.openai.com/v1/images/edits",
            headers={"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"},
            json={
                "image": img_str,
                "prompt": prompts.get(treatment_type, "Enhance skin appearance"),
                "n": 1,
                "size": "1024x1024"
            }
        )

        if response.status_code != 200:
            raise Exception(f"API Error: {response.text}")

        # Save the generated image
        result = response.json()
        preview_url = result['data'][0]['url']
        
        # Download and save the preview
        preview_response = requests.get(preview_url)
        if preview_response.status_code == 200:
            filename = secure_filename(f"preview_{treatment_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg")
            filepath = os.path.join(current_app.static_folder, 'previews', filename)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Save the file
            with open(filepath, 'wb') as f:
                f.write(preview_response.content)
            
            return url_for('static', filename=f'previews/{filename}')
            
        raise Exception("Failed to download preview image")

    except Exception as e:
        print(f"Error generating preview: {str(e)}")
        return None
