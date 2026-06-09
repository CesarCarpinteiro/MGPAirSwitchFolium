import hashlib

from flask import Blueprint, jsonify, render_template_string, request, send_from_directory
from flask_login import current_user, login_required

from db import db
from models import Mensagem, Notificacao, Organizacao, PushSubscription
from utils import VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY, VAPID_CLAIMS, save_notificacao

push_bp = Blueprint('push', __name__)


@push_bp.route('/push/vapid-public-key')
def push_vapid_key():
    return jsonify({'publicKey': VAPID_PUBLIC_KEY})


@push_bp.route('/push/test')
@login_required
def push_test():
    try:
        from pywebpush import webpush
        import json
        subs = db.session.query(PushSubscription).filter_by(user_id=current_user.id).all()
        if not subs:
            return jsonify({'ok': False, 'error': 'Sem subscrições para este user'})
        results = []
        for sub in subs:
            try:
                webpush(
                    subscription_info={'endpoint': sub.endpoint, 'keys': {'p256dh': sub.p256dh, 'auth': sub.auth}},
                    data=json.dumps({'title': '🔔 Teste', 'body': 'As notificações estão a funcionar!', 'url': '/'}),
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims=VAPID_CLAIMS
                )
                results.append({'ok': True, 'endpoint': sub.endpoint[:50]})
            except Exception as e:
                results.append({'ok': False, 'error': str(e), 'endpoint': sub.endpoint[:50]})
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@push_bp.route('/push/subscribe', methods=['POST'])
@login_required
def push_subscribe():
    data = request.get_json()
    endpoint = data.get('endpoint')
    p256dh = data.get('keys', {}).get('p256dh')
    auth = data.get('keys', {}).get('auth')
    if not endpoint or not p256dh or not auth:
        return jsonify({'ok': False})
    db.session.query(PushSubscription).filter_by(user_id=current_user.id).delete()
    db.session.add(PushSubscription(
        user_id=current_user.id, org_id=current_user.org_id,
        endpoint=endpoint, p256dh=p256dh, auth=auth
    ))
    db.session.commit()
    return jsonify({'ok': True})


@push_bp.route('/push/clear', methods=['POST'])
@login_required
def push_clear():
    db.session.query(PushSubscription).filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({'ok': True})


@push_bp.route('/push/unsubscribe', methods=['POST'])
@login_required
def push_unsubscribe():
    data = request.get_json()
    endpoint = data.get('endpoint')
    sub = db.session.query(PushSubscription).filter_by(user_id=current_user.id, endpoint=endpoint).first()
    if sub:
        db.session.delete(sub)
        db.session.commit()
    return jsonify({'ok': True})


@push_bp.route('/api/notificacoes')
@login_required
def api_notificacoes():
    notifs = db.session.query(Notificacao).filter_by(
        user_id=current_user.id, lida=False
    ).order_by(Notificacao.id.desc()).limit(20).all()
    return jsonify([{
        'id': n.id, 'titulo': n.titulo, 'corpo': n.corpo,
        'url': n.url, 'criada_em': n.criada_em
    } for n in notifs])


@push_bp.route('/api/notificacoes/lida/<int:nid>', methods=['POST'])
@login_required
def api_notificacao_lida(nid):
    n = db.session.query(Notificacao).filter_by(id=nid, user_id=current_user.id).first()
    if n:
        n.lida = True
        db.session.commit()
    return jsonify({'ok': True})


@push_bp.route('/api/notificacoes/lidas-todas', methods=['POST'])
@login_required
def api_notificacoes_lidas_todas():
    db.session.query(Notificacao).filter_by(user_id=current_user.id, lida=False).update({'lida': True})
    db.session.commit()
    return jsonify({'ok': True})


@push_bp.route('/api/mensagens/estado')
@login_required
def api_mensagens_estado():
    if current_user.is_admin:
        rows = db.session.query(Mensagem.id).filter_by(org_id=current_user.org_id).all()
    else:
        rows = db.session.query(Mensagem.id).filter_by(
            org_id=current_user.org_id, user_id=current_user.id).all()
    fp = hashlib.md5('|'.join(str(r.id) for r in rows).encode()).hexdigest()
    return jsonify({'fp': fp})


@push_bp.route('/api/ferias/estado')
@login_required
def api_ferias_estado():
    from models import Ferias
    if current_user.is_admin:
        rows = db.session.query(Ferias.id, Ferias.estado).filter_by(org_id=current_user.org_id).all()
    else:
        rows = db.session.query(Ferias.id, Ferias.estado).filter_by(
            org_id=current_user.org_id, user_id=current_user.id).all()
    fp = hashlib.md5('|'.join(f'{r.id}:{r.estado}' for r in rows).encode()).hexdigest()
    return jsonify({'fp': fp})


@push_bp.route('/politica-cookies')
def politica_cookies():
    org = db.session.query(Organizacao).filter_by(id=current_user.org_id).first() if current_user.is_authenticated else None
    org_nome = org.nome if org else 'GestãoPro'
    return render_template_string('''<!DOCTYPE html>
<html lang="pt"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Política de Cookies</title>
<style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:Arial,sans-serif;background:#f0f2f5;padding-bottom:60px}
.header{background:linear-gradient(135deg,#2d3a6e,#4a5fa8);padding:14px 24px;color:white}
.header h1{font-size:1.3em;font-weight:700}.header a{color:rgba(255,255,255,0.85);font-size:0.85em;text-decoration:none}
.content{max-width:700px;margin:32px auto;padding:0 20px}
.card{background:white;border-radius:12px;padding:28px;box-shadow:0 2px 8px rgba(0,0,0,0.07)}
h2{color:#2d3a6e;font-size:1em;margin:20px 0 8px}p,li{color:#555;font-size:0.9em;line-height:1.7}
ul{padding-left:18px;margin-top:6px}
footer{text-align:center;padding:10px;background:#2d3a6e;color:rgba(255,255,255,0.8);font-size:12px;position:fixed;bottom:0;width:100%}
</style></head><body>
<div class="header"><a href="javascript:history.back()">← Voltar</a><h1>Política de Cookies</h1></div>
<div class="content"><div class="card">
<h2>O que são cookies?</h2>
<p>Cookies são pequenos ficheiros de texto armazenados no seu dispositivo quando visita um site.</p>
<h2>Que cookies utilizamos?</h2>
<p>Este site utiliza exclusivamente <strong>cookies essenciais</strong>:</p>
<ul>
<li><strong>Cookie de sessão</strong> — mantém a sua sessão ativa após o login.</li>
<li><strong>Preferências locais</strong> — guardadas no seu dispositivo (localStorage).</li>
</ul>
<h2>Não utilizamos</h2>
<ul><li>Cookies de publicidade ou rastreamento</li><li>Cookies de terceiros para analytics</li></ul>
<h2>Base legal</h2>
<p>Os cookies essenciais são necessários para o funcionamento do serviço e não requerem consentimento ao abrigo do RGPD.</p>
<h2>Contacto</h2>
<p>Para questões sobre privacidade, contacte o administrador da plataforma <strong>{{ org_nome }}</strong>.</p>
</div></div>
<footer>&copy; GestãoPro</footer>
</body></html>''', org_nome=org_nome)


@push_bp.route('/sw.js')
def service_worker():
    response = send_from_directory('static', 'sw.js')
    response.headers['Service-Worker-Allowed'] = '/'
    response.headers['Content-Type'] = 'application/javascript'
    return response