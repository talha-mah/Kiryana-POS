from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import db, DailyReconciliation, Sale, PaymentType
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import func

recon_bp = Blueprint('reconciliation', __name__, url_prefix='/reconciliation')

def get_shop_id():
    return current_user.shop_id

@recon_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    today = date.today()
    existing = DailyReconciliation.query.filter_by(
        shop_id=get_shop_id(), recon_date=today
    ).first()

    # Calculate today's recorded cash sales
    recorded = db.session.query(func.sum(Sale.total_amount)).filter(
        Sale.shop_id == get_shop_id(),
        Sale.payment_type == PaymentType.cash,
        func.date(Sale.created_at) == today
    ).scalar() or Decimal('0')

    if request.method == 'POST' and not existing:
        physical_cash = Decimal(str(request.form.get('physical_cash', 0)))
        note = request.form.get('note', '').strip()
        difference = physical_cash - recorded
        recon = DailyReconciliation(
            shop_id=get_shop_id(),
            recon_date=today,
            physical_cash=physical_cash,
            recorded_sales=recorded,
            difference=difference,
            note=note
        )
        db.session.add(recon)
        db.session.commit()
        flash(f'Reconciliation saved. Difference: Rs. {difference:,.0f}', 'success')
        return redirect(url_for('reconciliation.history'))

    return render_template('reconciliation/form.html',
                           existing=existing, recorded=recorded, today=today)

@recon_bp.route('/history')
@login_required
def history():
    records = DailyReconciliation.query.filter_by(shop_id=get_shop_id())\
        .order_by(DailyReconciliation.recon_date.desc()).limit(60).all()
    return render_template('reconciliation/history.html', records=records)
