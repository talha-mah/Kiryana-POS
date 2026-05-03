from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import enum

db = SQLAlchemy()

# ─────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────

class UserRole(enum.Enum):
    admin = 'admin'
    owner = 'owner'

class RegistrationStatus(enum.Enum):
    pending = 'pending'
    approved = 'approved'
    rejected = 'rejected'

class PaymentType(enum.Enum):
    cash = 'cash'
    udhaar = 'udhaar'

class LedgerType(enum.Enum):
    credit = 'credit'
    payment = 'payment'

class SupplierLedgerType(enum.Enum):
    delivery = 'delivery'
    payment = 'payment'

class ExpenseCategory(enum.Enum):
    rent = 'rent'
    electricity = 'electricity'
    salary = 'salary'
    stock = 'stock'
    other = 'other'

# ─────────────────────────────────────────────────────────────
# NORMALISATION NOTES (for DB course)
# Functional Dependencies for key tables:
#
# Sale: sale_id → shop_id, customer_id, total_amount, payment_type, loose_amount, created_at
#   No partial or transitive dependencies → BCNF ✓
#
# Customer_Ledger: ledger_id → customer_id, sale_id, amount, type, balance_after, note, created_at
#   balance_after is derived but stored for performance (audit trail pattern) → BCNF ✓
#
# Sale_Item: item_id → sale_id, shop_product_id, name_snapshot, qty, unit_price, subtotal
#   name_snapshot intentionally denormalised (product name may change after sale) → BCNF ✓
#
# Shop_Product: id → shop_id, product_id, name, price, is_custom, is_active
#   shop_id + product_id is a candidate key for non-custom items → BCNF ✓
# ─────────────────────────────────────────────────────────────

class Shop(db.Model):
    __tablename__ = 'shop'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    owner_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    users = db.relationship('User', backref='shop', lazy='dynamic')
    customers = db.relationship('Customer', backref='shop', lazy='dynamic')
    suppliers = db.relationship('Supplier', backref='shop', lazy='dynamic')
    sales = db.relationship('Sale', backref='shop', lazy='dynamic')
    expenses = db.relationship('Expense', backref='shop', lazy='dynamic')
    reconciliations = db.relationship('DailyReconciliation', backref='shop', lazy='dynamic')
    shop_products = db.relationship('ShopProduct', backref='shop', lazy='dynamic')

    def __repr__(self):
        return f'<Shop {self.name}>'


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=True)  # null = Admin
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.owner)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == UserRole.admin

    def __repr__(self):
        return f'<User {self.email}>'


class ShopRegistrationRequest(db.Model):
    __tablename__ = 'shop_registration_request'
    id = db.Column(db.Integer, primary_key=True)
    shop_name = db.Column(db.String(120), nullable=False)
    owner_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    status = db.Column(db.Enum(RegistrationStatus), nullable=False, default=RegistrationStatus.pending, index=True)
    admin_note = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = db.Column(db.DateTime)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    reviewed_by = db.relationship('User', foreign_keys=[reviewed_by_id])

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def __repr__(self):
        return f'<ShopRegistrationRequest {self.email} {self.status.value}>'


class Product(db.Model):
    """Global shared product catalog managed by Admin."""
    __tablename__ = 'product'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    brand = db.Column(db.String(100))
    unit = db.Column(db.String(30), default='piece')
    default_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    shop_products = db.relationship('ShopProduct', backref='product', lazy='dynamic')

    def __repr__(self):
        return f'<Product {self.name}>'


