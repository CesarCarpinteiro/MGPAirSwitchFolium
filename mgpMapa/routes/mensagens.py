from flask import Blueprint, render_template
from flask_login import current_user, login_required

from db import db
from models import Mensagem, Usuario

mensagens_bp = Blueprint('mensagens', __name__)


@mensagens_bp.route('/mensagens')
@login_required
def mensagens():
    is_admin = current_user.is_admin
    if is_admin:
        todas = db.session.query(Mensagem, Usuario).join(Usuario, Mensagem.user_id == Usuario.id).filter(
            Mensagem.org_id == current_user.org_id).order_by(Mensagem.id.desc()).all()
    else:
        todas = db.session.query(Mensagem, Usuario).join(Usuario, Mensagem.user_id == Usuario.id).filter(
            Mensagem.org_id == current_user.org_id, Mensagem.user_id == current_user.id).order_by(Mensagem.id.desc()).all()
    return render_template('mensagens.html', mensagens=todas, is_admin=is_admin)