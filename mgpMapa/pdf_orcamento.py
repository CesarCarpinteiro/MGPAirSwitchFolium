import io
import os
from datetime import datetime, timedelta
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

# Cores (as da app + o laranja da marca como destaque)
AZUL = colors.HexColor('#2d3a6e')
AZUL_CLARO = colors.HexColor('#eef0f8')
LARANJA = colors.HexColor('#f26a1b')
TEXTO = colors.HexColor('#1f2433')
CINZA = colors.HexColor('#6b7190')
CINZA_CLARO = colors.HexColor('#9aa0b8')
LINHA = colors.HexColor('#e3e6ef')
FUNDO = colors.HexColor('#f6f7fb')
VALIDADE_DIAS = 30

LARGURA, ALTURA = A4
MARGEM = 16 * mm


def eur(valor):
    """1417.5 -> '1 417,50 €' (formato português)"""
    s = f'{valor or 0:,.2f}'.replace(',', ' ').replace('.', ',')
    return f'{s} €'


def qtd(valor):
    return f'{valor:g}'.replace('.', ',')


class _CanvasNumerado(rl_canvas.Canvas):
    """Canvas que sabe o total de páginas, para o rodapé "Página X de Y"."""

    def __init__(self, *args, rodape=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._paginas = []
        self._rodape = rodape

    def showPage(self):
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self._desenhar_moldura(total)
            super().showPage()
        super().save()

    def _desenhar_moldura(self, total):
        self.saveState()
        # Barra de cor no topo
        self.setFillColor(AZUL)
        self.rect(0, ALTURA - 5 * mm, LARGURA, 5 * mm, stroke=0, fill=1)
        self.setFillColor(LARANJA)
        self.rect(0, ALTURA - 5 * mm, 38 * mm, 5 * mm, stroke=0, fill=1)
        # Rodapé: contactos da empresa e nº de página
        y = 11 * mm
        self.setStrokeColor(LINHA)
        self.setLineWidth(0.6)
        self.line(MARGEM, y + 5 * mm, LARGURA - MARGEM, y + 5 * mm)
        self.setFillColor(CINZA)
        self.setFont('Helvetica', 7.3)
        if self._rodape:
            self.drawString(MARGEM, y, self._rodape[:150])
        self.drawRightString(LARGURA - MARGEM, y, f'Página {self._pageNumber} de {total}')
        self.restoreState()


def gerar_pdf_orcamento(o, org, totais, logo_path=None):
    buf = io.BytesIO()
    empresa = (org.designacao_social or org.nome) if org else ''
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=MARGEM, rightMargin=MARGEM,
                            topMargin=14 * mm, bottomMargin=24 * mm,
                            title=f'Orçamento nº {o.id} - {o.cliente}', author=empresa)
    largura_util = LARGURA - 2 * MARGEM

    base = ParagraphStyle('base', fontName='Helvetica', fontSize=9, leading=12.5, textColor=TEXTO)

    def estilo(nome, **kw):
        return ParagraphStyle(nome, parent=base, **kw)

    st = {
        'empresa': estilo('empresa', fontName='Helvetica-Bold', fontSize=13, leading=16, textColor=AZUL),
        'empresa_sub': estilo('empresa_sub', fontSize=8.3, leading=11.5, textColor=CINZA),
        'doc_titulo': estilo('doc_titulo', fontName='Helvetica-Bold', fontSize=22, leading=25, textColor=AZUL, alignment=TA_RIGHT),
        'doc_num': estilo('doc_num', fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=LARANJA, alignment=TA_RIGHT),
        'meta_l': estilo('meta_l', fontSize=8, leading=11, textColor=CINZA, alignment=TA_RIGHT),
        'meta_v': estilo('meta_v', fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=TA_RIGHT),
        'caixa_t': estilo('caixa_t', fontName='Helvetica-Bold', fontSize=7.3, leading=10, textColor=LARANJA),
        'caixa_nome': estilo('caixa_nome', fontName='Helvetica-Bold', fontSize=10.5, leading=14),
        'caixa_txt': estilo('caixa_txt', fontSize=8.3, leading=11.5, textColor=CINZA),
        'th': estilo('th', fontName='Helvetica-Bold', fontSize=7.8, leading=10, textColor=colors.white),
        'th_r': estilo('th_r', fontName='Helvetica-Bold', fontSize=7.8, leading=10, textColor=colors.white, alignment=TA_RIGHT),
        'th_c': estilo('th_c', fontName='Helvetica-Bold', fontSize=7.8, leading=10, textColor=colors.white, alignment=TA_CENTER),
        'td': estilo('td', fontSize=8.8, leading=11.8),
        'td_num': estilo('td_num', fontSize=8.3, leading=11.8, textColor=CINZA_CLARO, alignment=TA_CENTER),
        'td_r': estilo('td_r', fontSize=8.8, leading=11.8, alignment=TA_RIGHT),
        'td_c': estilo('td_c', fontSize=8.8, leading=11.8, alignment=TA_CENTER),
        'td_rb': estilo('td_rb', fontName='Helvetica-Bold', fontSize=8.8, leading=11.8, alignment=TA_RIGHT),
        'nota': estilo('nota', fontName='Helvetica-Oblique', fontSize=7.8, leading=10.5, textColor=CINZA, spaceBefore=2),
        'incl': estilo('incl', fontSize=8.2, leading=10.8, textColor=CINZA, leftIndent=8),
        'incl_desc': estilo('incl_desc', fontName='Helvetica-Oblique', fontSize=7.6, leading=10, textColor=CINZA_CLARO, leftIndent=16),
        'incl_tag': estilo('incl_tag', fontName='Helvetica-Bold', fontSize=7, leading=10, textColor=colors.HexColor('#2e7d4f'), alignment=TA_RIGHT),
        'tot_l': estilo('tot_l', fontSize=9, leading=12, textColor=CINZA),
        'tot_v': estilo('tot_v', fontSize=9, leading=12, alignment=TA_RIGHT),
        'tot_fl': estilo('tot_fl', fontName='Helvetica-Bold', fontSize=10.5, leading=14, textColor=colors.white),
        'tot_fv': estilo('tot_fv', fontName='Helvetica-Bold', fontSize=14, leading=18, textColor=colors.white, alignment=TA_RIGHT),
        'seccao': estilo('seccao', fontName='Helvetica-Bold', fontSize=9.5, leading=13, textColor=AZUL),
        'texto': estilo('texto', fontSize=8.5, leading=12.2, textColor=colors.HexColor('#3a4055')),
        'pequeno': estilo('pequeno', fontSize=7.5, leading=10, textColor=CINZA),
        'assin': estilo('assin', fontSize=7.8, leading=10, textColor=CINZA, alignment=TA_CENTER),
    }

    def p(texto, nome):
        return Paragraph(escape(str(texto or '')).replace('\n', '<br/>'), st[nome])

    def sem_margens(t, extra=()):
        t.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                               ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                               ('VALIGN', (0, 0), (-1, -1), 'TOP')] + list(extra)))
        return t

    story = []

    # ── Cabeçalho: logótipo + empresa | ORÇAMENTO nº, data, validade ──
    try:
        data = datetime.strptime(o.created_at, '%d/%m/%Y')
    except (TypeError, ValueError):
        data = datetime.now()

    esquerda = []
    if logo_path and os.path.exists(logo_path):
        try:
            img = Image(logo_path)
            escala = min(42 * mm / img.imageWidth, 20 * mm / img.imageHeight)
            img.drawWidth, img.drawHeight = img.imageWidth * escala, img.imageHeight * escala
            img.hAlign = 'LEFT'
            esquerda += [img, Spacer(1, 3 * mm)]
        except Exception:
            pass
    esquerda.append(p(empresa, 'empresa'))
    if org and org.morada:
        esquerda.append(p(org.morada, 'empresa_sub'))

    meta = Table([[p('Data', 'meta_l'), p(f'{data:%d/%m/%Y}', 'meta_v')],
                  [p('Válido até', 'meta_l'), p(f'{data + timedelta(days=VALIDADE_DIAS):%d/%m/%Y}', 'meta_v')]],
                 colWidths=[22 * mm, 24 * mm], hAlign='RIGHT')
    sem_margens(meta, [('BOTTOMPADDING', (0, 0), (-1, -1), 1.5)])
    direita = [p('ORÇAMENTO', 'doc_titulo'), p(f'Nº {o.id:04d}', 'doc_num'), Spacer(1, 3 * mm), meta]

    cab = sem_margens(Table([[esquerda, direita]], colWidths=[largura_util - 70 * mm, 70 * mm]))
    story += [Spacer(1, 4 * mm), cab, Spacer(1, 8 * mm)]

    # ── Cartões: cliente | empresa ──
    cliente = [p('CLIENTE', 'caixa_t'), Spacer(1, 1.5 * mm), p(o.cliente, 'caixa_nome')]
    det_cliente = [x for x in [f'NIF {o.cliente_nif}' if o.cliente_nif else '', o.cliente_morada,
                               o.cliente_contacto, o.cliente_email] if x]
    if det_cliente:
        cliente.append(p('\n'.join(det_cliente), 'caixa_txt'))

    emissor = [p('EMITIDO POR', 'caixa_t'), Spacer(1, 1.5 * mm), p(empresa, 'caixa_nome')]
    det_emp = [x for x in [f'NIF {org.nif}' if org and org.nif else '', org.telefone if org else '',
                           org.email if org else '', org.redes if org else ''] if x]
    if det_emp:
        emissor.append(p('\n'.join(det_emp), 'caixa_txt'))

    meio = 6 * mm
    larg_caixa = (largura_util - meio) / 2
    caixas = Table([[cliente, '', emissor]], colWidths=[larg_caixa, meio, larg_caixa])
    caixas.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (0, 0), FUNDO), ('BACKGROUND', (2, 0), (2, 0), FUNDO),
        ('LINEBEFORE', (0, 0), (0, 0), 2.2, AZUL), ('LINEBEFORE', (2, 0), (2, 0), 2.2, LARANJA),
        ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
        ('LEFTPADDING', (1, 0), (1, 0), 0), ('RIGHTPADDING', (1, 0), (1, 0), 0),
    ]))
    story += [caixas, Spacer(1, 8 * mm)]

    # ── Tabela de artigos ──
    iva_txt = f'{qtd(o.iva_taxa or 0)}%'
    dados = [[p('#', 'th_c'), p('DESCRIÇÃO', 'th'), p('QTD', 'th_c'), p('PREÇO UNIT.', 'th_r'),
              p('IVA', 'th_c'), p('TOTAL', 'th_r')]]
    estilos = []
    art = 0
    ultima_do_artigo = {}  # nº do artigo -> última linha da tabela (para a linha separadora)
    inicio_do_artigo = {}  # nº do artigo -> 1.ª linha (o artigo e o material incluído não se separam entre páginas)
    for l in o.linhas:
        r = len(dados)
        if l.incluido:  # material incluído no artigo de cima
            designacao = [p('+ ' + l.descricao, 'incl')] + ([p(l.nota, 'incl_desc')] if l.nota else [])
            dados.append(['', designacao, p(qtd(l.quantidade or 0), 'td_c'), p('INCLUÍDO', 'incl_tag'), '', ''])
            estilos += [('TOPPADDING', (0, r), (-1, r), 0), ('SPAN', (3, r), (5, r))]
            if art % 2 == 0:
                estilos.append(('BACKGROUND', (0, r), (-1, r), FUNDO))
            ultima_do_artigo[art] = r
            continue
        art += 1
        inicio_do_artigo[art] = r
        designacao = [p(l.descricao, 'td')] + ([p(l.nota, 'nota')] if l.nota else [])
        dados.append([p(art, 'td_num'), designacao, p(qtd(l.quantidade or 0), 'td_c'),
                      p(eur(l.preco_unitario), 'td_r'), p(iva_txt, 'td_c'),
                      p(eur((l.quantidade or 0) * (l.preco_unitario or 0)), 'td_rb')])
        if art % 2 == 0:
            estilos.append(('BACKGROUND', (0, r), (-1, r), FUNDO))
        ultima_do_artigo[art] = r

    tabela = Table(dados, colWidths=[9 * mm, None, 13 * mm, 26 * mm, 13 * mm, 28 * mm], repeatRows=1)
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), AZUL),
        ('TOPPADDING', (0, 0), (-1, 0), 6), ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6), ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW', (0, -1), (-1, -1), 0.8, AZUL),
    ] + [('LINEBELOW', (0, r), (-1, r), 0.5, LINHA) for r in ultima_do_artigo.values()]
      + [('NOSPLIT', (0, inicio_do_artigo[a]), (-1, fim)) for a, fim in ultima_do_artigo.items()
         if a in inicio_do_artigo and fim > inicio_do_artigo[a]] + estilos))
    story += [tabela, Spacer(1, 6 * mm)]

    # ── Totais (à direita) ──
    linhas_tot = [[p('Subtotal', 'tot_l'), p(eur(totais['subtotal']), 'tot_v')]]
    if o.desconto:
        linhas_tot += [[p(f'Desconto ({qtd(o.desconto)}%)', 'tot_l'), p('− ' + eur(totais['desconto_valor']), 'tot_v')],
                       [p('Base tributável', 'tot_l'), p(eur(totais['base']), 'tot_v')]]
    linhas_tot += [[p(f'IVA ({iva_txt})', 'tot_l'), p(eur(totais['iva']), 'tot_v')],
                   [p('Total a pagar', 'tot_fl'), p(eur(totais['total']), 'tot_fv')]]
    n = len(linhas_tot)
    tot = Table(linhas_tot, colWidths=[38 * mm, 36 * mm], hAlign='RIGHT')
    tot.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW', (0, n - 2), (-1, n - 2), 0.5, LINHA),
        ('BACKGROUND', (0, n - 1), (-1, n - 1), AZUL),
        ('TOPPADDING', (0, n - 1), (-1, n - 1), 8), ('BOTTOMPADDING', (0, n - 1), (-1, n - 1), 8),
        ('LINEBEFORE', (0, n - 1), (0, n - 1), 3, LARANJA),
    ]))
    story += [KeepTogether([tot]), Spacer(1, 9 * mm)]

    # ── Termos e condições / Condições de pagamento ──
    def seccao(titulo, conteudo, largura):
        barra = Table([[p(titulo, 'seccao')]], colWidths=[largura])
        barra.setStyle(TableStyle([('LINEBEFORE', (0, 0), (0, 0), 2.5, LARANJA),
                                   ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                                   ('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1)]))
        return [barra, Spacer(1, 2.5 * mm)] + conteudo

    blocos = []
    if o.termos:
        blocos.append(('Termos e condições', lambda w: [p(o.termos, 'texto')]))
    if o.condicoes_pagamento:
        itens = [l.strip().lstrip('*•-').strip() for l in o.condicoes_pagamento.splitlines() if l.strip()]

        def lista(w, itens=itens):
            t = Table([[p('•', 'texto'), p(i, 'texto')] for i in itens], colWidths=[4 * mm, w - 4 * mm])
            return [sem_margens(t, [('BOTTOMPADDING', (0, 0), (-1, -1), 1.5)])]
        blocos.append(('Condições de pagamento', lista))
    if len(blocos) == 2:  # lado a lado
        larg = (largura_util - 8 * mm) / 2
        duas = Table([[seccao(blocos[0][0], blocos[0][1](larg), larg), '', seccao(blocos[1][0], blocos[1][1](larg), larg)]],
                     colWidths=[larg, 8 * mm, larg])
        story += [sem_margens(duas), Spacer(1, 8 * mm)]
    elif blocos:
        story += [KeepTogether(seccao(blocos[0][0], blocos[0][1](largura_util), largura_util)), Spacer(1, 8 * mm)]

    # ── Aceitação ──
    def linha_assinatura(rotulo):
        t = Table([[''], [p(rotulo, 'assin')]], colWidths=[70 * mm], rowHeights=[12 * mm, None])
        t.setStyle(TableStyle([('LINEBELOW', (0, 0), (0, 0), 0.6, CINZA_CLARO),
                               ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                               ('TOPPADDING', (0, 1), (0, 1), 3)]))
        return t

    aceitacao = Table([[linha_assinatura('Data'), '', linha_assinatura('Assinatura do cliente')]],
                      colWidths=[70 * mm, largura_util - 140 * mm, 70 * mm])
    sem_margens(aceitacao)
    story.append(KeepTogether([
        p(f'Orçamento válido por {VALIDADE_DIAS} dias a contar da data de emissão. '
          'Para adjudicar, devolva este documento assinado ou confirme por escrito.', 'pequeno'),
        Spacer(1, 4 * mm), aceitacao,
    ]))

    rodape = '  ·  '.join(x for x in [empresa, f'NIF {org.nif}' if org and org.nif else '',
                                       org.telefone if org else '', org.email if org else ''] if x)
    doc.build(story, canvasmaker=lambda *a, **k: _CanvasNumerado(*a, rodape=rodape, **k))
    return buf.getvalue()