class ShopProduct(db.Model):
    """Shop-specific product list (references global catalog or custom items)."""
    __tablename__ = 'shop_product'
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    name = db.Column(db.String(150), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    is_custom = db.Column(db.Boolean, default=False)  # True = shop added, not from catalog
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    sale_items = db.relationship('SaleItem', backref='shop_product', lazy='dynamic')

    def __repr__(self):
        return f'<ShopProduct {self.name}>'


class Customer(db.Model):
    __tablename__ = 'customer'
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    credit_limit = db.Column(db.Numeric(10, 2), default=5000)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    ledger_entries = db.relationship('CustomerLedger', backref='customer', lazy='dynamic',
                                      order_by='CustomerLedger.created_at')
    sales = db.relationship('Sale', backref='customer', lazy='dynamic')

    @property
    def current_balance(self):
        credits = sum(
            entry.amount for entry in self.ledger_entries
            if entry.type == LedgerType.credit
        )
        payments = sum(
            entry.amount for entry in self.ledger_entries
            if entry.type == LedgerType.payment
        )
        return max(credits - payments, 0)

    def __repr__(self):
        return f'<Customer {self.name}>'


class CustomerLedger(db.Model):
    __tablename__ = 'customer_ledger'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False, index=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    type = db.Column(db.Enum(LedgerType), nullable=False)
    balance_after = db.Column(db.Numeric(10, 2), nullable=False)
    note = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<CustomerLedger {self.type} {self.amount}>'


class Sale(db.Model):
    __tablename__ = 'sale'
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=True)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_type = db.Column(db.Enum(PaymentType), nullable=False, default=PaymentType.cash)
    loose_amount = db.Column(db.Numeric(10, 2), default=0)  # undocumented petty items
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    items = db.relationship('SaleItem', backref='sale', lazy='dynamic', cascade='all, delete-orphan')
    ledger_entries = db.relationship('CustomerLedger', backref='sale', lazy='dynamic')

    def __repr__(self):
        return f'<Sale #{self.id} {self.total_amount}>'


class SaleItem(db.Model):
    __tablename__ = 'sale_item'
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False, index=True)
    shop_product_id = db.Column(db.Integer, db.ForeignKey('shop_product.id'), nullable=True)
    name_snapshot = db.Column(db.String(150), nullable=False)  # denormalised intentionally
    qty = db.Column(db.Numeric(10, 2), nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)

    def __repr__(self):
        return f'<SaleItem {self.name_snapshot}>'


class Supplier(db.Model):
    __tablename__ = 'supplier'
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    payment_terms_days = db.Column(db.Integer, default=7)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    ledger_entries = db.relationship('SupplierLedger', backref='supplier', lazy='dynamic',
                                      order_by='SupplierLedger.created_at')

    @property
    def current_balance(self):
        deliveries = sum(
            entry.amount for entry in self.ledger_entries
            if entry.type == SupplierLedgerType.delivery
        )
        payments = sum(
            entry.amount for entry in self.ledger_entries
            if entry.type == SupplierLedgerType.payment
        )
        return max(deliveries - payments, 0)

    def __repr__(self):
        return f'<Supplier {self.name}>'


class SupplierLedger(db.Model):
    __tablename__ = 'supplier_ledger'
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=False, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    type = db.Column(db.Enum(SupplierLedgerType), nullable=False)
    balance_after = db.Column(db.Numeric(10, 2), nullable=False)
    note = db.Column(db.String(255))
    due_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<SupplierLedger {self.type} {self.amount}>'


class Expense(db.Model):
    __tablename__ = 'expense'
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False, index=True)
    category = db.Column(db.Enum(ExpenseCategory), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    note = db.Column(db.String(255))
    expense_date = db.Column(db.Date, default=date.today, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Expense {self.category} {self.amount}>'


class DailyReconciliation(db.Model):
    __tablename__ = 'daily_reconciliation'
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False, index=True)
    recon_date = db.Column(db.Date, nullable=False, default=date.today)
    physical_cash = db.Column(db.Numeric(10, 2), nullable=False)
    recorded_sales = db.Column(db.Numeric(10, 2), nullable=False)
    difference = db.Column(db.Numeric(10, 2), nullable=False)  # undocumented sales
    note = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('shop_id', 'recon_date', name='uq_shop_recon_date'),
    )

    def __repr__(self):
        return f'<DailyReconciliation {self.recon_date}>'
