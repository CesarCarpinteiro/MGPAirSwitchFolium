from datetime import datetime, timedelta

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from db import db
from models import LembreteSMS, Obra, ObraFuncionario, Organizacao, Registo, Servico, TipoServico
from lembretes import TIPO_MANUTENCAO, definir_agendamento, proxima_por_omissao, situacao, ultimo_servico
from utils import TWILIO_ACCOUNT_SID, converter_data, send_sms, texto_sms

registos_bp = Blueprint('registos', __name__)

def _mensagem_servico(tipo_servico):
    """Texto do aviso de serviço concluído, conforme o tipo de serviço."""
    tipo = (tipo_servico or '').strip()
    t = tipo.lower()
    if 'instala' in t:
        feito = 'a sua instalação está concluída.'
    elif 'manuten' in t:
        feito = 'a sua manutenção está concluída.'
    elif tipo:
        feito = f'o seu serviço de {t} está concluído.'
    else:
        feito = 'o seu serviço está concluído.'
    return f'{feito} Obrigado pela preferência e confiança!'


def _notificar_cliente(registo, tipo_servico):
    """SMS ao cliente a avisar que o serviço está pronto (só admins, se a opção vier marcada)."""
    if request.form.get('notificar_cliente') != '1' or not TWILIO_ACCOUNT_SID or not current_user.is_admin:
        return
    if not registo.contacto:
        flash('Cliente sem contacto: SMS não enviado.', 'error')
        return
    org = db.session.query(Organizacao).filter_by(id=current_user.org_id).first()
    ok, erro = send_sms(registo.contacto, texto_sms(org, _mensagem_servico(tipo_servico)))
    if ok:
        flash(f'SMS enviado ao cliente ({registo.contacto}).', 'success')
    else:
        flash(f'O SMS ao cliente falhou: {erro}', 'error')


# ── Marcações automáticas ─────────────────────────────────────────────
# Cada serviço registado e cada manutenção agendada no mapa aparecem no calendário de Marcações.

def _obra_agendamento(r):
    """Marcação em aberto criada pelo agendamento no mapa (ainda sem serviço registado)."""
    return db.session.query(Obra).filter(Obra.registo_id == r.id, Obra.servico_id.is_(None),
                                         Obra.estado.notin_(['concluida', 'cancelada'])).first()


def _apagar_obra(obra):
    db.session.query(ObraFuncionario).filter_by(obra_id=obra.id).delete()
    db.session.delete(obra)


def _notas_cliente(r, extra=''):
    return ' · '.join(x for x in [f'Contacto: {r.contacto}' if r.contacto else '', extra or ''] if x)[:500]


def _marcar_servico(r, servico):
    """Cria/atualiza a marcação do serviço; se o cliente tinha manutenção agendada, é essa que fica concluída."""
    data = servico.data_servico or r.data_instalacao
    try:
        dia = datetime.strptime(data or '', '%d/%m/%Y').date()
    except ValueError:
        return
    estado = 'concluida' if dia <= datetime.now().date() else 'agendada'
    obra = db.session.query(Obra).filter_by(servico_id=servico.id).first() if servico.id else None
    if not obra and estado == 'concluida':
        obra = _obra_agendamento(r)
        if obra:
            r.manutencao_agendada = None  # a manutenção agendada foi feita
    nova = obra is None
    if nova:
        obra = Obra(org_id=r.org_id, created_by=current_user.id, registo_id=r.id)
        db.session.add(obra)
    obra.servico_id = servico.id
    obra.nome = f'{servico.tipo_servico or "Serviço"} — {r.nome}'[:200]
    obra.local = (r.morada or '')[:300]
    obra.data_inicio = obra.data_fim = data
    obra.estado = estado
    obra.notas = _notas_cliente(r, servico.notas)
    if nova:  # quem registou o serviço fica como funcionário da marcação
        db.session.flush()
        db.session.add(ObraFuncionario(obra_id=obra.id, usuario_id=current_user.id, org_id=r.org_id))


def _marcar_agendamento(r):
    """Mantém a marcação da manutenção agendada no mapa igual a r.manutencao_agendada."""
    obra = _obra_agendamento(r)
    if not r.manutencao_agendada:
        if obra:
            _apagar_obra(obra)
        return
    if not obra:
        obra = Obra(org_id=r.org_id, created_by=current_user.id, registo_id=r.id, estado='agendada')
        db.session.add(obra)
    obra.nome = f'{TIPO_MANUTENCAO} — {r.nome}'[:200]
    obra.local = (r.morada or '')[:300]
    obra.data_inicio = obra.data_fim = r.manutencao_agendada
    obra.notas = _notas_cliente(r)


def _erro_data(r):
    ultimo = ultimo_servico(r)
    return (f'A próxima manutenção tem de ser depois do último serviço ({ultimo.data_servico if ultimo else "—"}); '
            'não foi alterada.')


