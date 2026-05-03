"""
Seed script for Kiryana — run with: python seed.py
Creates admin, 2 shops, 30+ products, customers, suppliers, sales, expenses.
"""
import os, sys
from datetime import datetime, timedelta, date
from decimal import Decimal
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('FLASK_ENV', 'development')

from app import create_app
from app.models import (db, Shop, User, Product, ShopProduct, Customer,
                        CustomerLedger, Sale, SaleItem, Supplier, SupplierLedger,
                        Expense, DailyReconciliation,
                        UserRole, PaymentType, LedgerType, SupplierLedgerType, ExpenseCategory)

app = create_app()

PRODUCTS_DATA = [
    # (name, brand, unit, price)
    ("Tapal Danedar 200g", "Tapal", "pack", 320),
    ("Tapal Family Mixture 200g", "Tapal", "pack", 290),
    ("Lipton Yellow Label 200g", "Lipton", "pack", 350),
    ("Nescafe Classic 50g", "Nescafe", "pack", 420),
    ("Milo 400g", "Nestle", "pack", 580),
    ("Surf Excel 500g", "Unilever", "pack", 290),
    ("Ariel 500g", "P&G", "pack", 310),
    ("Bonus Washing Powder 1kg", "Bonus", "pack", 220),
    ("Shan Biryani Masala", "Shan", "pack", 95),
    ("Shan Karahi Masala", "Shan", "pack", 85),
    ("National Biryani Masala", "National", "pack", 90),
    ("Olpers Full Cream Milk 1L", "Olpers", "litre", 155),
    ("Nestle Milkpak 1L", "Nestle", "litre", 160),
    ("Pepsi 1.5L", "Pepsi", "piece", 110),
    ("Coca Cola 1.5L", "Coca Cola", "piece", 115),
    ("7Up 1.5L", "7Up", "piece", 110),
    ("Sprite 500ml", "Coca Cola", "piece", 70),
    ("Mountain Dew 500ml", "Pepsi", "piece", 70),
    ("Lays Classic 30g", "Lays", "pack", 30),
    ("Lays Masala 30g", "Lays", "pack", 30),
    ("Kurkure Chilli Chatka", "Kurkure", "pack", 30),
    ("Cocomo Biscuits", "EBM", "pack", 35),
    ("Peek Freans Sooper", "Peek Freans", "pack", 60),
    ("Rio Biscuits", "EBM", "pack", 50),
    ("Candy Land Pasta 400g", "Candy Land", "pack", 120),
    ("Knorr Noodles Masala", "Knorr", "pack", 45),
    ("Freshly Bread", "Freshly", "piece", 65),
    ("Eggs (Dozen)", "Local", "dozen", 340),
    ("Cooking Oil 1L (Dalda)", "Dalda", "litre", 480),
    ("Sunflower Oil 1L", "Sunflower", "litre", 460),
    ("Sugar 1kg", "Local", "kg", 170),
    ("Flour (Atta) 5kg", "Sunridge", "pack", 760),
    ("Rice Basmati 1kg", "Guard", "kg", 280),
    ("Red Chilli Powder 100g", "National", "pack", 65),
    ("Turmeric 100g", "Shan", "pack", 55),
    ("Salt 800g (Habib)", "Habib", "pack", 55),
    ("Garlic Paste 300g", "Mitchell's", "pack", 120),
    ("Tomato Ketchup 500g", "National", "pack", 175),
    ("Colgate Toothpaste 75ml", "Colgate", "piece", 135),
    ("Lifebuoy Soap 115g", "Unilever", "piece", 65),
    ("Panadol 10 tablets", "GSK", "pack", 45),
    ("Disprin 10 tablets", "Reckitt", "pack", 35),
]

