import hashlib
import os
import smtplib
import threading
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from werkzeug.security import generate_password_hash

GMAIL_USER = os.getenv('GMAIL_USER', '')
GMAIL_PASS = os.getenv('GMAIL_PASS', '')

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx', 'xlsx'}

VAPID_PUBLIC_KEY = os.getenv('VAPID_PUBLIC_KEY', '')
_vapid_pem_path = os.path.join(os.path.dirname(__file__), 'vapid_private.pem')
VAPID_CLAIMS = {'sub': os.getenv('VAPID_CLAIMS_EMAIL', 'mailto:admin@example.com')}


def _load_vapid_private_key():
    if os.path.exists(_vapid_pem_path):
        try:
            from cryptography.hazmat.primitives.serialization import load_pem_private_key
            import base64
            with open(_vapid_pem_path, 'rb') as f:
                pem = f.read()
            key = load_pem_private_key(pem, password=None)
            d = key.private_numbers().private_value.to_bytes(32, 'big')
            return base64.urlsafe_b64encode(d).rstrip(b'=').decode()
        except Exception as e:
            print(f'VAPID PEM load error: {e}')
    return os.getenv('VAPID_PRIVATE_KEY', '').replace('\\n', '\n')


VAPID_PRIVATE_KEY = _load_vapid_private_key()


def hash_password(txt):
    return generate_password_hash(txt)


def legacy_sha256(txt):
    return hashlib.sha256(txt.encode('utf-8')).hexdigest()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def converter_data(d):
    if d:
        from datetime import datetime
        try:
            return datetime.strptime(d, '%Y-%m-%d').strftime('%d/%m/%Y')
        except Exception:
            return d
    return None


def send_welcome_email(to_email, nome, org_nome, username, password_temp, codigo=None, criado_por=None):
    try:
        msg = MIMEMultipart('alternative')
        msg["Subject"] = f"Bem-vindo à plataforma {org_nome}"
        msg["From"] = formataddr((str(Header("GestãoPro", "utf-8")), GMAIL_USER))
        msg["To"] = to_email
        criado_por_block = (
            f'<div style="background:#e8f0fe;border:1px solid #b3c6f7;border-radius:8px;padding:10px 14px;margin-bottom:20px;">'
            f'<p style="font-size:13px;color:#3c5a99;margin:0;">Conta criada pelo administrador <strong>{criado_por}</strong>.</p>'
            f'</div>'
        ) if criado_por else ""
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;">
            <div style="background:#2d3a6e;padding:28px 32px;text-align:center;">
                <p style="color:white;font-size:20px;font-weight:bold;margin:0 0 4px;">Bem-vindo à plataforma</p>
                <p style="color:rgba(255,255,255,0.75);font-size:13px;margin:0;">{org_nome}</p>
            </div>
            <div style="background:white;padding:28px 32px;">
                <p style="font-size:15px;color:#1a1a1a;margin:0 0 12px;">Olá <strong>{nome}</strong>,</p>
                <p style="font-size:14px;color:#555;line-height:1.6;margin:0 0 20px;">A tua conta foi criada com sucesso na plataforma <strong>{org_nome}</strong>. Aqui estão os teus dados de acesso:</p>
                <div style="background:#eaf3de;border:1px solid #c0dd97;border-radius:8px;padding:20px 24px;margin-bottom:20px;">
                    <p style="font-size:11px;color:#639922;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 4px;">Utilizador</p>
                    <p style="font-size:20px;font-weight:bold;color:#2d3a6e;margin:0 0 16px;">{username}</p>
                    <p style="font-size:11px;color:#639922;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 4px;">Password temporária</p>
                    <p style="font-size:20px;font-weight:bold;color:#2d3a6e;margin:0;">{password_temp}</p>
                </div>
                {f'<div style="background:#e8f0fe;border:1px solid #b3c6f7;border-radius:8px;padding:20px 24px;margin-bottom:20px;"><p style="font-size:11px;color:#3c5a99;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 8px;">Código de verificação</p><p style="font-size:32px;font-weight:bold;color:#1a3a8f;margin:0;letter-spacing:8px;">' + (codigo or '') + '</p></div>' if codigo else ''}
                <div style="background:#faeeda;border:1px solid #fac775;border-radius:8px;padding:10px 14px;margin-bottom:20px;">
                    <p style="font-size:13px;color:#854f0b;margin:0;">Por segurança, altera a tua password no primeiro login.</p>
                </div>
                {criado_por_block}
                <p style="font-size:14px;color:#555;line-height:1.6;margin:0;">Se tiveres alguma questão, responde a este email.<br>Bem-vindo à equipa!</p>
            </div>
            <div style="background:#f8f8f8;border-top:1px solid #eee;padding:16px 32px;text-align:center;">
                <p style="font-size:12px;color:#aaa;margin:0;">© {org_nome} — Plataforma de Gestão</p>
            </div>
        </div>
        """
        msg.attach(MIMEText(html, 'html'))
        with smtplib.SMTP("smtp.gmail.com", 587) as connection:
            connection.starttls()
            connection.login(user=GMAIL_USER, password=GMAIL_PASS)
            connection.send_message(msg)
        print(f"Email enviado para {to_email}")
    except Exception as e:
        print(f"Erro email: {e}")


def save_notificacao(db, user_id, org_id, title, body, url='/'):
    from models import Notificacao
    try:
        db.session.add(Notificacao(user_id=user_id, org_id=org_id, titulo=title, corpo=body, url=url))
        db.session.commit()
    except Exception as e:
        print(f'save_notificacao error: {e}')


def send_push_to_user(app, user_id, title, body, url='/'):
    with app.app_context():
        from db import db
        from models import Usuario, PushSubscription
        user = db.session.query(Usuario).filter_by(id=user_id).first()
        org_id = user.org_id if user else None
        save_notificacao(db, user_id, org_id, title, body, url)
        subs = db.session.query(PushSubscription).filter_by(user_id=user_id).all()
        if not subs or not VAPID_PUBLIC_KEY:
            return
        try:
            from pywebpush import webpush
        except ImportError:
            print('pywebpush not installed')
            return
        import json
        data = json.dumps({'title': title, 'body': body, 'url': url})
        for sub in subs:
            try:
                webpush(
                    subscription_info={'endpoint': sub.endpoint, 'keys': {'p256dh': sub.p256dh, 'auth': sub.auth}},
                    data=data,
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims=VAPID_CLAIMS
                )
                print(f'Push OK → user {user_id}')
            except Exception as e:
                print(f'Push error user {user_id}: {e}')
                if any(c in str(e) for c in ['410', '404', 'expired', 'unsubscribed']):
                    db.session.delete(sub)
                    db.session.commit()


def bg_push(app, user_id, title, body, url='/'):
    threading.Thread(
        target=send_push_to_user,
        args=(app, user_id, title, body, url),
        daemon=True
    ).start()