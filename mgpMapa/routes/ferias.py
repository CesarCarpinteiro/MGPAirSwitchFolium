import json
import threading
from datetime import datetime

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from db import db
from models import ConfigFeriasAno, Ferias, Usuario
from utils import bg_push

ferias_bp = Blueprint('ferias', __name__)

DIAS_ANO_DEFAULT = 22


@ferias_bp.route('/ferias', methods=['GET', 'POST'])
@login_required
def ferias():
    if request.method == 'POST':
        data_inicio = request.form.get('data_inicio')
        data_fim = request.form.get('data_fim')
        nota = request.form.get('nota')
        target_user_id = request.form.get('target_user_id')
        if current_user.is_admin and target_user_id:
            target_user = db.session.query(Usuario).filter_by(id=int(target_user_id), org_id=current_user.org_id).first()
        else:
            target_user = current_user
        if data_inicio and data_fim:
            try:
                from datetime import date, timedelta
                d1 = datetime.strptime(data_inicio, '%d/%m/%Y')
                d2 = datetime.strptime(data_fim, '%d/%m/%Y')
                year = d1.year
                feriados_pt = []
                for mes, dia in [(1,1),(4,25),(5,1),(6,10),(8,15),(10,5),(11,1),(12,1),(12,8),(12,25)]:
                    try:
                        feriados_pt.append(date(year, mes, dia))
                    except Exception:
                        pass
                a = year % 19; b = year // 100; c = year % 100
                d = b // 4; e = b % 4; f_ = (b + 8) // 25
                g = (b - f_ + 1) // 3; h = (19 * a + b - d - g + 15) % 30
                i = c // 4; k = c % 4; l = (32 + 2 * e + 2 * i - h - k) % 7
                m_ = (a + 11 * h + 22 * l) // 451
                em = (h + l - 7 * m_ + 114) // 31; ed = (h + l - 7 * m_ + 114) % 31 + 1
                easter = date(year, em, ed)
                feriados_pt += [easter, easter - timedelta(days=2), easter + timedelta(days=60)]
                num_dias = 0
                cur = d1
                while cur <= d2:
                    if cur.weekday() < 5 and cur.date() not in feriados_pt:
                        num_dias += 1
                    cur += timedelta(days=1)
            except Exception:
                num_dias = 0

            admin_adding_for_other = current_user.is_admin and target_user.id != current_user.id
            nova = Ferias(org_id=current_user.org_id, user_id=target_user.id,
                          data_inicio=data_inicio, data_fim=data_fim, nota=nota, num_dias=num_dias,
                          estado='aprovado' if admin_adding_for_other else 'pendente')
            db.session.add(nova)
            db.session.commit()

            from flask import current_app
            _app = current_app._get_current_object()

            if admin_adding_for_other:
                flash(f'Férias de {target_user.nome_completo or target_user.nome} adicionadas e aprovadas.', 'success')
                bg_push(_app, target_user.id, '✅ Férias aprovadas',
                        f'O admin adicionou férias aprovadas de {data_inicio} a {data_fim}.', '/ferias')
            else:
                flash('Pedido de férias enviado.', 'success')
                _nome = target_user.nome_completo or target_user.nome
                _org_id = current_user.org_id
                def _notify_admins(nome=_nome, org_id=_org_id, di=data_inicio, df=data_fim):
                    with _app.app_context():
                        admins = db.session.query(Usuario).filter_by(org_id=org_id, is_admin=True).all()
                        for admin in admins:
                            from utils import send_push_to_user
                            send_push_to_user(_app, admin.id, '📅 Novo pedido de férias',
                                              f'{nome} pediu férias de {di} a {df}.', '/ferias')
                threading.Thread(target=_notify_admins, daemon=True).start()

    is_admin = current_user.is_admin
    usuarios = db.session.query(Usuario).filter_by(org_id=current_user.org_id).all() if is_admin else []
    if is_admin:
        todos = db.session.query(Ferias, Usuario).join(Usuario, Ferias.user_id == Usuario.id).filter(
            Ferias.org_id == current_user.org_id).order_by(Ferias.id.desc()).all()
    else:
        todos = db.session.query(Ferias, Usuario).join(Usuario, Ferias.user_id == Usuario.id).filter(
            Ferias.org_id == current_user.org_id, Ferias.user_id == current_user.id).order_by(Ferias.id.desc()).all()

    resumo_ferias = []
    ano_atual = datetime.now().year
    configs_ferias = {c.ano: c.dias for c in db.session.query(ConfigFeriasAno).filter_by(org_id=current_user.org_id).all()}
    if is_admin:
        for u in usuarios:
            ferias_user = [f for f, usr in todos if usr.id == u.id]
            aprovadas = sum(f.num_dias or 0 for f in ferias_user
                            if f.estado == 'aprovado' and f.data_inicio and str(ano_atual) in f.data_inicio)
            pendentes_dias = sum(f.num_dias or 0 for f in ferias_user
                                 if f.estado == 'pendente' and f.data_inicio and str(ano_atual) in f.data_inicio)
            total_ano = configs_ferias.get(ano_atual, DIAS_ANO_DEFAULT)
            disponiveis = max(0, total_ano - aprovadas - pendentes_dias)
            resumo_ferias.append({
                'user': u, 'aprovadas': aprovadas, 'pendentes': pendentes_dias,
                'disponiveis': disponiveis, 'total': total_ano,
                'n_pedidos': len([f for f in ferias_user if f.data_inicio and str(ano_atual) in f.data_inicio]),
            })
        resumo_ferias.sort(key=lambda x: x['aprovadas'], reverse=True)

    ferias_json = json.dumps([{
        'user_nome': u.nome, 'estado': f.estado, 'data_inicio': f.data_inicio,
        'data_fim': f.data_fim, 'num_dias': f.num_dias or 0
    } for f, u in todos])
    return render_template('ferias.html', ferias=todos, ferias_json=ferias_json, is_admin=is_admin,
                           usuarios=usuarios, current_user=current_user, now=datetime.now(),
                           resumo_ferias=resumo_ferias, configs_ferias=configs_ferias,
                           dias_ano=configs_ferias.get(ano_atual, DIAS_ANO_DEFAULT), ano_atual=ano_atual)


