# ============================================================
# GITORA APPLICATION INITIALIZATION
# ============================================================

import os

from flask import Flask

from dotenv import load_dotenv

load_dotenv()

from app.models import db


# ============================================================
# CREATE APPLICATION
# ============================================================

def create_app():

    app = Flask(__name__)

    # --------------------------------------------------------
    # SECRET KEY
    # --------------------------------------------------------

    app.config["SECRET_KEY"] = os.getenv(
        "SECRET_KEY",
        "gitora-development-secret"
    )

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    database_url = os.getenv(
        "DATABASE_URL"
    )

    if database_url:

        # Render/Postgres URLs sometimes begin with
        # postgres://. SQLAlchemy expects postgresql://.

        if database_url.startswith(
            "postgres://"
        ):

            database_url = (
                database_url.replace(
                    "postgres://",
                    "postgresql://",
                    1
                )
            )

        app.config[
            "SQLALCHEMY_DATABASE_URI"
        ] = database_url

    else:

        app.config[
            "SQLALCHEMY_DATABASE_URI"
        ] = "sqlite:///gitora.db"

    app.config[
        "SQLALCHEMY_TRACK_MODIFICATIONS"
    ] = False

    # --------------------------------------------------------
    # DATABASE INITIALIZATION
    # --------------------------------------------------------

    db.init_app(app)

    # --------------------------------------------------------
    # ROUTES
    # --------------------------------------------------------

    from app.routes import main

    app.register_blueprint(
        main
    )

    # --------------------------------------------------------
    # CREATE TABLES
    # --------------------------------------------------------

    with app.app_context():

        db.create_all()

    return app


# ============================================================
# APPLICATION INSTANCE
# ============================================================

app = create_app()