def seed():
    with app.app_context():
        print("🌱 Starting seed...")

        # Clear existing data (careful — only for dev!)
        db.drop_all()
        db.create_all()

        # ── 1. Admin ──
        admin = User(email='admin@kiryana.pk', role=UserRole.admin)
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.flush()
        print("✅ Admin created: admin@kiryana.pk / admin123")

        # ── 2. Global Products ──
        products = []
        for name, brand, unit, price in PRODUCTS_DATA:
            p = Product(name=name, brand=brand, unit=unit, default_price=Decimal(str(price)))
            db.session.add(p)
            products.append(p)
        db.session.flush()
        print(f"✅ {len(products)} global products created")

        # ── 3. Two Shops ──
        shops_data = [
            ("Ahmed General Store", "Ahmed Khan", "0300-1234567", "Block 5, Gulshan-e-Iqbal, Karachi", "ahmed@kiryana.pk", "ahmed123"),
            ("Bilal Kiryana", "Bilal Hussain", "0321-9876543", "G-11, Islamabad", "bilal@kiryana.pk", "bilal123"),
        ]

        for shop_name, owner_name, phone, address, email, password in shops_data:
            shop = Shop(name=shop_name, owner_name=owner_name, phone=phone, address=address)
            db.session.add(shop)
            db.session.flush()

            owner = User(shop_id=shop.id, email=email, role=UserRole.owner)
            owner.set_password(password)
            db.session.add(owner)

            # Add all global products to this shop
            for p in products:
                sp = ShopProduct(
                    shop_id=shop.id, product_id=p.id,
                    name=p.name, price=p.default_price, is_custom=False
                )
                db.session.add(sp)
            db.session.flush()
            print(f"✅ Shop '{shop_name}' created: {email} / {password}")

            seed_shop_data(shop, products)

        db.session.commit()
        print("\n🎉 Seed complete!")
        print("\nLogin credentials:")
        print("  Admin:  admin@kiryana.pk / admin123")
        print("  Shop 1: ahmed@kiryana.pk / ahmed123")
        print("  Shop 2: bilal@kiryana.pk / bilal123")


