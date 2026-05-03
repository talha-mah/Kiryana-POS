from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from functools import wraps
from app.models import (db, Product, Shop, User, ShopProduct, UserRole,
                        ShopRegistrationRequest, RegistrationStatus, SaleItem,
                        Sale, Customer, CustomerLedger, Supplier, SupplierLedger,
                        Expense, DailyReconciliation)
from decimal import Decimal
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def add_product_to_all_shops(product):
    shops = Shop.query.all()
    added_count = 0
    for shop in shops:
        existing = ShopProduct.query.filter_by(shop_id=shop.id, product_id=product.id).first()
        if existing:
            existing.name = product.name
            existing.price = product.default_price
            existing.is_active = product.is_active
            continue

        db.session.add(ShopProduct(
            shop_id=shop.id,
            product_id=product.id,
            name=product.name,
            price=product.default_price,
            is_custom=False,
            is_active=product.is_active
        ))
        added_count += 1
    return added_count

def sync_product_to_shops(product):
    for shop_product in ShopProduct.query.filter_by(product_id=product.id, is_custom=False).all():
        shop_product.name = product.name
        shop_product.price = product.default_price
        shop_product.is_active = product.is_active

def product_has_sales(product):
    return db.session.query(SaleItem.id).join(
        ShopProduct, SaleItem.shop_product_id == ShopProduct.id
    ).filter(ShopProduct.product_id == product.id).first() is not None

def shop_has_business_history(shop):
    return any([
        Sale.query.filter_by(shop_id=shop.id).first(),
        Customer.query.filter_by(shop_id=shop.id).first(),
        Supplier.query.filter_by(shop_id=shop.id).first(),
        Expense.query.filter_by(shop_id=shop.id).first(),
        DailyReconciliation.query.filter_by(shop_id=shop.id).first(),
    ])

def delete_shop_permanently(shop):
    customer_ids = [id_ for (id_,) in db.session.query(Customer.id).filter_by(shop_id=shop.id).all()]
    supplier_ids = [id_ for (id_,) in db.session.query(Supplier.id).filter_by(shop_id=shop.id).all()]
    sale_ids = [id_ for (id_,) in db.session.query(Sale.id).filter_by(shop_id=shop.id).all()]

    if customer_ids:
        CustomerLedger.query.filter(CustomerLedger.customer_id.in_(customer_ids)).delete(synchronize_session=False)
    if supplier_ids:
        SupplierLedger.query.filter(SupplierLedger.supplier_id.in_(supplier_ids)).delete(synchronize_session=False)
    if sale_ids:
        SaleItem.query.filter(SaleItem.sale_id.in_(sale_ids)).delete(synchronize_session=False)

    Sale.query.filter_by(shop_id=shop.id).delete(synchronize_session=False)
    Customer.query.filter_by(shop_id=shop.id).delete(synchronize_session=False)
    Supplier.query.filter_by(shop_id=shop.id).delete(synchronize_session=False)
    Expense.query.filter_by(shop_id=shop.id).delete(synchronize_session=False)
    DailyReconciliation.query.filter_by(shop_id=shop.id).delete(synchronize_session=False)
    ShopProduct.query.filter_by(shop_id=shop.id).delete(synchronize_session=False)
    User.query.filter_by(shop_id=shop.id).delete(synchronize_session=False)
    db.session.delete(shop)

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated

@admin_bp.route('/')
@admin_required
def index():
    return redirect(url_for('admin.catalog'))

@admin_bp.route('/catalog', methods=['GET', 'POST'])
@admin_required
def catalog():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name', '').strip()
            brand = request.form.get('brand', '').strip()
            unit = request.form.get('unit', 'piece').strip()
            price = Decimal(str(request.form.get('default_price', 0)))
            if name:
                p = Product(name=name, brand=brand, unit=unit, default_price=price)
                db.session.add(p)
                db.session.flush()
                added_count = add_product_to_all_shops(p)
                db.session.commit()
                flash(f'Product "{name}" added to catalog and synced to {added_count} shops.', 'success')
        elif action == 'toggle':
            product_id = int(request.form.get('product_id'))
            p = Product.query.get_or_404(product_id)
            p.is_active = not p.is_active
            sync_product_to_shops(p)
            db.session.commit()
            flash(f'Product "{p.name}" {"activated" if p.is_active else "deactivated"}.', 'info')
        return redirect(url_for('admin.catalog'))

    products = Product.query.order_by(Product.name).all()
    return render_template('admin/catalog.html', products=products)

