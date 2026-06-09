import json
from datetime import datetime

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from db import db
from models import (Fatura, Ferias, HorasTrabalhadas, Organizacao, Registo,
                    Servico, TipoServico, Usuario)
from utils import hash_password, send_welcome_email
import threading

users_bp = Blueprint('users', __name__)


@users_bp.route('/registrar', methods=['GET', 'POST'])
@login_required
def registrar():
    if not current_user.is_admin:
        return jsonify({'ok': False, 'error': 'Sem permissão'})
    if request.method == 'GET':
        return redirect(url_for('users.perfil'))
    data = request.get_json()
    nome = data.get('nomeForm', '').strip()
    senha = data.get('senhaForm', '').strip()
    email = data.get('emailForm', '').strip()
    telefone = data.get('telefoneForm', '').strip()
    cargo = data.get('cargo', '').strip()
    is_admin_user = data.get('is_admin', False)

    if not nome or not senha:
        return jsonify({'ok': False, 'error': 'Nome e password são obrigatórios'})
    if db.session.query(Usuario).filter_by(nome=nome).first():
        return jsonify({'ok': False, 'error': 'Este nome de utilizador já existe'})

    novo_usuario = Usuario(nome=nome, senha=hash_password(senha), is_admin=is_admin_user,
                           email=email, telefone=telefone, cargo=cargo, org_id=current_user.org_id)
    db.session.add(novo_usuario)
    db.session.commit()

    if email:
        org_nome = (db.session.query(Organizacao).filter_by(id=current_user.org_id).first()
                    or type('', (), {'nome': 'A minha Organização'})()).nome
        criado_por = current_user.nome_completo or current_user.nome
        def _send():
            try:
                send_welcome_email(to_email=email, nome=nome, org_nome=org_nome,
                                   username=nome, password_temp=senha, criado_por=criado_por)
            except Exception as e:
                print(f'Erro email registar: {e}')
        threading.Thread(target=_send, daemon=True).start()

    return jsonify({
        'ok': True, 'id': novo_usuario.id, 'nome': novo_usuario.nome,
        'email': email or '—', 'telefone': telefone or '—',
        'cargo': cargo or '—', 'is_admin': is_admin_user
    })


@users_bp.route('/edit_user/<int:id>', methods=['POST'])
@login_required
def edit_user(id):
    if not current_user.is_admin:
        return jsonify({'ok': False, 'error': 'Sem permissão'})
    u = db.session.query(Usuario).filter_by(id=id, org_id=current_user.org_id).first()
    if not u:
        return jsonify({'ok': False, 'error': 'Utilizador não encontrado'})
    data = request.get_json()
    email = data.get('email', '').strip()
    telefone = data.get('telefone', '').strip()
    cargo = data.get('cargo', '').strip()
    nova_senha = data.get('nova_senha', '').strip()
    u.email = email or u.email
    u.telefone = telefone or u.telefone
    u.cargo = cargo
    if nova_senha:
        u.senha = hash_password(nova_senha)
    db.session.commit()
    return jsonify({'ok': True, 'email': u.email or '—', 'telefone': u.telefone or '—', 'cargo': u.cargo or '—'})


@users_bp.route('/delete_user/<int:id>', methods=['POST'])
@login_required
def delete_user(id):
    if not current_user.is_admin:
        return jsonify({'ok': False})
    user = db.session.query(Usuario).filter_by(id=id, org_id=current_user.org_id).first()
    if user and user.id != current_user.id:
        db.session.delete(user)
        db.session.commit()
        return jsonify({'ok': True})
    return jsonify({'ok': False})


@users_bp.route('/toggle_admin/<int:id>', methods=['POST'])
@login_required
def toggle_admin(id):
    if not current_user.is_admin:
        return jsonify({'ok': False})
    u = db.session.query(Usuario).filter_by(id=id, org_id=current_user.org_id).first()
    if u and u.id != current_user.id:
        u.is_admin = not u.is_admin
        db.session.commit()
        return jsonify({'ok': True, 'is_admin': u.is_admin})
    return jsonify({'ok': False})


