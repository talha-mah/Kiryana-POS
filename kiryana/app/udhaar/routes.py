from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import db, Customer, CustomerLedger, LedgerType, Sale
from datetime import datetime, timedelta
from decimal import Decimal

udhaar_bp = Blueprint('udhaar', __name__, url_prefix='/udhaar')

def get_shop_id():
    return current_user.shop_id

def recalculate_customer_ledger(customer):
    balance = Decimal('0')
    changed = False
    entries = customer.ledger_entries.order_by(CustomerLedger.id.asc()).all()

    for entry in entries:
        amount = Decimal(str(entry.amount))
        if entry.type == LedgerType.credit:
            balance += amount
        else:
            balance = max(balance - amount, Decimal('0'))

        if Decimal(str(entry.balance_after)) != balance:
            entry.balance_after = balance
            changed = True

    return balance, changed

@udhaar_bp.route('/')
@login_required
def index():
    customers = Customer.query.filter_by(shop_id=get_shop_id()).order_by(Customer.name).all()
    overdue_threshold = datetime.utcnow() - timedelta(days=30)
    customer_data = []
    any_changed = False
    for c in customers:
        balance, changed = recalculate_customer_ledger(c)
        any_changed = any_changed or changed
        last_entry = c.ledger_entries.order_by(CustomerLedger.id.desc()).first()
        is_overdue = (
            balance > 0 and last_entry and
            last_entry.created_at < overdue_threshold
        )
        customer_data.append({
            'customer': c,
            'balance': balance,
            'is_overdue': is_overdue
        })
    if any_changed:
        db.session.commit()
    return render_template('udhaar/list.html', customer_data=customer_data)

@udhaar_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_customer():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        credit_limit = request.form.get('credit_limit', 5000)
        if not name:
            flash('Customer name is required.', 'danger')
            return render_template('udhaar/add_customer.html')
        customer = Customer(
            shop_id=get_shop_id(),
            name=name,
            phone=phone,
            credit_limit=Decimal(str(credit_limit))
        )
        db.session.add(customer)
        db.session.commit()
        flash(f'Customer "{name}" added.', 'success')
        return redirect(url_for('udhaar.index'))
    return render_template('udhaar/add_customer.html')

@udhaar_bp.route('/<int:customer_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_customer(customer_id):
    customer = Customer.query.filter_by(id=customer_id, shop_id=get_shop_id()).first_or_404()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        credit_limit = request.form.get('credit_limit', 5000)
        if not name:
            flash('Customer name is required.', 'danger')
            return render_template('udhaar/edit_customer.html', customer=customer)
        customer.name = name
        customer.phone = phone
        customer.credit_limit = Decimal(str(credit_limit or 0))
        db.session.commit()
        flash(f'Customer "{customer.name}" updated.', 'success')
        return redirect(url_for('udhaar.customer_detail', customer_id=customer.id))
    return render_template('udhaar/edit_customer.html', customer=customer)

@udhaar_bp.route('/<int:customer_id>/delete', methods=['POST'])
@login_required
def delete_customer(customer_id):
    customer = Customer.query.filter_by(id=customer_id, shop_id=get_shop_id()).first_or_404()
    balance, changed = recalculate_customer_ledger(customer)
    if changed:
        db.session.commit()
    if balance > 0:
        flash('Clear the customer balance before deleting this customer.', 'warning')
        return redirect(url_for('udhaar.customer_detail', customer_id=customer.id))

    customer_name = customer.name
    Sale.query.filter_by(customer_id=customer.id, shop_id=get_shop_id()).update(
        {Sale.customer_id: None},
        synchronize_session=False
    )
    CustomerLedger.query.filter_by(customer_id=customer.id).delete(synchronize_session=False)
    db.session.delete(customer)
    db.session.commit()
    flash(f'Customer "{customer_name}" deleted.', 'info')
    return redirect(url_for('udhaar.index'))

@udhaar_bp.route('/<int:customer_id>')
@login_required
def customer_detail(customer_id):
    customer = Customer.query.filter_by(id=customer_id, shop_id=get_shop_id()).first_or_404()
    balance, changed = recalculate_customer_ledger(customer)
    if changed:
        db.session.commit()
    entries = customer.ledger_entries.order_by(CustomerLedger.created_at.desc()).all()
    return render_template('udhaar/customer.html', customer=customer, entries=entries, balance=balance)

@udhaar_bp.route('/<int:customer_id>/payment', methods=['POST'])
@login_required
def record_payment(customer_id):
    customer = Customer.query.filter_by(id=customer_id, shop_id=get_shop_id()).first_or_404()
    amount = Decimal(str(request.form.get('amount', 0)))
    note = request.form.get('note', '').strip()
    if amount <= 0:
        flash('Invalid payment amount.', 'danger')
        return redirect(url_for('udhaar.customer_detail', customer_id=customer_id))
    current_bal, changed = recalculate_customer_ledger(customer)
    new_balance = max(current_bal - amount, Decimal('0'))
    ledger = CustomerLedger(
        customer_id=customer.id,
        amount=amount,
        type=LedgerType.payment,
        balance_after=new_balance,
        note=note or 'Payment received'
    )
    db.session.add(ledger)
    db.session.commit()
    flash(f'Payment of Rs. {amount:,.0f} recorded.', 'success')
    return redirect(url_for('udhaar.customer_detail', customer_id=customer_id))

@udhaar_bp.route('/wa')
@login_required
def whatsapp_draft():
    customer_id = request.args.get('customer_id')
    customer = Customer.query.filter_by(id=customer_id, shop_id=get_shop_id()).first_or_404()
    balance, changed = recalculate_customer_ledger(customer)
    if changed:
        db.session.commit()
    message = f"Assalam o Alaikum {customer.name}, aapka udhaar Rs. {balance:,.0f} hai. Meherbani kar ke payment kar dain. Shukriya!"
    wa_link = f"https://wa.me/92{customer.phone.lstrip('0')}?text={message}" if customer.phone else None
    return render_template('udhaar/whatsapp.html', customer=customer, balance=balance,
                           message=message, wa_link=wa_link)
