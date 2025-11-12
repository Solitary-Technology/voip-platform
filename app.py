from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
import os
from datetime import datetime
from sqlalchemy import func

app = Flask(__name__)

# Database configuration 
DB_USER = os.getenv('DB_USER', 'voip_admin')
DB_PASS = os.getenv('DB_PASS', 'ChangeThisToSecurePassword123!')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'voip_platform')

app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Models
class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    sip_password = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    forward_to = db.Column(db.String(20))
    forward_enabled = db.Column(db.Boolean, default=False)
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class CDR(db.Model):
    __tablename__ = 'cdr'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    direction = db.Column(db.String(10))
    caller_id = db.Column(db.String(50))
    destination = db.Column(db.String(50))
    start_time = db.Column(db.DateTime)
    answer_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    duration = db.Column(db.Integer)
    billsec = db.Column(db.Integer)
    hangup_cause = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Authentication decorator
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('Authorization', '').replace('Bearer ', '')
        expected_key = os.getenv('API_KEY', 'default_insecure_key_change_this')
        
        if not api_key or api_key != expected_key:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

# Customer Management Endpoints
@app.route('/customers', methods=['POST'])
@require_api_key
def create_customer():
    data = request.json
    
    # Validate required fields
    required_fields = ['username', 'sip_password', 'phone_number']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Check for duplicate username
    if Customer.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 400
    
    # Check for duplicate phone number
    if Customer.query.filter_by(phone_number=data['phone_number']).first():
        return jsonify({'error': 'Phone number already exists'}), 400
    
    customer = Customer(
        username=data['username'],
        sip_password=data['sip_password'],
        email=data.get('email'),
        phone_number=data['phone_number']
    )
    
    db.session.add(customer)
    db.session.commit()
    
    return jsonify({
        'id': customer.id,
        'username': customer.username,
        'phone_number': customer.phone_number,
        'email': customer.email,
        'enabled': customer.enabled
    }), 201

@app.route('/customers', methods=['GET'])
@require_api_key
def list_customers():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    query = Customer.query
    
    # Filter by enabled status
    if request.args.get('enabled') is not None:
        enabled = request.args.get('enabled').lower() == 'true'
        query = query.filter_by(enabled=enabled)
    
    # Search across fields
    search = request.args.get('search')
    if search:
        search_pattern = f'%{search}%'
        query = query.filter(
            db.or_(
                Customer.username.ilike(search_pattern),
                Customer.email.ilike(search_pattern),
                Customer.phone_number.ilike(search_pattern)
            )
        )
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'customers': [{
            'id': c.id,
            'username': c.username,
            'email': c.email,
            'phone_number': c.phone_number,
            'enabled': c.enabled,
            'forward_enabled': c.forward_enabled,
            'forward_to': c.forward_to,
            'created_at': c.created_at.isoformat()
        } for c in pagination.items]
    })

@app.route('/customers/<int:customer_id>', methods=['GET'])
@require_api_key
def get_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    
    return jsonify({
        'id': customer.id,
        'username': customer.username,
        'email': customer.email,
        'phone_number': customer.phone_number,
        'enabled': customer.enabled,
        'forward_enabled': customer.forward_enabled,
        'forward_to': customer.forward_to,
        'created_at': customer.created_at.isoformat(),
        'updated_at': customer.updated_at.isoformat()
    })

@app.route('/customers/<int:customer_id>', methods=['PUT'])
@require_api_key
def update_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    data = request.json
    
    # Update allowed fields
    if 'email' in data:
        customer.email = data['email']
    if 'sip_password' in data:
        customer.sip_password = data['sip_password']
    if 'enabled' in data:
        customer.enabled = data['enabled']
    if 'phone_number' in data:
        # Check if new phone number is already taken
        existing = Customer.query.filter_by(phone_number=data['phone_number']).first()
        if existing and existing.id != customer_id:
            return jsonify({'error': 'Phone number already exists'}), 400
        customer.phone_number = data['phone_number']
    
    customer.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'id': customer.id,
        'username': customer.username,
        'email': customer.email,
        'phone_number': customer.phone_number,
        'enabled': customer.enabled
    })

@app.route('/customers/<int:customer_id>', methods=['DELETE'])
@require_api_key
def delete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    
    db.session.delete(customer)
    db.session.commit()
    
    return jsonify({'message': 'Customer deleted successfully'}), 200

