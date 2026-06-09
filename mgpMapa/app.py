import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate

from db import db

load_dotenv()

login_manager = LoginManager()
migrate = Migrate()


def create_app():
    app = Flask(__name__)

    app.secret_key = os.getenv('SECRET_KEY', 'fallback-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///database.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)
    app.config['REMEMBER_COOKIE_SECURE'] = os.getenv('FLASK_DEBUG', '1') == '0'
    app.config['REMEMBER_COOKIE_HTTPONLY'] = True
    app.config['UPLOAD_FOLDER'] = 'static/uploads'

    # Redis sessions
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
    app.config['SESSION_TYPE'] = 'redis'
    app.config['SESSION_PERMANENT'] = False
    app.config['SESSION_USE_SIGNER'] = True
    try:
        import redis
        app.config['SESSION_REDIS'] = redis.from_url(redis_url)
    except Exception as e:
        print(f'Redis not available, using filesystem sessions: {e}')
        app.config['SESSION_TYPE'] = 'filesystem'

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    try:
        from flask_session import Session
        Session(app)
    except ImportError:
        pass

    # Register blueprints
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.home import home_bp
    from routes.users import users_bp
    from routes.registos import registos_bp
    from routes.faturas import faturas_bp
    from routes.ferias import ferias_bp
    from routes.orcamentos import orcamentos_bp
    from routes.horas import horas_bp
    from routes.mensagens import mensagens_bp
    from routes.obras import obras_bp
    from routes.push import push_bp

    for bp in [auth_bp, dashboard_bp, home_bp, users_bp, registos_bp,
               faturas_bp, ferias_bp, orcamentos_bp, horas_bp,
               mensagens_bp, obras_bp, push_bp]:
        app.register_blueprint(bp)

    # User loader
    from models import Usuario

    @login_manager.user_loader
    def user_loader(user_id):
        return db.session.query(Usuario).filter_by(id=user_id).first()

    # Inject org context into all templates
    from flask import g
    from flask_login import current_user
    from models import Organizacao

    @app.context_processor
    def inject_org():
        try:
            if current_user.is_authenticated and current_user.org_id:
                org = db.session.query(Organizacao).filter_by(id=current_user.org_id).first()
                tipo = getattr(org, 'tipo_negocio', 'cliente') if org else 'cliente'
                return dict(
                    org_nome=org.nome if org else 'A minha Organização',
                    org=org,
                    tem_mapa=tipo != 'espaco'
                )
            return dict(org_nome='A minha Organização', org=None, tem_mapa=True)
        except Exception:
            return dict(org_nome='A minha Organização', org=None, tem_mapa=True)

    return app