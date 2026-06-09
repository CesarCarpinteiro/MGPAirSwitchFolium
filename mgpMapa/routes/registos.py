from datetime import datetime

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from db import db
from models import Registo, Servico, TipoServico
from utils import converter_data

registos_bp = Blueprint('registos', __name__)


@registos_bp.route('/registos', methods=['GET', 'POST'])
@login_required
def nova_pagina():
    is_admin = current_user.is_admin
    if request.method == 'POST':
        nome = request.form.get('nome')
        contacto = request.form.get('contacto')
        num_maquinas = request.form.get('num_maquinas')
        tipo_servico = request.form.get('tipo_servico')
        marca = request.form.get('marca')
        data_instalacao = request.form.get('data_instalacao')
        morada = request.form.get('morada')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        valor_pago = request.form.get('valor_pago') if is_admin else None
        if nome:
            _ds2 = converter_data(data_instalacao)
            _prox2 = None
            if _ds2:
                try:
                    _d2 = datetime.strptime(_ds2, '%d/%m/%Y')
                    _prox2 = _d2.replace(year=_d2.year + 1).strftime('%d/%m/%Y')
                except Exception:
                    pass
            novo_registo = Registo(
                org_id=current_user.org_id, nome=nome, contacto=contacto,
                morada=morada,
                latitude=float(latitude) if latitude else None,
                longitude=float(longitude) if longitude else None,
                data_instalacao=_ds2 or datetime.now().strftime('%d/%m/%Y'),
            )
            db.session.add(novo_registo)
            db.session.flush()

            _dur2 = request.form.get('duracao_horas')
            primeiro_servico = Servico(
                registo_id=novo_registo.id,
                org_id=current_user.org_id,
                tipo_servico=tipo_servico,
                data_servico=_ds2,
                proxima_manutencao=_prox2,
                num_maquinas=int(num_maquinas) if num_maquinas else None,
                marca=marca,
                valor_pago=float(valor_pago) if valor_pago else None,
                duracao_horas=float(_dur2) if _dur2 else None
            )
            db.session.add(primeiro_servico)
            db.session.commit()
            flash('Cliente adicionado com sucesso.', 'success')

    page = request.args.get('page', 1, type=int)
    per_page = 25
    base_query = db.session.query(Registo).filter_by(org_id=current_user.org_id)
    total_registos = base_query.count()
    total_pages = (total_registos + per_page - 1) // per_page
    registos = base_query.order_by(Registo.id.desc()).offset((page - 1) * per_page).limit(per_page).options(joinedload(Registo.servicos)).all()
    tipos_servico = db.session.query(TipoServico).filter_by(org_id=current_user.org_id).all()

    current_date = datetime.now().date()
    status_map = {}
    for r in registos:
        svcs = sorted([s for s in r.servicos if s.data_servico], key=lambda s: s.data_servico, reverse=True)
        data_ref = svcs[0].data_servico if svcs else r.data_instalacao
        months = 0
        if data_ref:
            try:
                ref = datetime.strptime(data_ref, '%d/%m/%Y').date()
                months = (current_date.year - ref.year) * 12 + (current_date.month - ref.month)
            except Exception:
                pass
        if months <= 8:
            status_map[r.id] = ('Em dia', '#2d3a6e', '#e8eaf6')
        elif months <= 10:
            status_map[r.id] = ('Atenção', '#c47c2b', '#fff8e1')
        else:
            status_map[r.id] = ('Urgente', '#a33b3b', '#ffebee')

    return render_template('registos.html', registos=registos, current_user=current_user, is_admin=is_admin,
                           page=page, total_pages=total_pages, total_registos=total_registos,
                           tipos_servico=tipos_servico, status_map=status_map)


@registos_bp.route('/registos/add_servico/<int:registo_id>', methods=['POST'])
@login_required
def add_servico(registo_id):
    r = db.session.query(Registo).filter_by(id=registo_id, org_id=current_user.org_id).first()
    if r:
        is_admin = current_user.is_admin
        _ds = converter_data(request.form.get('data_servico'))
        _prox = None
        if _ds:
            try:
                _d = datetime.strptime(_ds, '%d/%m/%Y')
                _prox = _d.replace(year=_d.year + 1).strftime('%d/%m/%Y')
            except Exception:
                pass
        _dur = request.form.get('duracao_horas')
        novo = Servico(
            registo_id=r.id,
            org_id=current_user.org_id,
            tipo_servico=request.form.get('tipo_servico'),
            data_servico=_ds,
            proxima_manutencao=_prox,
            num_maquinas=int(request.form.get('num_maquinas')) if request.form.get('num_maquinas') else None,
            marca=request.form.get('marca'),
            valor_pago=float(request.form.get('valor_pago')) if request.form.get('valor_pago') and is_admin else None,
            notas=request.form.get('notas'),
            duracao_horas=float(_dur) if _dur else None
        )
        db.session.add(novo)
        db.session.commit()
        flash('Serviço registado com sucesso.', 'success')
    return redirect(url_for('registos.nova_pagina', page=request.args.get('page', 1)))