# Call Forwarding Endpoints
@app.route('/customers/<int:customer_id>/forwarding', methods=['POST'])
@require_api_key
def enable_forwarding(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    data = request.json
    
    if 'forward_to' not in data:
        return jsonify({'error': 'forward_to is required'}), 400
    
    customer.forward_to = data['forward_to']
    customer.forward_enabled = True
    customer.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'status': 'forwarding enabled',
        'forward_to': customer.forward_to
    })

@app.route('/customers/<int:customer_id>/forwarding', methods=['DELETE'])
@require_api_key
def disable_forwarding(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    
    customer.forward_enabled = False
    customer.forward_to = None
    customer.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'status': 'forwarding disabled'})

# CDR Endpoints
@app.route('/cdr', methods=['GET'])
@require_api_key
def get_cdrs():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    query = CDR.query
    
    # Filter by customer
    customer_id = request.args.get('customer_id', type=int)
    if customer_id:
        query = query.filter_by(customer_id=customer_id)
    
    # Filter by direction
    direction = request.args.get('direction')
    if direction:
        query = query.filter_by(direction=direction)
    
    # Filter by date range
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    if start_date:
        query = query.filter(CDR.start_time >= start_date)
    if end_date:
        query = query.filter(CDR.start_time <= end_date)
    
    # Order by most recent first
    query = query.order_by(CDR.start_time.desc())
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'records': [{
            'id': cdr.id,
            'customer_id': cdr.customer_id,
            'direction': cdr.direction,
            'caller_id': cdr.caller_id,
            'destination': cdr.destination,
            'start_time': cdr.start_time.isoformat() if cdr.start_time else None,
            'answer_time': cdr.answer_time.isoformat() if cdr.answer_time else None,
            'end_time': cdr.end_time.isoformat() if cdr.end_time else None,
            'duration': cdr.duration,
            'billsec': cdr.billsec,
            'hangup_cause': cdr.hangup_cause
        } for cdr in pagination.items]
    })

@app.route('/customers/<int:customer_id>/cdr/summary', methods=['GET'])
@require_api_key
def get_cdr_summary(customer_id):
    query = CDR.query.filter_by(customer_id=customer_id)
    
    # Filter by date range if provided
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    if start_date:
        query = query.filter(CDR.start_time >= start_date)
    if end_date:
        query = query.filter(CDR.start_time <= end_date)
    
    # Calculate summary statistics
    total_calls = query.count()
    inbound_calls = query.filter_by(direction='inbound').count()
    outbound_calls = query.filter_by(direction='outbound').count()
    
    answered_calls = query.filter(CDR.answer_time.isnot(None)).count()
    missed_calls = query.filter(CDR.answer_time.is_(None)).count()
    
    total_duration = db.session.query(func.sum(CDR.duration)).filter(
        CDR.customer_id == customer_id
    ).scalar() or 0
    
    total_billsec = db.session.query(func.sum(CDR.billsec)).filter(
        CDR.customer_id == customer_id
    ).scalar() or 0
    
    return jsonify({
        'customer_id': customer_id,
        'total_calls': total_calls,
        'inbound_calls': inbound_calls,
        'outbound_calls': outbound_calls,
        'answered_calls': answered_calls,
        'missed_calls': missed_calls,
        'total_duration_seconds': total_duration,
        'total_billable_seconds': total_billsec
    })

# FreeSWITCH Integration Endpoints
@app.route('/freeswitch/directory', methods=['POST'])
def freeswitch_directory():
    """Handle FreeSWITCH directory lookups for authentication"""
    username = request.values.get('user') or request.values.get('username')
    domain = request.values.get('domain') or 'default'
    
    if not username:
        return '''<?xml version="1.0" encoding="UTF-8"?>
<document type="freeswitch/xml">
  <section name="result">
    <result status="not found" />
  </section>
</document>''', 404
    
    customer = Customer.query.filter_by(username=username, enabled=True).first()
    
    if not customer:
        return '''<?xml version="1.0" encoding="UTF-8"?>
<document type="freeswitch/xml">
  <section name="result">
    <result status="not found" />
  </section>
</document>''', 404
    
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<document type="freeswitch/xml">
  <section name="directory">
    <domain name="{domain}">
      <user id="{customer.username}">
        <params>
          <param name="password" value="{customer.sip_password}"/>
        </params>
        <variables>
          <variable name="user_context" value="default"/>
          <variable name="customer_id" value="{customer.id}"/>
          <variable name="phone_number" value="{customer.phone_number}"/>
          <variable name="forward_enabled" value="{str(customer.forward_enabled).lower()}"/>
          <variable name="forward_to" value="{customer.forward_to or ''}"/>
          <variable name="outbound_caller_id_number" value="{customer.phone_number}"/>
        </variables>
      </user>
    </domain>
  </section>