@admin_bp.route('/catalog/<int:product_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        brand = request.form.get('brand', '').strip()
        unit = request.form.get('unit', 'piece').strip()
        price = Decimal(str(request.form.get('default_price', 0) or 0))

        if not name:
            flash('Product name is required.', 'danger')
            return render_template('admin/edit_product.html', product=product)

        product.name = name
        product.brand = brand
        product.unit = unit
        product.default_price = price
        sync_product_to_shops(product)
        db.session.commit()
        flash(f'Product "{product.name}" updated and synced to shops.', 'success')
        return redirect(url_for('admin.catalog'))

    return render_template('admin/edit_product.html', product=product)

@admin_bp.route('/catalog/<int:product_id>/delete', methods=['POST'])
@admin_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    if product_has_sales(product):
        product.is_active = False
        sync_product_to_shops(product)
        db.session.commit()
        flash(f'Product "{product.name}" has sale history, so it was deactivated instead of deleted.', 'warning')
        return redirect(url_for('admin.catalog'))

    product_name = product.name
    ShopProduct.query.filter_by(product_id=product.id, is_custom=False).delete(synchronize_session=False)
    db.session.delete(product)
    db.session.commit()
    flash(f'Product "{product_name}" deleted.', 'info')
    return redirect(url_for('admin.catalog'))

@admin_bp.route('/shops')
@admin_required
def shops():
    all_shops = Shop.query.order_by(Shop.name).all()
    pending_requests = ShopRegistrationRequest.query.filter_by(
        status=RegistrationStatus.pending
    ).order_by(ShopRegistrationRequest.created_at.desc()).all()
    reviewed_requests = ShopRegistrationRequest.query.filter(
        ShopRegistrationRequest.status != RegistrationStatus.pending
    ).order_by(ShopRegistrationRequest.reviewed_at.desc()).limit(10).all()
    return render_template(
        'admin/shops.html',
        shops=all_shops,
        pending_requests=pending_requests,
        reviewed_requests=reviewed_requests
    )

@admin_bp.route('/shops/add', methods=['GET', 'POST'])
@admin_required
def add_shop():
    if request.method == 'POST':
        shop_name = request.form.get('shop_name', '').strip()
        owner_name = request.form.get('owner_name', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not all([shop_name, owner_name, email, password]):
            flash('All required fields must be filled.', 'danger')
            return render_template('admin/add_shop.html')

        if User.query.filter_by(email=email).first():
            flash('Email already in use.', 'danger')
            return render_template('admin/add_shop.html')

        shop = Shop(name=shop_name, owner_name=owner_name, phone=phone, address=address)
        db.session.add(shop)
        db.session.flush()

        user = User(shop_id=shop.id, email=email, role=UserRole.owner)
        user.set_password(password)
        db.session.add(user)

        # Auto-add all active global products to this shop
        products = Product.query.filter_by(is_active=True).all()
        for p in products:
            sp = ShopProduct(
                shop_id=shop.id,
                product_id=p.id,
                name=p.name,
                price=p.default_price,
                is_custom=False
            )
            db.session.add(sp)

        db.session.commit()
        flash(f'Shop "{shop_name}" created with owner account {email}.', 'success')
        return redirect(url_for('admin.shops'))

    return render_template('admin/add_shop.html')

@admin_bp.route('/shops/<int:shop_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_shop(shop_id):
    shop = Shop.query.get_or_404(shop_id)
    owner = shop.users.filter_by(role=UserRole.owner).first()

    if request.method == 'POST':
        shop_name = request.form.get('shop_name', '').strip()
        owner_name = request.form.get('owner_name', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        email = request.form.get('email', '').strip().lower()

        if not all([shop_name, owner_name]):
            flash('Shop name and owner name are required.', 'danger')
            return render_template('admin/edit_shop.html', shop=shop, owner=owner)

        if owner and email:
            existing = User.query.filter(User.email == email, User.id != owner.id).first()
            if existing:
                flash('Email already in use.', 'danger')
                return render_template('admin/edit_shop.html', shop=shop, owner=owner)
            owner.email = email

        shop.name = shop_name
        shop.owner_name = owner_name
        shop.phone = phone
        shop.address = address
        db.session.commit()
        flash(f'Shop "{shop.name}" updated.', 'success')
        return redirect(url_for('admin.shops'))

    return render_template('admin/edit_shop.html', shop=shop, owner=owner)

@admin_bp.route('/shops/<int:shop_id>/delete', methods=['POST'])
@admin_required
def delete_shop(shop_id):
    shop = Shop.query.get_or_404(shop_id)
    shop_name = shop.name
    delete_shop_permanently(shop)
    db.session.commit()
    flash(f'Shop "{shop_name}" and all related records were permanently deleted.', 'info')
    return redirect(url_for('admin.shops'))

@admin_bp.route('/shops/<int:shop_id>/toggle', methods=['POST'])
@admin_required
def toggle_shop(shop_id):
    shop = Shop.query.get_or_404(shop_id)
    shop.is_active = not shop.is_active
    db.session.commit()
    flash(f'Shop "{shop.name}" {"activated" if shop.is_active else "deactivated"}.', 'info')
    return redirect(url_for('admin.shops'))

@admin_bp.route('/shop-requests/<int:request_id>/approve', methods=['POST'])
@admin_required
def approve_shop_request(request_id):
    registration = ShopRegistrationRequest.query.get_or_404(request_id)
    if registration.status != RegistrationStatus.pending:
        flash('This registration request has already been reviewed.', 'warning')
        return redirect(url_for('admin.shops'))

    if User.query.filter_by(email=registration.email).first():
        registration.status = RegistrationStatus.rejected
        registration.admin_note = 'Email already exists as an active account.'
        registration.reviewed_at = datetime.utcnow()
        registration.reviewed_by_id = current_user.id
        db.session.commit()
        flash('Request rejected because that email already has an account.', 'danger')
        return redirect(url_for('admin.shops'))

    shop = Shop(
        name=registration.shop_name,
        owner_name=registration.owner_name,
        phone=registration.phone,
        address=registration.address,
        is_active=True
    )
    db.session.add(shop)
    db.session.flush()

    user = User(
        shop_id=shop.id,
        email=registration.email,
        password_hash=registration.password_hash,
        role=UserRole.owner
    )
    db.session.add(user)

    products = Product.query.filter_by(is_active=True).all()
    for p in products:
        db.session.add(ShopProduct(
            shop_id=shop.id,
            product_id=p.id,
            name=p.name,
            price=p.default_price,
            is_custom=False
        ))

    registration.status = RegistrationStatus.approved
    registration.reviewed_at = datetime.utcnow()
    registration.reviewed_by_id = current_user.id
    registration.admin_note = 'Approved and owner account created.'

    db.session.commit()
    flash(f'Shop "{shop.name}" approved and owner account created.', 'success')
    return redirect(url_for('admin.shops'))

@admin_bp.route('/shop-requests/<int:request_id>/reject', methods=['POST'])
@admin_required
def reject_shop_request(request_id):
    registration = ShopRegistrationRequest.query.get_or_404(request_id)
    if registration.status != RegistrationStatus.pending:
        flash('This registration request has already been reviewed.', 'warning')
        return redirect(url_for('admin.shops'))

    registration.status = RegistrationStatus.rejected
    registration.admin_note = request.form.get('admin_note', '').strip() or 'Rejected by admin.'
    registration.reviewed_at = datetime.utcnow()
    registration.reviewed_by_id = current_user.id
    db.session.commit()

    flash(f'Registration request for {registration.shop_name} rejected.', 'info')
    return redirect(url_for('admin.shops'))
