from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import db, Supplier, SupplierLedger, SupplierLedgerType
from datetime import datetime, timedelta, date
from decimal import Decimal

supplier_bp = Blueprint('supplier', __name__, url_prefix='/supplier')

def get_shop_id():
    return current_user.shop_id

def recalculate_supplier_balance(supplier):
    balance = Decimal('0')
    entries = supplier.ledger_entries.order_by(SupplierLedger.id.asc()).all()
    for entry in entries:
        if entry.type == SupplierLedgerType.delivery:
            balance += Decimal(str(entry.amount))
        else:
            balance = max(balance - Decimal(str(entry.amount)), Decimal('0'))
        entry.balance_after = balance
    return balance

@supplier_bp.route('/')
@login_required
def index():
    suppliers = Supplier.query.filter_by(shop_id=get_shop_id()).order_by(Supplier.name).all()
    today = date.today()
    supplier_data = []
    for s in suppliers:
        balance = s.current_balance
        last = s.ledger_entries.order_by(SupplierLedger.id.desc()).first()
        is_overdue = last and last.due_date and last.due_date < today and balance > 0
        supplier_data.append({
            'supplier': s,
            'balance': balance,
            'is_overdue': is_overdue,
            'due_date': last.due_date if last else None
        })
    return render_template('supplier/list.html', supplier_data=supplier_data)

@supplier_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_supplier():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        terms = int(request.form.get('payment_terms_days', 7))
        if not name:
            flash('Supplier name is required.', 'danger')
            return render_template('supplier/add_supplier.html')
        supplier = Supplier(shop_id=get_shop_id(), name=name, phone=phone, payment_terms_days=terms)
        db.session.add(supplier)
        db.session.commit()
        flash(f'Supplier "{name}" added.', 'success')
        return redirect(url_for('supplier.index'))
    return render_template('supplier/add_supplier.html')

@supplier_bp.route('/<int:supplier_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_supplier(supplier_id):
    supplier = Supplier.query.filter_by(id=supplier_id, shop_id=get_shop_id()).first_or_404()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        terms = int(request.form.get('payment_terms_days', 7) or 7)
        if not name:
            flash('Supplier name is required.', 'danger')
            return render_template('supplier/edit_supplier.html', supplier=supplier)
        supplier.name = name
        supplier.phone = phone
        supplier.payment_terms_days = terms
        db.session.commit()
        flash(f'Supplier "{supplier.name}" updated.', 'success')
        return redirect(url_for('supplier.supplier_detail', supplier_id=supplier.id))
    return render_template('supplier/edit_supplier.html', supplier=supplier)

@supplier_bp.route('/<int:supplier_id>/delete', methods=['POST'])
@login_required
def delete_supplier(supplier_id):
    supplier = Supplier.query.filter_by(id=supplier_id, shop_id=get_shop_id()).first_or_404()
    if Decimal(str(supplier.current_balance)) > 0:
        flash('Clear the supplier balance before deleting this supplier.', 'warning')
        return redirect(url_for('supplier.supplier_detail', supplier_id=supplier.id))

    supplier_name = supplier.name
    SupplierLedger.query.filter_by(supplier_id=supplier.id).delete(synchronize_session=False)
    db.session.delete(supplier)
    db.session.commit()
    flash(f'Supplier "{supplier_name}" deleted.', 'info')
    return redirect(url_for('supplier.index'))

@supplier_bp.route('/<int:supplier_id>')
@login_required
def supplier_detail(supplier_id):
    supplier = Supplier.query.filter_by(id=supplier_id, shop_id=get_shop_id()).first_or_404()
    recalculate_supplier_balance(supplier)
    db.session.commit()
    entries = supplier.ledger_entries.order_by(SupplierLedger.created_at.desc()).all()
    return render_template('supplier/detail.html', supplier=supplier, entries=entries, today=date.today())

@supplier_bp.route('/<int:supplier_id>/delivery', methods=['POST'])
@login_required
def record_delivery(supplier_id):
    supplier = Supplier.query.filter_by(id=supplier_id, shop_id=get_shop_id()).first_or_404()
    amount = Decimal(str(request.form.get('amount', 0)))
    note = request.form.get('note', '').strip()
    if amount <= 0:
        flash('Invalid amount.', 'danger')
        return redirect(url_for('supplier.supplier_detail', supplier_id=supplier_id))
    current_bal = Decimal(str(supplier.current_balance))
    new_balance = current_bal + amount
    due = date.today() + timedelta(days=supplier.payment_terms_days)
    entry = SupplierLedger(
        supplier_id=supplier.id,
        amount=amount,
        type=SupplierLedgerType.delivery,
        balance_after=new_balance,
        note=note or 'Delivery received',
        due_date=due
    )
    db.session.add(entry)
    recalculate_supplier_balance(supplier)
    db.session.commit()
    flash(f'Delivery of Rs. {amount:,.0f} recorded.', 'success')
    return redirect(url_for('supplier.supplier_detail', supplier_id=supplier_id))

@supplier_bp.route('/<int:supplier_id>/payment', methods=['POST'])
@login_required
def record_payment(supplier_id):
    supplier = Supplier.query.filter_by(id=supplier_id, shop_id=get_shop_id()).first_or_404()
    amount = Decimal(str(request.form.get('amount', 0)))
    note = request.form.get('note', '').strip()
    if amount <= 0:
        flash('Invalid amount.', 'danger')
        return redirect(url_for('supplier.supplier_detail', supplier_id=supplier_id))
    current_bal = Decimal(str(supplier.current_balance))
    new_balance = max(current_bal - amount, Decimal('0'))
    entry = SupplierLedger(
        supplier_id=supplier.id,
        amount=amount,
        type=SupplierLedgerType.payment,
        balance_after=new_balance,
        note=note or 'Payment made'
    )
    db.session.add(entry)
    recalculate_supplier_balance(supplier)
    db.session.commit()
    flash(f'Payment of Rs. {amount:,.0f} recorded.', 'success')
    return redirect(url_for('supplier.supplier_detail', supplier_id=supplier_id))

@supplier_bp.route('/daily', methods=['GET', 'POST'])
@login_required
def daily_vendor():
    suppliers = Supplier.query.filter_by(shop_id=get_shop_id()).order_by(Supplier.name).all()
    if request.method == 'POST':
        supplier_id = int(request.form.get('supplier_id'))
        amount = Decimal(str(request.form.get('amount', 0)))
        supplier = Supplier.query.filter_by(id=supplier_id, shop_id=get_shop_id()).first_or_404()
        if amount > 0:
            current_bal = Decimal(str(supplier.current_balance))
            new_balance = current_bal + amount
            due = date.today() + timedelta(days=supplier.payment_terms_days)
            entry = SupplierLedger(
                supplier_id=supplier.id, amount=amount,
                type=SupplierLedgerType.delivery, balance_after=new_balance,
                note='Daily delivery', due_date=due
            )
            db.session.add(entry)
            recalculate_supplier_balance(supplier)
            db.session.commit()
            flash(f'{supplier.name}: Rs. {amount:,.0f} logged.', 'success')
        return redirect(url_for('supplier.daily_vendor'))
    return render_template('supplier/daily.html', suppliers=suppliers)
