#!/usr/bin/env python3
"""
IoT Honeypot Flask Server
Logs and analyzes IoT device activity
"""

from flask import Flask, render_template, request, jsonify
from datetime import datetime
import json
import sqlite3
import os
import logging
from utils import log_event, get_threat_level, analyze_pattern

# Initialize Flask app
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Configure logging
logging.basicConfig(
    filename='logs/honeypot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Database setup
def init_db():
    """Initialize SQLite database"""
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS events
                 (id INTEGER PRIMARY KEY,
                  timestamp TEXT,
                  device_id TEXT,
                  event_type TEXT,
                  source_ip TEXT,
                  data TEXT,
                  threat_level TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS devices
                 (id INTEGER PRIMARY KEY,
                  device_id TEXT UNIQUE,
                  first_seen TEXT,
                  last_seen TEXT,
                  status TEXT,
                  ip_address TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS attacks
                 (id INTEGER PRIMARY KEY,
                  timestamp TEXT,
                  attack_type TEXT,
                  source_ip TEXT,
                  target_port INTEGER,
                  payload TEXT)''')
    
    conn.commit()
    conn.close()

@app.route('/')
def index():
    """Render main dashboard"""
    return render_template('index.html')

@app.route('/api/telemetry', methods=['POST'])
def receive_telemetry():
    """Receive telemetry data from IoT devices"""
    try:
        data = request.get_json()
        device_id = data.get('device_id', 'UNKNOWN')
        timestamp = data.get('timestamp', datetime.now().isoformat())
        source_ip = request.remote_addr
        
        # Log the event
        log_event('telemetry', device_id, timestamp, data, source_ip)
        
        # Store in database
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        
        threat_level = get_threat_level(data)
        
        c.execute('''INSERT INTO events 
                     (timestamp, device_id, event_type, source_ip, data, threat_level)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (timestamp, device_id, 'telemetry', source_ip, 
                   json.dumps(data), threat_level))
        
        # Update device record
        c.execute('''INSERT OR IGNORE INTO devices 
                     (device_id, first_seen, last_seen, status, ip_address)
                     VALUES (?, ?, ?, ?, ?)''',
                  (device_id, timestamp, timestamp, 'active', source_ip))
        
        c.execute('''UPDATE devices 
                     SET last_seen = ?, ip_address = ?, status = 'active'
                     WHERE device_id = ?''',
                  (timestamp, source_ip, device_id))
        
        conn.commit()
        conn.close()
        
        logging.info(f"Telemetry received from {device_id} ({source_ip})")
        
        return jsonify({'status': 'success', 'message': 'Telemetry received'}), 200
    
    except Exception as e:
        logging.error(f"Error processing telemetry: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/attack', methods=['POST'])
def log_attack():
    """Log detected attack attempts"""
    try:
        data = request.get_json()
        timestamp = datetime.now().isoformat()
        source_ip = data.get('source_ip', request.remote_addr)
        attack_type = data.get('attack_type', 'UNKNOWN')
        target_port = data.get('target_port', 0)
        payload = data.get('payload', '')
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        
        c.execute('''INSERT INTO attacks 
                     (timestamp, attack_type, source_ip, target_port, payload)
                     VALUES (?, ?, ?, ?, ?)''',
                  (timestamp, attack_type, source_ip, target_port, payload))
        
        conn.commit()
        conn.close()
        
        logging.warning(f"Attack detected: {attack_type} from {source_ip}")
        
        return jsonify({'status': 'success', 'message': 'Attack logged'}), 200
    
    except Exception as e:
        logging.error(f"Error logging attack: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/events', methods=['GET'])
def get_events():
    """Retrieve logged events"""
    try:
        limit = request.args.get('limit', 100, type=int)
        event_type = request.args.get('type', None)
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        
        if event_type:
            c.execute('''SELECT * FROM events 
                         WHERE event_type = ? 
                         ORDER BY timestamp DESC 
                         LIMIT ?''', (event_type, limit))
        else:
            c.execute('''SELECT * FROM events 
                         ORDER BY timestamp DESC 
                         LIMIT ?''', (limit,))
        
        events = c.fetchall()
        conn.close()
        
        events_list = [
            {
                'id': e[0],
                'timestamp': e[1],
                'device_id': e[2],
                'event_type': e[3],
                'source_ip': e[4],
                'data': json.loads(e[5]),
                'threat_level': e[6]
            }
            for e in events
        ]
        
        return jsonify(events_list), 200
    
    except Exception as e:
        logging.error(f"Error retrieving events: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/devices', methods=['GET'])
def get_devices():
    """Retrieve connected devices"""
    try:
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        
        c.execute('SELECT * FROM devices ORDER BY last_seen DESC')
        devices = c.fetchall()
        conn.close()
        
        devices_list = [
            {
                'id': d[0],
                'device_id': d[1],
                'first_seen': d[2],
                'last_seen': d[3],
                'status': d[4],
                'ip_address': d[5]
            }
            for d in devices
        ]
        
        return jsonify(devices_list), 200
    
    except Exception as e:
        logging.error(f"Error retrieving devices: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get overall statistics"""
    try:
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        
        # Count total events
        c.execute('SELECT COUNT(*) FROM events')
        total_events = c.fetchone()[0]
        
        # Count active devices
        c.execute("SELECT COUNT(*) FROM devices WHERE status = 'active'")
        active_devices = c.fetchone()[0]
        
        # Count attacks
        c.execute('SELECT COUNT(*) FROM attacks')
        total_attacks = c.fetchone()[0]
        
        # Get threat levels distribution
        c.execute('''SELECT threat_level, COUNT(*) FROM events 
                     GROUP BY threat_level''')
        threat_distribution = dict(c.fetchall())
        
        conn.close()
        
        stats = {
            'total_events': total_events,
            'active_devices': active_devices,
            'total_attacks': total_attacks,
            'threat_distribution': threat_distribution,
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify(stats), 200
    
    except Exception as e:
        logging.error(f"Error retrieving stats: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    }), 200

if __name__ == '__main__':
    # Initialize database
    init_db()
    
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)
