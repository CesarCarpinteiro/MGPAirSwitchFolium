"""Estado de manutenção dos clientes e lembretes automáticos por SMS.

Uma só regra, usada pelo mapa, pela página de registos e pelos SMS (contada a partir do último serviço):
  - Em dia:   menos de 8 meses
  - Atenção:  a partir dos 8 meses   -> SMS "já passaram 8 meses, marque a manutenção anual"
  - Urgente:  a partir dos 10 meses  -> SMS "faltam 2 meses para a manutenção anual"
  - Agendada: há uma manutenção agendada (no mapa) depois do último serviço -> sem SMS

Os SMS são preparados na véspera: `flask enviar-lembretes` corre todos os dias às 9h, envia os que estavam
previstos para hoje e prepara os de amanhã, avisando os admins nas notificações. Até à hora de envio, cada
SMS pode ser cancelado ("Não enviar") ou enviado logo ("Enviar já") na página /lembretes.
Clientes com 12 meses ou mais não recebem SMS (já passou a data, a contactar manualmente).
"""
import calendar
from datetime import date, datetime, timedelta

from flask import current_app
from sqlalchemy.orm import joinedload

from db import db
from models import LembreteSMS, Obra, Organizacao, Registo, Servico, Usuario
from utils import TWILIO_ACCOUNT_SID, normalizar_telemovel, send_push_to_user, send_sms, texto_sms


TIPO_MANUTENCAO = 'Manutenção AC'  # tipo dos serviços criados quando uma manutenção agendada é feita


def _data(texto):
    try:
        return datetime.strptime(texto, '%d/%m/%Y').date()
    except (TypeError, ValueError):
        return None


def _somar_meses(d, meses):
    m = d.month - 1 + meses
    ano, mes = d.year + m // 12, m % 12 + 1
    return d.replace(year=ano, month=mes, day=min(d.day, calendar.monthrange(ano, mes)[1]))


def ultimo_servico(registo):
    """Serviço mais recente (por data real, não por texto) ou None."""
    datados = [(d, s) for s in registo.servicos if (d := _data(s.data_servico))]
    return max(datados, key=lambda x: x[0])[1] if datados else None


def proxima_por_omissao(servico):
    """Próxima manutenção por omissão: um ano depois do serviço."""
    d = _data(servico.data_servico)
    return _somar_meses(d, 12).strftime('%d/%m/%Y') if d else None


def definir_agendamento(registo, data):
    """Agenda (data 'dd/mm/aaaa') ou desmarca (None) a próxima manutenção.

    Data futura (ou hoje): fica agendada e substitui a próxima manutenção do último serviço.
    Data passada: a manutenção já foi feita, fica registada como último serviço.
    Sem data: volta a ser um ano depois do último serviço.
    Tem de ser depois do último serviço; se não for, não muda nada.
    Devolve 'agendada', 'feita', 'invalida' ou None.
    """
    ultimo = ultimo_servico(registo)
    d = _data(data)
    ref = _data(ultimo.data_servico) if ultimo else None
    if d and ref and d <= ref:
        return 'invalida'
    if d and d < date.today():
        registar_manutencao_feita(registo, data)
        return 'feita'
    registo.manutencao_agendada = data or None
    if ultimo:
        ultimo.proxima_manutencao = data or proxima_por_omissao(ultimo)
    return 'agendada' if data else None


def registar_manutencao_feita(registo, data):
    """Manutenção de `data` (passada) feita: novo último serviço (próxima a +1 ano) e marcação concluída."""
    servico = Servico(org_id=registo.org_id, tipo_servico=TIPO_MANUTENCAO, data_servico=data)
    servico.proxima_manutencao = proxima_por_omissao(servico)
    registo.servicos.append(servico)
    registo.manutencao_agendada = None
    db.session.flush()
    obra = db.session.query(Obra).filter(Obra.registo_id == registo.id, Obra.servico_id.is_(None),
                                         Obra.estado.notin_(['concluida', 'cancelada'])).first()
    if not obra:
        obra = Obra(org_id=registo.org_id, registo_id=registo.id, local=(registo.morada or '')[:300],
                    notas=f'Contacto: {registo.contacto}' if registo.contacto else '')
        db.session.add(obra)
    obra.nome = f'{TIPO_MANUTENCAO} — {registo.nome}'[:200]
    obra.servico_id = servico.id
    obra.data_inicio = obra.data_fim = data
    obra.estado = 'concluida'
    return servico


