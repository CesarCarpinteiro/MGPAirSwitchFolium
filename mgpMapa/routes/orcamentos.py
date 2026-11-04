import csv
import io
import os
import re
import unicodedata
from datetime import datetime

from flask import Blueprint, Response, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from db import db
from models import Orcamento, OrcamentoLinha, Organizacao, Produto, Usuario
from utils import TWILIO_ACCOUNT_SID, send_sms, texto_sms

orcamentos_bp = Blueprint('orcamentos', __name__)

IVA_PADRAO = 23.0
MARGEM_PADRAO = 35.0

# Textos por omissão (do orçamento modelo da MGP Air Switch); cada organização pode alterá-los
TERMOS_PADRAO = (
    'Neste orçamento está incluída a mão de obra.\n'
    'Tubagem em cobre isolado a poliuretano de alta densidade entre as unidades interiores e exteriores.\n'
    'Drenagem de condensados em PVC.\n'
    'Instalação elétrica para cada aparelho.\n'
    'Excluímos todos os trabalhos de construção.'
)
PAGAMENTO_PADRAO = (
    'Na adjudicação 50% do valor da obra\n'
    'Os restantes 50%\n'
    'Autos mensais do 25 ao 30 de cada mês\n'
    'Emissão da fatura ao dia 1\n'
    'Recebimento até ao dia 10 do mesmo mês da emissão da fatura, sem retenções'
)


def _org():
    return db.session.query(Organizacao).filter_by(id=current_user.org_id).first()


def _margem(org):
    return MARGEM_PADRAO if org is None or org.orc_margem is None else org.orc_margem


def _texto(valor, padrao):
    # None = nunca definido (usa o modelo); '' = o admin apagou de propósito
    return padrao if valor is None else valor


@orcamentos_bp.route('/orcamentos')
@login_required
def orcamentos():
    is_admin = current_user.is_admin
    if is_admin:
        todos = db.session.query(Orcamento, Usuario).join(Usuario, Orcamento.user_id == Usuario.id).filter(
            Orcamento.org_id == current_user.org_id).order_by(Orcamento.id.desc()).all()
    else:
        todos = db.session.query(Orcamento, Usuario).join(Usuario, Orcamento.user_id == Usuario.id).filter(
            Orcamento.org_id == current_user.org_id, Orcamento.user_id == current_user.id).order_by(Orcamento.id.desc()).all()
    return render_template('orcamentos.html', orcamentos=todos, is_admin=is_admin,
                           novo_id=request.args.get('novo', type=int))


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
    novo = request.form.get('estado')
    if o and novo in ESTADOS and novo != o.estado:
        o.estado = novo
        db.session.commit()
        _sms_estado(o)
    return redirect(url_for('orcamentos.orcamentos'))


ESTADOS = ('Pendente', 'Aprovado', 'Rejeitado', 'Concluído')
SMS_ESTADO = {
    'Aprovado': 'o seu orçamento nº {id} foi aprovado. Vamos contactá-lo para agendar.',
    'Concluído': 'a sua instalação está concluída. Obrigado pela preferência e confiança!',
}


def _sms_estado(o):
    """Avisa o cliente por SMS quando o orçamento é aprovado ou concluído (se houver telemóvel)."""
    modelo = SMS_ESTADO.get(o.estado)
    if not modelo or not o.cliente_contacto or not TWILIO_ACCOUNT_SID:
        return
    org = _org()
    ok, erro = send_sms(o.cliente_contacto, texto_sms(org, modelo.format(id=o.id)),
                        remetente=org.nome if org else None)
    if ok:
        flash(f'SMS enviado ao cliente ({o.cliente_contacto}).', 'success')
    else:
        flash(f'Estado atualizado, mas o SMS falhou: {erro}', 'error')


# ── Orçamento automático ──────────────────────────────────────────────

