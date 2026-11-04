// Botões de ação dentro das notificações do sino (ex.: SMS de manutenção: "Não enviar" / "Enviar já").
// A API /api/notificacoes devolve, por notificação, `acoes` (botões) ou `estado_acao` (resultado já conhecido).
(function () {
    var css = document.createElement('style');
    css.textContent =
        '.notif-acoes{display:flex;gap:6px;margin-top:8px}' +
        '.notif-acao{flex:1;padding:6px 8px;border-radius:6px;font-size:0.75em;font-weight:bold;cursor:pointer;' +
        'border:1px solid #f0d0d0;background:white;color:#a33b3b;font-family:inherit}' +
        '.notif-acao.principal{border:none;background:#2d3a6e;color:white}' +
        '.notif-acao-estado{display:block;margin-top:6px;font-size:0.75em;font-weight:bold;color:#888}' +
        '.notif-acao-estado.ok{color:#2e7d4f}.notif-acao-estado.erro{color:#a33b3b}';
    document.head.appendChild(css);

    function esc(s) {
        return String(s).replace(/[&<>"']/g, function (c) {
            return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c];
        });
    }

    window.notifAcoes = function (n) {
        if (n.acoes && n.acoes.length) {
            return '<div class="notif-acoes">' + n.acoes.map(function (a) {
                return '<button type="button" class="notif-acao' + (a.principal ? ' principal' : '') + '"'
                    + ' data-url="' + esc(a.url) + '" data-notif="' + n.id + '"'
                    + ' onclick="notifAcao(event, this)">' + esc(a.label) + '</button>';
            }).join('') + '</div>';
        }
        return n.estado_acao ? '<span class="notif-acao-estado">' + esc(n.estado_acao) + '</span>' : '';
    };

    window.notifAcao = function (e, btn) {
        e.stopPropagation();  // não abrir a notificação
        var box = btn.parentNode;
        box.innerHTML = '<span class="notif-acao-estado">A processar…</span>';
        fetch(btn.dataset.url, {method: 'POST', headers: {'Accept': 'application/json'}})
            .then(function (r) { return r.json(); })
            .then(function (d) {
                box.innerHTML = '<span class="notif-acao-estado ' + (d.ok ? 'ok' : 'erro') + '">' + esc(d.mensagem) + '</span>';
                if (d.ok) fetch('/api/notificacoes/lida/' + btn.dataset.notif, {method: 'POST'});
            })
            .catch(function () {
                box.innerHTML = '<span class="notif-acao-estado erro">Sem ligação, tente outra vez.</span>';
            });
    };
})();
