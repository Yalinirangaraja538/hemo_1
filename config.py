import os

class Config:
    # Use environment variable for security
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default-secret-key')

    # Use environment variable for DB URI, fallback to local MySQL
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'mysql+pymysql://root:yalini@localhost/hemoglobindetect_db'
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Uploads directory
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'app', 'static', 'uploads')

    # Additional config if needed (e.g., max upload size, etc.)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