def _num(value, default=0.0):
    """Converte '1.234,56 €', '1234.56' ou 1234.56 para float."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value) if value == value else default  # NaN -> default
    s = re.sub(r'[^\d,.\-]', '', str(value))
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    else:
        s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return default


def calcular_totais(linhas, desconto, iva_taxa):
    subtotal = sum((l.quantidade or 0) * (l.preco_unitario or 0) for l in linhas)
    desconto_valor = subtotal * (desconto or 0) / 100
    base = subtotal - desconto_valor
    iva = base * (iva_taxa or 0) / 100
    return dict(subtotal=subtotal, desconto_valor=desconto_valor, base=base, iva=iva, total=base + iva)


@orcamentos_bp.route('/orcamentos/novo', methods=['GET', 'POST'])
@login_required
def novo_orcamento():
    if request.method == 'POST':
        cliente = request.form.get('cliente', '').strip()
        produto_ids = request.form.getlist('linha_produto_id')
        descricoes = request.form.getlist('linha_descricao')
        quantidades = request.form.getlist('linha_qtd')
        precos = request.form.getlist('linha_preco')

        # Só aceita produtos do catálogo da própria organização
        ids_validos = {p.id for p in db.session.query(Produto.id).filter_by(org_id=current_user.org_id)}
        linhas = []
        for pid, desc, qtd, preco in zip(produto_ids, descricoes, quantidades, precos):
            desc = desc.strip()
            if not desc:
                continue
            pid = int(pid) if pid.isdigit() and int(pid) in ids_validos else None
            linhas.append(OrcamentoLinha(produto_id=pid, descricao=desc[:300],
                                         quantidade=_num(qtd, 1), preco_unitario=_num(preco)))

        if not cliente or not linhas:
            flash('Indique o cliente e pelo menos uma linha.', 'error')
            return redirect(url_for('orcamentos.novo_orcamento'))

        desconto = min(max(_num(request.form.get('desconto')), 0), 100)
        iva_taxa = _num(request.form.get('iva_taxa'), IVA_PADRAO)
        totais = calcular_totais(linhas, desconto, iva_taxa)
        num_maquinas = request.form.get('num_maquinas', type=int)

        o = Orcamento(org_id=current_user.org_id, user_id=current_user.id, cliente=cliente,
                      cliente_nif=request.form.get('cliente_nif', '').strip(),
                      cliente_contacto=request.form.get('cliente_contacto', '').strip(),
                      cliente_email=request.form.get('cliente_email', '').strip(),
                      cliente_morada=request.form.get('cliente_morada', '').strip(),
                      descricao='; '.join(l.descricao for l in linhas)[:500],
                      termos=request.form.get('termos', '').strip(),
                      condicoes_pagamento=request.form.get('condicoes_pagamento', '').strip(),
                      num_maquinas=num_maquinas, desconto=desconto, iva_taxa=iva_taxa,
                      valor=round(totais['total'], 2), estado='Pendente',
                      created_at=datetime.now().strftime('%d/%m/%Y'), linhas=linhas)
        db.session.add(o)
        db.session.commit()
        flash(f'Orçamento #{o.id} criado.', 'success')
        return redirect(url_for('orcamentos.orcamentos', novo=o.id))

    org = _org()
    tem_catalogo = db.session.query(Produto.id).filter_by(org_id=current_user.org_id).first() is not None
    return render_template('orcamento_novo.html', iva_padrao=IVA_PADRAO, tem_catalogo=tem_catalogo,
                           is_admin=current_user.is_admin, margem=_margem(org),
                           termos=_texto(org.orc_termos if org else None, TERMOS_PADRAO),
                           pagamento=_texto(org.orc_pagamento if org else None, PAGAMENTO_PADRAO))


@orcamentos_bp.route('/api/produtos')
@login_required
def api_produtos():
    q = request.args.get('q', '').strip()
    query = db.session.query(Produto).filter(Produto.org_id == current_user.org_id)
    for termo in q.split()[:6]:
        like = f'%{termo}%'
        query = query.filter(or_(Produto.marca.ilike(like), Produto.modelo.ilike(like),
                                 Produto.descricao.ilike(like), Produto.categoria.ilike(like)))
    produtos = query.order_by(Produto.marca, Produto.modelo).limit(15).all()
    fator = 1 + _margem(_org()) / 100
    return jsonify([{
        'id': p.id,
        'marca': p.marca or '',
        'modelo': p.modelo,
        'descricao': p.descricao or '',
        'categoria': p.categoria or '',
        'preco': round(p.preco * fator, 2),  # preço de venda (catálogo + margem), sem IVA
        'label': ' '.join(x for x in [p.marca, p.modelo, p.descricao] if x),
    } for p in produtos])


@orcamentos_bp.route('/orcamentos/<int:id>/pdf')
@login_required
def orcamento_pdf(id):
    o = db.session.query(Orcamento).filter_by(id=id, org_id=current_user.org_id).first()
    if not o or not (o.user_id == current_user.id or current_user.is_admin):
        return redirect(url_for('orcamentos.orcamentos'))
    from pdf_orcamento import gerar_pdf_orcamento
    org = db.session.query(Organizacao).filter_by(id=current_user.org_id).first()
    totais = calcular_totais(o.linhas, o.desconto, o.iva_taxa)
    logo = os.path.join(current_app.root_path, current_app.config['UPLOAD_FOLDER'], org.logo) if org and org.logo else None
    pdf = gerar_pdf_orcamento(o, org, totais, logo)
    nome = re.sub(r'[^\w\-]+', '_', o.cliente or 'cliente')
    return send_file(io.BytesIO(pdf), mimetype='application/pdf',
                     download_name=f'orcamento_{o.id}_{nome}.pdf',
                     as_attachment=request.args.get('download') == '1')


# ── Catálogo de produtos (admin) ──────────────────────────────────────

COLUNAS_CATALOGO = {
    'marca': ['marca', 'brand', 'fabricante'],
    'modelo': ['modelo', 'model', 'referencia', 'ref', 'codigo'],
    'descricao': ['descricao', 'description', 'designacao', 'produto', 'nome'],
    'categoria': ['categoria', 'tipo', 'category', 'familia', 'gama'],
    'preco': ['preco', 'price', 'pvp', 'valor', 'custo'],
}


def _normalizar(texto):
    texto = unicodedata.normalize('NFKD', str(texto)).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]', '', texto.lower())


def _mapear_colunas(colunas):
    mapa = {}
    for campo, aliases in COLUNAS_CATALOGO.items():
        for col in colunas:
            n = _normalizar(col)
            if col not in mapa.values() and any(n == a or n.startswith(a) for a in aliases):
                mapa[campo] = col
                break
    return mapa


def _ler_tabela(ficheiro):
    """Lê um CSV (separador detetado) ou .xlsx; devolve (colunas, linhas)."""
    if ficheiro.filename.lower().endswith('.xlsx'):
        from openpyxl import load_workbook
        ws = load_workbook(ficheiro, read_only=True, data_only=True).active
        linhas = [list(r) for r in ws.iter_rows(values_only=True) if any(c not in (None, '') for c in r)]
    else:
        raw = ficheiro.read()
        try:
            texto = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            texto = raw.decode('latin-1')
        try:
            dialeto = csv.Sniffer().sniff(texto[:4096], delimiters=';,\t|')
        except csv.Error:
            dialeto = csv.excel
        linhas = [r for r in csv.reader(io.StringIO(texto), dialeto) if any(c.strip() for c in r)]
    if not linhas:
        raise ValueError('ficheiro vazio')
    colunas = [str(c).strip() if c is not None else '' for c in linhas[0]]
    return colunas, linhas[1:]


def _admin_required():
    if not current_user.is_admin:
        flash('Apenas administradores podem gerir o catálogo.', 'error')
        return redirect(url_for('orcamentos.orcamentos'))
    return None


@orcamentos_bp.route('/orcamentos/catalogo', methods=['GET', 'POST'])
@login_required
def catalogo():
    negado = _admin_required()
    if negado:
        return negado
    if request.method == 'POST':
        modelo = request.form.get('modelo', '').strip()
        preco = request.form.get('preco', '')
        if modelo and preco:
            db.session.add(Produto(org_id=current_user.org_id, marca=request.form.get('marca', '').strip(),
                                   modelo=modelo, descricao=request.form.get('descricao', '').strip(),
                                   categoria=request.form.get('categoria', '').strip(), preco=_num(preco)))
            db.session.commit()
            flash('Produto adicionado.', 'success')
        return redirect(url_for('orcamentos.catalogo'))
    produtos = db.session.query(Produto).filter_by(org_id=current_user.org_id).order_by(
        Produto.categoria, Produto.marca, Produto.modelo).all()
    return render_template('catalogo.html', produtos=produtos, is_admin=True)


@orcamentos_bp.route('/orcamentos/catalogo/importar', methods=['POST'])
@login_required
def importar_catalogo():
    negado = _admin_required()
    if negado:
        return negado
    ficheiro = request.files.get('ficheiro')
    if not ficheiro or not ficheiro.filename:
        flash('Escolha um ficheiro CSV ou Excel.', 'error')
        return redirect(url_for('orcamentos.catalogo'))

    try:
        colunas, linhas = _ler_tabela(ficheiro)
    except Exception as e:
        flash(f'Não foi possível ler o ficheiro: {e}', 'error')
        return redirect(url_for('orcamentos.catalogo'))

    mapa = _mapear_colunas(colunas)
    if 'preco' not in mapa or not ({'modelo', 'descricao'} & mapa.keys()):
        flash('O ficheiro precisa de uma coluna de preço e de uma coluna modelo (ou descrição). '
              f'Colunas encontradas: {", ".join(colunas)}', 'error')
        return redirect(url_for('orcamentos.catalogo'))
    indice = {campo: colunas.index(col) for campo, col in mapa.items()}

    def valor(row, campo):
        i = indice.get(campo)
        if i is None or i >= len(row) or row[i] is None:
            return ''
        return str(row[i]).strip()

    novos, ignorados = [], 0
    for row in linhas:
        modelo = valor(row, 'modelo') or valor(row, 'descricao')
        preco = _num(row[indice['preco']], None) if valor(row, 'preco') else None
        if not modelo or preco is None:
            ignorados += 1
            continue
        descricao = valor(row, 'descricao') if 'modelo' in mapa else ''
        novos.append(Produto(org_id=current_user.org_id, marca=valor(row, 'marca')[:100], modelo=modelo[:200],
                             descricao=descricao[:300], categoria=valor(row, 'categoria')[:100], preco=preco))

    if request.form.get('substituir') == '1':
        ids_org = db.session.query(Produto.id).filter_by(org_id=current_user.org_id)
        db.session.query(OrcamentoLinha).filter(OrcamentoLinha.produto_id.in_(ids_org)).update(
            {'produto_id': None}, synchronize_session=False)
        db.session.query(Produto).filter_by(org_id=current_user.org_id).delete(synchronize_session=False)
    db.session.add_all(novos)
    db.session.commit()
    msg = f'{len(novos)} produtos importados.'
    if ignorados:
        msg += f' {ignorados} linhas ignoradas (sem modelo ou preço).'
    flash(msg, 'success')
    return redirect(url_for('orcamentos.catalogo'))


@orcamentos_bp.route('/orcamentos/catalogo/modelo.csv')
@login_required
def modelo_catalogo_csv():
    csv = ('marca;modelo;descricao;categoria;preco\n'
           'Daikin;FTXM35R;Split mural 3,5 kW;Ar condicionado;689,00\n'
           ';Instalação standard;Até 3 m de tubagem;Serviço;180,00\n')
    return Response(csv.encode('utf-8-sig'), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=modelo_catalogo.csv'})


@orcamentos_bp.route('/orcamentos/catalogo/editar/<int:id>', methods=['POST'])
@login_required
def editar_produto(id):
    negado = _admin_required()
    if negado:
        return negado
    p = db.session.query(Produto).filter_by(id=id, org_id=current_user.org_id).first()
    if p:
        p.marca = request.form.get('marca', p.marca or '').strip()
        p.modelo = request.form.get('modelo', p.modelo).strip() or p.modelo
        p.descricao = request.form.get('descricao', p.descricao or '').strip()
        p.categoria = request.form.get('categoria', p.categoria or '').strip()
        p.preco = _num(request.form.get('preco'), p.preco)
        db.session.commit()
        flash('Produto atualizado.', 'success')
    return redirect(url_for('orcamentos.catalogo'))


@orcamentos_bp.route('/orcamentos/catalogo/delete/<int:id>', methods=['POST'])
@login_required
def delete_produto(id):
    negado = _admin_required()
    if negado:
        return negado
    p = db.session.query(Produto).filter_by(id=id, org_id=current_user.org_id).first()
    if p:
        db.session.query(OrcamentoLinha).filter_by(produto_id=p.id).update({'produto_id': None})
        db.session.delete(p)
        db.session.commit()
        flash('Produto removido.', 'success')
    return redirect(url_for('orcamentos.catalogo'))


# ── Definições do orçamento (admin) ───────────────────────────────────

@orcamentos_bp.route('/orcamentos/definicoes', methods=['GET', 'POST'])
@login_required
def definicoes():
    negado = _admin_required()
    if negado:
        return negado
    org = _org()
    if request.method == 'POST' and org:
        for campo in ['designacao_social', 'morada', 'email', 'redes', 'nif', 'telefone']:
            setattr(org, campo, request.form.get(campo, '').strip())
        org.orc_margem = min(max(_num(request.form.get('orc_margem'), MARGEM_PADRAO), 0), 1000)
        org.orc_termos = request.form.get('orc_termos', '').strip()
        org.orc_pagamento = request.form.get('orc_pagamento', '').strip()
        org.sms_lembretes = request.form.get('sms_lembretes') == '1'

        logo = request.files.get('logo')
        if logo and logo.filename:
            ext = os.path.splitext(logo.filename)[1].lower()
            if ext not in ('.png', '.jpg', '.jpeg'):
                flash('O logótipo tem de ser PNG ou JPG.', 'error')
                return redirect(url_for('orcamentos.definicoes'))
            pasta = current_app.config['UPLOAD_FOLDER']
            os.makedirs(pasta, exist_ok=True)
            nome = f'logo_org_{org.id}{ext}'
            logo.save(os.path.join(pasta, nome))
            org.logo = nome
        elif request.form.get('remover_logo') == '1':
            org.logo = None

        db.session.commit()
        flash('Definições guardadas.', 'success')
        return redirect(url_for('orcamentos.definicoes'))
    return render_template('orcamento_definicoes.html', o=org, margem=_margem(org),
                           termos=_texto(org.orc_termos if org else None, TERMOS_PADRAO),
                           pagamento=_texto(org.orc_pagamento if org else None, PAGAMENTO_PADRAO),
                           sms_configurado=bool(TWILIO_ACCOUNT_SID), is_admin=True)
