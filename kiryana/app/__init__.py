from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from config import config
from app.models import db, User

login_manager = LoginManager()
migrate = Migrate()

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from app.auth.routes import auth_bp
    from app.pos.routes import pos_bp
    from app.udhaar.routes import udhaar_bp
    from app.supplier.routes import supplier_bp
    from app.reconciliation.routes import recon_bp
    from app.expenses.routes import expenses_bp
    from app.dashboard.routes import dashboard_bp
    from app.admin.routes import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(pos_bp)
    app.register_blueprint(udhaar_bp)
    app.register_blueprint(supplier_bp)
    app.register_blueprint(recon_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp)

    return app
