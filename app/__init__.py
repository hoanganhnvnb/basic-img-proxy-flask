import os

from dotenv import load_dotenv
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.routes import bp

load_dotenv()


def create_app():
    app = Flask(__name__)

    app.config["DEBUG"] = os.getenv("FLASK_ENV", "development") == "development"
    app.config["HOST"] = os.getenv("HOST", "127.0.0.1")
    app.config["PORT"] = int(os.getenv("PORT", "8080"))
    app.config["PROXY_TIMEOUT"] = int(os.getenv("PROXY_TIMEOUT", "20"))
    app.config["ENABLE_CACHE"] = os.getenv("ENABLE_CACHE", "false").lower() == "true"
    app.config["CACHE_DIR"] = os.getenv("CACHE_DIR", ".cache")

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    app.register_blueprint(bp)

    return app