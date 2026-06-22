"""
OnTime Moving - Flask API Server
Modern booking system backend with authentication
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from booking_database import BookingDatabase
from email_notifier import EmailNotifier
from functools import wraps
from datetime import datetime
import os

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'), override=True)

# Chatbot setup (Groq — free tier, no credit card)
_SYSTEM_PROMPT = (
    "You are a friendly, helpful assistant for OnTime Moving and Storage, "
    "a professional moving company in the Lower Mainland, BC, Canada. "
    "The business has 22+ years of experience, 11,000+ happy customers, "
    "an A+ BBB rating, and is fully licensed and insured. "
    "Address: 104-1525 Broadway St, Port Coquitlam, BC V3C 6M2. "
    "Phone: (604) 505-0026. Email: info@ontime-moving.com. "
    "Services: Residential Moving, Commercial Moving, Storage Solutions (secure/climate-controlled), Packing Services. "
    "Service area: Vancouver, Burnaby, Port Coquitlam, Port Moody, Coquitlam, Surrey, Langley, Richmond, and the entire Lower Mainland. "
    "To book a move or get a free quote, direct customers to call (604) 505-0026 or visit the Book Now page. "
    "Keep replies concise and friendly. If you don't know a specific price, "
    "say pricing depends on move size and distance and invite them to call for a free quote. "
    "Never make up specific prices or availability. "
    "If someone wants to book, guide them to the booking form or phone number."
)

try:
    import groq as _groq_lib
    _groq_key = os.getenv('GROQ_API_KEY', '').strip()
    if _groq_key and _groq_key != 'your_groq_key_here':
        _groq_client = _groq_lib.Groq(api_key=_groq_key)
        print("✓ Groq chatbot initialized")
    else:
        _groq_client = None
        print("⚠  GROQ_API_KEY not set — get a free key at https://console.groq.com")
except ImportError:
    _groq_client = None
    print("⚠  groq package not installed — run: pip install groq")
except Exception as e:
    _groq_client = None
    print(f"⚠  Groq chatbot unavailable: {e}")

# Initialize Flask app
app = Flask(__name__, static_folder='.')
CORS(app)  # Enable CORS for frontend-backend communication

# Initialize database
db = BookingDatabase()
db.initialize_database()
db.initialize_auth_tables()

# Initialize email notifier
try:
    notifier = EmailNotifier()
    print(f"✓ Email notifier initialized (enabled: {notifier.enabled})")
except Exception as e:
    print(f"✗ Failed to initialize email notifier: {e}")
    notifier = None


# ==================== AUTHENTICATION MIDDLEWARE ====================

def require_auth(f):
    """Decorator to require authentication for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header:
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 401
        
        # Extract token from Bearer format
        token = auth_header.replace('Bearer ', '') if auth_header.startswith('Bearer ') else auth_header
        
        user = db.validate_session(token)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'Invalid or expired session'
            }), 401
        
        # Add user to request context
        request.current_user = user
        return f(*args, **kwargs)
    
    return decorated_function


# ==================== AUTHENTICATION ENDPOINTS ====================

