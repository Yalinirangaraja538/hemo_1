from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import extract, func
from app import db
from app.db_models import User, Patient, MedicalReport, Prediction, Log
import os

admin = Blueprint('admin', __name__)

ALLOWED_MODEL_EXT = {'h5', 'pt', 'pkl'}
ALLOWED_DATASET_EXT = {'csv', 'xlsx', 'xls'}

# ========== Utility Functions ==========

def is_admin():
    return current_user.is_authenticated and current_user.role and current_user.role.lower() == 'admin'

def log_event(level, message):
    log = Log(level=level, message=message)
    db.session.add(log)
    db.session.commit()

def get_user_growth_data():
    data = db.session.query(
        extract('month', User.created_at).label('month'),
        func.count(User.id).label('count')
    ).group_by('month').order_by('month').all()
    months = [int(row.month) for row in data]
    counts = [row.count for row in data]
    return months, counts

def get_prediction_trends():
    data = db.session.query(
        extract('month', Prediction.created_at).label('month'),
        Prediction.result,
        func.count(Prediction.id)
    ).group_by('month', Prediction.result).order_by('month').all()

    trend_months = sorted(list(set(row[0] for row in data)))
    leukemia_counts = []
    healthy_counts = []

    for month in trend_months:
        leukemia = next((count for m, result, count in data if m == month and result == 'Leukemia'), 0)
        healthy = next((count for m, result, count in data if m == month and result == 'Healthy'), 0)
        leukemia_counts.append(leukemia)
        healthy_counts.append(healthy)

    return trend_months, leukemia_counts, healthy_counts

# ========== Admin Dashboard ==========

@admin.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not is_admin():
        flash('Access Denied. Admins only.', 'danger')
        return redirect(url_for('main_routes.logout'))

    total_users = User.query.count()
    total_patients = Patient.query.count()
    total_doctors = User.query.filter_by(role='doctor').count()
    total_reports = MedicalReport.query.count()
    total_predictions = Prediction.query.count()

    users_per_month, counts = get_user_growth_data()
    pred_months, pred_counts = zip(*db.session.query(
        extract('month', Prediction.created_at),
        func.count(Prediction.id)
    ).group_by(extract('month', Prediction.created_at)).all() or [])

    log_event("INFO", f"Admin '{current_user.email}' viewed dashboard.")
    return render_template('admin_dashboard.html',
                           total_users=total_users,
                           total_patients=total_patients,
                           total_doctors=total_doctors,
                           total_reports=total_reports,
                           total_predictions=total_predictions,
                           months=users_per_month,
                           counts=counts,
                           prediction_months=pred_months,
                           prediction_counts=pred_counts)

# ========== User Management ==========

@admin.route('/admin/manage_users')
@login_required
def manage_users():
    if not is_admin():
        flash('Access Denied.', 'danger')
        return redirect(url_for('main_routes.logout'))

    search = request.args.get('search', '')
    role_filter = request.args.get('role', None)

    query = User.query
    if search:
        query = query.filter(User.email.ilike(f'%{search}%'))
    if role_filter:
        query = query.filter_by(role=role_filter)

    users = query.order_by(User.created_at.desc()).all()
    log_event("INFO", f"Admin '{current_user.email}' accessed user management.")
    return render_template('admin_manage_users.html', users=users)

@admin.route('/admin/update_role', methods=['POST'])
@login_required
def update_role():
    if not is_admin():
        flash('Access Denied.', 'danger')
        return redirect(url_for('main_routes.logout'))

    user_id = request.form.get('user_id')
    new_role = request.form.get('new_role')
    user = User.query.get(user_id)

    if user:
        old_role = user.role
        user.role = new_role
        db.session.commit()
        flash('User role updated successfully!', 'success')
        log_event("INFO", f"Role for user {user.email} changed from {old_role} to {new_role} by admin {current_user.email}.")
    else:
        flash('User not found.', 'danger')
        log_event("WARNING", f"Attempted role update for non-existent user ID {user_id}.")

    return redirect(url_for('admin.manage_users'))

@admin.route('/admin/delete_user/<int:user_id>')
@login_required
def delete_user(user_id):
    if not is_admin():
        flash('Access Denied.', 'danger')
        return redirect(url_for('main_routes.logout'))

    user = User.query.get(user_id)
    if user:
        email = user.email
        if user.role == 'patient':
            Patient.query.filter_by(id=user.id).delete()
            MedicalReport.query.filter_by(patient_id=user.id).delete()
            Prediction.query.filter_by(patient_id=user.id).delete()

        db.session.delete(user)
        db.session.commit()
        flash('User deleted successfully.', 'success')
        log_event("WARNING", f"Admin {current_user.email} deleted user {email}.")
    else:
        flash('User not found.', 'danger')
        log_event("WARNING", f"Attempted deletion of non-existent user ID {user_id}.")

    return redirect(url_for('admin.manage_users'))