@ferias_bp.route('/ferias/responder-bulk', methods=['POST'])
@login_required
def responder_ferias_bulk():
    if not current_user.is_admin:
        return redirect(url_for('ferias.ferias'))
    ids = request.form.getlist('ids')
    estado = request.form.get('estado', 'aprovado')
    notified = []
    for fid in ids:
        f = db.session.query(Ferias).filter_by(id=int(fid), org_id=current_user.org_id).first()
        if f and f.estado == 'pendente':
            f.estado = estado
            f.aprovado_por = current_user.nome
            notified.append((f.user_id, f.data_inicio, f.data_fim))
    db.session.commit()
    flash(f'{len(notified)} pedido(s) {"aprovado" if estado == "aprovado" else "rejeitado"}(s).', 'success')
    emoji = '✅' if estado == 'aprovado' else '❌'
    label = 'aprovadas' if estado == 'aprovado' else 'recusadas'
    from flask import current_app
    _app = current_app._get_current_object()
    def _bulk_notify(notified=notified, emoji=emoji, label=label):
        for uid, di, df in notified:
            from utils import send_push_to_user
            send_push_to_user(_app, uid, f'{emoji} Férias {label}',
                              f'As tuas férias de {di} a {df} foram {label}.', '/ferias')
    threading.Thread(target=_bulk_notify, daemon=True).start()
    return redirect(url_for('ferias.ferias'))