@users_bp.route('/perfil')
@login_required
def perfil():
    is_admin = current_user.is_admin
    todos_usuarios = db.session.query(Usuario).filter_by(org_id=current_user.org_id).all() if is_admin else []
    registos = db.session.query(Registo).filter_by(org_id=current_user.org_id).all() if is_admin else []
    servicos = db.session.query(Servico).filter_by(org_id=current_user.org_id).all() if is_admin else []

    def _data_ref(r):
        if r.data_instalacao:
            return r.data_instalacao
        datas = [s.data_servico for s in r.servicos if s.data_servico]
        if datas:
            try:
                return min(datas, key=lambda d: datetime.strptime(d, '%d/%m/%Y'))
            except Exception:
                pass
        return datetime.now().strftime('%d/%m/%Y')

    registos_json = json.dumps([{
        'data_instalacao': _data_ref(r), 'valor_pago': r.valor_pago, 'morada': r.morada or ''
    } for r in registos])
    servicos_json = json.dumps([{
        'data_servico': s.data_servico, 'tipo_servico': s.tipo_servico or '',
        'valor_pago': s.valor_pago or 0, 'marca': s.marca or '', 'num_maquinas': s.num_maquinas or 0
    } for s in servicos])
    org = db.session.query(Organizacao).filter_by(id=current_user.org_id).first()
    tipos_servico = db.session.query(TipoServico).filter_by(org_id=current_user.org_id).all() if is_admin else []

    total_clientes = len(registos)
    total_servicos = len(servicos)
    receita_total = sum(s.valor_pago or 0 for s in servicos)
    media_maquinas = round(sum(s.num_maquinas or 0 for s in servicos) / total_servicos, 1) if total_servicos else 0

    now = datetime.now()
    urgentes = atencao = em_dia = 0
    for r in registos:
        svcs = sorted([s for s in r.servicos if s.data_servico], key=lambda x: x.data_servico, reverse=True)
        if svcs:
            try:
                d = datetime.strptime(svcs[0].data_servico, '%d/%m/%Y')
                months = (now.year - d.year) * 12 + (now.month - d.month)
                if months > 10:
                    urgentes += 1
                elif months > 8:
                    atencao += 1
                else:
                    em_dia += 1
            except Exception:
                pass

    user_horas_mes = user_ferias_aprovadas = user_ferias_pendentes = 0
    user_faturas_mes = 0
    user_valor_faturas_mes = 0.0
    if not is_admin:
        horas_mes = db.session.query(HorasTrabalhadas).filter_by(
            user_id=current_user.id, mes=now.month, ano=now.year).all()
        user_horas_mes = round(sum(h.total for h in horas_mes), 1)
        ferias_user = db.session.query(Ferias).filter_by(user_id=current_user.id, org_id=current_user.org_id).all()
        user_ferias_aprovadas = sum(f.num_dias or 0 for f in ferias_user
                                    if f.estado == 'aprovado' and (f.data_inicio or '').endswith(str(now.year)))
        user_ferias_pendentes = sum(1 for f in ferias_user if f.estado == 'pendente')
        faturas_user = db.session.query(Fatura).filter_by(user_id=current_user.id, org_id=current_user.org_id).all()
        faturas_mes_list = [f for f in faturas_user if f.data and len(f.data.split('/')) == 3
                            and f.data.split('/')[1] == str(now.month).zfill(2)
                            and f.data.split('/')[2] == str(now.year)]
        user_faturas_mes = len(faturas_mes_list)
        user_valor_faturas_mes = round(sum(f.valor or 0 for f in faturas_mes_list), 2)

    return render_template('perfil.html', user=current_user, usuarios=todos_usuarios,
                           registos=registos, registos_json=registos_json, servicos_json=servicos_json,
                           is_admin=is_admin, org=org, tipos_servico=tipos_servico,
                           total_clientes=total_clientes, total_servicos=total_servicos,
                           receita_total=receita_total, media_maquinas=media_maquinas,
                           urgentes=urgentes, atencao=atencao, em_dia=em_dia,
                           user_horas_mes=user_horas_mes, user_ferias_aprovadas=user_ferias_aprovadas,
                           user_ferias_pendentes=user_ferias_pendentes, user_faturas_mes=user_faturas_mes,
                           user_valor_faturas_mes=user_valor_faturas_mes)


@users_bp.route('/org/tipo_negocio', methods=['POST'])
@login_required
def update_tipo_negocio():
    if not current_user.is_admin:
        return jsonify({'ok': False})
    org = db.session.query(Organizacao).filter_by(id=current_user.org_id).first()
    if org:
        org.tipo_negocio = request.get_json().get('tipo_negocio', org.tipo_negocio)
        db.session.commit()
        return jsonify({'ok': True})
    return jsonify({'ok': False})