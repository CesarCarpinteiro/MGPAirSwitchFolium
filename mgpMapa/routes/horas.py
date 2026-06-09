from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from db import db
from models import HorasTrabalhadas, Usuario

horas_bp = Blueprint('horas', __name__)


@horas_bp.route('/horas', methods=['GET', 'POST'])
@login_required
def horas():
    mes = request.args.get('mes', datetime.now().month, type=int)
    ano = request.args.get('ano', datetime.now().year, type=int)
    is_admin = current_user.is_admin
    if is_admin:
        registos = db.session.query(HorasTrabalhadas).filter_by(
            org_id=current_user.org_id, mes=mes, ano=ano).order_by(HorasTrabalhadas.dia).all()
    else:
        registos = db.session.query(HorasTrabalhadas).filter_by(
            org_id=current_user.org_id, user_id=current_user.id, mes=mes, ano=ano).order_by(HorasTrabalhadas.dia).all()
    usuarios = db.session.query(Usuario).filter_by(org_id=current_user.org_id).all() if is_admin else []
    return render_template('horas.html', registos=registos, mes=mes, ano=ano, is_admin=is_admin,
                           usuarios=usuarios, current_user=current_user, today_dia=datetime.now().day)


@horas_bp.route('/horas/add', methods=['POST'])
@login_required
def horas_add():
    mes = request.form.get('mes', type=int)
    ano = request.form.get('ano', type=int)
    dia = request.form.get('dia', type=int)
    manha = request.form.get('manha', 0, type=float)
    tarde = request.form.get('tarde', 0, type=float)
    extra = request.form.get('extra', 0, type=float)
    observacoes = request.form.get('observacoes', '')
    local = request.form.get('local', '')
    novo = HorasTrabalhadas(org_id=current_user.org_id, user_id=current_user.id, user_nome=current_user.nome,
                            mes=mes, ano=ano, dia=dia, manha=manha, tarde=tarde, extra=extra,
                            total=manha + tarde + extra, observacoes=observacoes, local=local)
    db.session.add(novo)
    db.session.commit()
    flash('Horas registadas.', 'success')
    return redirect(url_for('horas.horas', mes=mes, ano=ano))


@horas_bp.route('/horas/edit/<int:id>', methods=['POST'])
@login_required
def horas_edit(id):
    registo = db.session.query(HorasTrabalhadas).filter_by(id=id, org_id=current_user.org_id).first()
    if registo and (registo.user_id == current_user.id or current_user.is_admin):
        registo.manha = request.form.get('manha', 0, type=float)
        registo.tarde = request.form.get('tarde', 0, type=float)
        registo.extra = request.form.get('extra', 0, type=float)
        registo.total = registo.manha + registo.tarde + registo.extra
        registo.observacoes = request.form.get('observacoes', '')
        registo.local = request.form.get('local', '')
        db.session.commit()
        flash('Horas atualizadas.', 'success')
    return redirect(url_for('horas.horas', mes=registo.mes, ano=registo.ano))


@horas_bp.route('/horas/delete/<int:id>', methods=['POST'])
@login_required
def horas_delete(id):
    registo = db.session.query(HorasTrabalhadas).filter_by(id=id, org_id=current_user.org_id).first()
    mes, ano = registo.mes, registo.ano
    if registo and (registo.user_id == current_user.id or current_user.is_admin):
        db.session.delete(registo)
        db.session.commit()
        flash('Registo removido.', 'success')
    return redirect(url_for('horas.horas', mes=mes, ano=ano))