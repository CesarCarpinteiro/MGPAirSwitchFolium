from datetime import datetime

from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required

from db import db
from models import (Fatura, Ferias, HorasTrabalhadas, Obra, ObraFuncionario,
                    Orcamento, Organizacao, Usuario)

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    if not current_user.is_admin:
        return redirect(url_for('home.home'))
    now = datetime.now()
    mes, ano = now.month, now.year
    org_id = current_user.org_id
    org = db.session.query(Organizacao).filter_by(id=org_id).first()
    org_nome = org.nome if org else 'A minha Organização'
    tem_mapa = org.tipo_negocio != 'espaco' if org else True

    pendentes = db.session.query(Ferias, Usuario).join(Usuario, Ferias.user_id == Usuario.id).filter(
        Ferias.org_id == org_id, Ferias.estado == 'pendente').order_by(Ferias.id.desc()).all()

    horas_mes = db.session.query(HorasTrabalhadas).filter_by(org_id=org_id, mes=mes, ano=ano).all()
    total_horas = sum(h.total or 0 for h in horas_mes)
    horas_por_func = {}
    for h in horas_mes:
        horas_por_func[h.user_nome] = horas_por_func.get(h.user_nome, 0) + (h.total or 0)

    faturas_mes = db.session.query(Fatura).filter_by(org_id=org_id).filter(
        Fatura.data.like(f'%/{str(mes).zfill(2)}/{ano}')).all()
    total_faturas = sum(f.valor or 0 for f in faturas_mes)

    orcamentos_pendentes = db.session.query(Orcamento).filter_by(org_id=org_id, estado='Pendente').count()

    obras_ativas = db.session.query(Obra).filter_by(org_id=org_id).filter(
        Obra.estado.in_(['agendada', 'em_curso'])).order_by(Obra.data_inicio).all()
    obra_funcs = {of.obra_id: [] for of in db.session.query(ObraFuncionario).filter_by(org_id=org_id).all()}
    for of in db.session.query(ObraFuncionario, Usuario).join(
            Usuario, ObraFuncionario.usuario_id == Usuario.id).filter(ObraFuncionario.org_id == org_id).all():
        obra_funcs.setdefault(of[0].obra_id, []).append(of[1].nome)

    num_funcionarios = db.session.query(Usuario).filter_by(org_id=org_id).count()

    return render_template('dashboard.html',
        org_nome=org_nome, tem_mapa=tem_mapa,
        pendentes=pendentes, total_horas=total_horas, horas_por_func=horas_por_func,
        total_faturas=total_faturas, orcamentos_pendentes=orcamentos_pendentes,
        obras_ativas=obras_ativas, obra_funcs=obra_funcs,
        num_funcionarios=num_funcionarios,
        mes_nome=now.strftime('%B %Y').capitalize(), now=now)