def _proxima_do_formulario(r):
    """Campo opcional 'Próx. manutenção' (só admins) nos formulários de cliente e de serviço:
    data futura fica agendada, data passada fica registada como último serviço. Vazio: +1 ano."""
    data = converter_data(request.form.get('proxima_manutencao')) if current_user.is_admin else None
    if data:
        db.session.expire(r, ['servicos'])
        if definir_agendamento(r, data) == 'invalida':
            flash(_erro_data(r), 'error')
        _marcar_agendamento(r)


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
            _ds2 = converter_data(data_instalacao) or datetime.now().strftime('%d/%m/%Y')
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
            db.session.flush()
            _marcar_servico(novo_registo, primeiro_servico)
            _proxima_do_formulario(novo_registo)
            db.session.commit()
            flash('Cliente adicionado com sucesso.', 'success')
            _notificar_cliente(novo_registo, tipo_servico)

    page = request.args.get('page', 1, type=int)
    per_page = 25
    base_query = db.session.query(Registo).filter_by(org_id=current_user.org_id)
    # ?ver=<id> (botão "Ver registo" do mapa): abre a página onde está o cliente
    ver = request.args.get('ver', type=int)
    if ver and base_query.filter(Registo.id == ver).count():
        page = base_query.filter(Registo.id > ver).count() // per_page + 1
    else:
        ver = None
    total_registos = base_query.count()
    total_pages = (total_registos + per_page - 1) // per_page
    registos = base_query.order_by(Registo.id.desc()).offset((page - 1) * per_page).limit(per_page).options(joinedload(Registo.servicos)).all()
    tipos_servico = db.session.query(TipoServico).filter_by(org_id=current_user.org_id).all()

    # Mesma regra do mapa e dos lembretes por SMS
    cores = {'Em dia': ('#2d3a6e', '#e8eaf6'), 'Atenção': ('#c47c2b', '#fff8e1'),
             'Urgente': ('#a33b3b', '#ffebee'), 'Agendada': ('#2e7d4f', '#e8f5e9')}
    status_map, ultimo_map = {}, {}
    for r in registos:
        sit = situacao(r)
        status_map[r.id] = (sit['estado'], *cores[sit['estado']], sit['proxima'])
        ultimo_map[r.id] = ultimo_servico(r)

    return render_template('registos.html', registos=registos, current_user=current_user, is_admin=is_admin,
                           page=page, ver=ver, total_pages=total_pages, total_registos=total_registos,
                           tipos_servico=tipos_servico, status_map=status_map, ultimo_map=ultimo_map, sms_ativo=bool(TWILIO_ACCOUNT_SID) and is_admin)


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
        db.session.flush()
        _marcar_servico(r, novo)
        _proxima_do_formulario(r)
        db.session.commit()
        flash('Serviço registado com sucesso.', 'success')
        _notificar_cliente(r, novo.tipo_servico)
    return redirect(url_for('registos.nova_pagina', page=request.args.get('page', 1)))


@registos_bp.route('/registos/agendar/<int:id>', methods=['POST'])
@login_required
def agendar_manutencao(id):
    """Marca (ou limpa) a data da próxima manutenção já agendada; enquanto existir, não há lembretes por SMS."""
    r = db.session.query(Registo).filter_by(id=id, org_id=current_user.org_id).first()
    if r:
        data = converter_data(request.form.get('data'))
        resultado = definir_agendamento(r, None if request.form.get('remover') else data)
        _marcar_agendamento(r)
        db.session.commit()
        if resultado == 'invalida':
            flash(_erro_data(r), 'error')
        elif resultado == 'feita':
            flash(f'A data já passou: manutenção de {r.nome} a {data} registada como último serviço.', 'success')
        elif not r.manutencao_agendada:
            flash(f'Agendamento de {r.nome} removido.', 'success')
        elif request.form.get('avisar_cliente') == '1' and current_user.is_admin and TWILIO_ACCOUNT_SID:
            org = db.session.query(Organizacao).filter_by(id=current_user.org_id).first()
            ok, erro = send_sms(r.contacto, texto_sms(org, f'a sua manutenção está agendada para dia {data}.'))
            if ok:
                flash(f'Manutenção agendada para {data} e SMS enviado a {r.nome}.', 'success')
            else:
                flash(f'Manutenção agendada para {data}, mas o SMS falhou: {erro}', 'error')
        else:
            flash(f'Manutenção de {r.nome} agendada para {data}.', 'success')
    return redirect(url_for('home.home'))