def _registar_agendadas_passadas(org, hoje):
    """Manutenções agendadas cuja data já passou ficam registadas como feitas (último serviço)."""
    feitas = []
    for r in db.session.query(Registo).filter(Registo.org_id == org.id, Registo.manutencao_agendada.isnot(None)).all():
        d = _data(r.manutencao_agendada)
        if not d or d >= hoje:
            continue
        if situacao(r, hoje)['agendada']:
            feitas.append(f'{r.nome} ({r.manutencao_agendada})')
            registar_manutencao_feita(r, r.manutencao_agendada)
        else:
            r.manutencao_agendada = None  # agendamento antigo, já há serviço mais recente
    db.session.commit()
    return feitas


def situacao(registo, hoje=None):
    """Estado de manutenção do cliente: {'estado', 'ref', 'tipo', 'agendada', 'proxima'}."""
    hoje = hoje or date.today()
    ultimo = ultimo_servico(registo)
    ref = _data(ultimo.data_servico) if ultimo else _data(registo.data_instalacao)
    tipo = (ultimo.tipo_servico if ultimo else None) or 'Instalação'
    agendada = _data(registo.manutencao_agendada)
    if agendada and ref and agendada <= ref:
        agendada = None  # agendamento antigo, já houve serviço depois
    if agendada:
        proxima = f'{registo.manutencao_agendada} (agendada)'
    else:
        proxima = (ultimo.proxima_manutencao if ultimo else None) or \
            (_somar_meses(ref, 12).strftime('%d/%m/%Y') if ref else None)
    if agendada and agendada >= hoje:
        estado = 'Agendada'
    elif ref and hoje >= _somar_meses(ref, 10):
        estado = 'Urgente'
    elif ref and hoje >= _somar_meses(ref, 8):
        estado = 'Atenção'
    else:
        estado = 'Em dia'
    return {'estado': estado, 'ref': ref, 'tipo': tipo, 'agendada': agendada, 'proxima': proxima}


def _lembrete_devido(registo, dia):
    """('8m'|'10m', ref) se nesse dia o cliente deve ter lembrete; senão (None, ref)."""
    if not normalizar_telemovel(registo.contacto):
        return None, None  # fixo ou número mal escrito: não dá para SMS
    sit = situacao(registo, dia)
    ref = sit['ref']
    if not ref or sit['agendada'] or dia >= _somar_meses(ref, 12):
        return None, ref
    if dia >= _somar_meses(ref, 10):
        return '10m', ref
    if dia >= _somar_meses(ref, 8):
        return '8m', ref
    return None, ref


def _texto(org, tipo, tipo_servico):
    if tipo == '10m':
        return texto_sms(org, 'faltam 2 meses para a manutenção anual do seu ar condicionado.', 'Contacte-nos para marcar:')
    t = (tipo_servico or '').lower()
    desde = 'a sua instalação' if 'instala' in t else 'a última manutenção' if 'manuten' in t else 'o último serviço'
    return texto_sms(org, f'já passaram 8 meses desde {desde}. Está na altura de marcar a manutenção anual.', 'Contacte-nos:')


def enviar_lembrete(lembrete):
    """Envia um lembrete já preparado e regista o resultado. Devolve (ok, erro)."""
    ok, erro = send_sms(lembrete.registo.contacto, lembrete.texto)
    lembrete.estado = 'enviado' if ok else 'falhou'
    lembrete.motivo = None if ok else (erro or '')[:200]
    lembrete.enviado_em = datetime.now() if ok else None
    db.session.commit()
    return ok, erro


