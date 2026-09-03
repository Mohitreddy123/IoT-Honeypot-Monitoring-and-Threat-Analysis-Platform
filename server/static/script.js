// IoT Honeypot Dashboard JavaScript

// Configuration
const API_BASE = '/api';
const REFRESH_INTERVAL = 30000; // 30 seconds
let autoRefreshInterval;

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard initialized');
    updateServerTime();
    refreshDashboard();
    
    // Set up auto-refresh
    autoRefreshInterval = setInterval(refreshDashboard, REFRESH_INTERVAL);
});

// Update server time
function updateServerTime() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('en-US', { 
        hour12: false, 
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit' 
    });
    document.getElementById('server-time').textContent = timeStr;
    document.getElementById('last-update').textContent = timeStr;
}

// Refresh entire dashboard
function refreshDashboard() {
    updateServerTime();
    refreshStats();
    refreshDevices();
    refreshEvents();
}

// Refresh statistics
function refreshStats() {
    fetch(`${API_BASE}/stats`)
        .then(response => response.json())
        .then(data => {
            document.getElementById('total-events').textContent = data.total_events;
            document.getElementById('active-devices').textContent = data.active_devices;
            document.getElementById('total-attacks').textContent = data.total_attacks;
            
            // Update threat level
            let overallThreat = 'LOW';
            if (data.threat_distribution.CRITICAL > 0) {
                overallThreat = 'CRITICAL';
            } else if (data.threat_distribution.HIGH > 0) {
                overallThreat = 'HIGH';
            } else if (data.threat_distribution.MEDIUM > 0) {
                overallThreat = 'MEDIUM';
            }
            
            const threatElement = document.getElementById('threat-level');
            threatElement.textContent = overallThreat;
            threatElement.className = `stat-value threat-${overallThreat.toLowerCase()}`;
            
            // Update threat distribution chart
            const total = data.total_events || 1;
            const critical = (data.threat_distribution.CRITICAL || 0) * 100 / total;
            const high = (data.threat_distribution.HIGH || 0) * 100 / total;
            const medium = (data.threat_distribution.MEDIUM || 0) * 100 / total;
            const low = (data.threat_distribution.LOW || 0) * 100 / total;
            
            document.getElementById('threat-critical').style.width = critical + '%';
            document.getElementById('threat-high').style.width = high + '%';
            document.getElementById('threat-medium').style.width = medium + '%';
            document.getElementById('threat-low').style.width = low + '%';
            
            // Update status indicator
            const statusIndicator = document.getElementById('server-status');
            if (overallThreat === 'CRITICAL') {
                statusIndicator.style.color = '#e74c3c';
            } else if (overallThreat === 'HIGH') {
                statusIndicator.style.color = '#f39c12';
            } else {
                statusIndicator.style.color = '#2ecc71';
            }
        })
        .catch(error => {
            console.error('Error fetching stats:', error);
            updateServerStatus(false);
        });
}

// Refresh devices list
function refreshDevices() {
    fetch(`${API_BASE}/devices`)
        .then(response => response.json())
        .then(devices => {
            const tbody = document.getElementById('devices-tbody');
            
            if (devices.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No devices connected</td></tr>';
                return;
            }
            
            tbody.innerHTML = devices.map(device => {
                const status = device.status === 'active' ? '🟢 Active' : '🔴 Inactive';
                return `
                    <tr>
                        <td><code>${device.device_id}</code></td>
                        <td>${device.ip_address || 'N/A'}</td>
                        <td>${status}</td>
                        <td>${formatTime(device.first_seen)}</td>
                        <td>${formatTime(device.last_seen)}</td>
                    </tr>
                `;
            }).join('');
        })
        .catch(error => {
            console.error('Error fetching devices:', error);
            document.getElementById('devices-tbody').innerHTML = 
                '<tr><td colspan="5" class="empty-state error">Error loading devices</td></tr>';
        });
}

