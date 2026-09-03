"""Shared Flask extensions for the IoT Honeypot Monitoring Platform."""

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_wtf import CSRFProtect

db = SQLAlchemy()
socketio = SocketIO(cors_allowed_origins="*")
csrf = CSRFProtect()
