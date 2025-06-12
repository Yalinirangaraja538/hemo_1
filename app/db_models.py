from app import db
from flask_login import UserMixin
from datetime import datetime
import pyotp


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100))
      # Added this line
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    profile_photo = db.Column(db.String(255), default='default.jpg')

    _is_active = db.Column('is_active', db.Boolean, default=True)
    is_approved = db.Column(db.Boolean, default=True)

    two_factor_enabled = db.Column(db.Boolean, default=False)
    two_factor_secret = db.Column(db.String(32), nullable=True)

    @property
    def is_active(self):
        return self._is_active

    @is_active.setter
    def is_active(self, value):
        self._is_active = value

    def generate_2fa_secret(self):
        self.two_factor_secret = pyotp.random_base32()

    def get_totp_uri(self):
        return f"otpauth://totp/HemoDetect:{self.username}?secret={self.two_factor_secret}&issuer=HemoDetect"

    def verify_2fa_token(self, token):
        if not self.two_factor_secret:
            return False
        totp = pyotp.TOTP(self.two_factor_secret)
        return totp.verify(token)

    # Relationships
    patient = db.relationship('Patient', back_populates='user', uselist=False)
    doctor_notes_written = db.relationship('DoctorNote', back_populates='author', foreign_keys='DoctorNote.doctor_id')
    predictions = db.relationship('Prediction', back_populates='user', foreign_keys='Prediction.user_id')


class Patient(db.Model):
    __tablename__ = 'patients'

    id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    name = db.Column(db.String(100))
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    dob = db.Column(db.Date)
    medical_history = db.Column(db.Text)
    address = db.Column(db.String(255))
    country = db.Column(db.String(100))
    city = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    

    # Relationships
    user = db.relationship('User', back_populates='patient', uselist=False)
    reports = db.relationship('MedicalReport', backref='patient', lazy=True)
    notes = db.relationship('DoctorNote', back_populates='patient_user', lazy=True)
    predictions = db.relationship('Prediction', back_populates='patient', lazy=True)


class MedicalReport(db.Model):
    __tablename__ = 'medical_reports'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    prediction = db.Column(db.String(100))
    confidence = db.Column(db.Float)
    result = db.Column(db.String(255))
    image_path = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    image_filename = db.Column(db.String(200))
    

class DoctorNote(db.Model):
    __tablename__ = 'doctor_notes'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    note = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    author = db.relationship('User', back_populates='doctor_notes_written', foreign_keys=[doctor_id])
    patient_user = db.relationship('Patient', back_populates='notes', foreign_keys=[patient_id])


class Prediction(db.Model):
    __tablename__ = 'predictions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    prediction_result = db.Column(db.String(100), nullable=False)
    confidence_score = db.Column(db.Float)
    image_filename = db.Column(db.String(150))
    image_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    result = db.Column(db.String(100))  #

    # Relationships
    user = db.relationship('User', back_populates='predictions')
    patient = db.relationship('Patient', back_populates='predictions')


class Log(db.Model):
    __tablename__ = 'logs'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    level = db.Column(db.String(20), nullable=False)
    message = db.Column(db.String(255), nullable=False)


class SecuritySettings(db.Model):
    __tablename__ = 'security_settings'

    id = db.Column(db.Integer, primary_key=True)
    min_length = db.Column(db.Integer, default=8)
    require_upper = db.Column(db.Boolean, default=True)
    require_lower = db.Column(db.Boolean, default=True)
    require_number = db.Column(db.Boolean, default=True)
    expiration_days = db.Column(db.Integer, default=90)
    enforced = db.Column(db.Boolean, default=False)


class PasswordPolicy(db.Model):
    __tablename__ = 'password_policies'

    id = db.Column(db.Integer, primary_key=True)
    min_length = db.Column(db.Integer, nullable=False, default=8)
    require_uppercase = db.Column(db.Boolean, default=True)
    require_lowercase = db.Column(db.Boolean, default=True)
    require_number = db.Column(db.Boolean, default=True)
    enforce_expiry = db.Column(db.Boolean, default=False)
    expiry_days = db.Column(db.Integer, nullable=True)
