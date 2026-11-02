import io
import os
from datetime import datetime, timedelta
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

# Cores do orçamento modelo
AZUL = colors.HexColor('#1f3aa6')
AZUL_TABELA = colors.HexColor('#8db3e2')
AZUL_LINHA_1 = colors.HexColor('#c6d9f1')
AZUL_LINHA_2 = colors.HexColor('#dce6f2')
CINZA_AZUL = colors.HexColor('#7f93a8')
LARANJA = colors.HexColor('#f26a1b')
TEXTO = colors.HexColor('#222222')
VALIDADE_DIAS = 30


def eur(valor):
    """1417.5 -> '1 417,50 €' (formato português)"""
    s = f'{valor or 0:,.2f}'.replace(',', ' ').replace('.', ',')
    return f'{s} €'


def qtd(valor):
    return f'{valor:g}'.replace('.', ',')


def _decoracao(canvas, doc):
    """Faixas laranja/azul nos cantos, como no orçamento modelo."""
    w, h = A4
    canvas.saveState()
    canvas.setFillColor(LARANJA)
    p = canvas.beginPath(); p.moveTo(w - 115, h); p.lineTo(w, h); p.lineTo(w, h - 78); p.close()
    canvas.drawPath(p, stroke=0, fill=1)
    canvas.setFillColor(AZUL)
    p = canvas.beginPath(); p.moveTo(w - 148, h); p.lineTo(w - 131, h); p.lineTo(w, h - 89); p.lineTo(w, h - 101); p.close()
    canvas.drawPath(p, stroke=0, fill=1)

    canvas.setFillColor(LARANJA)
    canvas.setFillAlpha(0.9)
    p = canvas.beginPath(); p.moveTo(0, 0); p.lineTo(230, 0); p.lineTo(0, 120); p.close()
    canvas.drawPath(p, stroke=0, fill=1)
    canvas.setFillAlpha(0.18)
    p = canvas.beginPath(); p.moveTo(0, 120); p.lineTo(230, 0); p.lineTo(330, 0); p.lineTo(0, 170); p.close()
    canvas.drawPath(p, stroke=0, fill=1)

    canvas.setFillAlpha(1)
    canvas.setFillColor(CINZA_AZUL)
    canvas.setFont('Helvetica', 7.5)
    canvas.drawRightString(w - 18 * mm, 10 * mm, f'Página {doc.page}')
    canvas.restoreState()


