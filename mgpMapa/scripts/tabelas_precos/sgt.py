"""Extrai modelos e preços (PVP) da Tabela de Preços SGT / Midea 2026-2027 para CSV.

Uso: python sgt.py tabela.pdf saida.csv
"""
import csv
import re
import sys

import os

import pdfplumber

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mitsubishi import cx, linhas, texto

PRECO = re.compile(r'^(\d{1,3}(?:[.,]\d{3})*)[.,](\d{2})€$')  # aceita 3.850,00€ e 3,850.00€
MODELO = re.compile(r'^(?=.*\d)(?=.*[A-Za-z])(?=.*[-/])[A-Za-z0-9()/\-.]{4,}$')
NAO_MODELO = re.compile(r'^\d|^Ø|SEER|SCOP|^\(.*~', re.I)


def preco(t):
    m = PRECO.match(t)
    return float(re.sub(r'[.,]', '', m.group(1)) + '.' + m.group(2)) if m else None


def e_modelo(t):
    return bool(MODELO.match(t)) and not NAO_MODELO.search(t) and t.count('(') == t.count(')')


def titulo_coluna(rows, top, x0, x1):
    """Nome em maiúsculas por cima da coluna do preço (ex.: "KIT VÁLVULAS 3 VIAS 4 TUBOS")."""
    for r in sorted((r for r in rows if top - 90 < r[0]['top'] < top), key=lambda r: -r[0]['top']):
        ws = [w for w in r if w['x0'] >= x0 - 20 and w['x1'] <= x1 + 10]
        t = ' '.join(w['text'] for w in ws)
        if ws and t.upper() == t and re.search(r'[A-ZÁÉÍÓÚÇÃÕ]{3}', t) and not re.search(r'Modelo|PVP|SEER|SCOP', t, re.I):
            return t
    return None