@admin.route('/admin/approve_doctor/<int:user_id>', methods=['POST'])
@login_required
def approve_doctor(user_id):
    if not is_admin():
        flash("Unauthorized access.", "danger")
        return redirect(url_for('main_routes.logout'))

    user = User.query.get_or_404(user_id)
    if user.role == 'doctor':
        user.is_approved = True
        db.session.commit()
        flash(f'Doctor {user.username} approved.', 'success')
        log_event("INFO", f"Admin '{current_user.email}' approved doctor '{user.email}'.")

    return redirect(url_for('admin.manage_users'))

# ========== Model Upload ==========

@admin.route('/admin/upload_model', methods=['GET', 'POST'])
@login_required
def upload_model():
    if not is_admin():
        flash('Access Denied.', 'danger')
        return redirect(url_for('main_routes.logout'))

    model_dir = 'app/static/models'
    os.makedirs(model_dir, exist_ok=True)

    if request.method == 'POST':
        file = request.files.get('model')
        if not file or file.filename == '':
            flash('No model file selected.', 'warning')
            return redirect(request.url)

        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower()
        if ext not in ALLOWED_MODEL_EXT:
            flash('Invalid file type.', 'danger')
            return redirect(request.url)

        filepath = os.path.join(model_dir, filename)
        if os.path.exists(filepath):
            flash('Model with the same name already exists.', 'warning')
        else:
            file.save(filepath)
            flash('Model uploaded successfully!', 'success')
            log_event("INFO", f"Model '{filename}' uploaded by admin {current_user.email}.")

        return redirect(url_for('admin.upload_model'))

    return render_template('admin_upload_model.html')

# ========== Dataset Upload ==========

@admin.route('/admin/dataset', methods=['GET', 'POST'])
@login_required
def dataset():
    if not is_admin():
        flash('Access Denied.', 'danger')
        return redirect(url_for('main_routes.logout'))

    dataset_dir = 'app/static/datasets'
    os.makedirs(dataset_dir, exist_ok=True)

    if request.method == 'POST':
        file = request.files.get('dataset_file')
        if file and file.filename:
            filename = secure_filename(file.filename)
            ext = filename.rsplit('.', 1)[1].lower()
            if ext not in ALLOWED_DATASET_EXT:
                flash('Invalid dataset file type.', 'danger')
                return redirect(request.url)

            filepath = os.path.join(dataset_dir, filename)
            if os.path.exists(filepath):
                flash('File with the same name already exists.', 'warning')
            else:
                file.save(filepath)
                flash('Dataset uploaded successfully!', 'success')
                log_event("INFO", f"Dataset '{filename}' uploaded by admin {current_user.email}.")
        else:
            flash('No file selected.', 'danger')
        return redirect(url_for('admin.dataset'))

    datasets = os.listdir(dataset_dir)
    return render_template('admin_dataset.html', datasets=datasets)

# ========== Logs and Security ==========

@admin.route('/admin/logs')
@login_required
def logs():
    if not is_admin():
        flash('Access Denied.', 'danger')
        return redirect(url_for('main_routes.logout'))

    logs = Log.query.order_by(Log.timestamp.desc()).limit(100).all()
    return render_template('admin_logs.html', logs=logs)

@admin.route('/admin/security')
@login_required
def security():
    if not is_admin():
        flash('Access Denied.', 'danger')
        return redirect(url_for('main_routes.logout'))

    return render_template('admin_security.html')

# ========== Download Reports ==========

@admin.route('/admin/download_reports')
@login_required
def download_reports():
    if not is_admin():
        flash('Access Denied.', 'danger')
        return redirect(url_for('main_routes.logout'))

    return render_template('admin_download_reports.html')

# ========== Analytics ==========

@admin.route('/admin/analytics')
@login_required
def admin_analytics():
    if not is_admin():
        flash('Access Denied.', 'danger')
        return redirect(url_for('main_routes.logout'))

    total_users = User.query.count()
    total_patients = User.query.filter_by(role='patient').count()
    total_doctors = User.query.filter_by(role='doctor').count()
    active_doctors = User.query.filter_by(role='doctor', is_active=True).count()
    
    total_predictions = Prediction.query.count()
    leukemia_cases = Prediction.query.filter_by(result='Leukemia').count()
    healthy_cases = Prediction.query.filter_by(result='Healthy').count()

    months, counts = get_user_growth_data()
    trend_months, trend_leukemia, trend_healthy = get_prediction_trends()

    return render_template('admin_analytics.html',
                           total_users=total_users,
                           total_patients=total_patients,
                           total_doctors=total_doctors,
                           active_doctors=active_doctors,
                           total_predictions=total_predictions,
                           leukemia_cases=leukemia_cases,
                           healthy_cases=healthy_cases,
                           months=months,
                           counts=counts,
                           trend_months=trend_months,
                           trend_leukemia=trend_leukemia,
                           trend_healthy=trend_healthy)
