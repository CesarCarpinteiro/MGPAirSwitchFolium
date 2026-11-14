import io
import json
import os
import re
import uuid
from datetime import datetime

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from PIL import Image, UnidentifiedImageError

from db import db
from models import Organizacao, Planta, Usuario

plantas_bp = Blueprint('plantas', __name__)

MAX_LADO = 4000            # px; plantas maiores são reduzidas
MAX_UPLOAD = 15 * 1024 * 1024
MAX_DESENHO = 1024 * 1024  # bytes de JSON


def _pasta():
    pasta = os.path.join(current_app.root_path, current_app.config['UPLOAD_FOLDER'], 'plantas')
    os.makedirs(pasta, exist_ok=True)
    return pasta


def _planta(id):
    p = db.session.query(Planta).filter_by(id=id, org_id=current_user.org_id).first()
    if not p:
        abort(404)
    return p


def _pode_apagar(p):
    return current_user.is_admin or p.created_by == current_user.id


@plantas_bp.route('/plantas')
@login_required
def plantas():
    lista = db.session.query(Planta, Usuario).outerjoin(Usuario, Planta.created_by == Usuario.id).filter(
        Planta.org_id == current_user.org_id).order_by(Planta.atualizado_em.desc()).all()
    return render_template('plantas.html', plantas=lista, is_admin=current_user.is_admin)


@plantas_bp.route('/plantas/nova', methods=['POST'])
@login_required
def nova_planta():
    """Recebe a planta já em imagem (o browser converte os PDF) e grava-a em JPEG."""
    if (request.content_length or 0) > MAX_UPLOAD:
        return jsonify({'ok': False, 'mensagem': 'O ficheiro é demasiado grande (máx. 15 MB).'}), 400
    nome = request.form.get('nome', '').strip()
    ficheiro = request.files.get('imagem')
    if not nome or not ficheiro:
        return jsonify({'ok': False, 'mensagem': 'Indique o nome e escolha a planta.'}), 400
    try:
        img = Image.open(ficheiro.stream)
        if img.format not in ('JPEG', 'PNG', 'WEBP'):
            raise UnidentifiedImageError
        img.load()
    except (UnidentifiedImageError, OSError):
        return jsonify({'ok': False, 'mensagem': 'Formato não suportado. Use PDF, JPG ou PNG.'}), 400

    if img.mode in ('RGBA', 'LA', 'P'):
        fundo = Image.new('RGB', img.size, 'white')  # transparência passa a branco
        img = img.convert('RGBA')
        fundo.paste(img, mask=img.split()[-1])
        img = fundo
    else:
        img = img.convert('RGB')
    img.thumbnail((MAX_LADO, MAX_LADO))
    nome_ficheiro = f'{uuid.uuid4().hex}.jpg'
    img.save(os.path.join(_pasta(), nome_ficheiro), 'JPEG', quality=90)

    p = Planta(org_id=current_user.org_id, created_by=current_user.id, nome=nome[:200],
               morada=request.form.get('morada', '').strip()[:300], imagem=nome_ficheiro,
               largura=img.width, altura=img.height, desenho=None)
    db.session.add(p)
    db.session.commit()
    return jsonify({'ok': True, 'url': url_for('plantas.editor', id=p.id)})


@plantas_bp.route('/plantas/<int:id>')
@login_required
def editor(id):
    p = _planta(id)
    try:
        desenho = json.loads(p.desenho) if p.desenho else None
    except ValueError:
        desenho = None
    return render_template('planta.html', p=p, desenho=desenho, pode_apagar=_pode_apagar(p))


@plantas_bp.route('/plantas/<int:id>/imagem')
@login_required
def imagem(id):
    p = _planta(id)
    return send_file(os.path.join(_pasta(), p.imagem), mimetype='image/jpeg', max_age=86400)


@plantas_bp.route('/plantas/<int:id>/guardar', methods=['POST'])
@login_required
def guardar(id):
    p = _planta(id)
    if (request.content_length or 0) > MAX_DESENHO:
        return jsonify({'ok': False, 'mensagem': 'Desenho demasiado grande.'}), 400
    dados = request.get_json(silent=True) or {}
    desenho = dados.get('desenho')
    if not isinstance(desenho, dict) or not isinstance(desenho.get('itens', []), list):
        return jsonify({'ok': False, 'mensagem': 'Desenho inválido.'}), 400
    nome = str(dados.get('nome') or '').strip()
    if nome:
        p.nome = nome[:200]
    if 'morada' in dados:
        p.morada = str(dados.get('morada') or '').strip()[:300]
    p.desenho = json.dumps(desenho, ensure_ascii=False)
    p.atualizado_em = datetime.now()
    db.session.commit()
    return jsonify({'ok': True, 'mensagem': 'Planta guardada.'})


