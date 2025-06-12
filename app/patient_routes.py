import os
import uuid
from io import BytesIO
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.db_models import Patient, MedicalReport
import zipfile

# ----------------------------- Configuration -----------------------------
patient_routes = Blueprint('patient_routes', __name__)
UPLOAD_FOLDER = 'app/static/uploads/predictions'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ----------------------------- Dashboard Route -----------------------------
@patient_routes.route('/patient/dashboard', methods=['GET'])
@login_required
def dashboard():
    if current_user.role.lower() != 'patient':
        flash('Access Denied', 'danger')
        return redirect(url_for('main_routes.login'))

    patient = Patient.query.get(current_user.id)
    if not patient:
        flash("Patient profile not found.", "danger")
        return redirect(url_for('main_routes.login'))

    reports = MedicalReport.query.filter_by(patient_id=patient.id).order_by(MedicalReport.timestamp.desc()).all()
    return render_template('patient_dashboard.html', patient=patient, reports=reports)

# ----------------------------- Prediction Upload Route -----------------------------
@patient_routes.route('/patient/predict', methods=['POST'])
@login_required
def predict():
    if current_user.role.lower() != 'patient':
        flash('Access Denied.', 'danger')
        return redirect(url_for('patient_routes.dashboard'))

    file = request.files.get('image')
    if not file or file.filename == '':
        flash('No image selected.', 'warning')
        return redirect(url_for('patient_routes.dashboard'))

    filename = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4()}_{filename}"
    filepath = os.path.join(UPLOAD_FOLDER, unique_filename)

    try:
        file.save(filepath)
        from app.predictor import predict_image
        predicted_class, confidence = predict_image(filepath)
    except Exception as e:
        flash(f'Prediction failed: {e}', 'danger')
        return redirect(url_for('patient_routes.dashboard'))

    patient = Patient.query.get(current_user.id)
    if not patient:
        patient = Patient(
            id=current_user.id,
            name=current_user.name,
            age=0,
            gender=None,
            dob=None,
            medical_history=None,
            address=None,
            country=None,
            city=None,
            phone=None,
            created_at=datetime.utcnow()
        )
        db.session.add(patient)
        db.session.commit()

    report = MedicalReport(
        patient_id=patient.id,
        result=predicted_class,
        confidence=confidence,
        image_filename=unique_filename,
        timestamp=datetime.utcnow()
    )
    db.session.add(report)
    db.session.commit()

    return redirect(url_for('patient_routes.results', report_id=report.id))

# ----------------------------- Results Page -----------------------------
@patient_routes.route('/results/<int:report_id>')
@login_required
def results(report_id):
    report = MedicalReport.query.get_or_404(report_id)
    patient = Patient.query.filter_by(id=current_user.id).first()

    confidence = round(report.confidence * 100, 2) if report.confidence else None
    prediction_result = "Positive" if report.confidence >= 0.5 else "Negative"
    image_url = url_for('static', filename='uploads/predictions/' + report.image_filename) if report.image_filename else None

    reports = MedicalReport.query.filter_by(patient_id=current_user.id).order_by(MedicalReport.timestamp.desc()).all()

    return render_template(
        'patient_results.html',
        report=report,
        patient=patient,
        reports=reports,
        prediction_result=prediction_result,
        confidence=confidence,
        image_url=image_url
    )

# ----------------------------- Report Download Route -----------------------------
@patient_routes.route('/patient/download_report/<int:report_id>', methods=['GET'])
@login_required
def download_report(report_id):
    report = MedicalReport.query.get_or_404(report_id)
    patient = Patient.query.get(current_user.id)

    if not patient or report.patient_id != patient.id:
        flash("Unauthorized access or profile not found.", "danger")
        return redirect(url_for('patient_routes.dashboard'))

    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    p = canvas.Canvas(buffer)
    p.setFont("Helvetica", 12)

    p.drawString(100, 800, "HemoDetect - Diagnosis Report")
    p.line(100, 795, 500, 795)
    p.drawString(100, 760, f"Patient Name: {patient.name}")
    p.drawString(100, 740, f"Age: {patient.age}")
    p.drawString(100, 720, f"Gender: {patient.gender}")
    p.drawString(100, 700, f"Diagnosis: {report.result}")
    p.drawString(100, 680, f"Confidence: {round(report.confidence * 100, 2)}%")
    p.drawString(100, 640, f"Date: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    p.drawString(100, 600, "Generated by HemoDetect AI System")

    p.showPage()
    p.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"Diagnosis_Report_{report.id}.pdf",
        mimetype='application/pdf'
    )

# ----------------------------- AI Chatbot Route -----------------------------
@patient_routes.route('/chatbot', methods=['POST'])
@login_required
def chatbot():
    data = request.get_json()
    user_message = data.get("message", "").lower()

    suggestions = [
        "What is hemoglobin?",
        "How do I upload a report?",
        "Tell me about leukemia",
        "What is a normal hemoglobin level?",
        "Can I download my report?",
        "How secure is my data?"
    ]

    if "hemoglobin" in user_message:
        bot_response = "Hemoglobin is a protein in red blood cells responsible for carrying oxygen to your tissues."

    elif "upload" in user_message or "report" in user_message:
        bot_response = "Go to your dashboard and click on 'Upload Image' to submit a blood sample for analysis."
    
    elif "Hi" in user_message or "Hello" in user_message:
        bot_response = "hi! i am happy assist you today."

    elif "leukemia" in user_message:
        bot_response = "Leukemia is a type of blood cancer caused by the rapid production of abnormal white blood cells."

    elif "help" in user_message:
        bot_response = "I can help with questions about reports, uploading images, hemoglobin, leukemia, and using the HemoDetect platform."

    elif "normal range" in user_message or "hemoglobin level" in user_message:
        bot_response = "Typical hemoglobin levels are: Men: 13.8–17.2 g/dL, Women: 12.1–15.1 g/dL, Children: 11–16 g/dL."

    elif "doctor" in user_message:
        bot_response = "Doctors will review your reports and can leave notes. You can read their feedback under each report."

    elif "prediction" in user_message or "ai result" in user_message:
        bot_response = "Once your image is uploaded, our AI model analyzes it and provides a diagnosis report based on blood cell patterns."

    elif "pdf" in user_message or "download" in user_message:
        bot_response = "Each completed report has a 'Download PDF' option so you can save or print your results."

    elif "dashboard" in user_message:
        bot_response = "Your dashboard shows your latest reports, doctor notes, and allows uploading new images for analysis."

    elif "secure" in user_message or "privacy" in user_message:
        bot_response = "Your data is securely stored and encrypted. Only authorized doctors and you can view your reports."

    else:
        bot_response = "I'm here to assist you with using the platform. You can ask about hemoglobin, leukemia, or uploading images."

    return jsonify({
        "response": bot_response,
        "suggestions": suggestions
    })
# ----------------------------- Download All Reports as ZIP -----------------------------
@patient_routes.route('/download_all')
@login_required
def download_all():
    user_id = str(current_user.id)
    report_folder = os.path.join(current_app.root_path, 'static', 'reports', user_id)

    if not os.path.exists(report_folder):
        return "No reports found.", 404

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
        for filename in os.listdir(report_folder):
            if filename.endswith('.pdf'):
                file_path = os.path.join(report_folder, filename)
                zip_file.write(file_path, arcname=filename)
    zip_buffer.seek(0)

    return send_file(
        zip_buffer,
        as_attachment=True,
        download_name=f'{user_id}_reports.zip',
        mimetype='application/zip'
    )
