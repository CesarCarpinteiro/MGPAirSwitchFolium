from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from db import db
from models import Orcamento, Usuario

orcamentos_bp = Blueprint('orcamentos', __name__)


@orcamentos_bp.route('/orcamentos', methods=['GET', 'POST'])
@login_required
def orcamentos():
    is_admin = current_user.is_admin
    if request.method == 'POST':
        cliente = request.form.get('cliente')
        descricao = request.form.get('descricao')
        num_maquinas = request.form.get('num_maquinas', type=int)
        valor = request.form.get('valor', type=float)
        if cliente:
            novo = Orcamento(org_id=current_user.org_id, user_id=current_user.id, cliente=cliente,
                             descricao=descricao, num_maquinas=num_maquinas, valor=valor,
                             estado='Pendente', created_at=datetime.now().strftime('%d/%m/%Y'))
            db.session.add(novo)
            db.session.commit()
            flash('Orçamento criado.', 'success')
    if is_admin:
        todos = db.session.query(Orcamento, Usuario).join(Usuario, Orcamento.user_id == Usuario.id).filter(
            Orcamento.org_id == current_user.org_id).order_by(Orcamento.id.desc()).all()
    else:
        todos = db.session.query(Orcamento, Usuario).join(Usuario, Orcamento.user_id == Usuario.id).filter(
            Orcamento.org_id == current_user.org_id, Orcamento.user_id == current_user.id).order_by(Orcamento.id.desc()).all()
    return render_template('orcamentos.html', orcamentos=todos, is_admin=is_admin)


@orcamentos_bp.route('/orcamentos/delete/<int:id>', methods=['POST'])
@login_required
def delete_orcamento(id):
    o = db.session.query(Orcamento).filter_by(id=id, org_id=current_user.org_id).first()
    if o and (o.user_id == current_user.id or current_user.is_admin):
        db.session.delete(o)
        db.session.commit()
        flash('Orçamento removido.', 'success')
    return redirect(url_for('orcamentos.orcamentos'))


@orcamentos_bp.route('/orcamentos/estado/<int:id>', methods=['POST'])
@login_required
def update_estado_orcamento(id):
    if not current_user.is_admin:
        return redirect(url_for('orcamentos.orcamentos'))
    o = db.session.query(Orcamento).filter_by(id=id, org_id=current_user.org_id).first()
    if o:
        o.estado = request.form.get('estado')
        db.session.commit()
    return redirect(url_for('orcamentos.orcamentos'))