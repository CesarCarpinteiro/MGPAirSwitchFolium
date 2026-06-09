import os

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from db import db
from models import Fatura, Usuario
from utils import UPLOAD_FOLDER, allowed_file

faturas_bp = Blueprint('faturas', __name__)


@faturas_bp.route('/faturas', methods=['GET', 'POST'])
@login_required
def faturas():
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    if request.method == 'POST':
        local = request.form.get('local')
        valor = request.form.get('valor')
        data = request.form.get('data')
        nota = request.form.get('nota')
        ficheiro_path = None
        file = request.files.get('ficheiro')
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(f"{current_user.id}_{file.filename}")
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            ficheiro_path = filename
        if local and valor and data:
            nova = Fatura(org_id=current_user.org_id, user_id=current_user.id,
                          local=local, valor=float(valor), data=data, nota=nota, ficheiro=ficheiro_path)
            db.session.add(nova)
            db.session.commit()
            flash('Fatura guardada.', 'success')
    if current_user.is_admin:
        todas = db.session.query(Fatura, Usuario).join(Usuario, Fatura.user_id == Usuario.id).filter(
            Fatura.org_id == current_user.org_id).order_by(Fatura.id.desc()).all()
    else:
        todas = db.session.query(Fatura, Usuario).join(Usuario, Fatura.user_id == Usuario.id).filter(
            Fatura.org_id == current_user.org_id, Fatura.user_id == current_user.id).order_by(Fatura.id.desc()).all()
    usuarios = db.session.query(Usuario).filter_by(org_id=current_user.org_id).all()
    total = sum(f.valor for f, u in todas)
    return render_template('faturas.html', faturas=todas, total=total, usuarios=usuarios)


@faturas_bp.route('/faturas/delete/<int:id>', methods=['POST'])
@login_required
def delete_fatura(id):
    fatura = db.session.query(Fatura).filter_by(id=id, org_id=current_user.org_id).first()
    if fatura and (fatura.user_id == current_user.id or current_user.is_admin):
        if fatura.ficheiro:
            try:
                os.remove(os.path.join(UPLOAD_FOLDER, fatura.ficheiro))
            except Exception:
                pass
        db.session.delete(fatura)
        db.session.commit()
        flash('Fatura removida.', 'success')
    return redirect(url_for('faturas.faturas'))