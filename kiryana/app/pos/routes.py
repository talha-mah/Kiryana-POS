from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app.models import db, Sale, SaleItem, ShopProduct, Customer, CustomerLedger, PaymentType, LedgerType, Product
from decimal import Decimal
from sqlalchemy import func

pos_bp = Blueprint('pos', __name__, url_prefix='/pos')

def get_shop_id():
    return current_user.shop_id

def sync_active_catalog_to_shop(shop_id):
    existing_product_ids = {
        product_id for (product_id,) in db.session.query(ShopProduct.product_id).filter(
            ShopProduct.shop_id == shop_id,
            ShopProduct.product_id.isnot(None)
        ).all()
    }

    added = False
    active_products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    for product in active_products:
        if product.id in existing_product_ids:
            continue
        db.session.add(ShopProduct(
            shop_id=shop_id,
            product_id=product.id,
            name=product.name,
            price=product.default_price,
            is_custom=False,
            is_active=True
        ))
        added = True

    if added:
        db.session.commit()

def product_payload(product):
    return {
        'id': product.id,
        'name': product.name,
        'price': float(product.price)
    }

@pos_bp.route('/')
@login_required
def checkout():
    if current_user.is_admin:
        flash('Admins do not have a shop. Use Admin panel.', 'warning')
        return redirect(url_for('dashboard.index'))
    sync_active_catalog_to_shop(get_shop_id())
    customers = Customer.query.filter_by(shop_id=get_shop_id()).order_by(Customer.name).all()

    top_products = db.session.query(
        ShopProduct,
        func.coalesce(func.sum(SaleItem.qty), 0).label('sold_qty')
    ).join(SaleItem, SaleItem.shop_product_id == ShopProduct.id) \
     .join(Sale, Sale.id == SaleItem.sale_id) \
     .filter(
        Sale.shop_id == get_shop_id(),
        ShopProduct.shop_id == get_shop_id(),
        ShopProduct.is_active == True
    ).group_by(ShopProduct.id) \
     .order_by(func.sum(SaleItem.qty).desc(), ShopProduct.name.asc()) \
     .limit(12).all()

    quick_products = [product for product, sold_qty in top_products]
    if len(quick_products) < 12:
        used_ids = [product.id for product in quick_products]
        filler_query = ShopProduct.query.filter(
            ShopProduct.shop_id == get_shop_id(),
            ShopProduct.is_active == True
        )
        if used_ids:
            filler_query = filler_query.filter(~ShopProduct.id.in_(used_ids))
        quick_products.extend(
            filler_query.order_by(ShopProduct.name.asc()).limit(12 - len(quick_products)).all()
        )

    quick_products_payload = [product_payload(product) for product in quick_products]
    return render_template('pos/checkout.html', customers=customers, quick_products=quick_products_payload)

@pos_bp.route('/search')
@login_required
def search():
    q = request.args.get('q', '').strip()
    if len(q) < 1:
        return jsonify([])
    products = ShopProduct.query.filter(
        ShopProduct.shop_id == get_shop_id(),
        ShopProduct.is_active == True,
        ShopProduct.name.ilike(f'%{q}%')
    ).limit(15).all()
    return jsonify([product_payload(p) for p in products])

@pos_bp.route('/checkout', methods=['POST'])
@login_required
def process_checkout():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data received'}), 400

    items = data.get('items', [])
    loose_amount = Decimal(str(data.get('loose_amount', 0)))
    payment_type = data.get('payment_type', 'cash')
    customer_id = data.get('customer_id')

    if loose_amount < 0:
        return jsonify({'success': False, 'error': 'Loose amount cannot be negative'}), 400

    if not items and loose_amount == 0:
        return jsonify({'success': False, 'error': 'Cart is empty'}), 400

    if payment_type == 'udhaar' and not customer_id:
        return jsonify({'success': False, 'error': 'Customer required for udhaar'}), 400

    try:
        # Calculate total
        total = loose_amount
        sale_items = []
        for item in items:
            sp = ShopProduct.query.filter_by(id=item['id'], shop_id=get_shop_id()).first()
            if not sp:
                return jsonify({'success': False, 'error': f'Product not found'}), 400
            qty = Decimal(str(item.get('qty', 1)))
            if qty <= 0:
                return jsonify({'success': False, 'error': 'Quantity must be greater than zero'}), 400
            unit_price = Decimal(str(sp.price))
            subtotal = qty * unit_price
            total += subtotal
            sale_items.append({
                'shop_product_id': sp.id,
                'name_snapshot': sp.name,
                'qty': qty,
                'unit_price': unit_price,
                'subtotal': subtotal
            })

        if loose_amount > 0:
            sale_items.append({
                'shop_product_id': None,
                'name_snapshot': 'Loose Items',
                'qty': Decimal('1'),
                'unit_price': loose_amount,
                'subtotal': loose_amount
            })

        # Create sale
        sale = Sale(
            shop_id=get_shop_id(),
            customer_id=int(customer_id) if customer_id else None,
            total_amount=total,
            payment_type=PaymentType[payment_type],
            loose_amount=loose_amount
        )
        db.session.add(sale)
        db.session.flush()  # get sale.id

        # Create sale items
        for si_data in sale_items:
            si = SaleItem(sale_id=sale.id, **si_data)
            db.session.add(si)

        # If udhaar — update customer ledger
        if payment_type == 'udhaar' and customer_id:
            customer = Customer.query.filter_by(id=customer_id, shop_id=get_shop_id()).first()
            if not customer:
                raise ValueError('Customer not found')
            current_bal = customer.current_balance
            new_balance = Decimal(str(current_bal)) + total
            ledger = CustomerLedger(
                customer_id=customer.id,
                sale_id=sale.id,
                amount=total,
                type=LedgerType.credit,
                balance_after=new_balance,
                note=f'Sale #{sale.id}'
            )
            db.session.add(ledger)

        db.session.commit()
        return jsonify({'success': True, 'sale_id': sale.id, 'total': float(total)})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
