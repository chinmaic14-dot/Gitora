from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class SavedFileSelection(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    repository = db.Column(
        db.String(300),
        nullable=False
    )

    file_path = db.Column(
        db.String(500),
        nullable=False
    )