def enviar_lembretes(simular=False, hoje=None):
    """Trabalho diário: envia os SMS previstos para hoje e prepara os de amanhã."""
    hoje = hoje or date.today()
    amanha = hoje + timedelta(days=1)
    for org in db.session.query(Organizacao).all():
        # 0. Manutenções agendadas que já passaram passam a último serviço
        feitas = [] if simular else _registar_agendadas_passadas(org, hoje)
        desligado = 'lembretes desligados no Dashboard' if not org.sms_lembretes else \
            'Twilio não configurado' if not TWILIO_ACCOUNT_SID else None
        # A simulação mostra o que aconteceria mesmo com os lembretes ainda desligados (para testar antes de ligar)
        if desligado and not simular:
            if feitas:
                _notificar_admins(org, [], [], [], feitas)
            print(f'{org.nome}: sem SMS ({desligado}), {len(feitas)} manutenções agendadas registadas como feitas.')
            continue
        if desligado:
            print(f'[simular] {org.nome}: {desligado}; mostra o que seria enviado se estivessem ligados.')
        # 1. Enviar os de hoje (se ainda fizerem sentido: entretanto pode ter sido agendada ou feita a manutenção)
        enviados, falhados = [], []
        pendentes = db.session.query(LembreteSMS).filter(LembreteSMS.org_id == org.id, LembreteSMS.estado == 'pendente',
                                                         LembreteSMS.enviar_em <= hoje).all()
        for lem in pendentes:
            tipo, ref = _lembrete_devido(lem.registo, hoje)
            if not tipo or ref.strftime('%d/%m/%Y') != lem.referencia:
                if not simular:
                    lem.estado, lem.motivo = 'cancelado', 'Já não se aplica (manutenção agendada ou feita entretanto)'
                    db.session.commit()
                continue
            if simular:
                print(f'[simular] hoje   | {lem.registo.nome} ({lem.registo.contacto}): {lem.texto}')
                enviados.append(lem.registo.nome)
                continue
            ok, erro = enviar_lembrete(lem)
            (enviados if ok else falhados).append(lem.registo.nome)
            if not ok:
                print(f'Falhou {lem.registo.nome} ({lem.registo.contacto}): {erro}')

        # 2. Preparar os de amanhã
        preparados = []
        registos = db.session.query(Registo).filter(Registo.org_id == org.id).options(
            joinedload(Registo.servicos), joinedload(Registo.lembretes)).all()
        for r in registos:
            tipo, ref = _lembrete_devido(r, amanha)
            if not tipo:
                continue
            ref_txt = ref.strftime('%d/%m/%Y')
            if any(lem.tipo == tipo and lem.referencia == ref_txt for lem in r.lembretes):
                continue  # já foi preparado (enviado, cancelado ou pendente)
            texto = _texto(org, tipo, situacao(r, amanha)['tipo'])
            if simular:
                print(f'[simular] amanhã | {r.nome} ({r.contacto}): {texto}')
                preparados.append(r)  # só para a contagem do resumo
                continue
            lem = LembreteSMS(org_id=org.id, registo_id=r.id, tipo=tipo, referencia=ref_txt, texto=texto, enviar_em=amanha)
            db.session.add(lem)
            preparados.append(lem)
        db.session.commit()

        if not simular:
            _notificar_admins(org, enviados, falhados, preparados, feitas)
        print(f'{org.nome}: {len(enviados)} enviados, {len(falhados)} falhados, {len(preparados)} preparados para amanhã, '
              f'{len(feitas)} manutenções agendadas registadas como feitas.')


MAX_NOTIFICACOES_SMS = 10


def _lista(nomes, maximo=8):
    return ', '.join(nomes[:maximo]) + (f' e mais {len(nomes) - maximo}' if len(nomes) > maximo else '')


def _notificar_admins(org, enviados, falhados, preparados, feitas=()):
    """Notificações (sino + push) aos admins: o que saiu hoje, o que sai amanhã e as manutenções dadas como feitas."""
    avisos = []
    if len(preparados) > MAX_NOTIFICACOES_SMS:
        # Muitos de uma vez (ex.: no 1.º dia): um resumo, para não encher o sino
        nomes = [f'{lem.registo.nome} ({"faltam 2 meses" if lem.tipo == "10m" else "8 meses"})' for lem in preparados]
        avisos.append((f'📅 Amanhã saem {len(preparados)} SMS de manutenção',
                       f'{_lista(nomes)}. Toque para ver ou cancelar.', '/lembretes'))
    else:
        # Um por SMS, com os botões "Não enviar" / "Enviar já" no sino
        for lem in preparados:
            motivo = 'faltam 2 meses para a manutenção anual' if lem.tipo == '10m' else '8 meses desde o último serviço'
            avisos.append((f'📅 Amanhã sai SMS para {lem.registo.nome}',
                           f'{motivo} ({lem.registo.contacto}). Sai às 9h, a não ser que cancele.', f'/lembretes#l{lem.id}'))
    if enviados or falhados:
        corpo = _lista(enviados) if enviados else ''
        if falhados:
            corpo += ('. ' if corpo else '') + f'Falharam ({len(falhados)}): {_lista(falhados, 5)}'
        avisos.append((f'📱 {len(enviados)} SMS de manutenção enviado{"s" if len(enviados) != 1 else ""} hoje',
                       corpo, '/lembretes'))
    if feitas:
        n = len(feitas)
        avisos.append((f'✅ {n} manutenç{"ões" if n != 1 else "ão"} agendada{"s" if n != 1 else ""} registada{"s" if n != 1 else ""} como feita{"s" if n != 1 else ""}',
                       f'{_lista(feitas)}. A data já passou e passou a último serviço.', '/registos'))
    if not avisos:
        return
    app = current_app._get_current_object()
    for admin in db.session.query(Usuario).filter_by(org_id=org.id, is_admin=True).all():
        for titulo, corpo, url in avisos:
            send_push_to_user(app, admin.id, titulo, corpo, url)
