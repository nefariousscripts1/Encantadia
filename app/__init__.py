"""Flask application factory."""

from flask import Flask


def create_app():
    """Create and configure the Flask application."""

    app = Flask(__name__)

    from .routes import main

    app.register_blueprint(main)
    return app