@registos_bp.route('/registos/edit/<int:id>', methods=['POST'])
@login_required
def edit_registo(id):
    r = db.session.query(Registo).filter_by(id=id, org_id=current_user.org_id).first()
    if r:
        r.nome = request.form.get('nome', r.nome)
        r.contacto = request.form.get('contacto', r.contacto)
        r.morada = request.form.get('morada', r.morada)
        lat = request.form.get('latitude')
        lon = request.form.get('longitude')
        r.latitude = float(lat) if lat else r.latitude
        r.longitude = float(lon) if lon else r.longitude
        di = request.form.get('data_instalacao')
        if di:
            converted = converter_data(di)
            if converted:
                r.data_instalacao = converted
        db.session.commit()
        flash('Cliente atualizado.', 'success')
    return redirect(url_for('registos.nova_pagina', page=request.args.get('page', 1)))


@registos_bp.route('/registos/delete/<int:id>', methods=['POST'])
@login_required
def delete_registo(id):
    registo = db.session.query(Registo).filter_by(id=id, org_id=current_user.org_id).first()
    if registo:
        db.session.delete(registo)
        db.session.commit()
        flash('Cliente removido.', 'success')
    return redirect(url_for('registos.nova_pagina'))


@registos_bp.route('/servico/delete/<int:id>', methods=['POST'])
@login_required
def delete_servico(id):
    s = db.session.query(Servico).filter_by(id=id, org_id=current_user.org_id).first()
    if s:
        db.session.delete(s)
        db.session.commit()
        flash('Serviço removido.', 'success')
    return redirect(url_for('registos.nova_pagina'))


@registos_bp.route('/servico/edit/<int:id>', methods=['POST'])
@login_required
def edit_servico(id):
    s = db.session.query(Servico).filter_by(id=id, org_id=current_user.org_id).first()
    if s:
        s.tipo_servico = request.form.get('tipo_servico') or s.tipo_servico
        s.data_servico = converter_data(request.form.get('data_servico')) or s.data_servico
        s.proxima_manutencao = converter_data(request.form.get('proxima_manutencao')) or s.proxima_manutencao
        s.marca = request.form.get('marca') or s.marca
        num = request.form.get('num_maquinas')
        s.num_maquinas = int(num) if num else s.num_maquinas
        dur = request.form.get('duracao_horas')
        s.duracao_horas = float(dur) if dur else s.duracao_horas
        s.notas = request.form.get('notas', s.notas)
        val = request.form.get('valor_pago')
        s.valor_pago = float(val) if val else s.valor_pago
        db.session.commit()
        flash('Serviço atualizado.', 'success')
    return redirect(url_for('registos.nova_pagina', page=request.args.get('page', 1)))


@registos_bp.route('/tipos_servico/add', methods=['POST'])
@login_required
def add_tipo_servico():
    if not current_user.is_admin:
        return jsonify({'ok': False})
    nome = request.get_json().get('nome', '').strip()
    if not nome:
        return jsonify({'ok': False, 'error': 'Nome vazio'})
    existing = db.session.query(TipoServico).filter_by(nome=nome, org_id=current_user.org_id).first()
    if existing:
        return jsonify({'ok': False, 'error': 'Já existe'})
    novo = TipoServico(nome=nome, org_id=current_user.org_id)
    db.session.add(novo)
    db.session.commit()
    return jsonify({'ok': True, 'id': novo.id, 'nome': novo.nome})


@registos_bp.route('/tipos_servico/delete/<int:id>', methods=['POST'])
@login_required
def delete_tipo_servico(id):
    if not current_user.is_admin:
        return jsonify({'ok': False})
    t = db.session.query(TipoServico).filter_by(id=id, org_id=current_user.org_id).first()
    if t:
        db.session.delete(t)
        db.session.commit()
    return jsonify({'ok': True})


@registos_bp.route('/tipos_servico/edit/<int:id>', methods=['POST'])
@login_required
def edit_tipo_servico(id):
    if not current_user.is_admin:
        return jsonify({'ok': False})
    t = db.session.query(TipoServico).filter_by(id=id, org_id=current_user.org_id).first()
    if not t:
        return jsonify({'ok': False})
    nome = request.get_json().get('nome', '').strip()
    if nome:
        t.nome = nome
        db.session.commit()
    return jsonify({'ok': True, 'nome': t.nome})