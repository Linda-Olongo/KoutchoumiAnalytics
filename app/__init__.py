from flask import Flask
from .database.db_config import DatabaseConnection  
from dotenv import load_dotenv
import os

load_dotenv()

def create_app():
    """Fonction de création et configuration de l'application Flask"""
    app = Flask(__name__)
    
    # Configuration de base
    app.config.update(
        SECRET_KEY='dev',
        STATIC_FOLDER='static',
        TEMPLATE_FOLDER='templates'
    )
    
    # Initialisation de la base de données
    app.db = DatabaseConnection()
    
    # Enregistrement des routes
    from .routes import main_bp  # Notez le point avant routes
    app.register_blueprint(main_bp)
    
    return app

# Créer une instance de l'application pour Gunicorn
app = create_app()