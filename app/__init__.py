from flask import Flask

from app.config import Config
from app.db import init_app as init_db
from app.routes import main_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    init_db(app)
    app.register_blueprint(main_bp)

    return app