def gerar_pdf_orcamento(o, org, totais, logo_path=None):
    buf = io.BytesIO()
    empresa = (org.designacao_social or org.nome) if org else ''
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=14 * mm, bottomMargin=22 * mm,
                            title=f'Orçamento #{o.id} - {o.cliente}', author=empresa)

    base = ParagraphStyle('base', fontName='Helvetica', fontSize=9, leading=12.5, textColor=TEXTO)
    st = {
        'empresa': ParagraphStyle('empresa', parent=base, fontName='Helvetica-Bold', fontSize=15, leading=19, textColor=AZUL),
        'morada': ParagraphStyle('morada', parent=base, fontName='Helvetica-Bold', fontSize=10.5, leading=14, textColor=AZUL),
        'contacto': ParagraphStyle('contacto', parent=base, fontSize=8.5, alignment=TA_RIGHT),
        'titulo': ParagraphStyle('titulo', parent=base, fontName='Helvetica-Bold', fontSize=12, textColor=AZUL),
        'dir': ParagraphStyle('dir', parent=base, alignment=TA_RIGHT),
        'th': ParagraphStyle('th', parent=base, fontName='Helvetica-Bold', fontSize=8.5),
        'th_r': ParagraphStyle('th_r', parent=base, fontName='Helvetica-Bold', fontSize=8.5, alignment=TA_RIGHT),
        'td': ParagraphStyle('td', parent=base, fontSize=8.5, leading=11),
        'td_r': ParagraphStyle('td_r', parent=base, fontSize=8.5, leading=11, alignment=TA_RIGHT),
        'td_rb': ParagraphStyle('td_rb', parent=base, fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=TA_RIGHT),
        'tot': ParagraphStyle('tot', parent=base, fontSize=12, leading=17, textColor=CINZA_AZUL, alignment=TA_RIGHT),
        'tot_final': ParagraphStyle('tot_final', parent=base, fontName='Helvetica-Bold', fontSize=16, leading=22,
                                    textColor=AZUL, alignment=TA_RIGHT),
        'seccao': ParagraphStyle('seccao', parent=base, fontName='Helvetica-Bold', fontSize=12.5, leading=16,
                                 textColor=AZUL, spaceAfter=4),
        'pequeno': ParagraphStyle('pequeno', parent=base, fontSize=7.5, textColor=CINZA_AZUL),
    }

    def p(texto, estilo):
        return Paragraph(escape(str(texto or '')).replace('\n', '<br/>'), st[estilo])

    story = []

    # ── Cabeçalho: empresa à esquerda, contactos à direita ──
    esquerda = []
    if logo_path and os.path.exists(logo_path):
        img = Image(logo_path)
        escala = min(40 * mm / img.imageWidth, 18 * mm / img.imageHeight)
        img.drawWidth, img.drawHeight = img.imageWidth * escala, img.imageHeight * escala
        img.hAlign = 'LEFT'
        esquerda += [img, Spacer(1, 2 * mm)]
    esquerda.append(p(empresa, 'empresa'))
    if org and org.morada:
        esquerda.append(p(org.morada, 'morada'))
    if org and org.nif:
        esquerda.append(p(f'NIF {org.nif}', 'td'))
    direita = [p(x, 'contacto') for x in [org.telefone, org.redes, org.email] if x] if org else []
    cab = Table([[esquerda, direita]], colWidths=[None, 55 * mm])
    cab.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                             ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                             ('TOPPADDING', (1, 0), (1, 0), 14 * mm)]))  # contactos abaixo da faixa laranja
    story += [cab, Spacer(1, 10 * mm)]

    # ── Nº do orçamento, datas e cliente ──
    try:
        data = datetime.strptime(o.created_at, '%d/%m/%Y')
    except (TypeError, ValueError):
        data = datetime.now()
    cliente = [o.cliente]
    if o.cliente_nif:
        cliente.append(f'NIF: {o.cliente_nif}')
    if o.cliente_morada:
        cliente.append(o.cliente_morada)
    contactos = ' · '.join(x for x in [o.cliente_contacto, o.cliente_email] if x)
    if contactos:
        cliente.append(contactos)
    info = Table([[[p(f'ORÇAMENTO Nº {o.id}', 'titulo'), Spacer(1, 1.5 * mm), p('Cliente', 'th'), p('\n'.join(cliente), 'td')],
                   [p(f'Data: {data:%d/%m/%Y}', 'dir'),
                    p(f'Válido até: {data + timedelta(days=VALIDADE_DIAS):%d/%m/%Y}', 'dir')]]],
                 colWidths=[None, 55 * mm])
    info.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                              ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0)]))
    story += [info, Spacer(1, 7 * mm)]

    # ── Tabela de artigos ──
    dados = [[p('ART', 'th'), p('DESIGNAÇÃO', 'th'), p('UN', 'th'), p('Qtd', 'th_r'),
              p('PVP Unit', 'th_r'), p('Imposto', 'th_r'), p('Total ilíquido', 'th_r')]]
    iva_txt = f'{qtd(o.iva_taxa or 0)}%'
    for i, l in enumerate(o.linhas, 1):
        dados.append([p(i, 'td'), p(l.descricao, 'td'), p('UN', 'td'), p(qtd(l.quantidade or 0), 'td_r'),
                      p(eur(l.preco_unitario), 'td_r'), p(iva_txt, 'td_r'),
                      p(eur((l.quantidade or 0) * (l.preco_unitario or 0)), 'td_rb')])
    tabela = Table(dados, colWidths=[10 * mm, None, 10 * mm, 11 * mm, 25 * mm, 16 * mm, 27 * mm], repeatRows=1)
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), AZUL_TABELA),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [AZUL_LINHA_1, AZUL_LINHA_2]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story += [tabela, Spacer(1, 9 * mm)]

    # ── Totais ──
    linhas_tot = [p(f'Total ilíquido: {eur(totais["subtotal"])}', 'tot')]
    if o.desconto:
        linhas_tot += [p(f'Desconto ({qtd(o.desconto)}%): −{eur(totais["desconto_valor"])}', 'tot'),
                       p(f'Base tributável: {eur(totais["base"])}', 'tot')]
    linhas_tot += [p(f'IVA total: {eur(totais["iva"])}', 'tot'),
                   p(f'Total a pagar: {eur(totais["total"])}', 'tot_final')]
    story += [KeepTogether(linhas_tot), Spacer(1, 10 * mm)]

    # ── Termos e condições / Condições de pagamento ──
    if o.termos:
        story.append(KeepTogether([p('TERMOS E CONDIÇÕES', 'seccao'), p(o.termos, 'td'), Spacer(1, 7 * mm)]))
    if o.condicoes_pagamento:
        itens = [l.strip().lstrip('*•-').strip() for l in o.condicoes_pagamento.splitlines() if l.strip()]
        story.append(KeepTogether([p('CONDIÇÕES DE PAGAMENTO', 'seccao')] +
                                  [Paragraph('• ' + escape(i), st['td']) for i in itens] + [Spacer(1, 6 * mm)]))

    story.append(p(f'Orçamento válido por {VALIDADE_DIAS} dias a contar da data de emissão.', 'pequeno'))

    doc.build(story, onFirstPage=_decoracao, onLaterPages=_decoracao)
    return buf.getvalue()
