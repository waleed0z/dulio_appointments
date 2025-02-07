from flask_migrate import Migrate
from app import db  # Assuming your SQLAlchemy instance is named 'db'

migrate = Migrate(app, db)