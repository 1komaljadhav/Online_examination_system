from flask import Flask
from .main import main
from .auth import auth

def create_app():
    app = Flask(__name__)

    # Register Blueprints
    app.register_blueprint(main)
    app.register_blueprint(auth, url_prefix='/auth')

    return app
