from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import db, Expense, Sale, ExpenseCategory
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import func
import calendar

expenses_bp = Blueprint('expenses', __name__, url_prefix='/expenses')

def get_shop_id():
    return current_user.shop_id

@expenses_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        category = request.form.get('category')
        amount = Decimal(str(request.form.get('amount', 0)))
        note = request.form.get('note', '').strip()
        expense_date_str = request.form.get('expense_date', str(date.today()))
        try:
            expense_date = datetime.strptime(expense_date_str, '%Y-%m-%d').date()
        except ValueError:
            expense_date = date.today()
        if amount <= 0:
            flash('Invalid amount.', 'danger')
        else:
            expense = Expense(
                shop_id=get_shop_id(),
                category=ExpenseCategory[category],
                amount=amount,
                note=note,
                expense_date=expense_date
            )
            db.session.add(expense)
            db.session.commit()
            flash('Expense logged.', 'success')
        return redirect(url_for('expenses.index'))

    # Current month expenses
    today = date.today()
    recent = Expense.query.filter_by(shop_id=get_shop_id())\
        .order_by(Expense.expense_date.desc()).limit(20).all()
    categories = [c.value for c in ExpenseCategory]
    return render_template('expenses/log.html', recent=recent, categories=categories, today=today)

@expenses_bp.route('/summary')
@login_required
def summary():
    today = date.today()
    month = int(request.args.get('month', today.month))
    year = int(request.args.get('year', today.year))

    # Monthly expenses by category
    expenses_q = db.session.query(
        Expense.category, func.sum(Expense.amount).label('total')
    ).filter(
        Expense.shop_id == get_shop_id(),
        func.extract('month', Expense.expense_date) == month,
        func.extract('year', Expense.expense_date) == year
    ).group_by(Expense.category).all()

    total_expenses = sum(r.total for r in expenses_q)

    # Monthly sales revenue
    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])
    total_sales = db.session.query(func.sum(Sale.total_amount)).filter(
        Sale.shop_id == get_shop_id(),
        func.date(Sale.created_at) >= month_start,
        func.date(Sale.created_at) <= month_end
    ).scalar() or Decimal('0')

    profit = Decimal(str(total_sales)) - Decimal(str(total_expenses))

    return render_template('expenses/summary.html',
                           expenses_q=expenses_q, total_expenses=total_expenses,
                           total_sales=total_sales, profit=profit,
                           month=month, year=year)
