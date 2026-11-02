"""Extrai modelos e preços (PVR) da Tabela de Preços Mitsubishi Electric 2025 para CSV.

Uso: python mitsubishi.py tabela.pdf saida.csv [pagina_ini pagina_fim]
"""
import csv
import re
import sys

import pdfplumber

PRECO = re.compile(r'^(\d{1,3}(?:\.\d{3})*)€$')
MODELO = re.compile(r'^[A-Z]{2,5}-[A-Z0-9#()/\-]*\d[A-Z0-9#()/\-]*\**$|^[A-Z]{2,5}-[A-Z]*##[A-Z0-9()/\-]*\**$')
PAREN = re.compile(r'^\(.*\)$')
EXTERIOR = re.compile(r'^(MUZ|SUZ|PUZ|PUHZ)-')


def e_modelo(t):
    return bool(MODELO.match(t)) and t.count('(') == t.count(')')


def limpar_modelo(m):
    # remove notas de rodapé: SEZ-M25DA(1), MSZ-LN##VG(W/R/B/V)*
    return re.sub(r'(\(\d\))+$', '', m.rstrip('*'))


def limpar_variante(v):
    v = re.sub(r'[()]', '', v).strip()
    return '' if v.isdigit() else v


def linhas(page):
    words = page.extract_words(x_tolerance=1.5, y_tolerance=2)
    rows = []
    for w in sorted(words, key=lambda w: (round(w['top']), w['x0'])):
        if rows and abs(rows[-1][0]['top'] - w['top']) < 3:
            rows[-1].append(w)
        else:
            rows.append([w])
    return [sorted(r, key=lambda w: w['x0']) for r in rows]


def cx(w):
    return (w['x0'] + w['x1']) / 2


def texto(r):
    return ' '.join(w['text'] for w in r)


def preco(t):
    m = PRECO.match(t)
    return float(m.group(1).replace('.', '')) if m else None


def categoria_pagina(rows):
    for r in rows[:6]:
        t = texto(r)
        if '|' in t and len(t) < 80 and not re.search(r'(.)\1\1', t):
            return re.sub(r'\s+', ' ', t).strip()
    return ''


def exterior_de(rows, top_header, col):
    """Unidade exterior na mesma coluna, nas linhas logo a seguir ao cabeçalho do modelo."""
    for r in rows:
        if not (top_header < r[0]['top'] < top_header + 70):
            continue
        ext = [w for w in r if e_modelo(w['text']) and EXTERIOR.match(w['text'])]
        if ext:
            e = min(ext, key=lambda m: abs(cx(m) - cx(col)))
            if abs(cx(e) - cx(col)) < 45:
                return limpar_modelo(e['text'])
    return None


