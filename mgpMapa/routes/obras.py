import json
import threading

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from db import db
from models import Ferias, Obra, ObraFuncionario, Organizacao, Usuario
from utils import bg_push

obras_bp = Blueprint('obras', __name__)

_estado_label = {
    'agendada': '📅 Agendada', 'em_curso': '🔧 Em curso',
    'concluida': '✅ Concluída', 'cancelada': '❌ Cancelada'
}


@obras_bp.route('/minhas-obras')
@login_required
def minhas_obras():
    org = db.session.query(Organizacao).filter_by(id=current_user.org_id).first()
    org_nome = org.nome if org else 'A minha Organização'
    tem_mapa = org.tipo_negocio != 'espaco' if org else True
    obra_ids = [of.obra_id for of in db.session.query(ObraFuncionario).filter_by(
        usuario_id=current_user.id, org_id=current_user.org_id).all()]
    obras = db.session.query(Obra).filter(Obra.id.in_(obra_ids)).order_by(Obra.data_inicio).all() if obra_ids else []
    colegas_map = {}
    for obra in obras:
        funcs = db.session.query(ObraFuncionario, Usuario).join(
            Usuario, ObraFuncionario.usuario_id == Usuario.id
        ).filter(ObraFuncionario.obra_id == obra.id).all()
        colegas_map[obra.id] = [u.nome for _, u in funcs if u.id != current_user.id]
    return render_template('minhas_obras.html', obras=obras, colegas_map=colegas_map,
                           estado_label=_estado_label, org_nome=org_nome, tem_mapa=tem_mapa,
                           is_admin=current_user.is_admin)


@obras_bp.route('/marcacoes')
@login_required
def marcacoes():
    if not current_user.is_admin:
        return redirect(url_for('home.home'))
    org = db.session.query(Organizacao).filter_by(id=current_user.org_id).first()
    org_nome = org.nome if org else 'A minha Organização'
    tem_mapa = org.tipo_negocio != 'espaco' if org else True

    obras = db.session.query(Obra).filter_by(org_id=current_user.org_id).order_by(Obra.data_inicio).all()
    all_users = db.session.query(Usuario).filter_by(org_id=current_user.org_id).all()
    obra_funcs = db.session.query(ObraFuncionario).filter_by(org_id=current_user.org_id).all()
    obra_funcs_map = {}
    for of in obra_funcs:
        obra_funcs_map.setdefault(of.obra_id, []).append(of.usuario_id)

    ferias_aprovadas = db.session.query(Ferias, Usuario).join(Usuario, Ferias.user_id == Usuario.id).filter(
        Ferias.org_id == current_user.org_id, Ferias.estado == 'aprovado').all()

    ferias_json = json.dumps([{
        'user_id': u.id, 'user_nome': u.nome,
        'data_inicio': f.data_inicio, 'data_fim': f.data_fim
    } for f, u in ferias_aprovadas])
    obras_json = json.dumps([{
        'id': o.id, 'nome': o.nome, 'local': o.local or '',
        'data_inicio': o.data_inicio, 'data_fim': o.data_fim,
        'estado': o.estado, 'notas': o.notas or '',
        'funcionarios': obra_funcs_map.get(o.id, [])
    } for o in obras])
    funcionarios_json = json.dumps([{
        'id': u.id, 'nome': u.nome, 'cargo': u.cargo or ''
    } for u in all_users])

    return render_template('marcacoes.html',
        obras=obras, obra_funcs_map=obra_funcs_map, all_users=all_users,
        obras_json=obras_json, ferias_json=ferias_json, funcionarios_json=funcionarios_json,
        org_nome=org_nome, tem_mapa=tem_mapa, is_admin=True)


@obras_bp.route('/marcacoes/criar', methods=['POST'])
@login_required
def criar_obra():
    if not current_user.is_admin:
        return jsonify({'ok': False}), 403
    data = request.get_json()
    obra = Obra(
        org_id=current_user.org_id, created_by=current_user.id,
        nome=data.get('nome', '').strip(), local=data.get('local', '').strip(),
        data_inicio=data.get('data_inicio', '').strip(), data_fim=data.get('data_fim', '').strip(),
        estado=data.get('estado', 'agendada'), notas=data.get('notas', '').strip()
    )
    db.session.add(obra)
    db.session.flush()
    funcionarios = data.get('funcionarios', [])
    for uid in funcionarios:
        db.session.add(ObraFuncionario(obra_id=obra.id, usuario_id=int(uid), org_id=current_user.org_id))
    db.session.commit()
    local_str = f' em {obra.local}' if obra.local else ''
    from flask import current_app
    _app = current_app._get_current_object()
    for uid in funcionarios:
        bg_push(_app, uid, '🔨 Nova obra atribuída',
                f'{obra.nome}{local_str} — {obra.data_inicio} a {obra.data_fim}', '/minhas-obras')
    return jsonify({'ok': True, 'id': obra.id, 'created_at': obra.created_at})


@obras_bp.route('/marcacoes/editar/<int:id>', methods=['POST'])
@login_required
def editar_obra(id):
    if not current_user.is_admin:
        return jsonify({'ok': False}), 403
    obra = db.session.query(Obra).filter_by(id=id, org_id=current_user.org_id).first()
    if not obra:
        return jsonify({'ok': False}), 404
    data = request.get_json()
    obra.nome = data.get('nome', obra.nome).strip()
    obra.local = data.get('local', obra.local or '').strip()
    obra.data_inicio = data.get('data_inicio', obra.data_inicio).strip()
    obra.data_fim = data.get('data_fim', obra.data_fim).strip()
    obra.estado = data.get('estado', obra.estado)
    obra.notas = data.get('notas', obra.notas or '').strip()
    db.session.query(ObraFuncionario).filter_by(obra_id=id).delete()
    for uid in data.get('funcionarios', []):
        db.session.add(ObraFuncionario(obra_id=id, usuario_id=int(uid), org_id=current_user.org_id))
    db.session.commit()
    return jsonify({'ok': True})


@obras_bp.route('/marcacoes/apagar/<int:id>', methods=['POST'])
@login_required
def apagar_obra(id):
    if not current_user.is_admin:
        return jsonify({'ok': False}), 403
    obra = db.session.query(Obra).filter_by(id=id, org_id=current_user.org_id).first()
    if not obra:
        return jsonify({'ok': False}), 404
    db.session.query(ObraFuncionario).filter_by(obra_id=id).delete()
    db.session.delete(obra)
    db.session.commit()
    return jsonify({'ok': True})