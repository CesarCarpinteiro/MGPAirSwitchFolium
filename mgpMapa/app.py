import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, request
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFError, CSRFProtect, generate_csrf

from db import db

load_dotenv()

login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()


APP_VERSION = os.getenv('APP_VERSION', '1.0')
CHAVES_EXPOSTAS = {'lancode', 'fallback-secret-key'}  # já estiveram no repositório público

def create_app():
    app = Flask(__name__)

    # A SECRET_KEY assina as sessões e os cookies "lembrar-me": tem de ser longa, aleatória e secreta
    secret_key = os.getenv('SECRET_KEY', '')
    if len(secret_key) < 32 or secret_key in CHAVES_EXPOSTAS:
        raise RuntimeError('SECRET_KEY em falta ou insegura no .env. Gere uma nova com: '
                           'python -c "import secrets; print(secrets.token_hex(32))"')
    app.secret_key = secret_key
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

    # CSRF: todos os POST precisam do token (static/csrf.js junta-o a formulários e fetch); válido enquanto durar a sessão
    app.config['WTF_CSRF_TIME_LIMIT'] = None
    csrf.init_app(app)

    @app.after_request
    def injetar_csrf(resposta):
        """Põe o token, o csrf.js e o ícone da aba no <head> de todas as páginas HTML (as páginas não partilham um template base)."""
        if resposta.mimetype == 'text/html' and not resposta.direct_passthrough and resposta.status_code < 400:
            html = resposta.get_data(as_text=True)
            if '</head>' in html:
                extra = f'<meta name="csrf-token" content="{generate_csrf()}"><script src="/static/csrf.js"></script>'
                if 'rel="icon"' not in html:
                    extra += '<link rel="icon" type="image/png" href="/static/icons/icon-64.png?v=2">'
                resposta.set_data(html.replace('</head>', extra + '</head>', 1))
        return resposta

    @app.route('/favicon.ico')
    def favicon():
        # Para os pedidos diretos do browser (ex.: ao abrir um PDF)
        return app.send_static_file('icons/icon-64.png')

    @app.errorhandler(CSRFError)
    def csrf_invalido(e):
        mensagem = 'A sessão expirou ou o pedido não é válido. Recarregue a página e tente outra vez.'
        if 'application/json' in request.headers.get('Accept', '') or request.is_json:
            return jsonify({'ok': False, 'mensagem': mensagem}), 400
        flash(mensagem, 'error')
        return redirect(request.referrer or '/')

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
        return db.session.query(Usuario).filter_by(id=int(user_id)).first()

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
                    tem_mapa=tipo != 'espaco',
                    app_version=APP_VERSION
                )
            return dict(org_nome='A minha Organização', org=None, tem_mapa=True, app_version=APP_VERSION)
        except Exception:
            return dict(org_nome='A minha Organização', org=None, tem_mapa=True, app_version=APP_VERSION)

    import click

    @app.cli.command('enviar-lembretes')
    @click.option('--simular', is_flag=True, help='Mostra o que seria enviado, sem enviar nem marcar.')
    def enviar_lembretes_cmd(simular):
        """SMS de manutenção aos clientes com 8 e 10 meses desde o último serviço (correr 1x por dia)."""
        from lembretes import enviar_lembretes
        enviar_lembretes(simular=simular)

    return app