@registos_bp.route('/lembretes')
@login_required
def lembretes():
    """SMS de manutenção preparados (para cancelar ou enviar já) e histórico dos últimos 60 dias."""
    if not current_user.is_admin:
        return redirect(url_for('registos.nova_pagina'))
    base = db.session.query(LembreteSMS).filter_by(org_id=current_user.org_id).options(joinedload(LembreteSMS.registo))
    pendentes = base.filter(LembreteSMS.estado == 'pendente').order_by(LembreteSMS.enviar_em, LembreteSMS.id).all()
    historico = base.filter(LembreteSMS.estado != 'pendente',
                            LembreteSMS.criado_em >= datetime.now() - timedelta(days=60)
                            ).order_by(LembreteSMS.criado_em.desc()).limit(200).all()
    org = db.session.query(Organizacao).filter_by(id=current_user.org_id).first()
    return render_template('lembretes.html', pendentes=pendentes, historico=historico,
                           ativo=bool(org and org.sms_lembretes), sms_configurado=bool(TWILIO_ACCOUNT_SID),
                           is_admin=True)


@registos_bp.route('/lembretes/ativar', methods=['POST'])
@login_required
def ativar_lembretes():
    """Liga/desliga os SMS automáticos de manutenção da organização (Perfil > Admin)."""
    org = db.session.query(Organizacao).filter_by(id=current_user.org_id).first()
    if current_user.is_admin and org:
        org.sms_lembretes = request.form.get('ativo') == '1'
        db.session.commit()
        flash('SMS automáticos de manutenção ' + ('ligados.' if org.sms_lembretes else 'desligados.'), 'success')
    return redirect(url_for('users.perfil') + '#sms-manutencao')


def _lembrete_da_org(id):
    if not current_user.is_admin:
        return None
    return db.session.query(LembreteSMS).filter_by(id=id, org_id=current_user.org_id).first()


@registos_bp.route('/lembretes/<int:id>/cancelar', methods=['POST'])
@login_required
def cancelar_lembrete(id):
    lem = _lembrete_da_org(id)
    ok, mensagem = False, 'Este SMS já não pode ser cancelado.'
    if lem and lem.estado == 'pendente':
        lem.estado, lem.motivo = 'cancelado', f'Cancelado por {current_user.nome}'
        db.session.commit()
        ok, mensagem = True, f'SMS a {lem.registo.nome} não vai ser enviado.'
    return _resposta_lembrete(ok, mensagem)


def _resposta_lembrete(ok, mensagem):
    """JSON para os botões do sino; redirecionamento com aviso para a página /lembretes."""
    if 'application/json' in request.headers.get('Accept', ''):
        return jsonify({'ok': ok, 'mensagem': mensagem})
    flash(mensagem, 'success' if ok else 'error')
    return redirect(url_for('registos.lembretes'))


@registos_bp.route('/lembretes/<int:id>/enviar', methods=['POST'])
@login_required
def enviar_lembrete_ja(id):
    from lembretes import enviar_lembrete
    lem = _lembrete_da_org(id)
    if not (lem and lem.estado != 'enviado' and TWILIO_ACCOUNT_SID):
        return _resposta_lembrete(False, 'Este SMS já não pode ser enviado.')
    ok, erro = enviar_lembrete(lem)
    return _resposta_lembrete(ok, f'SMS enviado a {lem.registo.nome}.' if ok else f'O SMS falhou: {erro}')


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
        for obra in db.session.query(Obra).filter(Obra.registo_id == registo.id,
                                                  Obra.estado.notin_(['concluida', 'cancelada'])).all():
            _apagar_obra(obra)  # as marcações já feitas ficam no calendário como histórico
        db.session.delete(registo)
        db.session.commit()
        flash('Cliente removido.', 'success')
    return redirect(url_for('registos.nova_pagina'))


@registos_bp.route('/servico/delete/<int:id>', methods=['POST'])
@login_required
def delete_servico(id):
    s = db.session.query(Servico).filter_by(id=id, org_id=current_user.org_id).first()
    if s:
        for obra in db.session.query(Obra).filter_by(servico_id=s.id).all():
            _apagar_obra(obra)
        db.session.delete(s)
        db.session.commit()
        flash('Serviço removido.', 'success')
    return redirect(url_for('registos.nova_pagina'))


@registos_bp.route('/servico/edit/<int:id>', methods=['POST'])
@login_required
def edit_servico(id):
    s = db.session.query(Servico).filter_by(id=id, org_id=current_user.org_id).first()
    if s:
        data_antes, proxima_antes = s.data_servico, s.proxima_manutencao
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
        r = s.registo
        if s is ultimo_servico(r):
            # A próxima manutenção do último serviço é a do cliente: uma data diferente de "um ano depois"
            # conta como manutenção agendada (aparece nas marcações e suspende os SMS)
            if s.proxima_manutencao != proxima_antes:
                nova = s.proxima_manutencao
                if definir_agendamento(r, None if nova == proxima_por_omissao(s) else nova) == 'invalida':
                    s.proxima_manutencao = proxima_antes
                    flash(_erro_data(r), 'error')
                _marcar_agendamento(r)
            elif s.data_servico != data_antes and not r.manutencao_agendada:
                s.proxima_manutencao = proxima_por_omissao(s)
        if db.session.query(Obra).filter_by(servico_id=s.id).first():
            _marcar_servico(r, s)
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