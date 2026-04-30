"""
InduSafe Sentinel - Flask Application
"""
from flask import Flask
from .models import Database
from .routes import main_bp
import os

def create_app(config_class='config.Config'):
    # Get the base directory (parent of app folder)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    app = Flask(__name__, 
                template_folder=os.path.join(base_dir, 'templates'),
                static_folder=os.path.join(base_dir, 'static'))
    app.config.from_object(config_class)
    
    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.dirname(app.config['DATABASE_PATH']), exist_ok=True)
    
    # Initialize database
    db = Database(app.config['DATABASE_PATH'])
    db.init_db()
    
    # Register blueprints
    app.register_blueprint(main_bp)
    
    return app