def extrair(pdf_path, ini=1, fim=None):
    out = []
    with pdfplumber.open(pdf_path) as pdf:
        for n, page in enumerate(pdf.pages[ini - 1:fim], start=ini):
            rows = linhas(page)
            cat = categoria_pagina(rows)
            if cat.startswith('Twin'):
                continue
            parens = [w for r in rows for w in r if PAREN.match(w['text'])]
            col_modelo = None  # x da coluna "MODELO" nas tabelas de acessórios
            headers = []    # (top, [palavras modelo], é_template)
            exteriores = []  # (top, [palavras modelo])
            for r in rows:
                t = texto(r)
                mods = [w for w in r if e_modelo(w['text'])]
                prices = [(i, w) for i, w in enumerate(r) if preco(w['text']) is not None]
                has_pvr = any(w['text'] == 'PVR' for w in r)

                palavras = [w['text'] for w in r]
                if 'MODELO' in palavras and any(p.startswith('DESCRI') for p in palavras):
                    col_modelo = cx(r[palavras.index('MODELO')])
                    continue

                if mods and not prices and not has_pvr:
                    if t.startswith('Unidade exterior') or all(EXTERIOR.match(w['text']) for w in mods):
                        exteriores.append((r[0]['top'], mods))
                    elif (t.startswith(('MODELO', 'Unidade interior')) or len(mods) >= 2 or len(r) == 1
                          or any('##' in w['text'] for w in mods)):
                        # "Unidade interior" repete o MODELO: só conta se não houver MODELO logo acima
                        if t.startswith('Unidade interior') and headers and r[0]['top'] - headers[-1][0] < 40:
                            continue
                        template = any('##' in w['text'] for w in mods)
                        # cabeçalhos partidos em duas linhas próximas formam um só
                        if headers and r[0]['top'] - headers[-1][0] < 8:
                            ptop, pmods, ptemplate = headers.pop()
                            mods, template = pmods + mods, ptemplate or template
                        headers.append((r[0]['top'], mods, template))
                    continue

                if has_pvr and prices:
                    pvr_i = next(i for i, w in enumerate(r) if w['text'] == 'PVR')
                    linha_cap = r[0]['text'] if pvr_i > 0 and r[0]['text'].isdigit() else None
                    variante_linha = ' '.join(w['text'] for w in r[pvr_i + 1:prices[0][0]] if not preco(w['text']))
                    acima = [h for h in headers if h[0] < r[0]['top']]
                    if not acima:
                        continue
                    _, mods_h, template = acima[-1]
                    for i, w in prices:
                        col = min(mods_h, key=lambda m: abs(cx(m) - cx(w)))
                        if abs(cx(col) - cx(w)) > 45:
                            continue
                        modelo = col['text']
                        seguinte = r[i + 1]['text'] if i + 1 < len(r) else ''
                        if not PAREN.match(seguinte):
                            # etiqueta "(VGW)" em letra mais pequena, ligeiramente abaixo do preço
                            perto = [pw for pw in parens if 0 <= pw['x0'] - w['x1'] < 12 and abs(pw['top'] - w['top']) < 8]
                            seguinte = perto[0]['text'] if perto else ''
                        variante = variante_linha
                        if PAREN.match(seguinte):
                            inner = seguinte.strip('()')
                            if e_modelo(inner):
                                modelo = inner
                            else:
                                variante = inner
                        if '##' in modelo:
                            if not linha_cap:
                                continue
                            modelo = re.sub(r'\(Y\)', '', modelo).replace('##', linha_cap)
                        modelo = limpar_modelo(modelo)
                        desc = []
                        if limpar_variante(variante):
                            desc.append(limpar_variante(variante))
                        if template:
                            desc.insert(0, 'Só unidade interior (multisplit)')
                        ext = exterior_de(rows, acima[-1][0], col)
                        if ext:
                            desc.insert(0, f'Conjunto c/ unid. exterior {ext}')
                        out.append(dict(marca='Mitsubishi Electric', modelo=modelo,
                                        descricao=' | '.join(desc), categoria=cat,
                                        preco=preco(w['text']), pagina=n))
                    continue

                # Tabelas de acessórios: "Descrição  MODELO  compatibilidade  90€"
                if prices and mods and prices[-1][0] == len(r) - 1 and not has_pvr:
                    if col_modelo is not None:
                        m = min(mods, key=lambda w: abs(cx(w) - col_modelo))
                    else:
                        m = mods[0]
                    i_m = r.index(m)
                    desc = ' '.join(w['text'] for w in (r[:i_m] if i_m else r[1:-1]))
                    if desc and not desc.startswith(('OPCIONAL', 'INCLUÍDO', 'NOTA')):
                        out.append(dict(marca='Mitsubishi Electric', modelo=limpar_modelo(m['text']), descricao=desc,
                                        categoria=cat or 'Acessórios', preco=preco(r[-1]['text']), pagina=n))
    # A mesma referência aparece em várias páginas (ex.: comandos): fica a primeira
    vistos, unicos = set(), []
    for d in out:
        chave = (d['modelo'], d['descricao'], d['preco'])
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(d)
    return unicos


if __name__ == '__main__':
    args = sys.argv[1:]
    ini, fim = (int(args[2]), int(args[3])) if len(args) >= 4 else (1, None)
    dados = extrair(args[0], ini, fim)
    with open(args[1], 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['marca', 'modelo', 'descricao', 'categoria', 'preco', 'pagina'], delimiter=';')
        w.writeheader()
        for d in dados:
            w.writerow({**d, 'preco': f'{d["preco"]:.2f}'.replace('.', ',')})
    print(len(dados), 'produtos')