def seed_shop_data(shop, global_products):
    """Add customers, suppliers, sales, expenses for a shop."""
    # Shop products (already added by caller)
    shop_products = ShopProduct.query.filter_by(shop_id=shop.id).all()
    sp_map = {sp.product_id: sp for sp in shop_products}

    # ── Customers ──
    customers_data = [
        ("Usman Ali", "0311-1111111", 8000),
        ("Farhan Sheikh", "0322-2222222", 5000),
        ("Imran Malik", "0333-3333333", 3000),
        ("Zara Bibi", "0344-4444444", 10000),
        ("Khalid Mehmood", "0355-5555555", 6000),
    ]
    customers = []
    for name, phone, limit in customers_data:
        c = Customer(shop_id=shop.id, name=name, phone=phone, credit_limit=Decimal(str(limit)))
        db.session.add(c)
        customers.append(c)
    db.session.flush()

    # ── Suppliers ──
    suppliers_data = [
        ("Karachi Wholesale Market", "0212-1234567", 14),
        ("Daily Bread Distributor", "0300-7777777", 3),
        ("Pepsi & Cola Agency", "0321-8888888", 7),
    ]
    suppliers = []
    for name, phone, terms in suppliers_data:
        s = Supplier(shop_id=shop.id, name=name, phone=phone, payment_terms_days=terms)
        db.session.add(s)
        suppliers.append(s)
    db.session.flush()

    # Add some supplier deliveries
    for i, supplier in enumerate(suppliers):
        amounts = [random.randint(3000, 15000) for _ in range(3)]
        bal = Decimal('0')
        for amt in amounts:
            amt_d = Decimal(str(amt))
            bal += amt_d
            entry = SupplierLedger(
                supplier_id=supplier.id,
                amount=amt_d,
                type=SupplierLedgerType.delivery,
                balance_after=bal,
                note='Stock delivery',
                due_date=date.today() + timedelta(days=supplier.payment_terms_days - random.randint(0, 5))
            )
            db.session.add(entry)
        # Partial payment
        payment = Decimal(str(random.randint(1000, int(bal * Decimal('0.6')))))
        bal -= payment
        db.session.add(SupplierLedger(
            supplier_id=supplier.id, amount=payment,
            type=SupplierLedgerType.payment, balance_after=bal, note='Partial payment'
        ))
    db.session.flush()

    # ── 14 days of Sales ──
    for days_ago in range(13, -1, -1):
        sale_date = datetime.utcnow() - timedelta(days=days_ago)
        num_sales = random.randint(8, 20)

        for _ in range(num_sales):
            is_udhaar = random.random() < 0.2
            customer = random.choice(customers) if is_udhaar else None
            num_items = random.randint(1, 5)
            chosen_sps = random.sample(shop_products, min(num_items, len(shop_products)))
            loose = Decimal(str(random.randint(0, 1) * random.randint(20, 200)))

            total = loose
            sale_items = []
            for sp in chosen_sps:
                qty = Decimal(str(random.randint(1, 3)))
                subtotal = qty * sp.price
                total += subtotal
                sale_items.append((sp, qty, subtotal))

            sale = Sale(
                shop_id=shop.id,
                customer_id=customer.id if customer else None,
                total_amount=total,
                payment_type=PaymentType.udhaar if is_udhaar else PaymentType.cash,
                loose_amount=loose,
                created_at=sale_date.replace(hour=random.randint(8, 21), minute=random.randint(0, 59))
            )
            db.session.add(sale)
            db.session.flush()

            for sp, qty, subtotal in sale_items:
                db.session.add(SaleItem(
                    sale_id=sale.id, shop_product_id=sp.id,
                    name_snapshot=sp.name, qty=qty, unit_price=sp.price, subtotal=subtotal
                ))

            # Udhaar ledger entry
            if is_udhaar and customer:
                prev = CustomerLedger.query.filter_by(customer_id=customer.id)\
                    .order_by(CustomerLedger.id.desc()).first()
                prev_bal = prev.balance_after if prev else Decimal('0')
                new_bal = prev_bal + total
                db.session.add(CustomerLedger(
                    customer_id=customer.id, sale_id=sale.id,
                    amount=total, type=LedgerType.credit,
                    balance_after=new_bal, note=f'Sale #{sale.id}',
                    created_at=sale.created_at
                ))

    db.session.flush()

    # Add some payments against udhaar
    for customer in customers[:3]:
        last = CustomerLedger.query.filter_by(customer_id=customer.id)\
            .order_by(CustomerLedger.id.desc()).first()
        if last and last.balance_after > 0:
            payment = min(last.balance_after * Decimal('0.4'), Decimal('2000'))
            db.session.add(CustomerLedger(
                customer_id=customer.id, amount=payment,
                type=LedgerType.payment,
                balance_after=last.balance_after - payment,
                note='Cash payment received'
            ))

    # ── Expenses (last 30 days) ──
    expense_data = [
        (ExpenseCategory.rent, 15000, 1, 'Monthly rent'),
        (ExpenseCategory.electricity, 4500, 15, 'KESC bill'),
        (ExpenseCategory.salary, 12000, 1, 'Staff salary'),
        (ExpenseCategory.stock, 8000, 5, 'Restocking'),
        (ExpenseCategory.stock, 6500, 10, 'Weekly restock'),
        (ExpenseCategory.other, 800, 7, 'Bags & packaging'),
    ]
    for cat, amt, days_ago, note in expense_data:
        db.session.add(Expense(
            shop_id=shop.id,
            category=cat,
            amount=Decimal(str(amt)),
            note=note,
            expense_date=date.today() - timedelta(days=days_ago)
        ))

    # ── Daily Reconciliation (last 7 days) ──
    for days_ago in range(6, 0, -1):
        recon_date = date.today() - timedelta(days=days_ago)
        recorded = db.session.query(db.func.sum(Sale.total_amount)).filter(
            Sale.shop_id == shop.id,
            Sale.payment_type == PaymentType.cash,
            db.func.date(Sale.created_at) == recon_date
        ).scalar() or Decimal('0')

        physical = Decimal(str(recorded)) + Decimal(str(random.randint(100, 800)))
        db.session.add(DailyReconciliation(
            shop_id=shop.id,
            recon_date=recon_date,
            physical_cash=physical,
            recorded_sales=Decimal(str(recorded)),
            difference=physical - Decimal(str(recorded)),
            note='End of day count'
        ))

    db.session.flush()
    print(f"   → Shop data seeded for '{shop.name}'")


if __name__ == '__main__':
    seed()