@ferias_bp.route('/ferias/responder/<int:id>', methods=['POST'])
@login_required
def responder_ferias(id):
    if not current_user.is_admin:
        return redirect(url_for('ferias.ferias'))
    f = db.session.query(Ferias).filter_by(id=id, org_id=current_user.org_id).first()
    if f:
        estado = request.form.get('estado')
        comentario = request.form.get('comentario', '')
        f.estado = estado
        f.comentario_admin = comentario
        f.aprovado_por = current_user.nome
        db.session.commit()
        flash('Resposta enviada.', 'success')

        user = db.session.query(Usuario).filter_by(id=f.user_id).first()
        from models import Organizacao
        org = db.session.query(Organizacao).filter_by(id=current_user.org_id).first()
        _user_id = f.user_id
        _user_email = user.email if user else None
        _user_nome = (user.nome_completo or user.nome) if user else ''
        _org_nome = org.nome if org else 'A minha Organização'
        _admin_nome = current_user.nome_completo or current_user.nome
        _data_inicio = f.data_inicio
        _data_fim = f.data_fim
        _num_dias = f.num_dias
        from flask import current_app
        _app = current_app._get_current_object()

        def _send_ferias_bg(estado=estado, comentario=comentario,
                            user_email=_user_email, user_nome=_user_nome,
                            org_nome=_org_nome, admin_nome=_admin_nome,
                            data_inicio=_data_inicio, data_fim=_data_fim,
                            num_dias=_num_dias, user_id=_user_id):
            import smtplib
            from email.header import Header
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            from email.utils import formataddr
            from utils import GMAIL_USER, GMAIL_PASS, send_push_to_user
            if user_email:
                try:
                    estado_label = 'aprovadas' if estado == 'aprovado' else 'recusadas'
                    cor = '#2d3a6e' if estado == 'aprovado' else '#c62828'
                    bg = '#eaf3de' if estado == 'aprovado' else '#fef2f2'
                    brd = '#c0dd97' if estado == 'aprovado' else '#fecaca'
                    acao = 'aprovou' if estado == 'aprovado' else 'recusou'
                    comentario_block = ''
                    if comentario:
                        comentario_block = (
                            '<div style="background:#f5f5f5;border-radius:8px;padding:12px 16px;margin-bottom:16px;">'
                            '<p style="font-size:12px;color:#888;margin:0 0 4px;">Comentário do administrador</p>'
                            f'<p style="font-size:14px;color:#333;margin:0;">{comentario}</p>'
                            '</div>'
                        )
                    periodo = f'{data_inicio} a {data_fim} ({num_dias} dia(s))'
                    html_ferias = (
                        '<div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;">'
                        f'<div style="background:{cor};padding:28px 32px;text-align:center;">'
                        '<p style="color:white;font-size:20px;font-weight:bold;margin:0 0 4px;">Pedido de Férias</p>'
                        f'<p style="color:rgba(255,255,255,0.8);font-size:13px;margin:0;">{org_nome}</p>'
                        '</div><div style="background:white;padding:28px 32px;">'
                        f'<p style="font-size:15px;color:#1a1a1a;margin:0 0 16px;">Olá <strong>{user_nome}</strong>,</p>'
                        f'<p style="font-size:14px;color:#555;margin:0 0 20px;">O seu administrador <strong>{admin_nome}</strong> {acao} o seu pedido de férias.</p>'
                        f'<div style="background:{bg};border:1px solid {brd};border-radius:8px;padding:16px 20px;margin-bottom:20px;">'
                        '<p style="font-size:12px;color:#888;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 8px;">Período</p>'
                        f'<p style="font-size:16px;font-weight:bold;color:{cor};margin:0;">{periodo}</p>'
                        f'</div>{comentario_block}'
                        '<p style="font-size:13px;color:#888;margin:0;">Se tiver questões, contacte o seu administrador.</p>'
                        '</div><div style="background:#f8f8f8;border-top:1px solid #eee;padding:16px 32px;text-align:center;">'
                        f'<p style="font-size:12px;color:#aaa;margin:0;">© {org_nome} — Plataforma de Gestão</p>'
                        '</div></div>'
                    )
                    msg_ferias = MIMEMultipart('alternative')
                    msg_ferias["Subject"] = f"As suas férias foram {estado_label}"
                    msg_ferias["From"] = formataddr((str(Header("GestãoPro", "utf-8")), GMAIL_USER))
                    msg_ferias["To"] = user_email
                    msg_ferias.attach(MIMEText(html_ferias, 'html'))
                    with smtplib.SMTP("smtp.gmail.com", 587) as conn:
                        conn.starttls()
                        conn.login(user=GMAIL_USER, password=GMAIL_PASS)
                        conn.send_message(msg_ferias)
                except Exception as e:
                    print(f'Erro email ferias: {e}')
            emoji = '✅' if estado == 'aprovado' else '❌'
            label = 'aprovadas' if estado == 'aprovado' else 'recusadas'
            send_push_to_user(_app, user_id, f'{emoji} Férias {label}',
                              f'As tuas férias de {data_inicio} a {data_fim} foram {label}.', '/ferias')

        threading.Thread(target=_send_ferias_bg, daemon=True).start()

    return redirect(url_for('ferias.ferias'))


@ferias_bp.route('/ferias/delete/<int:id>', methods=['POST'])
@login_required
def delete_ferias(id):
    f = db.session.query(Ferias).filter_by(id=id, org_id=current_user.org_id).first()
    if f and (f.user_id == current_user.id or current_user.is_admin):
        db.session.delete(f)
        db.session.commit()
        flash('Pedido removido.', 'success')
    return redirect(url_for('ferias.ferias'))


@ferias_bp.route('/ferias/config-dias', methods=['POST'])
@login_required
def ferias_config_dias():
    if not current_user.is_admin:
        return jsonify({'error': 'Sem permissão'}), 403
    data = request.get_json()
    ano = int(data.get('ano', 0))
    dias = int(data.get('dias', 22))
    if not ano or dias < 1:
        return jsonify({'error': 'Dados inválidos'}), 400
    cfg = db.session.query(ConfigFeriasAno).filter_by(org_id=current_user.org_id, ano=ano).first()
    if cfg:
        cfg.dias = dias
    else:
        db.session.add(ConfigFeriasAno(org_id=current_user.org_id, ano=ano, dias=dias))
    db.session.commit()
    return jsonify({'ok': True, 'ano': ano, 'dias': dias})


@ferias_bp.route('/ferias/config-dias/delete', methods=['POST'])
@login_required
def ferias_config_dias_delete():
    if not current_user.is_admin:
        return jsonify({'error': 'Sem permissão'}), 403
    data = request.get_json()
    ano = int(data.get('ano', 0))
    cfg = db.session.query(ConfigFeriasAno).filter_by(org_id=current_user.org_id, ano=ano).first()
    if cfg:
        db.session.delete(cfg)
        db.session.commit()
    return jsonify({'ok': True})