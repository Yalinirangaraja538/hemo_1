import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from dotenv import load_dotenv

# ------------------------- Load Environment Variables -------------------------
load_dotenv()

# ------------------------- Initialize Extensions -------------------------
db = SQLAlchemy()
login_manager = LoginManager()

# ------------------------- Application Factory -------------------------
def create_app():
    """Application factory for HemoDetect Flask app."""
    app = Flask(__name__)

    # --------------------- Core Configuration ---------------------
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
        'DATABASE_URI', 
        'mysql+pymysql://root:yalini@localhost/hemoglobindetect_db'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # --------------------- Upload Folder Configuration ---------------------
    app.config['PROFILE_PHOTO_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads', 'profile_photos')
    app.config['PREDICTION_UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads', 'predictions')

    # --------------------- Ensure Upload Folders Exist ---------------------
    os.makedirs(app.config['PROFILE_PHOTO_FOLDER'], exist_ok=True)
    os.makedirs(app.config['PREDICTION_UPLOAD_FOLDER'], exist_ok=True)

    # --------------------- Initialize Extensions ---------------------
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'main_routes.login'
    login_manager.login_message_category = 'info'

    # --------------------- User Loader ---------------------
    from app.db_models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # --------------------- Register Blueprints ---------------------
    from app.main_routes import main_routes
    from app.admin_routes import admin as admin_blueprint
    from app.patient_routes import patient_routes
    from app.doctor_routes import doctor_routes

    app.register_blueprint(main_routes)
    app.register_blueprint(admin_blueprint, url_prefix='/admin')
    app.register_blueprint(patient_routes)
    app.register_blueprint(doctor_routes)

    return app
