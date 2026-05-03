from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models import db, User, UserRole, ShopRegistrationRequest, RegistrationStatus

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if not user.is_admin and (not user.shop or not user.shop.is_active):
                flash('Your shop account is not active. Please contact the admin.', 'warning')
                return render_template('auth/login.html')
            login_user(user, remember=True)
            next_page = request.args.get('next')
            flash(f'Welcome back!', 'success')
            return redirect(next_page or url_for('dashboard.index'))
        flash('Invalid email or password.', 'danger')
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('dashboard.index'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # Only allow registration if no admin exists yet
    if User.query.filter_by(role=UserRole.admin).first():
        flash('Registration is closed. Contact the admin.', 'warning')
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('auth/register.html')
        user = User(email=email, role=UserRole.admin)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Admin account created!', 'success')
        return redirect(url_for('dashboard.index'))
    return render_template('auth/register.html')

@auth_bp.route('/shop-register', methods=['GET', 'POST'])
def shop_register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        shop_name = request.form.get('shop_name', '').strip()
        owner_name = request.form.get('owner_name', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not all([shop_name, owner_name, email, password]):
            flash('Please fill all required fields.', 'danger')
            return render_template('auth/shop_register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('auth/shop_register.html')

        if User.query.filter_by(email=email).first():
            flash('This email already has an active account.', 'danger')
            return render_template('auth/shop_register.html')

        existing_request = ShopRegistrationRequest.query.filter_by(email=email).first()
        if existing_request:
            if existing_request.status == RegistrationStatus.pending:
                flash('A registration request for this email is already waiting for admin approval.', 'warning')
            elif existing_request.status == RegistrationStatus.approved:
                flash('This request has already been approved. Please log in.', 'info')
                return redirect(url_for('auth.login'))
            else:
                flash('This email has a rejected request. Please contact the admin before trying again.', 'warning')
            return render_template('auth/shop_register.html')

        registration = ShopRegistrationRequest(
            shop_name=shop_name,
            owner_name=owner_name,
            phone=phone,
            address=address,
            email=email
        )
        registration.set_password(password)
        db.session.add(registration)
        db.session.commit()

        flash('Your shop registration request was sent. You can log in after the admin approves it.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/shop_register.html')