def extrair(pdf_path):
    out = []
    with pdfplumber.open(pdf_path) as pdf:
        for n, page in enumerate(pdf.pages, start=1):
            rows = linhas(page)
            for r in rows:
                for w in r:
                    w['text'] = w['text'].replace('\u2028', '').strip().rstrip('*')
            seccao = ' '.join(texto(r) for r in rows if r[0]['top'] < 70 and not any(c.isdigit() for c in texto(r)))
            seccao = re.sub(r'\s+', ' ', seccao).replace('Multi- Split', 'Multi-Split').replace('Split Multi-', 'Multi-Split').strip()
            serie = ''
            header = None  # linha "Modelo X Y Z" das tabelas em colunas
            prefixos = None  # nomes partidos em duas linhas: "MKT3-" / "V200G12-CL"

            for idx, r in enumerate(rows):
                t = texto(r)
                prices = [(i, w) for i, w in enumerate(r) if preco(w['text']) is not None]
                mods = [w for w in r if e_modelo(w['text'])]

                if not prices:
                    if len(r) >= 2 and all(w['text'].endswith('-') for w in r):
                        prefixos = r
                        continue
                    if prefixos and 0 < r[0]['top'] - prefixos[0]['top'] < 14:
                        for w in r:
                            pre = min(prefixos, key=lambda x: abs(cx(x) - cx(w)))
                            if abs(cx(pre) - cx(w)) < 15:
                                w['text'] = pre['text'] + w['text']
                        mods = [w for w in r if e_modelo(w['text'])]
                    if (r[0]['text'] == 'Modelo' and mods) or len(mods) >= 3:
                        header = mods
                    elif (r[0]['x0'] < 50 and not mods and len(t) < 70 and not t.startswith(('*', 'Modelo'))
                          and not re.search(r'\d', t) and r[0]['top'] > 70):
                        serie = re.sub(r'\s+', ' ', t).strip()
                    continue

                categoria = ' | '.join(x for x in [seccao, serie] if x)

                # Tabelas em colunas: "PVP 4.000,00€ 4.100,00€ ..." por baixo de "Modelo A B ..."
                if r[0]['text'] == 'PVP' and header:
                    rotulo = ' '.join(w['text'] for w in r[1:prices[0][0]])
                    for _, w in prices:
                        col = min(header, key=lambda m: abs(cx(m) - cx(w)))
                        if abs(cx(col) - cx(w)) < 40:
                            out.append(dict(marca='Midea', modelo=col['text'].upper(), descricao=rotulo,
                                            categoria=categoria, preco=preco(w['text']), pagina=n))
                    continue

                # Linhas: "MODELO ... 695,00€" (podem ter vários pares produto/preço na mesma linha)
                inicio = 0
                for k, (i, w) in enumerate(prices):
                    seg = r[inicio:i]
                    inicio = i + 1
                    seg_mods = [x for x in seg if e_modelo(x['text'])]
                    if seg_mods:
                        m = seg_mods[0]
                        desc = ' '.join(x['text'] for x in seg[:seg.index(m)])
                    elif mods and len(mods) == len(prices):
                        m, desc = mods[k], ''
                    elif seg and not any(re.search(r'SEER|SCOP', x['text']) for x in seg) or not seg:
                        x0 = seg[0]['x0'] if seg else (r[i - 1]['x1'] if i else w['x0'] - 120)
                        nome = titulo_coluna(rows, r[0]['top'], x0, w['x1'])
                        if not nome:
                            continue
                        out.append(dict(marca='Midea', modelo=nome, descricao=' '.join(x['text'] for x in seg),
                                        categoria=categoria, preco=preco(w['text']), pagina=n))
                        continue
                    else:
                        # Conjuntos: o preço fica numa linha entre "2x INTERIOR" e "+ 1x EXTERIOR"
                        perto = [x for rr in rows if 0 < abs(rr[0]['top'] - r[0]['top']) < 14
                                 for x in rr if x['x1'] < w['x0'] - 150]
                        partes, atual = [], []
                        for x in sorted(perto, key=lambda x: (x['top'], x['x0'])):
                            if re.match(r'^(\+|\d+x)$', x['text']) or e_modelo(x['text']):
                                atual.append(x['text'])
                                if e_modelo(x['text']):
                                    partes.append(' '.join(atual))
                                    atual = []
                        if not partes:
                            continue
                        out.append(dict(marca='Midea', modelo=' '.join(partes).upper().lstrip('+ '),
                                        descricao='Conjunto', categoria=categoria,
                                        preco=preco(w['text']), pagina=n))
                        continue
                    if 'Multi' in seccao:
                        # Na secção Multi-Split há unidades exteriores (M2O.., M3O..), depósitos e interiores avulsas
                        config = re.search(r'\b(\d)x1\b', t)
                        if re.match(r'^M\d[O0]', m['text'].upper()):  # o PDF às vezes usa zero: M40B
                            desc = 'Unidade exterior multisplit' + (f' {config.group(0)}' if config else '')
                            categoria = f'{seccao} | Unidades exteriores'
                        elif m['text'].upper().startswith('PLSX'):
                            desc = 'Depósito AQS'
                        else:
                            desc = ' '.join(x for x in ['Só unidade interior (multisplit)', desc] if x)
                    out.append(dict(marca='Midea', modelo=m['text'].upper(), descricao=desc,
                                    categoria=categoria, preco=preco(w['text']), pagina=n))

    vistos, unicos = set(), []
    for d in out:
        chave = (d['modelo'], d['descricao'], d['preco'])
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(d)
    return unicos


if __name__ == '__main__':
    dados = extrair(sys.argv[1])
    with open(sys.argv[2], 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['marca', 'modelo', 'descricao', 'categoria', 'preco', 'pagina'], delimiter=';')
        w.writeheader()
        for d in dados:
            w.writerow({**d, 'preco': f'{d["preco"]:.2f}'.replace('.', ',')})
    print(len(dados), 'produtos')
