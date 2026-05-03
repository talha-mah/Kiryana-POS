from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from app.models import db, Sale, Customer, CustomerLedger, Supplier, SupplierLedger, Expense, SaleItem
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import func, text

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/')

def get_shop_id():
    return current_user.shop_id

@dashboard_bp.route('/')
def index():
    if not current_user.is_authenticated:
        return render_template('landing.html')

    if current_user.is_admin:
        from app.models import Shop, ShopRegistrationRequest, RegistrationStatus
        shops = Shop.query.order_by(Shop.name).all()
        pending_count = ShopRegistrationRequest.query.filter_by(status=RegistrationStatus.pending).count()
        return render_template('dashboard/admin_home.html', shops=shops, pending_count=pending_count)

    shop_id = get_shop_id()
    today = date.today()
    yesterday = today - timedelta(days=1)

    # Today's sales
    today_sales = db.session.query(func.sum(Sale.total_amount)).filter(
        Sale.shop_id == shop_id,
        func.date(Sale.created_at) == today
    ).scalar() or 0

    # Yesterday's sales
    yesterday_sales = db.session.query(func.sum(Sale.total_amount)).filter(
        Sale.shop_id == shop_id,
        func.date(Sale.created_at) == yesterday
    ).scalar() or 0

    # Total outstanding udhaar
    customers = Customer.query.filter_by(shop_id=shop_id).all()
    total_udhaar = sum(Decimal(str(c.current_balance)) for c in customers)

    # Total supplier payables
    suppliers = Supplier.query.filter_by(shop_id=shop_id).all()
    total_payables = sum(Decimal(str(s.current_balance)) for s in suppliers)

    net_position = total_udhaar - total_payables

    # Top 5 debtors via stored procedure
    try:
        top_debtors = db.session.execute(
            text("SELECT * FROM get_top_debtors(:sid, 5)"),
            {"sid": shop_id}
        ).fetchall()
    except Exception:
        db.session.rollback()
        # Fallback if stored procedure not yet created
        top_debtors = sorted(
            [(c.name, c.current_balance) for c in customers if c.current_balance > 0],
            key=lambda x: x[1], reverse=True
        )[:5]

    # Best selling item (last 30 days)
    thirty_ago = datetime.utcnow() - timedelta(days=30)
    best_item = db.session.query(
        SaleItem.name_snapshot,
        func.sum(SaleItem.qty).label('total_qty')
    ).join(Sale).filter(
        Sale.shop_id == shop_id,
        Sale.created_at >= thirty_ago
    ).group_by(SaleItem.name_snapshot).order_by(func.sum(SaleItem.qty).desc()).first()

    return render_template('dashboard/index.html',
                           today_sales=today_sales,
                           yesterday_sales=yesterday_sales,
                           total_udhaar=total_udhaar,
                           total_payables=total_payables,
                           net_position=net_position,
                           top_debtors=top_debtors,
                           best_item=best_item,
                           now=datetime.utcnow())

@dashboard_bp.route('/reports')
@login_required
def reports():
    if current_user.is_admin:
        return render_template('dashboard/reports.html', sales=[], range_type='daily')

    shop_id = get_shop_id()
    range_type = request.args.get('range', 'daily')
    today = date.today()

    if range_type == 'weekly':
        start = today - timedelta(days=6)
    elif range_type == 'monthly':
        start = today.replace(day=1)
    else:
        start = today

    # Join Sale + SaleItem for detailed report
    sales = db.session.query(
        Sale.id,
        Sale.created_at,
        Sale.total_amount,
        Sale.payment_type,
        Customer.name.label('customer_name')
    ).outerjoin(Customer, Sale.customer_id == Customer.id).filter(
        Sale.shop_id == shop_id,
        func.date(Sale.created_at) >= start,
        func.date(Sale.created_at) <= today
    ).order_by(Sale.created_at.desc()).all()

    total = sum(s.total_amount for s in sales)

    return render_template('dashboard/reports.html',
                           sales=sales, total=total,
                           range_type=range_type, start=start, today=today)