// Refresh events list
function refreshEvents() {
    const filter = document.getElementById('event-filter').value;
    const url = filter ? `${API_BASE}/events?limit=50&type=${filter}` : `${API_BASE}/events?limit=50`;
    
    fetch(url)
        .then(response => response.json())
        .then(events => {
            const tbody = document.getElementById('events-tbody');
            
            if (events.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No events</td></tr>';
                return;
            }
            
            tbody.innerHTML = events.map(event => {
                const threatClass = `threat-${event.threat_level.toLowerCase()}`;
                return `
                    <tr>
                        <td>${formatTime(event.timestamp)}</td>
                        <td><code>${event.device_id}</code></td>
                        <td>${event.event_type}</td>
                        <td>${event.source_ip}</td>
                        <td class="${threatClass}"><strong>${event.threat_level}</strong></td>
                        <td>
                            <button class="detail-btn" onclick="showEventDetail('${JSON.stringify(event).replace(/'/g, "&#39;")}')">
                                View
                            </button>
                        </td>
                    </tr>
                `;
            }).join('');
        })
        .catch(error => {
            console.error('Error fetching events:', error);
            document.getElementById('events-tbody').innerHTML = 
                '<tr><td colspan="6" class="empty-state error">Error loading events</td></tr>';
        });
}

// Filter events by type
function filterEvents(type) {
    refreshEvents();
}

// Format timestamp to readable format
function formatTime(timestamp) {
    if (!timestamp) return 'N/A';
    try {
        const date = new Date(timestamp);
        return date.toLocaleTimeString('en-US', { 
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    } catch (e) {
        return timestamp;
    }
}

// Show event details in modal
function showEventDetail(eventJson) {
    try {
        const event = JSON.parse(eventJson.replace(/&#39;/g, "'"));
        const modal = document.getElementById('detail-modal');
        const content = document.getElementById('detail-content');
        
        content.textContent = JSON.stringify(event, null, 2);
        modal.style.display = 'block';
    } catch (error) {
        console.error('Error parsing event:', error);
        alert('Error displaying event details');
    }
}

// Close modal
function closeModal() {
    document.getElementById('detail-modal').style.display = 'none';
}

// Close modal when clicking outside of it
window.onclick = function(event) {
    const modal = document.getElementById('detail-modal');
    if (event.target === modal) {
        modal.style.display = 'none';
    }
}

// Manual refresh buttons
function refreshDevices() {
    console.log('Manually refreshing devices...');
    const btn = event.target;
    btn.style.opacity = '0.5';
    
    fetch(`${API_BASE}/devices`)
        .then(response => response.json())
        .then(devices => {
            const tbody = document.getElementById('devices-tbody');
            
            if (devices.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No devices connected</td></tr>';
                return;
            }
            
            tbody.innerHTML = devices.map(device => {
                const status = device.status === 'active' ? '🟢 Active' : '🔴 Inactive';
                return `
                    <tr>
                        <td><code>${device.device_id}</code></td>
                        <td>${device.ip_address || 'N/A'}</td>
                        <td>${status}</td>
                        <td>${formatTime(device.first_seen)}</td>
                        <td>${formatTime(device.last_seen)}</td>
                    </tr>
                `;
            }).join('');
            
            btn.style.opacity = '1';
        })
        .catch(error => {
            console.error('Error fetching devices:', error);
            btn.style.opacity = '1';
        });
}

function refreshEvents() {
    console.log('Manually refreshing events...');
    const btn = event.target;
    btn.style.opacity = '0.5';
    
    const filter = document.getElementById('event-filter').value;
    const url = filter ? `${API_BASE}/events?limit=50&type=${filter}` : `${API_BASE}/events?limit=50`;
    
    fetch(url)
        .then(response => response.json())
        .then(events => {
            const tbody = document.getElementById('events-tbody');
            
            if (events.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No events</td></tr>';
                return;
            }
            
            tbody.innerHTML = events.map(event => {
                const threatClass = `threat-${event.threat_level.toLowerCase()}`;
                return `
                    <tr>
                        <td>${formatTime(event.timestamp)}</td>
                        <td><code>${event.device_id}</code></td>
                        <td>${event.event_type}</td>
                        <td>${event.source_ip}</td>
                        <td class="${threatClass}"><strong>${event.threat_level}</strong></td>
                        <td>
                            <button class="detail-btn" onclick="showEventDetail('${JSON.stringify(event).replace(/'/g, "&#39;")}')">
                                View
                            </button>
                        </td>
                    </tr>
                `;
            }).join('');
            
            btn.style.opacity = '1';
        })
        .catch(error => {
            console.error('Error fetching events:', error);
            btn.style.opacity = '1';
        });
}

// Update server status
function updateServerStatus(isHealthy) {
    const statusIndicator = document.getElementById('server-status');
    if (isHealthy) {
        statusIndicator.style.color = '#2ecc71';
    } else {
        statusIndicator.style.color = '#e74c3c';
    }
}

// Log to console
console.log('IoT Honeypot Dashboard v1.0 loaded');
