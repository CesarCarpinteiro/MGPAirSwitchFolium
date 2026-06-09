import random
import threading

import requests
from flask import Blueprint, redirect, render_template, request, session as flask_session, url_for
from flask_login import login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from db import db
from models import Organizacao, TipoServico, Usuario
from utils import hash_password, legacy_sha256, send_welcome_email, GMAIL_USER

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html', error=False)
    nome = request.form.get('nomeForm', '').strip()
    senha = request.form.get('senhaForm', '').strip()
    if not nome or not senha:
        return render_template('login.html', error=True)
    user = db.session.query(Usuario).filter_by(nome=nome).first()
    if not user:
        return render_template('login.html', error=True)
    if check_password_hash(user.senha, senha):
        login_user(user, remember=True)
        return redirect(url_for('home.home'))
    if user.senha == legacy_sha256(senha):
        user.senha = generate_password_hash(senha)
        db.session.commit()
        login_user(user, remember=True)
        return redirect(url_for('home.home'))
    return render_template('login.html', error=True)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@auth_bp.route('/setup', methods=['GET', 'POST'])
def setup():
    if request.method == 'POST':
        if request.form.get('step') == 'verify':
            code_input = request.form.get('codigo', '').strip()
            if code_input == flask_session.get('setup_code'):
                flask_session.pop('setup_code', None)
                return redirect(url_for('home.home'))
            else:
                return render_template('setup.html', error=False, show_popup=True, code_error=True)

        nome = request.form.get('nomeForm')
        senha = request.form.get('senhaForm')
        email = request.form.get('email')
        telefone = request.form.get('telefone')
        nome_completo = request.form.get('nome_completo')
        cargo = request.form.get('cargo')
        org_nome = request.form.get('org_nome')
        pais = request.form.get('pais')
        org_telefone = request.form.get('org_telefone')
        tipo_negocio = request.form.get('tipo_negocio', 'cliente')

        if nome and senha:
            if db.session.query(Usuario).filter_by(nome=nome).first():
                return render_template('setup.html', error=True, show_popup=False)

            try:
                resp = requests.get('http://www.randomnumberapi.com/api/v1.0/random?min=100000&max=999999&count=1', timeout=5)
                code = str(resp.json()[0])
            except Exception:
                code = str(random.randint(100000, 999999))

            from datetime import datetime
            org = Organizacao(nome=org_nome, pais=pais, telefone=org_telefone,
                              created_at=datetime.now().strftime('%d/%m/%Y'),
                              tipo_negocio=tipo_negocio)
            db.session.add(org)
            db.session.flush()
            admin = Usuario(nome=nome, senha=hash_password(senha), email=email, telefone=telefone,
                            nome_completo=nome_completo, cargo=cargo, is_admin=True, org_id=org.id)
            db.session.add(admin)
            db.session.commit()

            for t in ['Instalação AC', 'Limpeza / Manutenção AC']:
                db.session.add(TipoServico(nome=t, org_id=org.id))
            db.session.commit()

            login_user(admin)
            flask_session['setup_code'] = code

            if email:
                try:
                    send_welcome_email(
                        to_email=email,
                        nome=nome_completo or nome,
                        org_nome=org_nome or 'A minha Organização',
                        username=nome,
                        password_temp=senha,
                        codigo=code
                    )
                except Exception as e:
                    print(f'Erro email setup: {e}')

            return render_template('setup.html', error=False, show_popup=True, code_error=False)

    return render_template('setup.html', error=False, show_popup=False)


@auth_bp.route('/forgot_password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    email = data.get('email', '').strip()
    user = db.session.query(Usuario).filter_by(email=email).first()
    if not user:
        from flask import jsonify
        return jsonify({'ok': False, 'error': 'Email não encontrado.'})

    try:
        resp = requests.get('http://www.randomnumberapi.com/api/v1.0/random?min=100000&max=999999&count=1', timeout=5)
        code = str(resp.json()[0])
    except Exception:
        code = str(random.randint(100000, 999999))

    flask_session['reset_code'] = code
    flask_session['reset_user_id'] = user.id

    import smtplib
    from email.header import Header
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.utils import formataddr
    try:
        msg = MIMEMultipart('alternative')
        msg["Subject"] = "Recuperação de password"
        msg["From"] = formataddr((str(Header("GestãoPro", "utf-8")), GMAIL_USER))
        msg["To"] = email
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;">
            <div style="background:#2d3a6e;padding:28px 32px;text-align:center;">
                <p style="color:white;font-size:20px;font-weight:bold;margin:0;">Recuperação de Password</p>
            </div>
            <div style="background:white;padding:28px 32px;">
                <p style="font-size:15px;color:#1a1a1a;margin:0 0 16px;">Olá {user.nome},</p>
                <p style="font-size:14px;color:#555;margin:0 0 20px;">Recebemos um pedido para redefinir a tua password. Usa o código abaixo:</p>
                <div style="background:#e8f0fe;border:1px solid #b3c6f7;border-radius:8px;padding:24px;text-align:center;margin-bottom:20px;">
                    <p style="font-size:11px;color:#3c5a99;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 8px;">Código de verificação</p>
                    <p style="font-size:36px;font-weight:bold;color:#1a3a8f;margin:0;letter-spacing:10px;">{code}</p>
                </div>
                <p style="font-size:13px;color:#888;margin:0;">Se não pediste esta alteração, ignora este email.</p>
            </div>
            <div style="background:#f8f8f8;border-top:1px solid #eee;padding:16px 32px;text-align:center;">
                <p style="font-size:12px;color:#aaa;margin:0;">Plataforma de Gestão de Serviços</p>
            </div>
        </div>
        """
        msg.attach(MIMEText(html, 'html'))
        from utils import GMAIL_PASS
        with smtplib.SMTP("smtp.gmail.com", 587) as connection:
            connection.starttls()
            connection.login(user=GMAIL_USER, password=GMAIL_PASS)
            connection.send_message(msg)
    except Exception as e:
        print(f'Erro email reset: {e}')

    from flask import jsonify
    return jsonify({'ok': True})


@auth_bp.route('/reset_password', methods=['POST'])
def reset_password():
    from flask import jsonify
    data = request.get_json()
    code = data.get('code', '').strip()
    new_password = data.get('password', '')

    if code != flask_session.get('reset_code'):
        return jsonify({'ok': False, 'error': 'Código incorreto. Tenta novamente.'})

    user_id = flask_session.get('reset_user_id')
    user = db.session.query(Usuario).filter_by(id=user_id).first()
    if not user:
        return jsonify({'ok': False, 'error': 'Utilizador não encontrado.'})

    user.senha = generate_password_hash(new_password)
    db.session.commit()
    flask_session.pop('reset_code', None)
    flask_session.pop('reset_user_id', None)

    return jsonify({'ok': True})