@app.route('/api/auth/login', methods=['POST'])
def login():
    """
    Authenticate user and create session.
    
    Expected JSON:
    {
        "username": "admin",
        "password": "password",
        "remember": false
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({
                'success': False,
                'error': 'Username and password are required'
            }), 400
        
        username = data['username']
        password = data['password']
        remember = data.get('remember', False)
        
        # Authenticate user
        user = db.authenticate_user(username, password)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'Invalid username or password'
            }), 401
        
        # Create session
        duration_days = 30 if remember else 1
        token = db.create_session(user['id'], duration_days=duration_days)
        
        return jsonify({
            'success': True,
            'token': token,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'full_name': user['full_name']
            }
        }), 200
        
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Logout user by deleting their session."""
    try:
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.replace('Bearer ', '') if auth_header.startswith('Bearer ') else auth_header
        
        if token:
            db.delete_session(token)
        
        return jsonify({
            'success': True,
            'message': 'Logged out successfully'
        }), 200
        
    except Exception as e:
        print(f"Logout error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@app.route('/api/auth/verify', methods=['GET'])
def verify_session():
    """Verify if a session token is valid."""
    try:
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.replace('Bearer ', '') if auth_header.startswith('Bearer ') else auth_header
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'No token provided'
            }), 401
        
        user = db.validate_session(token)
        
        if user:
            return jsonify({
                'success': True,
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'email': user['email'],
                    'full_name': user['full_name']
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid or expired session'
            }), 401
            
    except Exception as e:
        print(f"Verify session error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


# ==================== BOOKING ENDPOINTS (PUBLIC) ====================

# API Routes

@app.route('/')
def index():
    """Serve the main page"""
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    """Serve static files (CSS, JS, images)"""
    return send_from_directory('.', path)

@app.route('/api/booking', methods=['POST'])
def create_booking():
    """
    Create a new booking
    
    Expected JSON body:
    {
        "customer_name": "John Doe",
        "phone": "(604) 555-1234",
        "email": "john@example.com",
        "moving_from": "123 Main St, Vancouver",
        "moving_to": "456 Oak Ave, Burnaby",
        "move_date": "2026-03-20",
        "move_size": "2-bedroom",
        "notes": "Optional notes"
    }
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = [
            'customer_name', 'phone', 'email',
            'moving_from', 'moving_to', 'move_date', 'move_size'
        ]
        
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Validate email format
        email = data.get('email', '')
        if '@' not in email or '.' not in email:
            return jsonify({
                'success': False,
                'error': 'Invalid email address'
            }), 400
        
        # Validate date format and future date
        try:
            move_date = datetime.strptime(data['move_date'], '%Y-%m-%d')
            if move_date.date() < datetime.now().date():
                return jsonify({
                    'success': False,
                    'error': 'Move date must be in the future'
                }), 400
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Invalid date format. Use YYYY-MM-DD'
            }), 400
        
        # Insert booking
        booking_id = db.insert_booking(
            customer_name=data['customer_name'],
            phone=data['phone'],
            email=data['email'],
            moving_from=data['moving_from'],
            moving_to=data['moving_to'],
            move_date=data['move_date'],
            move_size=data['move_size'],
            notes=data.get('notes', '')
        )
        
        # Send email notifications
        try:
            booking_data = {
                'booking_id': booking_id,
                'customer_name': data['customer_name'],
                'phone': data['phone'],
                'email': data['email'],
                'moving_from': data['moving_from'],
                'moving_to': data['moving_to'],
                'move_date': data['move_date'],
                'move_size': data['move_size'],
                'notes': data.get('notes', '')
            }
            print(f"📧 Sending notification for booking #{booking_id}...")
            if notifier:
                notifier.send_booking_confirmation(booking_data)
            else:
                print("⚠️  Email not ifier not available")
        except Exception as e:
            print(f"Warning: Email notification failed: {e}")
            import traceback
            traceback.print_exc()
            # Don't fail the booking if email fails
        
        return jsonify({
            'success': True,
            'booking_id': booking_id,
            'message': 'Booking created successfully'
        }), 201
        
    except Exception as e:
        print(f"Error creating booking: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@app.route('/api/bookings', methods=['GET'])
def get_bookings():
    """
    Get all bookings with optional filters
    
    Query parameters:
    - status: Filter by status (pending, confirmed, completed, cancelled)
    - limit: Maximum number of results
    - search: Search by customer name, phone, or email
    """
    try:
        status = request.args.get('status')
        limit = request.args.get('limit', type=int)
        search = request.args.get('search')
        
        if search:
            bookings = db.search_bookings(search)
        elif status:
            bookings = db.get_bookings_by_status(status)
        else:
            bookings = db.get_all_bookings(limit=limit)
        
        return jsonify({
            'success': True,
            'bookings': bookings,
            'count': len(bookings)
        }), 200
        
    except Exception as e:
        print(f"Error fetching bookings: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@app.route('/api/booking/<int:booking_id>', methods=['GET'])
def get_booking(booking_id):
    """Get a specific booking by ID"""
    try:
        booking = db.get_booking(booking_id)
        
        if booking:
            return jsonify({
                'success': True,
                'booking': booking
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Booking not found'
            }), 404
            
    except Exception as e:
        print(f"Error fetching booking: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@app.route('/api/booking/<int:booking_id>/status', methods=['PATCH'])
def update_booking_status(booking_id):
    """
    Update booking status
    
    Expected JSON body:
    {
        "status": "confirmed"
    }
    """
    try:
        data = request.get_json()
        status = data.get('status')
        
        if not status:
            return jsonify({
                'success': False,
                'error': 'Status is required'
            }), 400
        
        success = db.update_booking_status(booking_id, status)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Booking status updated to {status}'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to update booking'
            }), 400
            
    except Exception as e:
        print(f"Error updating booking: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@app.route('/api/booking/<int:booking_id>', methods=['DELETE'])
def delete_booking(booking_id):
    """Delete a booking"""
    try:
        success = db.delete_booking(booking_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Booking deleted successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Booking not found'
            }), 404
            
    except Exception as e:
        print(f"Error deleting booking: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@app.route('/api/bookings/upcoming', methods=['GET'])
def get_upcoming_bookings():
    """Get upcoming bookings"""
    try:
        limit = request.args.get('limit', default=10, type=int)
        bookings = db.get_upcoming_bookings(limit=limit)
        
        return jsonify({
            'success': True,
            'bookings': bookings,
            'count': len(bookings)
        }), 200
        
    except Exception as e:
        print(f"Error fetching upcoming bookings: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """Get booking statistics"""
    try:
        stats = db.get_statistics()
        
        return jsonify({
            'success': True,
            'statistics': stats
        }), 200
        
    except Exception as e:
        print(f"Error fetching statistics: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'success': True,
        'status': 'healthy',
        'message': 'OnTime Moving API is running'
    }), 200


# ==================== CHATBOT ENDPOINT ====================

@app.route('/api/chat', methods=['POST'])
def chat():
    """
    AI chatbot endpoint using Groq free tier (llama-3.3-70b-versatile).

    Expected JSON:
    {
        "message": "How much does a 2-bedroom move cost?",
        "history": [
            {"role": "user",      "parts": [{"text": "Hello"}]},
            {"role": "assistant", "parts": [{"text": "Hi! How can I help?"}]}
        ]
    }
    """
    if not _groq_client:
        return jsonify({
            'success': False,
            'error': 'Chatbot is not configured. Please set GROQ_API_KEY in the .env file.'
        }), 503

    try:
        data = request.get_json()
        message = (data or {}).get('message', '').strip()
        raw_history = (data or {}).get('history', [])

        if not message:
            return jsonify({'success': False, 'error': 'Message is required'}), 400

        # Build Groq messages list (OpenAI-compatible format)
        messages = [{'role': 'system', 'content': _SYSTEM_PROMPT}]
        for turn in raw_history[-10:]:
            role = turn.get('role', 'user')
            # Map frontend 'model' role to 'assistant' for Groq
            if role == 'model':
                role = 'assistant'
            parts = turn.get('parts', [])
            content = parts[0].get('text', '') if parts and isinstance(parts[0], dict) else str(parts[0]) if parts else ''
            if content:
                messages.append({'role': role, 'content': content})
        messages.append({'role': 'user', 'content': message})

        response = _groq_client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=messages,
            max_tokens=512,
            temperature=0.7,
        )

        reply = response.choices[0].message.content
        return jsonify({'success': True, 'reply': reply}), 200

    except Exception as e:
        print(f"Chat error: {e}")
        return jsonify({
            'success': False,
            'error': 'Chat service temporarily unavailable. Please call us at (604) 505-0026.'
        }), 500


# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500


# Run server
if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚚 OnTime Moving - Modern Booking System 🚚")
    print("="*50)
    print("\n📡 Server starting...")
    print(f"🌐 Website:     http://localhost:5000")
    print(f"🔌 API:         http://localhost:5000/api")
    print(f"💚 Health:      http://localhost:5000/api/health")
    print("\n📝 Available Endpoints:")
    print("   POST   /api/booking              - Create booking")
    print("   GET    /api/bookings             - Get all bookings")
    print("   GET    /api/booking/<id>         - Get specific booking")
    print("   PATCH  /api/booking/<id>/status  - Update status")
    print("   DELETE /api/booking/<id>         - Delete booking")
    print("   GET    /api/bookings/upcoming    - Get upcoming bookings")
    print("   GET    /api/statistics           - Get statistics")
    print("\n✅ Press Ctrl+C to stop the server\n")
    print("="*50 + "\n")
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )
