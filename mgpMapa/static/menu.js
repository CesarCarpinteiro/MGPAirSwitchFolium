/* Menu lateral (direita) com todas as páginas. Posto em todas as páginas pelo app.py (as páginas não partilham um template base). */
(function() {
    var s = document.currentScript;
    var ADMIN = s.dataset.admin === '1', MAPA = s.dataset.mapa === '1', NOME = s.dataset.nome || '';

    var grupos = [
        ['', [
            MAPA && ['/', '🗺️', 'Mapa', /^\/$/],
            ['/registos', '👥', 'Registos', /^\/registos/],
            ADMIN && ['/dashboard', '📊', 'Dashboard', /^\/dashboard/],
        ]],
        ['Trabalho', [
            ['/orcamentos', '📄', 'Orçamentos', /^\/orcamentos(\/novo|\/\d+.*)?$/],
            ADMIN && ['/orcamentos/catalogo', '📦', 'Catálogo', /^\/orcamentos\/catalogo/, true],
            ADMIN && ['/orcamentos/definicoes', '⚙️', 'Definições de orçamentos', /^\/orcamentos\/definicoes/, true],
            ['/plantas', '📐', 'Plantas', /^\/plantas/],
            ADMIN ? ['/marcacoes', '📅', 'Marcações', /^\/marcacoes/] : ['/minhas-obras', '🔧', 'As minhas obras', /^\/minhas-obras/],
            ADMIN && ['/lembretes', '💬', 'SMS de manutenção', /^\/lembretes/],
            ['/mensagens', '✉️', 'Mensagens enviadas', /^\/mensagens/],
        ]],
        ['Pessoal', [
            ['/horas', '⏱️', 'Horas de trabalho', /^\/horas/],
            ['/ferias', '🏖️', 'Férias', /^\/ferias/],
            ['/faturas', '🧾', 'Faturas', /^\/faturas/],
        ]],
    ];

    var LARG = 236;
    function lerFixo() { try { return localStorage.getItem('menuFixo') !== '0'; } catch (e) { return true; } }
    function guardarFixo(v) { try { localStorage.setItem('menuFixo', v ? '1' : '0'); } catch (e) {} }
    var computador = window.matchMedia('(min-width:1100px)');
    if (lerFixo()) document.documentElement.classList.add('mn-fixo');  // já, para a página não saltar

    var css = '' +
        '.mn-btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;height:38px;min-width:42px;padding:0 12px;border-radius:7px;border:1px solid rgba(255,255,255,.35);background:rgba(255,255,255,.15);color:#fff;font:600 14px "DM Sans",sans-serif;cursor:pointer;flex-shrink:0}' +
        '.mn-btn:hover{background:rgba(255,255,255,.25)}' +
        '.mn-btn .mn-ic{font-size:20px;line-height:1}' +
        '.mn-btn.mn-claro{border-color:#c5cae9;background:#fff;color:#2d3a6e}' +
        '.mn-btn.mn-flutua{position:fixed;top:10px;right:10px;z-index:9000;box-shadow:0 2px 8px rgba(0,0,0,.15)}' +
        '.mn-fundo{position:fixed;inset:0;background:rgba(15,20,45,.4);z-index:99980;opacity:0;pointer-events:none;transition:opacity .2s}' +
        '.mn-painel{position:fixed;top:0;right:0;bottom:0;width:290px;max-width:86vw;background:#fff;z-index:99981;transform:translateX(100%);transition:transform .22s ease;display:flex;flex-direction:column;box-shadow:-6px 0 24px rgba(0,0,0,.18);font-family:"DM Sans",sans-serif}' +
        'body.mn-aberto .mn-fundo{opacity:1;pointer-events:auto}' +
        'body.mn-aberto .mn-painel{transform:none}' +
        '.mn-topo{display:flex;align-items:center;justify-content:space-between;padding:16px 16px 14px 18px;background:linear-gradient(135deg,#2d3a6e,#4a5fa8);color:#fff}' +
        '.mn-topo a{color:#fff;text-decoration:none;font-weight:700;font-size:15px}' +
        '.mn-topo small{display:block;font-weight:400;opacity:.8;font-size:12px}' +
        '.mn-fechar{background:none;border:none;color:#fff;font-size:26px;line-height:1;cursor:pointer;padding:4px 6px}' +
        '.mn-lista{flex:1;overflow-y:auto;padding:8px 0 12px;-webkit-overflow-scrolling:touch}' +
        '.mn-grupo{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#9aa0b8;padding:14px 20px 4px}' +
        '.mn-item{display:flex;align-items:center;gap:12px;padding:11px 20px;color:#1f2433;text-decoration:none;font-size:15px;font-weight:500;border-left:3px solid transparent}' +
        '.mn-item:hover{background:#f3f5fc}' +
        '.mn-item.mn-sub{padding:8px 20px 8px 50px;font-size:14px;color:#555}' +
        '.mn-item.mn-atual{background:#eef0fa;border-left-color:#2d3a6e;color:#2d3a6e;font-weight:700}' +
        '.mn-item .mn-i{width:24px;text-align:center;font-size:18px}' +
        '.mn-rodape{border-top:1px solid #eee;padding:8px 0 calc(8px + env(safe-area-inset-bottom))}' +
        '.mn-item.mn-sair{color:#c62828}' +
        '@media(max-width:600px){.mn-btn .mn-txt{display:none}.mn-btn{padding:0 10px}' +
        // no telemóvel o cabeçalho fica só com o essencial: o resto está no menu
        '.mn-casa>a[href="/"],.mn-casa>a[href="/registos"],.mn-casa>a[href="/perfil"],.mn-casa>a.user-pill{display:none!important}}' +
        '.mn-fixar{display:none;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.35);color:#fff;border-radius:6px;font-size:13px;padding:5px 8px;cursor:pointer;margin-right:4px}' +
        // Computador: menu sempre aberto à direita (pode-se esconder e voltar a fixar)
        '@media(min-width:1100px){' +
            '.mn-fixar{display:inline-block}' +
            'html.mn-fixo body{padding-right:' + LARG + 'px!important}' +
            'html.mn-fixo .mn-painel{transform:none;width:' + LARG + 'px;box-shadow:-1px 0 0 #e1e4ef;transition:none}' +
            'html.mn-fixo .mn-fundo{display:none}' +
            'html.mn-fixo .mn-btn{display:none!important}' +
            'html.mn-fixo .mn-casa>a[href="/"],html.mn-fixo .mn-casa>a[href="/registos"],html.mn-fixo .mn-casa>a[href="/perfil"],html.mn-fixo .mn-casa>a.user-pill{display:none!important}' +
            'html.mn-fixo .mn-item{padding-top:9px;padding-bottom:9px;font-size:14px}' +
            'html.mn-fixo .mn-item.mn-sub{padding-top:6px;padding-bottom:6px;font-size:13px}' +
        '}' +
        '@media print{.mn-btn,.mn-painel,.mn-fundo{display:none!important}html.mn-fixo body{padding-right:0!important}}';
    var st = document.createElement('style');
    st.textContent = css;
    document.head.appendChild(st);

    function esc(t) { return String(t).replace(/[&<>"]/g, function(c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }

    function item(l, aqui) {
        var atual = l[3].test(aqui);
        return '<a href="' + l[0] + '" class="mn-item' + (l[4] ? ' mn-sub' : '') + (atual ? ' mn-atual' : '') + '"' +
            (atual ? ' aria-current="page"' : '') + '><span class="mn-i">' + l[1] + '</span>' + esc(l[2]) + '</a>';
    }

    function montar() {
        if (document.querySelector('.mn-painel')) return;
        var aqui = location.pathname;
        var html = '<div class="mn-topo"><a href="/perfil">' + esc(NOME || 'Perfil') + '<small>Ver perfil</small></a>' +
            '<span><button type="button" class="mn-fixar" title="Manter o menu sempre aberto">📌 Fixar</button>' +
            '<button type="button" class="mn-fechar" aria-label="Fechar menu">×</button></span></div><nav class="mn-lista">';
        grupos.forEach(function(g) {
            var itens = g[1].filter(Boolean);
            if (!itens.length) return;
            if (g[0]) html += '<div class="mn-grupo">' + g[0] + '</div>';
            itens.forEach(function(l) { html += item(l, aqui); });
        });
        html += '</nav><div class="mn-rodape">' + item(['/perfil', '👤', 'Perfil', /^\/perfil/], aqui) +
            '<a href="/logout" class="mn-item mn-sair"><span class="mn-i">⎋</span>Terminar sessão</a></div>';

        var fundo = document.createElement('div');
        fundo.className = 'mn-fundo';
        var painel = document.createElement('aside');
        painel.className = 'mn-painel';
        painel.setAttribute('aria-label', 'Menu');
        painel.innerHTML = html;
        document.body.appendChild(fundo);
        document.body.appendChild(painel);

        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'mn-btn';
        btn.setAttribute('aria-label', 'Menu');
        btn.innerHTML = '<span class="mn-ic">☰</span><span class="mn-txt">Menu</span>';
        // No cabeçalho de cada página (no fim, à direita); se a página não tiver, fica a flutuar no canto
        var sitio = document.querySelector('.header-actions') ||
            (document.querySelector('.page-header') && document.querySelector('.page-header').lastElementChild) ||
            document.querySelector('.topo');
        if (sitio) { sitio.appendChild(btn); sitio.classList.add('mn-casa'); }
        else { btn.classList.add('mn-flutua', 'mn-claro'); document.body.appendChild(btn); }

        var raiz = document.documentElement, bFechar = painel.querySelector('.mn-fechar'), bFixar = painel.querySelector('.mn-fixar');
        function estado() {
            var fixo = raiz.classList.contains('mn-fixo') && computador.matches;
            bFechar.textContent = fixo ? '»' : '×';
            bFechar.title = fixo ? 'Esconder o menu' : 'Fechar';
            bFixar.style.visibility = fixo ? 'hidden' : '';
        }
        function abrir() { document.body.classList.add('mn-aberto'); }
        function fechar() {
            if (raiz.classList.contains('mn-fixo') && computador.matches) {  // esconder o menu fixo
                raiz.classList.remove('mn-fixo'); guardarFixo(false);
                window.dispatchEvent(new Event('resize'));  // mapas e desenhos reajustam-se ao novo espaço
            }
            document.body.classList.remove('mn-aberto');
            estado();
        }
        bFixar.addEventListener('click', function() {
            raiz.classList.add('mn-fixo'); guardarFixo(true);
            document.body.classList.remove('mn-aberto');
            window.dispatchEvent(new Event('resize'));
            estado();
        });
        if (computador.addEventListener) computador.addEventListener('change', estado);
        estado();
        btn.addEventListener('click', abrir);
        fundo.addEventListener('click', fechar);
        bFechar.addEventListener('click', fechar);
        document.addEventListener('keydown', function(e) { if (e.key === 'Escape' && document.body.classList.contains('mn-aberto')) document.body.classList.remove('mn-aberto'); });
        // Deslizar para a direita fecha (telemóvel)
        var x0 = null;
        painel.addEventListener('touchstart', function(e) { x0 = e.touches[0].clientX; }, {passive: true});
        painel.addEventListener('touchend', function(e) {
            if (x0 !== null && e.changedTouches[0].clientX - x0 > 60) fechar();
            x0 = null;
        });
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', montar);
    else montar();
})();
