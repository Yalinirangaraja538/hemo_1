from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from app import db
from app.db_models import User, Patient, MedicalReport, DoctorNote
from datetime import datetime
import os

main_routes = Blueprint('main_routes', __name__)

UPLOAD_FOLDER = os.path.join('app', 'static', 'uploads')
PROFILE_PHOTO_FOLDER = os.path.join(UPLOAD_FOLDER, 'profile_photos')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
os.makedirs(PROFILE_PHOTO_FOLDER, exist_ok=True)


# === Utility Functions ===

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_profile_photo(file, username):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        photo_filename = f"{username}_{timestamp}_{filename}"
        file.save(os.path.join(PROFILE_PHOTO_FOLDER, photo_filename))
        return photo_filename
    return None

def get_dashboard_redirect_for(user):
    return url_for(f'main_routes.{user.role}_dashboard')


# === Routes ===

@main_routes.route('/')
def home():
    return render_template('home.html')


@main_routes.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('user_id')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            if user.role == 'doctor' and not user.is_approved:
                flash('Your doctor account is pending admin approval.', 'warning')
                return redirect(url_for('main_routes.login'))

            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(get_dashboard_redirect_for(user))

        flash('Invalid credentials.', 'danger')

    return render_template('login.html')


@main_routes.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('main_routes.login'))


@main_routes.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role').lower()

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for('main_routes.register'))

        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
            return redirect(url_for('main_routes.register'))

        # Common fields
        name = request.form.get('name')
        email = request.form.get('email')
        profile_photo = request.files.get('profile_photo')
        photo_filename = save_profile_photo(profile_photo, username)

        # Create user
        hashed_password = generate_password_hash(password)
        new_user = User(
            username=username,
            password=hashed_password,
            role=role,
            name=name,
            email=email,
            profile_photo=photo_filename,
            is_approved=(role != 'doctor')
        )
        db.session.add(new_user)
        db.session.flush()
        db.session.refresh(new_user)  # <-- Ensures new_user.id is populated

        if role == 'patient':
            patient = Patient(
                id=new_user.id,
                name=name,
                age=int(request.form.get('age') or 0),
                gender=request.form.get('gender'),
                dob=datetime.strptime(request.form.get('dob'), '%Y-%m-%d') if request.form.get('dob') else None,
                medical_history=request.form.get('medical_history'),
                address=request.form.get('address'),
                country=request.form.get('country'),
                city=request.form.get('city'),
                phone=request.form.get('phone'),
                created_at=datetime.utcnow()
            )
            db.session.add(patient)

        db.session.commit()

        if role == 'doctor':
            flash('Doctor registered. Awaiting admin approval.', 'info')
            return redirect(url_for('main_routes.login'))

        login_user(new_user)
        flash('Registration successful.', 'success')
        return redirect(get_dashboard_redirect_for(new_user))

    return render_template('register.html')


@main_routes.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        new_password = request.form.get('password')
        profile_photo = request.files.get('profile_photo')

        if name:
            current_user.name = name
        if email:
            current_user.email = email
        if new_password:
            current_user.password = generate_password_hash(new_password)
        if profile_photo:
            filename = save_profile_photo(profile_photo, current_user.username)
            if filename:
                current_user.profile_photo = filename

        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(get_dashboard_redirect_for(current_user))

    return render_template('profile.html', user=current_user)


@main_routes.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main_routes.logout'))

    pending_doctors = User.query.filter_by(role='doctor', is_approved=False).all()
    return render_template('admin_dashboard.html', user=current_user, pending_doctors=pending_doctors)


@main_routes.route('/doctor/dashboard')
@login_required
def doctor_dashboard():
    if current_user.role != 'doctor':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main_routes.logout'))

    patients = Patient.query.all()
    return render_template('doctor_dashboard.html', user=current_user, patients=patients)


@main_routes.route('/patient/dashboard')
@login_required
def patient_dashboard():
    if current_user.role != 'patient':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main_routes.logout'))

    patient = Patient.query.get(current_user.id)
    reports = MedicalReport.query.filter_by(patient_id=current_user.id).order_by(MedicalReport.timestamp.desc()).all()
    notes = DoctorNote.query.filter_by(patient_id=current_user.id).all()

    return render_template('patient_dashboard.html', user=current_user, patient=patient, reports=reports, notes=notes)


@main_routes.route('/admin/approve_doctor/<int:doctor_id>')
@login_required
def approve_doctor(doctor_id):
    if current_user.role != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('main_routes.logout'))

    doctor = User.query.get_or_404(doctor_id)
    if doctor.role == 'doctor':
        doctor.is_approved = True
        db.session.commit()
        flash('Doctor approved.', 'success')
    else:
        flash('Invalid doctor record.', 'danger')

    return redirect(url_for('main_routes.admin_dashboard'))


@main_routes.route('/admin/reject_doctor/<int:doctor_id>')
@login_required
def reject_doctor(doctor_id):
    if current_user.role != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('main_routes.logout'))

    doctor = User.query.get_or_404(doctor_id)
    if doctor.role == 'doctor' and not doctor.is_approved:
        db.session.delete(doctor)
        db.session.commit()
        flash('Doctor rejected and removed.', 'info')
    else:
        flash('Invalid or already approved doctor.', 'danger')

    return redirect(url_for('main_routes.admin_dashboard'))
