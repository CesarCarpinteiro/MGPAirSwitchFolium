import io
import os
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

AZUL = colors.HexColor('#2d3a6e')
TEXTO = colors.HexColor('#222631')
CINZA = colors.HexColor('#70758a')
LINHA = colors.HexColor('#dcdfe8')
VALIDADE_DIAS = 30

LARGURA, ALTURA = A4
MARGEM = 18 * mm


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
            self._rodape_pagina(total)
            super().showPage()
        super().save()

    def _rodape_pagina(self, total):
        self.saveState()
        y = 12 * mm
        self.setStrokeColor(LINHA)
        self.setLineWidth(0.5)
        self.line(MARGEM, y + 4.5 * mm, LARGURA - MARGEM, y + 4.5 * mm)
        self.setFillColor(CINZA)
        self.setFont('Helvetica', 7.5)
        if self._rodape:
            self.drawString(MARGEM, y, self._rodape[:150])
        if total > 1:
            self.drawRightString(LARGURA - MARGEM, y, f'Página {self._pageNumber} de {total}')
        self.restoreState()


def gerar_pdf_orcamento(o, org, totais, logo_path=None):
    buf = io.BytesIO()
    empresa = (org.designacao_social or org.nome) if org else ''
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=MARGEM, rightMargin=MARGEM,
                            topMargin=15 * mm, bottomMargin=22 * mm,
                            title=f'Orçamento n.º {o.id} - {o.cliente}', author=empresa)
    largura_util = LARGURA - 2 * MARGEM - 12  # a moldura da página tem 6 pt de margem interna de cada lado

    base = ParagraphStyle('base', fontName='Helvetica', fontSize=9, leading=12.5, textColor=TEXTO)

    def estilo(nome, **kw):
        return ParagraphStyle(nome, parent=base, **kw)

    st = {
        'empresa': estilo('empresa', fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=AZUL),
        'empresa_sub': estilo('empresa_sub', fontSize=8.3, leading=11.5, textColor=CINZA),
        'titulo': estilo('titulo', fontName='Helvetica-Bold', fontSize=15, leading=19, alignment=TA_RIGHT),
        'data': estilo('data', fontSize=9, leading=12, textColor=CINZA, alignment=TA_RIGHT),
        'rotulo': estilo('rotulo', fontSize=8, leading=11, textColor=CINZA),
        'cliente': estilo('cliente', fontName='Helvetica-Bold', fontSize=10.5, leading=14),
        'cliente_txt': estilo('cliente_txt', fontSize=8.8, leading=12, textColor=colors.HexColor('#4a4f60')),
        'th': estilo('th', fontName='Helvetica-Bold', fontSize=8.3, leading=11, textColor=CINZA),
        'th_r': estilo('th_r', fontName='Helvetica-Bold', fontSize=8.3, leading=11, textColor=CINZA, alignment=TA_RIGHT),
        'td': estilo('td', fontSize=9, leading=12),
        'td_r': estilo('td_r', fontSize=9, leading=12, alignment=TA_RIGHT),
        'td_rb': estilo('td_rb', fontName='Helvetica-Bold', fontSize=9, leading=12, alignment=TA_RIGHT),
        'nota': estilo('nota', fontName='Helvetica-Oblique', fontSize=8, leading=10.8, textColor=CINZA, spaceBefore=1.5),
        'incl': estilo('incl', fontSize=8.5, leading=11, textColor=colors.HexColor('#4a4f60'), leftIndent=10),
        'incl_desc': estilo('incl_desc', fontSize=8, leading=10.5, textColor=CINZA, leftIndent=10),
        'incl_r': estilo('incl_r', fontName='Helvetica-Oblique', fontSize=8.5, leading=11, textColor=CINZA, alignment=TA_RIGHT),
        'tot_l': estilo('tot_l', fontSize=9, leading=12, textColor=CINZA),
        'tot_v': estilo('tot_v', fontSize=9, leading=12, alignment=TA_RIGHT),
        'tot_fl': estilo('tot_fl', fontName='Helvetica-Bold', fontSize=10.5, leading=14),
        'tot_fv': estilo('tot_fv', fontName='Helvetica-Bold', fontSize=12.5, leading=16, textColor=AZUL, alignment=TA_RIGHT),
        'seccao': estilo('seccao', fontName='Helvetica-Bold', fontSize=9.5, leading=13, spaceAfter=3),
        'texto': estilo('texto', fontSize=8.6, leading=12.2, textColor=colors.HexColor('#3a3f50')),
        'pequeno': estilo('pequeno', fontSize=8, leading=11, textColor=CINZA),
        'assin': estilo('assin', fontSize=8, leading=10, textColor=CINZA),
    }

    def p(texto, nome):
        return Paragraph(escape(str(texto or '')).replace('\n', '<br/>'), st[nome])

    def sem_margens(t, extra=()):
        t.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                               ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                               ('VALIGN', (0, 0), (-1, -1), 'TOP')] + list(extra)))
        return t

    story = []

    # ── Cabeçalho: logótipo e empresa | Orçamento n.º e data ──
    try:
        data = datetime.strptime(o.created_at, '%d/%m/%Y')
    except (TypeError, ValueError):
        data = datetime.now()

    esquerda = []
    if logo_path and os.path.exists(logo_path):
        try:
            img = Image(logo_path)
            escala = min(40 * mm / img.imageWidth, 18 * mm / img.imageHeight)
            img.drawWidth, img.drawHeight = img.imageWidth * escala, img.imageHeight * escala
            img.hAlign = 'LEFT'
            esquerda += [img, Spacer(1, 2.5 * mm)]
        except Exception:
            pass
    esquerda.append(p(empresa, 'empresa'))
    det_emp = [x for x in [org.morada if org else '', f'NIF {org.nif}' if org and org.nif else '',
                           ' · '.join(y for y in [org.telefone, org.email] if y) if org else ''] if x]
    if det_emp:
        esquerda.append(p('\n'.join(det_emp), 'empresa_sub'))

    direita = [p(f'Orçamento n.º {o.id}', 'titulo'), Spacer(1, 1 * mm), p(f'{data:%d/%m/%Y}', 'data')]
    cab = sem_margens(Table([[esquerda, direita]], colWidths=[largura_util - 60 * mm, 60 * mm]))
    story += [cab, Spacer(1, 5 * mm)]

    linha = Table([['']], colWidths=[largura_util], rowHeights=[1])
    linha.setStyle(TableStyle([('LINEABOVE', (0, 0), (-1, -1), 0.6, LINHA)]))
    story += [linha, Spacer(1, 4 * mm)]

    # ── Cliente ──
    det_cliente = [x for x in [f'NIF {o.cliente_nif}' if o.cliente_nif else '', o.cliente_morada,
                               ' · '.join(y for y in [o.cliente_contacto, o.cliente_email] if y)] if x]
    story += [p('Cliente', 'rotulo'), Spacer(1, 1 * mm), p(o.cliente, 'cliente')]
    if det_cliente:
        story.append(p('\n'.join(det_cliente), 'cliente_txt'))
    story.append(Spacer(1, 6 * mm))

    # ── Artigos ──
    iva_txt = f'{qtd(o.iva_taxa or 0)}%'
    dados = [[p('Descrição', 'th'), p('Qtd.', 'th_r'), p('Preço unit.', 'th_r'), p('IVA', 'th_r'), p('Total', 'th_r')]]
    estilos = []
    art = 0
    inicio, fim = {}, {}  # nº do artigo -> 1.ª e última linha (separador; artigo e material incluído não se separam)
    for l in o.linhas:
        r = len(dados)
        if l.incluido:  # material incluído no artigo de cima
            designacao = [p(l.descricao, 'incl')] + ([p(l.nota, 'incl_desc')] if l.nota else [])
            dados.append([designacao, p(qtd(l.quantidade or 0), 'td_r'), p('incluído', 'incl_r'), '', ''])
            estilos += [('TOPPADDING', (0, r), (-1, r), 1), ('SPAN', (2, r), (4, r))]
            fim[art] = r
            continue
        art += 1
        inicio[art] = fim[art] = r
        designacao = [p(l.descricao, 'td')] + ([p(l.nota, 'nota')] if l.nota else [])
        dados.append([designacao, p(qtd(l.quantidade or 0), 'td_r'), p(eur(l.preco_unitario), 'td_r'),
                      p(iva_txt, 'td_r'), p(eur((l.quantidade or 0) * (l.preco_unitario or 0)), 'td_rb')])

    tabela = Table(dados, colWidths=[None, 13 * mm, 26 * mm, 13 * mm, 27 * mm], repeatRows=1)
    tabela.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, 0), 0.8, TEXTO),
        ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (1, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ] + [('LINEBELOW', (0, r), (-1, r), 0.5, LINHA) for r in fim.values()]
      + [('BOTTOMPADDING', (0, r), (-1, r), 7) for r in fim.values()]
      + [('NOSPLIT', (0, inicio[a]), (-1, f)) for a, f in fim.items() if a in inicio and f > inicio[a]]
      + estilos))
    story += [tabela, Spacer(1, 5 * mm)]

    # ── Totais ──
    linhas_tot = [[p('Subtotal', 'tot_l'), p(eur(totais['subtotal']), 'tot_v')]]
    if o.desconto:
        linhas_tot += [[p(f'Desconto ({qtd(o.desconto)}%)', 'tot_l'), p('− ' + eur(totais['desconto_valor']), 'tot_v')],
                       [p('Base tributável', 'tot_l'), p(eur(totais['base']), 'tot_v')]]
    linhas_tot += [[p(f'IVA ({iva_txt})', 'tot_l'), p(eur(totais['iva']), 'tot_v')],
                   [p('Total', 'tot_fl'), p(eur(totais['total']), 'tot_fv')]]
    n = len(linhas_tot)
    tot = Table(linhas_tot, colWidths=[35 * mm, 35 * mm], hAlign='RIGHT')
    tot.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('LINEABOVE', (0, n - 1), (-1, n - 1), 0.8, TEXTO),
        ('TOPPADDING', (0, n - 1), (-1, n - 1), 6),
    ]))
    story += [KeepTogether([tot]), Spacer(1, 7 * mm)]

    # ── Termos e condições / Condições de pagamento (lado a lado quando há os dois) ──
    blocos = []
    if o.termos:
        blocos.append(('Termos e condições', lambda w: [p(o.termos, 'texto')]))
    if o.condicoes_pagamento:
        itens = [l.strip().lstrip('*•-').strip() for l in o.condicoes_pagamento.splitlines() if l.strip()]

        def lista(w, itens=itens):
            t = Table([[p('–', 'texto'), p(i, 'texto')] for i in itens], colWidths=[4 * mm, w - 4 * mm])
            return [sem_margens(t, [('BOTTOMPADDING', (0, 0), (-1, -1), 1)])]
        blocos.append(('Condições de pagamento', lista))

    def seccao(titulo, conteudo):
        return [p(titulo, 'seccao')] + conteudo

    if len(blocos) == 2:
        larg = (largura_util - 10 * mm) / 2
        duas = Table([[seccao(blocos[0][0], blocos[0][1](larg)), '', seccao(blocos[1][0], blocos[1][1](larg))]],
                     colWidths=[larg, 10 * mm, larg])
        story += [sem_margens(duas), Spacer(1, 6 * mm)]
    elif blocos:
        story += [KeepTogether(seccao(blocos[0][0], blocos[0][1](largura_util))), Spacer(1, 6 * mm)]

    # ── Validade e aceitação ──
    def linha_assinatura(rotulo):
        t = Table([[''], [p(rotulo, 'assin')]], colWidths=[75 * mm], rowHeights=[9 * mm, None])
        t.setStyle(TableStyle([('LINEBELOW', (0, 0), (0, 0), 0.5, CINZA),
                               ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                               ('TOPPADDING', (0, 1), (0, 1), 3)]))
        return t

    aceitacao = Table([[linha_assinatura('Data'), '', linha_assinatura('Assinatura do cliente')]],
                      colWidths=[75 * mm, largura_util - 150 * mm, 75 * mm])
    sem_margens(aceitacao)
    story.append(KeepTogether([
        p(f'Orçamento válido por {VALIDADE_DIAS} dias. Para adjudicar, basta devolver este documento assinado '
          'ou confirmar por escrito.', 'pequeno'),
        Spacer(1, 1 * mm), aceitacao,
    ]))

    rodape = '  ·  '.join(x for x in [empresa, f'NIF {org.nif}' if org and org.nif else '',
                                       org.telefone if org else '', org.email if org else ''] if x)
    doc.build(story, canvasmaker=lambda *a, **k: _CanvasNumerado(*a, rodape=rodape, **k))
    return buf.getvalue()
