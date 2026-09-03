#!/usr/bin/env python3
"""
Utility functions for IoT Honeypot
"""

import json
import logging
from datetime import datetime

def log_event(event_type, device_id, timestamp, data, source_ip):
    """
    Log an event to the cowrie logs file
    
    Args:
        event_type (str): Type of event (telemetry, attack, etc.)
        device_id (str): ID of the device
        timestamp (str): Event timestamp
        data (dict): Event data
        source_ip (str): Source IP address
    """
    try:
        log_entry = {
            'event_type': event_type,
            'device_id': device_id,
            'timestamp': timestamp,
            'source_ip': source_ip,
            'data': data
        }
        
        with open('logs/cowrie_logs.json', 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
        
        logging.info(f"Event logged: {event_type} from {device_id}")
    
    except Exception as e:
        logging.error(f"Error logging event: {str(e)}")

def get_threat_level(data):
    """
    Analyze data and determine threat level
    
    Args:
        data (dict): Event data to analyze
        
    Returns:
        str: Threat level (LOW, MEDIUM, HIGH, CRITICAL)
    """
    threat_level = "LOW"
    
    # Check for suspicious patterns
    if isinstance(data, dict):
        # Check temperature anomalies
        if 'temperature' in data:
            temp = data['temperature']
            if temp > 60 or temp < -40:
                threat_level = "MEDIUM"
        
        # Check for unusual signal strength
        if 'signal_strength' in data:
            signal = data['signal_strength']
            if signal < -80:
                threat_level = "MEDIUM"
        
        # Check for motion detection patterns
        if 'motion_detected' in data and data['motion_detected']:
            threat_level = "HIGH"
        
        # Check for rapid state changes
        if 'uptime' in data and data['uptime'] < 300:
            threat_level = "HIGH"
    
    return threat_level

def analyze_pattern(events, window_size=10):
    """
    Analyze event patterns to detect anomalies
    
    Args:
        events (list): List of events to analyze
        window_size (int): Size of the analysis window
        
    Returns:
        dict: Analysis results
    """
    analysis = {
        'total_events': len(events),
        'event_frequency': 0,
        'anomalies_detected': 0,
        'recommended_action': 'MONITOR'
    }
    
    if len(events) < 2:
        return analysis
    
    # Calculate event frequency
    time_diffs = []
    for i in range(1, min(len(events), window_size)):
        # Parse timestamps and calculate differences
        try:
            t1 = datetime.fromisoformat(events[i-1].get('timestamp', ''))
            t2 = datetime.fromisoformat(events[i].get('timestamp', ''))
            diff = (t2 - t1).total_seconds()
            time_diffs.append(diff)
        except:
            pass
    
    if time_diffs:
        analysis['event_frequency'] = len(time_diffs) / sum(time_diffs) if sum(time_diffs) > 0 else 0
    
    # Detect anomalies
    high_threat_count = sum(1 for e in events if e.get('threat_level') == 'HIGH')
    critical_threat_count = sum(1 for e in events if e.get('threat_level') == 'CRITICAL')
    
    analysis['anomalies_detected'] = high_threat_count + critical_threat_count
    
    if critical_threat_count > 0:
        analysis['recommended_action'] = 'ISOLATE'
    elif high_threat_count > 3:
        analysis['recommended_action'] = 'INVESTIGATE'
    elif high_threat_count > 0:
        analysis['recommended_action'] = 'MONITOR_CLOSELY'
    
    return analysis

def parse_cowrie_log(log_file):
    """
    Parse cowrie log file
    
    Args:
        log_file (str): Path to cowrie log file
        
    Returns:
        list: Parsed log entries
    """
    entries = []
    try:
        with open(log_file, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    entries.append(entry)
                except json.JSONDecodeError:
                    logging.warning(f"Could not parse log line: {line}")
    except FileNotFoundError:
        logging.error(f"Log file not found: {log_file}")
    
    return entries

def get_device_summary(device_id, events):
    """
    Generate a summary for a specific device
    
    Args:
        device_id (str): Device ID
        events (list): List of events for the device
        
    Returns:
        dict: Device summary
    """
    summary = {
        'device_id': device_id,
        'total_events': len(events),
        'last_event': None,
        'threat_count': 0,
        'avg_temp': 0,
        'status': 'UNKNOWN'
    }
    
    if not events:
        return summary
    
    summary['last_event'] = events[0].get('timestamp', None)
    summary['threat_count'] = sum(1 for e in events if e.get('threat_level') in ['HIGH', 'CRITICAL'])
    
    # Calculate average temperature
    temps = []
    for event in events:
        if 'data' in event and 'temperature' in event['data']:
            temps.append(event['data']['temperature'])
    
    if temps:
        summary['avg_temp'] = sum(temps) / len(temps)
    
    # Determine status
    if summary['threat_count'] > 0:
        summary['status'] = 'SUSPICIOUS'
    else:
        summary['status'] = 'NORMAL'
    
    return summary

def export_report(events, output_file):
    """
    Export events as a JSON report
    
    Args:
        events (list): List of events to export
        output_file (str): Output file path
        
    Returns:
        bool: Success status
    """
    try:
        report = {
            'generated': datetime.now().isoformat(),
            'total_events': len(events),
            'events': events
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logging.info(f"Report exported to {output_file}")
        return True
    
    except Exception as e:
        logging.error(f"Error exporting report: {str(e)}")
        return False