@plantas_bp.route('/plantas/<int:id>/pdf', methods=['POST'])
@login_required
def exportar_pdf(id):
    """Recebe a planta já desenhada (imagem feita no browser) e devolve-a num PDF A4 com cabeçalho."""
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    p = _planta(id)
    if (request.content_length or 0) > 25 * 1024 * 1024:
        return jsonify({'ok': False, 'mensagem': 'A imagem é demasiado grande.'}), 400
    try:
        img = Image.open(request.files['imagem'].stream)
        img.load()
        img = img.convert('RGB')
    except (KeyError, UnidentifiedImageError, OSError):
        return jsonify({'ok': False, 'mensagem': 'Não foi possível gerar o PDF.'}), 400

    org = db.session.get(Organizacao, current_user.org_id)
    pagina = landscape(A4) if img.width >= img.height else A4
    largura, altura = pagina
    margem, topo = 12 * mm, 20 * mm
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=pagina)
    c.setTitle(p.nome)

    # Cabeçalho: logótipo, empresa, nome e morada da planta, data
    x = margem
    if org and org.logo:
        caminho_logo = os.path.join(current_app.root_path, current_app.config['UPLOAD_FOLDER'], org.logo)
        if os.path.exists(caminho_logo):
            try:
                logo = ImageReader(caminho_logo)
                lw, lh = logo.getSize()
                h = 12 * mm
                c.drawImage(logo, x, altura - margem - h, width=h * lw / lh, height=h, mask='auto')
                x += h * lw / lh + 5 * mm
            except Exception:
                pass
    azul = HexColor('#2d3a6e')
    c.setFillColor(azul)
    c.setFont('Helvetica-Bold', 13)
    c.drawString(x, altura - margem - 5 * mm, p.nome[:90])
    c.setFont('Helvetica', 9)
    c.setFillColor(HexColor('#555555'))
    sub = ' · '.join(t for t in [p.morada, (org.designacao_social or org.nome) if org else ''] if t)
    if sub:
        c.drawString(x, altura - margem - 10 * mm, sub[:140])
    c.drawRightString(largura - margem, altura - margem - 5 * mm, datetime.now().strftime('%d/%m/%Y'))
    c.setStrokeColor(HexColor('#c5cae9'))
    c.line(margem, altura - margem - topo + 4 * mm, largura - margem, altura - margem - topo + 4 * mm)

    # Planta ajustada ao espaço que sobra, centrada
    caixa_l, caixa_a = largura - 2 * margem, altura - 2 * margem - topo
    escala = min(caixa_l / img.width, caixa_a / img.height)
    w, h = img.width * escala, img.height * escala
    c.drawImage(ImageReader(img), margem + (caixa_l - w) / 2, margem + (caixa_a - h) / 2, width=w, height=h)
    c.showPage()
    c.save()
    buf.seek(0)
    nome = re.sub(r'[^\w\-]+', '_', p.nome).strip('_') or 'planta'
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=f'{nome}.pdf')


@plantas_bp.route('/plantas/<int:id>/nome', methods=['POST'])
@login_required
def mudar_nome(id):
    p = _planta(id)
    dados = request.get_json(silent=True) or {}
    nome = str(dados.get('nome') or '').strip()
    if not nome:
        return jsonify({'ok': False, 'mensagem': 'Indique um nome.'}), 400
    p.nome = nome[:200]
    db.session.commit()
    return jsonify({'ok': True, 'nome': p.nome})


@plantas_bp.route('/plantas/<int:id>/apagar', methods=['POST'])
@login_required
def apagar(id):
    p = _planta(id)
    if not _pode_apagar(p):
        flash('Só quem criou a planta ou um administrador a pode apagar.', 'error')
        return redirect(url_for('plantas.editor', id=id))
    caminho = os.path.join(_pasta(), p.imagem)
    db.session.delete(p)
    db.session.commit()
    if os.path.exists(caminho):
        os.remove(caminho)
    flash('Planta apagada.', 'success')
    return redirect(url_for('plantas.plantas'))
