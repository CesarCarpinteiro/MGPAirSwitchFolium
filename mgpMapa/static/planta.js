// Editor de plantas: desenho da instalação de AC por cima da planta da casa.
// O desenho fica em coordenadas da imagem (px) e é guardado em JSON:
//   { escala: {x1, y1, x2, y2, metros} | null,
//     itens: [ {id, tipo: 'unidade', modelo: 'interior'|'exterior', x, y, nome},
//              {id, tipo: 'linha', categoria: 'cobre'|'dreno'|'eletrico', pontos: [[x, y], ...]},
//              {id, tipo: 'nota', x, y, texto} ] }
// Os símbolos e textos têm tamanho fixo no ecrã: são desenhados em unidades u = 1/zoom.
(function () {
    var dados = JSON.parse(document.getElementById('dadosPlanta').textContent);
    var W = dados.largura, H = dados.altura;
    var desenho = dados.desenho && Array.isArray(dados.desenho.itens) ? dados.desenho : { escala: null, itens: [] };
    if (!('escala' in desenho)) desenho.escala = null;

    var CATEGORIAS = {
        cobre: { nome: 'Tubagem de cobre', cor: '#c47c2b' },
        dreno: { nome: 'Dreno', cor: '#1e88e5', traco: [8, 6] },
        eletrico: { nome: 'Cabo elétrico', cor: '#e53935' }
    };
    var MODELOS = { interior: { nome: 'Unidade interior', cor: '#2d3a6e' }, exterior: { nome: 'Unidade exterior', cor: '#37474f' } };
    var DICAS = {
        selecionar: 'Toque num elemento para o selecionar e arraste-o para mover. Arraste o fundo para deslocar a planta.',
        interior: 'Toque na planta onde fica a unidade interior.',
        exterior: 'Toque na planta onde fica a unidade exterior.',
        cobre: 'Toque nos pontos do percurso da tubagem. Termine com duplo clique, Enter ou "Terminar".',
        dreno: 'Toque nos pontos do percurso do dreno. Termine com duplo clique, Enter ou "Terminar".',
        eletrico: 'Toque nos pontos do percurso do cabo. Termine com duplo clique, Enter ou "Terminar".',
        nota: 'Toque onde quer escrever a nota.',
        escala: 'Toque nas duas pontas de uma medida que conhece (ex.: uma parede) e indique quantos metros tem.'
    };

    var svg = document.getElementById('svg'), vista = document.getElementById('vista');
    var camada = document.getElementById('camada'), area = document.getElementById('area');
    var dica = document.getElementById('dica'), resumo = document.getElementById('resumo');
    var btnGuardar = document.getElementById('btnGuardar'), btnDesfazer = document.getElementById('btnDesfazer');
    var campoNome = document.getElementById('nome'), campoMorada = document.getElementById('morada');

    var ferramenta = 'selecionar', selecionado = null, rascunho = null, cursor = null;
    var s = 1, tx = 0, ty = 0;           // zoom e deslocamento da vista
    var historico = [], alterado = false;

    // ── Utilitários ───────────────────────────────────────────────────

    function esc(t) {
        return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }
    function n(v) { return Math.round(v * 10) / 10; }
    function dist(a, b) { return Math.hypot(a[0] - b[0], a[1] - b[1]); }
    function comprimento(pts) {
        var t = 0;
        for (var i = 1; i < pts.length; i++) t += dist(pts[i - 1], pts[i]);
        return t;
    }
    function pxPorMetro() {
        var e = desenho.escala;
        return e && e.metros > 0 ? dist([e.x1, e.y1], [e.x2, e.y2]) / e.metros : 0;
    }
    function metros(px) {
        var k = pxPorMetro();
        return k ? (px / k).toLocaleString('pt-PT', { maximumFractionDigits: 1 }) + ' m' : '';
    }
    function meio(pts) {  // ponto a meio do percurso; [x, y, troço vertical?]
        var alvo = comprimento(pts) / 2, feito = 0;
        for (var i = 1; i < pts.length; i++) {
            var d = dist(pts[i - 1], pts[i]);
            if (feito + d >= alvo && d > 0) {
                var f = (alvo - feito) / d, dx = pts[i][0] - pts[i - 1][0], dy = pts[i][1] - pts[i - 1][1];
                return [pts[i - 1][0] + dx * f, pts[i - 1][1] + dy * f, Math.abs(dy) > Math.abs(dx)];
            }
            feito += d;
        }
        return [pts[0][0], pts[0][1], false];
    }
    function novoId() { return 'i' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }
    function item(id) {
        for (var i = 0; i < desenho.itens.length; i++) if (desenho.itens[i].id === id) return desenho.itens[i];
        return null;
    }
    function texto(x, y, t, cor, tamanho, u, extra) {
        return '<text x="' + n(x) + '" y="' + n(y) + '" font-size="' + n(tamanho) + '" font-family="Arial, sans-serif" font-weight="bold"' +
            (extra && extra.indexOf('text-anchor') >= 0 ? '' : ' text-anchor="middle"') + ' fill="' + cor + '" stroke="white" stroke-width="' + n(3.5 * u) + '" paint-order="stroke"' +
            ' stroke-linejoin="round" ' + (extra || 'pointer-events="none"') + '>' + esc(t) + '</text>';
    }

    // ── Desenho (SVG) ─────────────────────────────────────────────────

    function svgLinha(it, u, ecra) {
        var cat = CATEGORIAS[it.categoria] || CATEGORIAS.cobre;
        var pts = it.pontos.map(function (p) { return n(p[0]) + ',' + n(p[1]); }).join(' ');
        var sel = ecra && selecionado === it.id, h = '';
        var base = ' points="' + pts + '" fill="none" stroke-linecap="round" stroke-linejoin="round"';
        if (sel) h += '<polyline' + base + ' stroke="' + cat.cor + '" stroke-opacity="0.25" stroke-width="' + n(14 * u) + '"/>';
        h += '<polyline' + base + ' stroke="' + cat.cor + '" stroke-width="' + n(3 * u) + '"' +
            (cat.traco ? ' stroke-dasharray="' + cat.traco.map(function (v) { return n(v * u); }).join(' ') + '"' : '') + '/>';
        if (ecra) h += '<polyline' + base + ' data-id="' + it.id + '" stroke="transparent" stroke-width="' + n(18 * u) + '" style="cursor:pointer"/>';
        var m = metros(comprimento(it.pontos));
        if (m) {  // ao lado de um troço vertical, por cima de um horizontal
            var c = meio(it.pontos);
            h += c[2] ? texto(c[0] + 8 * u, c[1] + 4 * u, m, cat.cor, 12 * u, u, 'pointer-events="none" text-anchor="start"')
                : texto(c[0], c[1] - 7 * u, m, cat.cor, 12 * u, u);
        }
        if (sel) it.pontos.forEach(function (p, i) {
            h += '<circle data-id="' + it.id + '" data-vertice="' + i + '" cx="' + n(p[0]) + '" cy="' + n(p[1]) + '" r="' + n(7 * u) +
                '" fill="white" stroke="' + cat.cor + '" stroke-width="' + n(2 * u) + '" style="cursor:move"/>';
        });
        return h;
    }

    function svgUnidade(it, u, ecra) {
        var mod = MODELOS[it.modelo] || MODELOS.interior, interior = it.modelo !== 'exterior';
        var w = (interior ? 38 : 30) * u, h = (interior ? 15 : 26) * u, x0 = it.x - w / 2, y0 = it.y - h / 2;
        var r = '<g' + (ecra ? ' data-id="' + it.id + '" style="cursor:' + (ferramenta === 'selecionar' ? 'move' : 'inherit') + '"' : '') + '>';
        if (ecra && selecionado === it.id) {
            r += '<rect x="' + n(x0 - 5 * u) + '" y="' + n(y0 - 5 * u) + '" width="' + n(w + 10 * u) + '" height="' + n(h + 10 * u) +
                '" rx="' + n(4 * u) + '" fill="rgba(74,95,168,0.1)" stroke="#4a5fa8" stroke-width="' + n(1.5 * u) + '" stroke-dasharray="' + n(4 * u) + ' ' + n(3 * u) + '"/>';
        }
        r += '<rect x="' + n(x0) + '" y="' + n(y0) + '" width="' + n(w) + '" height="' + n(h) + '" rx="' + n(3 * u) +
            '" fill="white" stroke="' + mod.cor + '" stroke-width="' + n(2.2 * u) + '"/>';
        if (interior) {
            r += '<line x1="' + n(x0 + 5 * u) + '" y1="' + n(y0 + h - 4.5 * u) + '" x2="' + n(x0 + w - 5 * u) + '" y2="' + n(y0 + h - 4.5 * u) +
                '" stroke="' + mod.cor + '" stroke-width="' + n(1.5 * u) + '"/>';
        } else {
            r += '<circle cx="' + n(it.x) + '" cy="' + n(it.y) + '" r="' + n(8 * u) + '" fill="none" stroke="' + mod.cor + '" stroke-width="' + n(1.5 * u) + '"/>' +
                '<path d="M' + n(it.x - 6 * u) + ' ' + n(it.y) + 'H' + n(it.x + 6 * u) + 'M' + n(it.x) + ' ' + n(it.y - 6 * u) + 'V' + n(it.y + 6 * u) +
                '" stroke="' + mod.cor + '" stroke-width="' + n(1.2 * u) + '"/>';
        }
        r += '</g>';
        if (it.nome) r += texto(it.x, interior ? y0 - 6 * u : y0 + h + 14 * u, it.nome, mod.cor, 11.5 * u, u);
        return r;
    }

    function svgNota(it, u, ecra) {
        var cor = ecra && selecionado === it.id ? '#4a5fa8' : '#222';
        var extra = ecra ? 'data-id="' + it.id + '" style="cursor:' + (ferramenta === 'selecionar' ? 'move' : 'inherit') + '"' : '';
        var r = texto(it.x, it.y, it.texto, cor, 13 * u, u, extra);
        if (ecra && selecionado === it.id) {
            var largura = String(it.texto).length * 7.2 * u;
            r += '<line x1="' + n(it.x - largura / 2) + '" y1="' + n(it.y + 4 * u) + '" x2="' + n(it.x + largura / 2) + '" y2="' + n(it.y + 4 * u) +
                '" stroke="#4a5fa8" stroke-width="' + n(1.5 * u) + '" stroke-dasharray="' + n(3 * u) + ' ' + n(2 * u) + '" pointer-events="none"/>';
        }
        return r;
    }

    function svgEscala(e, u, ecra) {
        var cor = ecra && selecionado === 'escala' ? '#4a5fa8' : '#607d8b';
        var a = [e.x1, e.y1], b = [e.x2, e.y2], ang = Math.atan2(b[1] - a[1], b[0] - a[0]);
        var px = -Math.sin(ang) * 6 * u, py = Math.cos(ang) * 6 * u;
        var linha = ' x1="' + n(a[0]) + '" y1="' + n(a[1]) + '" x2="' + n(b[0]) + '" y2="' + n(b[1]) + '"';
        var r = '<line' + linha + ' stroke="' + cor + '" stroke-width="' + n(2 * u) + '" stroke-dasharray="' + n(6 * u) + ' ' + n(4 * u) + '"/>';
        [a, b].forEach(function (p) {
            r += '<line x1="' + n(p[0] - px) + '" y1="' + n(p[1] - py) + '" x2="' + n(p[0] + px) + '" y2="' + n(p[1] + py) + '" stroke="' + cor + '" stroke-width="' + n(2 * u) + '"/>';
        });
        if (ecra) r += '<line' + linha + ' data-id="escala" stroke="transparent" stroke-width="' + n(16 * u) + '" style="cursor:pointer"/>';
        var c = meio([a, b]);
        return r + texto(c[0], c[1] - 8 * u, 'Escala: ' + String(e.metros).replace('.', ',') + ' m', cor, 11 * u, u);
    }

    function svgRascunho(u) {
        if (!rascunho) return '';
        var pts = rascunho.pontos.slice();
        if (cursor) pts.push(encaixar(cursor, pts[pts.length - 1]));
        var cor = rascunho.categoria === 'escala' ? '#607d8b' : CATEGORIAS[rascunho.categoria].cor;
        var r = '<polyline points="' + pts.map(function (p) { return n(p[0]) + ',' + n(p[1]); }).join(' ') +
            '" fill="none" stroke="' + cor + '" stroke-width="' + n(3 * u) + '" stroke-dasharray="' + n(5 * u) + ' ' + n(4 * u) +
            '" stroke-linecap="round" pointer-events="none"/>';
        rascunho.pontos.forEach(function (p) {
            r += '<circle cx="' + n(p[0]) + '" cy="' + n(p[1]) + '" r="' + n(4.5 * u) + '" fill="' + cor + '" pointer-events="none"/>';
        });
        if (rascunho.categoria !== 'escala') {
            var m = metros(comprimento(pts));
            if (m && pts.length > 1) { var c = pts[pts.length - 1]; r += texto(c[0], c[1] - 12 * u, m, cor, 12 * u, u); }
        }
        return r;
    }

    // Por baixo as linhas, por cima as unidades e as notas
    function marcacao(u, ecra) {
        var h = '';
        ['linha', 'unidade', 'nota'].forEach(function (tipo) {
            desenho.itens.forEach(function (it) {
                if (it.tipo !== tipo) return;
                h += tipo === 'linha' ? svgLinha(it, u, ecra) : tipo === 'unidade' ? svgUnidade(it, u, ecra) : svgNota(it, u, ecra);
            });
        });
        if (desenho.escala) h += svgEscala(desenho.escala, u, ecra);
        return h;
    }

    function aplicarVista() { vista.setAttribute('transform', 'translate(' + n(tx) + ' ' + n(ty) + ') scale(' + s + ')'); }

    function render() {
        aplicarVista();
        camada.innerHTML = marcacao(1 / s, true) + svgRascunho(1 / s);
        area.className = 'area ' + (ferramenta === 'selecionar' ? 'mao' : 'desenhar');
        atualizarResumo();
        atualizarDica();
        btnDesfazer.disabled = !historico.length;
    }

    function totais() {
        var t = { cobre: 0, dreno: 0, eletrico: 0, interior: 0, exterior: 0 };
        desenho.itens.forEach(function (it) {
            if (it.tipo === 'linha') t[it.categoria] += comprimento(it.pontos);
            else if (it.tipo === 'unidade') t[it.modelo] += 1;
        });
        return t;
    }

    function atualizarResumo() {
        var t = totais(), h = '';
        Object.keys(CATEGORIAS).forEach(function (k) {
            var cat = CATEGORIAS[k];
            h += '<span class="item"><span class="traco" style="border-color:' + cat.cor + ';' + (cat.traco ? 'border-top-style:dashed;' : '') +
                'width:16px;border-top-width:3px;"></span>' + cat.nome + ' <strong>' + (pxPorMetro() ? metros(t[k]) : (t[k] ? '—' : '0 m')) + '</strong></span>';
        });
        h += '<span class="item">Interiores <strong>' + t.interior + '</strong></span>';
        h += '<span class="item">Exteriores <strong>' + t.exterior + '</strong></span>';
        if (!pxPorMetro()) h += '<span class="item aviso">Marque a 📏 Escala para ver os metros.</span>';
        resumo.innerHTML = h;
    }

    function atualizarDica() {
        var h = '';
        if (rascunho) {
            var nome = rascunho.categoria === 'escala' ? 'Escala' : CATEGORIAS[rascunho.categoria].nome;
            if (rascunho.categoria === 'escala') {
                h = '<span><strong>Escala:</strong> toque na outra ponta da medida.</span><button class="sec" data-acao="cancelar">Cancelar</button>';
            } else {
                var m = metros(comprimento(rascunho.pontos));
                h = '<span><strong>' + nome + '</strong> · ' + rascunho.pontos.length + ' ponto' + (rascunho.pontos.length === 1 ? '' : 's') +
                    (m ? ' · ' + m : '') + '</span><button data-acao="terminar">✓ Terminar</button><button class="sec" data-acao="cancelar">Cancelar</button>';
            }
        } else if (selecionado) {
            var it = selecionado === 'escala' ? null : item(selecionado), desc = '';
            if (selecionado === 'escala') desc = '<strong>Escala</strong> · ' + String(desenho.escala.metros).replace('.', ',') + ' m';
            else if (it.tipo === 'linha') desc = '<strong>' + CATEGORIAS[it.categoria].nome + '</strong>' + (metros(comprimento(it.pontos)) ? ' · ' + metros(comprimento(it.pontos)) : '') + ' · arraste os pontos para ajustar';
            else if (it.tipo === 'unidade') desc = '<strong>' + MODELOS[it.modelo].nome + '</strong>' + (it.nome ? ' · ' + esc(it.nome) : '');
            else desc = '<strong>Nota</strong>';
            h = '<span>' + desc + '</span>';
            if (selecionado === 'escala') h += '<button data-acao="metros">Mudar metros</button>';
            else if (it.tipo !== 'linha') h += '<button data-acao="texto">' + (it.tipo === 'nota' ? 'Editar texto' : 'Mudar nome') + '</button>';
            h += '<button class="perigo" data-acao="apagar">Apagar</button>';
        } else {
            h = '<span>' + DICAS[ferramenta] + '</span>';
        }
        dica.innerHTML = h;
    }

    // ── Alterações e histórico ────────────────────────────────────────

    function guardarHistorico() {
        historico.push(JSON.stringify(desenho));
        if (historico.length > 60) historico.shift();
    }
    function marcarAlterado() {
        alterado = true;
        btnGuardar.classList.add('alterado');
        btnGuardar.textContent = 'Guardar';
    }
    function desfazer() {
        if (!historico.length) return;
        desenho = JSON.parse(historico.pop());
        selecionado = null; rascunho = null;
        marcarAlterado(); render();
    }

    function apagarSelecionado() {
        if (!selecionado) return;
        guardarHistorico();
        if (selecionado === 'escala') desenho.escala = null;
        else desenho.itens = desenho.itens.filter(function (it) { return it.id !== selecionado; });
        selecionado = null;
        marcarAlterado(); render();
    }

    function pedirMetros(atual) {
        var v = prompt('Quantos metros tem esta medida?', atual ? String(atual).replace('.', ',') : '');
        if (v === null) return null;
        v = parseFloat(String(v).replace(',', '.'));
        if (!(v > 0)) { showToast('Indique um número de metros maior que zero.', 'error'); return null; }
        return v;
    }

    function editarTexto() {
        var it = item(selecionado);
        if (!it || it.tipo === 'linha') return;
        var atual = it.tipo === 'nota' ? it.texto : it.nome;
        var v = prompt(it.tipo === 'nota' ? 'Texto da nota' : 'Nome da unidade (ex.: Sala 3,5 kW)', atual || '');
        if (v === null) return;
        v = v.trim().slice(0, 120);
        if (it.tipo === 'nota' && !v) return;
        guardarHistorico();
        if (it.tipo === 'nota') it.texto = v; else it.nome = v;
        marcarAlterado(); render();
    }

    function terminarRascunho() {
        if (!rascunho) return;
        var pts = rascunho.pontos;
        // o duplo clique acrescenta o mesmo ponto duas vezes
        while (pts.length > 1 && dist(pts[pts.length - 1], pts[pts.length - 2]) < 2 / s) pts.pop();
        if (rascunho.categoria !== 'escala' && pts.length >= 2) {
            guardarHistorico();
            desenho.itens.push({ id: novoId(), tipo: 'linha', categoria: rascunho.categoria, pontos: pts.map(function (p) { return [n(p[0]), n(p[1])]; }) });
            marcarAlterado();
        }
        rascunho = null;
        render();
    }

    // Encaixa nas unidades (para ligar as linhas às máquinas) e na horizontal/vertical
    function encaixar(p, anterior) {
        var limite = 16 / s, melhor = null;
        desenho.itens.forEach(function (it) {
            if (it.tipo !== 'unidade') return;
            var d = dist(p, [it.x, it.y]);
            if (d < limite) { limite = d; melhor = [it.x, it.y]; }
        });
        if (melhor) return melhor;
        if (anterior) {
            var ang = Math.abs(Math.atan2(p[1] - anterior[1], p[0] - anterior[0]) * 180 / Math.PI);
            if (ang < 6 || ang > 174) return [p[0], anterior[1]];
            if (Math.abs(ang - 90) < 6) return [anterior[0], p[1]];
        }
        return p;
    }

    function tocar(p, alvo) {
        if (ferramenta === 'selecionar') {
            selecionado = alvo ? alvo.id : null;
            render();
            return;
        }
        if (ferramenta === 'interior' || ferramenta === 'exterior') {
            guardarHistorico();
            var u = { id: novoId(), tipo: 'unidade', modelo: ferramenta, x: n(p[0]), y: n(p[1]), nome: '' };
            desenho.itens.push(u);
            marcarAlterado(); render();
            var nome = prompt('Nome da unidade (opcional, ex.: Sala 3,5 kW)', '');
            if (nome) { u.nome = nome.trim().slice(0, 120); render(); }
            return;
        }
        if (ferramenta === 'nota') {
            var t = prompt('Texto da nota (ex.: furo na parede, quadro elétrico)', '');
            if (!t || !t.trim()) return;
            guardarHistorico();
            desenho.itens.push({ id: novoId(), tipo: 'nota', x: n(p[0]), y: n(p[1]), texto: t.trim().slice(0, 120) });
            marcarAlterado(); render();
            return;
        }
        if (ferramenta === 'escala') {
            if (!rascunho) { rascunho = { categoria: 'escala', pontos: [p] }; render(); return; }
            var a = rascunho.pontos[0], b = encaixar(p, a);
            rascunho = null;
            if (dist(a, b) < 5 / s) { render(); return; }
            var m = pedirMetros(desenho.escala && desenho.escala.metros);
            if (m) {
                guardarHistorico();
                desenho.escala = { x1: n(a[0]), y1: n(a[1]), x2: n(b[0]), y2: n(b[1]), metros: m };
                marcarAlterado();
                escolherFerramenta('selecionar');
            }
            render();
            return;
        }
        // linhas
        if (!rascunho) rascunho = { categoria: ferramenta, pontos: [encaixar(p, null)] };
        else rascunho.pontos.push(encaixar(p, rascunho.pontos[rascunho.pontos.length - 1]));
        render();
    }

    function escolherFerramenta(f) {
        if (rascunho) {
            if (rascunho.categoria !== 'escala' && rascunho.pontos.length >= 2) terminarRascunho();
            rascunho = null;
        }
        ferramenta = f; selecionado = null;
        document.querySelectorAll('.ferr[data-ferramenta]').forEach(function (b) { b.classList.toggle('ativa', b.dataset.ferramenta === f); });
        render();
    }

    // ── Zoom e deslocamento ───────────────────────────────────────────

    function escalaAjustada() {
        var r = area.getBoundingClientRect();
        return Math.min(r.width / W, r.height / H) * 0.94;
    }
    function ajustar() {
        var r = area.getBoundingClientRect();
        s = escalaAjustada();
        tx = (r.width - W * s) / 2; ty = (r.height - H * s) / 2;
        render();
    }
    function zoomEm(novo, cx, cy) {
        novo = Math.max(escalaAjustada() * 0.5, Math.min(novo, 8));
        var ix = (cx - tx) / s, iy = (cy - ty) / s;
        s = novo; tx = cx - ix * s; ty = cy - iy * s;
        render();
    }
    function zoomCentro(f) { var r = area.getBoundingClientRect(); zoomEm(s * f, r.width / 2, r.height / 2); }

    function ecraParaImagem(cx, cy) { var r = svg.getBoundingClientRect(); return [(cx - r.left - tx) / s, (cy - r.top - ty) / s]; }

    // ── Ponteiro (rato e toque) ───────────────────────────────────────

    var ponteiros = new Map(), toque = null, pinca = null;

    function alvoDe(el) {
        var g = el && el.closest && el.closest('[data-id]');
        return g ? { id: g.dataset.id, vertice: g.dataset.vertice != null ? +g.dataset.vertice : null } : null;
    }

    svg.addEventListener('pointerdown', function (e) {
        svg.setPointerCapture(e.pointerId);
        ponteiros.set(e.pointerId, [e.clientX, e.clientY]);
        if (ponteiros.size === 2) {  // dois dedos: zoom
            var ps = Array.from(ponteiros.values()), r = svg.getBoundingClientRect();
            pinca = { d: dist(ps[0], ps[1]), m: [(ps[0][0] + ps[1][0]) / 2 - r.left, (ps[0][1] + ps[1][1]) / 2 - r.top], s: s, tx: tx, ty: ty };
            toque = null;
            return;
        }
        if (ponteiros.size > 2) return;
        var alvo = ferramenta === 'selecionar' ? alvoDe(e.target) : null;
        toque = { x: e.clientX, y: e.clientY, img: ecraParaImagem(e.clientX, e.clientY), alvo: alvo, movido: false, tx: tx, ty: ty, original: null };
        if (alvo) {
            var it = alvo.id === 'escala' ? desenho.escala : item(alvo.id);
            toque.original = JSON.parse(JSON.stringify(it));
            if (selecionado !== alvo.id) { selecionado = alvo.id; render(); }
        }
    });

    svg.addEventListener('pointermove', function (e) {
        if (ponteiros.has(e.pointerId)) ponteiros.set(e.pointerId, [e.clientX, e.clientY]);
        if (pinca && ponteiros.size >= 2) {
            var ps = Array.from(ponteiros.values()), r = svg.getBoundingClientRect();
            var m = [(ps[0][0] + ps[1][0]) / 2 - r.left, (ps[0][1] + ps[1][1]) / 2 - r.top];
            var novo = Math.max(escalaAjustada() * 0.5, Math.min(pinca.s * dist(ps[0], ps[1]) / pinca.d, 8));
            var ix = (pinca.m[0] - pinca.tx) / pinca.s, iy = (pinca.m[1] - pinca.ty) / pinca.s;
            s = novo; tx = m[0] - ix * s; ty = m[1] - iy * s;
            render();
            return;
        }
        cursor = ecraParaImagem(e.clientX, e.clientY);
        if (!toque) {
            if (rascunho) render();  // pré-visualização do próximo segmento
            return;
        }
        if (!toque.movido && Math.hypot(e.clientX - toque.x, e.clientY - toque.y) < 6) return;
        if (!toque.movido) {
            toque.movido = true;
            if (toque.alvo) guardarHistorico();
        }
        if (toque.alvo) {
            var dx = cursor[0] - toque.img[0], dy = cursor[1] - toque.img[1], o = toque.original;
            if (toque.alvo.id === 'escala') {
                desenho.escala = { x1: n(o.x1 + dx), y1: n(o.y1 + dy), x2: n(o.x2 + dx), y2: n(o.y2 + dy), metros: o.metros };
            } else {
                var it = item(toque.alvo.id);
                if (it.tipo === 'linha') {
                    if (toque.alvo.vertice != null) {
                        var p = encaixar(cursor, null);
                        it.pontos[toque.alvo.vertice] = [n(p[0]), n(p[1])];
                    } else {
                        it.pontos = o.pontos.map(function (p) { return [n(p[0] + dx), n(p[1] + dy)]; });
                    }
                } else { it.x = n(o.x + dx); it.y = n(o.y + dy); }
            }
            marcarAlterado();
            render();
        } else {
            tx = toque.tx + (e.clientX - toque.x); ty = toque.ty + (e.clientY - toque.y);
            aplicarVista();
        }
    });

    function largar(e) {
        ponteiros.delete(e.pointerId);
        if (pinca) { if (ponteiros.size < 2) pinca = null; return; }
        if (!toque) return;
        var t = toque; toque = null;
        if (!t.movido) tocar(ecraParaImagem(e.clientX, e.clientY), t.alvo);
    }
    svg.addEventListener('pointerup', largar);
    svg.addEventListener('pointercancel', function (e) { ponteiros.delete(e.pointerId); pinca = null; toque = null; });
    svg.addEventListener('pointerleave', function () { if (rascunho && !toque) { cursor = null; render(); } });

    svg.addEventListener('dblclick', function (e) {
        if (rascunho && rascunho.categoria !== 'escala') { terminarRascunho(); return; }
        // com a captura do ponteiro o alvo do duplo clique é o svg: usa-se o que ficou selecionado
        if (ferramenta === 'selecionar' && selecionado && selecionado !== 'escala') editarTexto();
    });

    svg.addEventListener('wheel', function (e) {
        e.preventDefault();
        var r = svg.getBoundingClientRect();
        zoomEm(s * Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top);
    }, { passive: false });

    // ── Botões e teclado ──────────────────────────────────────────────

    document.querySelectorAll('.ferr[data-ferramenta]').forEach(function (b) {
        b.addEventListener('click', function () { escolherFerramenta(b.dataset.ferramenta); });
    });
    btnDesfazer.addEventListener('click', desfazer);
    document.getElementById('zoomMais').addEventListener('click', function () { zoomCentro(1.4); });
    document.getElementById('zoomMenos').addEventListener('click', function () { zoomCentro(1 / 1.4); });
    document.getElementById('zoomAjustar').addEventListener('click', ajustar);

    dica.addEventListener('click', function (e) {
        var b = e.target.closest('button');
        if (!b) return;
        var acao = b.dataset.acao;
        if (acao === 'terminar') terminarRascunho();
        else if (acao === 'cancelar') { rascunho = null; render(); }
        else if (acao === 'apagar') apagarSelecionado();
        else if (acao === 'texto') editarTexto();
        else if (acao === 'metros') {
            var m = pedirMetros(desenho.escala.metros);
            if (m) { guardarHistorico(); desenho.escala.metros = m; marcarAlterado(); render(); }
        }
    });

    document.addEventListener('keydown', function (e) {
        var aEscrever = /INPUT|TEXTAREA/.test(document.activeElement.tagName);
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); guardar(); return; }
        if (aEscrever) return;
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); desfazer(); }
        else if (e.key === 'Escape') { rascunho = null; selecionado = null; render(); }
        else if (e.key === 'Enter') terminarRascunho();
        else if ((e.key === 'Delete' || e.key === 'Backspace') && selecionado) { e.preventDefault(); apagarSelecionado(); }
    });

    [campoNome, campoMorada].forEach(function (c) { c.addEventListener('input', marcarAlterado); });

    // ── Guardar e exportar ────────────────────────────────────────────

    function guardar() {
        if (rascunho && rascunho.categoria !== 'escala') terminarRascunho();
        btnGuardar.disabled = true;
        return fetch('/plantas/' + dados.id + '/guardar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
            body: JSON.stringify({ nome: campoNome.value, morada: campoMorada.value, desenho: desenho })
        }).then(function (r) { return r.json(); }).then(function (d) {
            btnGuardar.disabled = false;
            if (!d.ok) throw new Error(d.mensagem);
            alterado = false;
            btnGuardar.classList.remove('alterado');
            btnGuardar.textContent = 'Guardado ✓';
            if (campoNome.value.trim()) document.title = document.title.split(' — ')[0] + ' — ' + campoNome.value.trim();
        }).catch(function (err) {
            btnGuardar.disabled = false;
            showToast(err instanceof TypeError || err instanceof SyntaxError || !err.message ? 'Não foi possível guardar. Verifique a ligação.' : err.message, 'error');
        });
    }
    btnGuardar.addEventListener('click', guardar);

    window.addEventListener('beforeunload', function (e) {
        if (alterado) { e.preventDefault(); e.returnValue = ''; }
    });

    document.getElementById('btnImagem').addEventListener('click', function () {
        var u = Math.max(W, H) / 1100;  // símbolos do mesmo tamanho relativo que na planta vista inteira
        var marca = '<svg xmlns="http://www.w3.org/2000/svg" width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + ' ' + H + '">' + marcacao(u, false) + '</svg>';
        var fundo = new Image(), por_cima = new Image();
        fundo.onload = function () {
            por_cima.onload = function () {
                var c = document.createElement('canvas');
                c.width = W; c.height = H;
                var ctx = c.getContext('2d');
                ctx.drawImage(fundo, 0, 0, W, H);
                ctx.drawImage(por_cima, 0, 0, W, H);
                legenda(ctx, u);
                c.toBlob(function (blob) {
                    var a = document.createElement('a');
                    a.href = URL.createObjectURL(blob);
                    a.download = (campoNome.value.trim() || 'planta').replace(/[^\w\-]+/g, '_') + '.png';
                    a.click();
                    setTimeout(function () { URL.revokeObjectURL(a.href); }, 2000);
                }, 'image/png');
            };
            por_cima.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(marca);
        };
        fundo.src = document.getElementById('imagem').getAttribute('href');
    });

    function legenda(ctx, u) {  // caixa com os totais no canto inferior esquerdo
        var t = totais(), linhas = [];
        Object.keys(CATEGORIAS).forEach(function (k) {
            if (t[k]) linhas.push([CATEGORIAS[k].cor, CATEGORIAS[k].nome + (pxPorMetro() ? ': ' + metros(t[k]) : '')]);
        });
        if (t.interior) linhas.push([MODELOS.interior.cor, 'Unidades interiores: ' + t.interior]);
        if (t.exterior) linhas.push([MODELOS.exterior.cor, 'Unidades exteriores: ' + t.exterior]);
        if (!linhas.length) return;
        var f = 13 * u, alt = f * 1.6, pad = f * 0.9;
        ctx.font = 'bold ' + f + 'px Arial, sans-serif';
        var larg = Math.max.apply(null, linhas.map(function (l) { return ctx.measureText(l[1]).width; })) + f * 2.4 + pad * 2;
        var h = linhas.length * alt + pad * 2, x = pad, y = H - h - pad;
        ctx.fillStyle = 'rgba(255,255,255,0.92)'; ctx.strokeStyle = '#c5cae9'; ctx.lineWidth = u;
        ctx.fillRect(x, y, larg, h); ctx.strokeRect(x, y, larg, h);
        linhas.forEach(function (l, i) {
            var ly = y + pad + alt * i + alt / 2;
            ctx.fillStyle = l[0]; ctx.fillRect(x + pad, ly - f * 0.18, f * 1.6, f * 0.36);
            ctx.fillStyle = '#222'; ctx.textBaseline = 'middle'; ctx.fillText(l[1], x + pad + f * 2.2, ly);
        });
    }

    // ── Arranque ──────────────────────────────────────────────────────

    var img = document.getElementById('imagem');
    var pre = new Image();
    pre.onload = function () { document.getElementById('aCarregar').remove(); };
    pre.onerror = function () { document.getElementById('aCarregar').textContent = 'Não foi possível carregar a imagem da planta.'; };
    pre.src = img.getAttribute('href');
    window.addEventListener('resize', function () { aplicarVista(); });
    ajustar();
})();
