from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.db_models import Patient, Prediction, DoctorNote, MedicalReport, User
from app.model_inference import predict_image
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import uuid

doctor_routes = Blueprint('doctor_routes', __name__)
UPLOAD_FOLDER = 'app/static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@doctor_routes.route('/doctor/dashboard')
@login_required
def dashboard():
    if current_user.role.lower() != 'doctor':
        flash('Access Denied', 'danger')
        return redirect(url_for('main_routes.login'))

    query = Patient.query
    search_term = request.args.get('search')
    if search_term:
        query = query.filter(Patient.name.ilike(f"%{search_term}%"))

        patients = query.all()
    past_predictions = Prediction.query.order_by(Prediction.created_at.desc()).limit(10).all()
    total_cases = Prediction.query.count()

    return render_template(
        'doctor_dashboard.html',
        patients=patients,
        past_predictions=past_predictions,
        total_cases=total_cases,
        search_term=search_term or ""
    )


@doctor_routes.route('/doctor/predict', methods=['POST'])
@login_required
def predict_route():
    file = request.files.get('image')
    if not file or file.filename == '':
        flash('No image selected.', 'warning')
        return redirect(url_for('doctor_routes.dashboard'))

    filename = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4()}_{filename}"
    filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
    file.save(filepath)

    patient_name = request.form.get('patient_name')
    patient_age = request.form.get('patient_age')
    patient_gender = request.form.get('patient_gender')

    predicted_class, confidence = predict_image(filepath)

    new_prediction = Prediction(
        patient_name=patient_name,
        patient_age=patient_age,
        patient_gender=patient_gender,
        image_filename=unique_filename,
        prediction=predicted_class,
        confidence=confidence,
        created_at=datetime.utcnow()
    )
    db.session.add(new_prediction)
    db.session.commit()

    flash('Prediction completed successfully!', 'success')
    return redirect(url_for('doctor_routes.dashboard'))


@doctor_routes.route('/doctor/add_note/<int:patient_id>', methods=['POST'])
@login_required
def add_note(patient_id):
    if current_user.role.lower() != 'doctor':
        flash('Access Denied.', 'danger')
        return redirect(url_for('doctor_routes.dashboard'))

    note_text = request.form.get('note')
    new_note = DoctorNote(
        doctor_id=current_user.id,
        patient_id=patient_id,
        note=note_text,
        created_at=datetime.utcnow()
    )
    db.session.add(new_note)
    db.session.commit()
    flash('Note added successfully.', 'success')
    return redirect(url_for('doctor_routes.view_patient', patient_id=patient_id))


@doctor_routes.route('/doctor/edit_note/<int:note_id>', methods=['GET', 'POST'])
@login_required
def edit_note(note_id):
    note = DoctorNote.query.get_or_404(note_id)
    if note.doctor_id != current_user.id:
        flash("Unauthorized access.", "danger")
        return redirect(url_for('doctor_routes.dashboard'))

    if request.method == 'POST':
        note_text = request.form.get('note')
        note.note = note_text
        note.updated_at = datetime.utcnow()
        db.session.commit()
        flash("Note updated successfully.", "success")
        return redirect(url_for('doctor_routes.view_patient', patient_id=note.patient_id))

    return render_template('edit_note.html', note=note)


@doctor_routes.route('/doctor/view_patient/<int:patient_id>')
@login_required
def view_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    reports = MedicalReport.query.filter_by(patient_id=patient.id).all()
    notes = DoctorNote.query.filter_by(patient_id=patient.id).all()
    return render_template('patient_dashboard.html', patient=patient, reports=reports, notes=notes)


@doctor_routes.route('/doctor/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if current_user.role.lower() != 'doctor':
        flash('Access Denied.', 'danger')
        return redirect(url_for('main_routes.login'))

    if request.method == 'POST':
        current_user.name = request.form.get('name')
        current_user.specialty = request.form.get('specialty')
        current_user.phone = request.form.get('phone')

        if 'photo' in request.files:
            photo = request.files['photo']
            if photo.filename != '':
                filename = secure_filename(photo.filename)
                filepath = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_{filename}")
                photo.save(filepath)
                current_user.profile_photo = filepath.replace('app/', '')  # Save relative path

        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for('doctor_routes.profile'))

    return render_template('doctor_profile.html', doctor=current_user)