</document>'''
    
    return xml, 200, {'Content-Type': 'application/xml'}

@app.route('/freeswitch/dialplan', methods=['POST'])
def freeswitch_dialplan():
    """Handle FreeSWITCH dialplan lookups for call routing"""
    
    # DEBUG: Log all the values FreeSWITCH sends
    import sys
    print("=== DIALPLAN DEBUG ===", file=sys.stderr)
    
    destination = request.values.get('Caller-Destination-Number')
    caller = request.values.get('Caller-Caller-ID-Number')
    username = request.values.get('variable_user_name')
    context = request.values.get('Caller-Context')
    customer_id = request.values.get('variable_customer_id')
    
    print(f"Destination: {destination}", file=sys.stderr)
    print(f"Caller: {caller}", file=sys.stderr)
    print(f"Username: {username}", file=sys.stderr)
    print(f"Context: {context}", file=sys.stderr)
    print(f"Customer ID: {customer_id}", file=sys.stderr)
    print("=====================", file=sys.stderr)
    
    if not destination:
        return '''<?xml version="1.0" encoding="UTF-8"?>
<document type="freeswitch/xml">
  <section name="result">
    <result status="not found" />
  </section>
</document>''', 404
    
    # If we have a customer_id variable, this is from an authenticated user making an outbound call
    if customer_id and username:
        customer = Customer.query.filter_by(id=int(customer_id), username=username, enabled=True).first()
        if customer:
            # This is an outbound call
            xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<document type="freeswitch/xml">
  <section name="dialplan">
    <context name="{context or 'default'}">
      <extension name="outbound_{customer.id}">
        <condition field="destination_number" expression="^(.+)$">
          <action application="set" data="customer_id={customer.id}"/>
          <action application="set" data="direction=outbound"/>
          <action application="set" data="effective_caller_id_number={customer.phone_number}"/>
          <action application="set" data="hangup_after_bridge=true"/>
          <action application="bridge" data="sofia/gateway/solitary/$1"/>
        </condition>
      </extension>
    </context>
  </section>
</document>'''
            return xml, 200, {'Content-Type': 'application/xml'}
    
    # Check if this is an inbound call to a customer DID
    customer = Customer.query.filter_by(phone_number=destination).first()
    
    if not customer:
        return '''<?xml version="1.0" encoding="UTF-8"?>
<document type="freeswitch/xml">
  <section name="result">
    <result status="not found" />
  </section>
</document>''', 404
    
    # This is an inbound call
    if customer.forward_enabled and customer.forward_to:
        # Forward the call to external number
        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<document type="freeswitch/xml">
  <section name="dialplan">
    <context name="default">
      <extension name="forward_{customer.id}">
        <condition field="destination_number" expression="^{destination}$">
          <action application="set" data="customer_id={customer.id}"/>
          <action application="set" data="direction=inbound"/>
          <action application="set" data="hangup_after_bridge=true"/>
          <action application="bridge" data="sofia/gateway/solitary/{customer.forward_to}"/>
        </condition>
      </extension>
    </context>
  </section>
</document>'''
    else:
        # Route to registered device
        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<document type="freeswitch/xml">
  <section name="dialplan">
    <context name="default">
      <extension name="local_{customer.id}">
        <condition field="destination_number" expression="^{destination}$">
          <action application="set" data="customer_id={customer.id}"/>
          <action application="set" data="direction=inbound"/>
          <action application="set" data="hangup_after_bridge=true"/>
          <action application="bridge" data="user/{customer.username}@default"/>
        </condition>
      </extension>
    </context>
  </section>
</document>'''
    
    return xml, 200, {'Content-Type': 'application/xml'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)