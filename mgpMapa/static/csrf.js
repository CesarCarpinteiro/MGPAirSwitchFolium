// Proteção CSRF: junta o token (meta csrf-token, injetado pelo servidor em todas as páginas) a todos os
// pedidos que alteram dados feitos pela própria app: formulários POST (incluindo form.submit() e os criados
// por JavaScript) e fetch/XMLHttpRequest. Pedidos para outros sites não levam o token.
(function () {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (!meta) return;
    var token = meta.getAttribute('content');

    function mesmaOrigem(url) {
        try { return new URL(url, location.href).origin === location.origin; } catch (e) { return false; }
    }
    function alteraDados(metodo) {
        return ['GET', 'HEAD', 'OPTIONS'].indexOf(String(metodo || 'GET').toUpperCase()) === -1;
    }

    var _fetch = window.fetch;
    window.fetch = function (input, init) {
        init = init || {};
        var pedido = input instanceof Request ? input : null;
        var metodo = init.method || (pedido && pedido.method);
        if (alteraDados(metodo) && mesmaOrigem(pedido ? pedido.url : input)) {
            var headers = new Headers(init.headers || (pedido ? pedido.headers : undefined));
            headers.set('X-CSRFToken', token);
            init.headers = headers;
        }
        return _fetch.call(this, input, init);
    };

    var _open = XMLHttpRequest.prototype.open, _send = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function (metodo, url) {
        this._csrf = alteraDados(metodo) && mesmaOrigem(url);
        return _open.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function () {
        if (this._csrf) this.setRequestHeader('X-CSRFToken', token);
        return _send.apply(this, arguments);
    };

    function juntarToken(form) {
        if (!(form instanceof HTMLFormElement) || String(form.method).toLowerCase() !== 'post') return;
        if (!mesmaOrigem(form.getAttribute('action') || location.href)) return;
        var campo = form.querySelector('input[name="csrf_token"]');
        if (!campo) {
            campo = document.createElement('input');
            campo.type = 'hidden';
            campo.name = 'csrf_token';
            form.appendChild(campo);
        }
        campo.value = token;
    }
    document.addEventListener('submit', function (e) { juntarToken(e.target); }, true);
    var _submit = HTMLFormElement.prototype.submit;  // form.submit() não dispara o evento submit
    HTMLFormElement.prototype.submit = function () { juntarToken(this); return _submit.call(this); };
})();
