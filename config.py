"""
InduSafe Sentinel - Configuration
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'indusafe-sentinel-secret-key-2024'
    
    # Database
    DATABASE_PATH = os.path.join(BASE_DIR, 'database', 'indusafe.db')
    
    # Uploads
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Camera
    CAMERA_INDEX = 0  # Default webcam
    CAMERA_WIDTH = 640
    CAMERA_HEIGHT = 480
    CAMERA_FPS = 30
    
    # Detection
    DETECTION_CONFIDENCE = 0.5
    VIOLATION_THRESHOLD = 1  # Alert on first detection (more responsive)
    VIOLATION_COOLDOWN = 2  # Seconds between database saves
    
    # Evidence
    IMAGE_CAPTURE_THRESHOLD = 1  # Capture image on every violation
    EVIDENCE_VIDEO_DURATION = 0  # 0 = disable video capture
    
    # Alerts
    VOICE_ALERT_ENABLED = True
    VOICE_ALERT_VOLUME = 0.9
    VOICE_ALERT_RATE = 150  # Words per minute
    
    # Zones
    DEFAULT_ZONE = "Main Floor"
    
    # Email Configuration (Edit these for permanent settings)
    SUPERVISOR_EMAIL = "22q71a05g6@gmail.com"  # Change this to your email
    SMTP_USERNAME = "22q71a05g6@gmail.com"  # Leave empty to use environment variable
    SMTP_PASSWORD = "wkmn esyu cltc ulga"  # Leave empty to use environment variable
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
