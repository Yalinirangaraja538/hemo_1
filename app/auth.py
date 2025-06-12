from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from app.db_models import User
from app import db

auth = Blueprint('auth', __name__)

# 🚀 LOGIN
@auth.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        password = request.form.get('password')
        user = User.query.filter_by(user_id=user_id).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Logged in successfully!', 'success')

            # 👑 Redirect based on role
            if user.role.lower() == 'admin':
                return redirect(url_for('admin.dashboard'))  # Admin goes to dashboard
            else:
                return redirect(url_for('auth.profile'))  # Normal user goes to profile

        flash('Invalid user ID or password.', 'danger')
        return redirect(url_for('auth.login'))

    return render_template('login.html')

# 🚀 LOGOUT
@auth.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('auth.login'))

# 🚀 PROFILE (for normal users)
@auth.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.name = request.form.get('name')
        current_user.email = request.form.get('email')
        if request.form.get('password'):
            current_user.password = generate_password_hash(request.form.get('password'), method='sha256')
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('profile.html')

# 🚀 REGISTER
@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        existing_user = User.query.filter_by(user_id=user_id).first()
        if existing_user:
            flash('User ID already exists. Please choose a different one.', 'danger')
            return redirect(url_for('auth.register'))

        # By default set new users as 'user' role
        new_user = User(
            user_id=user_id,
            name=name,
            email=email,
            password=generate_password_hash(password, method='sha256'),
            role='user'  # 🔥 Default role 'user'
        )
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')
