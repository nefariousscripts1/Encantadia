"""Flask application factory."""

from flask import Flask


def create_app():
    """Create and configure the Flask application."""

    app = Flask(__name__)

    from .routes import main
    from .text_routes import text_api

    app.register_blueprint(main)
    app.register_blueprint(text_api)
    return app
