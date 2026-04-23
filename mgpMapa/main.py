from flask import Flask, render_template, request, redirect, url_for, render_template_string
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import Usuario, Registo, Fatura, Ferias
from folium.plugins import Geocoder, TagFilterButton, Fullscreen
from db import db
import hashlib
import folium
from datetime import datetime
import json
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'lancode'
lm = LoginManager(app)
lm.login_view = 'login'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db.init_app(app)

def hash(txt):
    return hashlib.sha256(txt.encode('utf-8')).hexdigest()

@lm.user_loader
def user_loader(id):
    return db.session.query(Usuario).filter_by(id=id).first()

@app.route('/')
@login_required
def home():
    MAPBOX_TOKEN = 'pk.eyJ1IjoiY2VzYXIxOTk4IiwiYSI6ImNtbzhqaHhvNDAyZW0ycnF6YWxhNndpZ2wifQ.IKEgSQLTLT1Q45MJ1ZlCfg'

    m = folium.Map(
        location=[41.1579, -8.6291],
        zoom_start=13,
        zoom_control=False,
        tiles=f'https://api.mapbox.com/styles/v1/mapbox/streets-v12/tiles/{{z}}/{{x}}/{{y}}?access_token={MAPBOX_TOKEN}',
        attr='© <a href="https://www.mapbox.com/">Mapbox</a>'
    )

    Fullscreen(position='bottomright').add_to(m)
    Geocoder(position='topright').add_to(m)
    TagFilterButton(['Em dia', 'Atenção', 'Urgente'], name='Filtrar').add_to(m)

    registos = db.session.query(Registo).filter(
        Registo.latitude.isnot(None),
        Registo.longitude.isnot(None)
    ).all()

    sidebar_items = []
    current_date = datetime.now().date()

    for r in registos:
        # Calculate status from data_instalacao
        months_passed = 0
        next_maintenance_display = r.proxima_manutencao or 'N/A'

        if r.data_instalacao:
            try:
                install_date = datetime.strptime(r.data_instalacao, '%d/%m/%Y').date()
                months_passed = (current_date.year - install_date.year) * 12 + (current_date.month - install_date.month)
            except:
                pass

        if months_passed <= 8:
            color = '#6c757d'
            filter_value = 'Em dia'
            status_label = 'Em dia'
        elif 8 < months_passed <= 10:
            color = '#fd7e14'
            filter_value = 'Atenção'
            status_label = 'Atenção'
        else:
            color = '#dc3545'
            filter_value = 'Urgente'
            status_label = 'Urgente'

        popup_html = f"""
        <div style="font-family: Arial, sans-serif; width: 280px; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.2);">
            <div style="background-color: {color}; padding: 12px 16px; display: flex; justify-content: space-between; align-items: center;">
                <span style="color: white; font-size: 15px; font-weight: bold;">{r.nome}</span>
                <span style="background: rgba(255,255,255,0.25); color: white; font-size: 11px; padding: 2px 8px; border-radius: 12px;">{status_label}</span>
            </div>
            <div style="padding: 12px 16px; background: white;">
                <p style="margin: 6px 0; font-size: 13px;">📞 <strong>Contacto:</strong> {r.contacto or 'N/A'}</p>
                <p style="margin: 6px 0; font-size: 13px;">⚙️ <strong>Nº Máquinas:</strong> {r.num_maquinas or 'N/A'} &nbsp;|&nbsp; <strong>Marca:</strong> {r.marca or 'N/A'}</p>
                <p style="margin: 6px 0; font-size: 13px;">📅 <strong>Instalação:</strong> {r.data_instalacao or 'N/A'}</p>
                <p style="margin: 6px 0; font-size: 13px;">🔧 <strong>Próx. Manutenção:</strong> {next_maintenance_display}</p>
                <a href="tel:{r.contacto}" style="display: block; margin-top: 12px; text-align: center; background-color: {color}; color: white; padding: 8px; border-radius: 6px; text-decoration: none; font-size: 13px; font-weight: bold;">
                    📞 Ligar
                </a>
            </div>
        </div>
        """

        svg_icon = f"""
        <div style="position:relative; width:32px; height:42px;">
            <svg xmlns="http://www.w3.org/2000/svg" width="32" height="42" viewBox="0 0 32 42">
                <path d="M16 0 C7.163 0 0 7.163 0 16 C0 28 16 42 16 42 C16 42 32 28 32 16 C32 7.163 24.837 0 16 0 Z"
                      fill="{color}" stroke="white" stroke-width="2"/>
                <g transform="translate(16,15)">
                    <path d="M0,0 C0,-6 4,-7 3,-3 Z" fill="white" opacity="0.95"/>
                    <path d="M0,0 C0,-6 4,-7 3,-3 Z" fill="white" opacity="0.95" transform="rotate(90)"/>
                    <path d="M0,0 C0,-6 4,-7 3,-3 Z" fill="white" opacity="0.95" transform="rotate(180)"/>
                    <path d="M0,0 C0,-6 4,-7 3,-3 Z" fill="white" opacity="0.95" transform="rotate(270)"/>
                    <circle cx="0" cy="0" r="1.8" fill="white"/>
                </g>
            </svg>
        </div>
        """

        icon = folium.DivIcon(
            html=svg_icon,
            icon_size=(32, 42),
            icon_anchor=(16, 42),
            popup_anchor=(0, -42)
        )

        folium.Marker(
            location=[r.latitude, r.longitude],
            popup=folium.Popup(popup_html, max_width=300),
            icon=icon,
            tags=[filter_value]
        ).add_to(m)

        sidebar_items.append({
            'cliente': r.nome,
            'status': status_label,
            'dot_color': color,
            'next_maintenance': next_maintenance_display,
            'lat': r.latitude,
            'lng': r.longitude,
            'months': months_passed
        })

    # Auto-center map if there are points
    if registos:
        lats = [r.latitude for r in registos]
        lngs = [r.longitude for r in registos]
        m.location = [sum(lats)/len(lats), sum(lngs)/len(lngs)]

    sidebar_items.sort(key=lambda x: x['months'], reverse=True)

    sidebar_html_items = ''
    for item in sidebar_items:
        sidebar_html_items += f"""
        <div class="sidebar-item" onclick="flyTo({item['lat']}, {item['lng']})"
             style="border-left: 4px solid {item['dot_color']};">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <strong style="font-size:13px;">{item['cliente']}</strong>
                <span style="font-size:11px; color:{item['dot_color']}; font-weight:bold;">{item['status']}</span>
            </div>
            <div style="font-size:12px; color:#666; margin-top:3px;">🔧 {item['next_maintenance']}</div>
        </div>
        """

    custom_js = """
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        var clearButton = document.querySelector('.tag-filter-tags-container ul.header li.ripple a');
        if (clearButton) clearButton.textContent = 'Limpar';

        var searchInput = document.querySelector('.leaflet-control-geocoder-form input');
        if (searchInput) searchInput.setAttribute('placeholder', 'Pesquisar...');

        var mapEl = document.querySelector('.folium-map');
        if (mapEl) {
            var map = window[mapEl.id];
            if (map) {
                L.control.zoom({ position: 'bottomright' }).addTo(map);

                var legend = L.control({ position: 'bottomleft' });
                legend.onAdd = function() {
                    var div = L.DomUtil.create('div');
                    div.style.cssText = 'background:white; padding:10px 14px; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.15); font-size:12px; font-family:Arial;';
                    div.innerHTML =
                        '<div style="font-weight:bold; margin-bottom:6px; font-size:13px;">Estado da Manutenção</div>' +
                        '<div style="display:flex; align-items:center; gap:8px; margin:4px 0;"><div style="width:12px;height:12px;border-radius:50%;background:#6c757d;flex-shrink:0;"></div><span>Em dia (&lt; 8 meses)</span></div>' +
                        '<div style="display:flex; align-items:center; gap:8px; margin:4px 0;"><div style="width:12px;height:12px;border-radius:50%;background:#fd7e14;flex-shrink:0;"></div><span>Atenção (8–10 meses)</span></div>' +
                        '<div style="display:flex; align-items:center; gap:8px; margin:4px 0;"><div style="width:12px;height:12px;border-radius:50%;background:#dc3545;flex-shrink:0;"></div><span>Urgente (&gt; 10 meses)</span></div>';
                    return div;
                };
                legend.addTo(map);
            }
        }
    });

    function flyTo(lat, lng) {
        var mapEl = document.querySelector('.folium-map');
        if (mapEl) {
            var map = window[mapEl.id];
            if (map) map.flyTo([lat, lng], 16, { duration: 1.2 });
        }
    }
    </script>
    """

    m.get_root().html.add_child(folium.Element(custom_js))
    m.get_root().render()
    header = m.get_root().header.render()
    body_html = m.get_root().html.render()
    script = m.get_root().script.render()

    return render_template_string("""
        <!DOCTYPE html>
        <html lang="pt">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>MGP Air Switch - Mapa de Serviços Executados</title>
                <style>
                    * { box-sizing: border-box; margin: 0; padding: 0; }
                    html, body { height: 100%; font-family: 'Arial', sans-serif; background-color: #f0f2f5; display: flex; flex-direction: column; overflow: hidden; }
                    .page-header { background: linear-gradient(135deg, #2e7d32, #4CAF50); padding: 14px 24px; display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
                    .page-header h1 { font-size: 1.4em; color: white; letter-spacing: 0.5px; font-weight: 700; }
                    .page-header .subtitle { font-size: 0.8em; color: rgba(255,255,255,0.75); margin-top: 2px; }
                    .page-header a { padding: 9px 20px; background: white; color: #2e7d32; text-decoration: none; border-radius: 6px; font-size: 0.9em; font-weight: bold; white-space: nowrap; box-shadow: 0 1px 4px rgba(0,0,0,0.15); transition: background 0.2s; }
                    .page-header a:hover { background: #f0f0f0; }
                    .main-content { display: flex; flex: 1; min-height: 0; gap: 10px; padding: 10px; overflow: hidden; }
                    .sidebar { width: 260px; flex-shrink: 0; background: white; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); display: flex; flex-direction: column; overflow: hidden; }
                    .sidebar-header { background: #2e7d32; color: white; padding: 12px 16px; font-size: 14px; font-weight: bold; flex-shrink: 0; }
                    .sidebar-search { padding: 8px 10px; border-bottom: 1px solid #eee; flex-shrink: 0; }
                    .sidebar-search input { width: 100%; padding: 6px 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px; outline: none; }
                    .sidebar-list { overflow-y: auto; flex: 1; }
                    .sidebar-item { padding: 10px 14px; border-bottom: 1px solid #f0f0f0; cursor: pointer; transition: background 0.15s; }
                    .sidebar-item:hover { background-color: #f8f8f8; }
                    .map-container { flex: 1; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); overflow: hidden; min-width: 0; position: relative; }
                    .map-container > div { position: absolute !important; top: 0 !important; left: 0 !important; width: 100% !important; height: 100% !important; }
                    .folium-map { width: 100% !important; height: 100% !important; }
                    footer { flex-shrink: 0; text-align: center; padding: 7px; background: #2e7d32; color: rgba(255,255,255,0.8); font-size: 12px; }
                    @media only screen and (max-width: 767px) { .sidebar { display: none; } .main-content { padding: 6px; } .page-header h1 { font-size: 1em; } }
                </style>
                {{ header|safe }}
            </head>
            <body>
                <div class="page-header">
                    <div>
                        <div class="subtitle">Gestão de Serviços</div>
                        <h1>MGP Air Switch — Mapa de Serviços Executados</h1>
                    </div>
                    <div style="display:flex; align-items:center; gap:10px; margin-left:auto;">
                        <a href="test">+ Registo</a>
                        <a href="/perfil" style="background:rgba(255,255,255,0.15); color:white; border:1px solid rgba(255,255,255,0.3); display:flex; align-items:center; gap:8px; font-size:0.85em;">
                            👤 {{ current_user.nome }}
                        </a>
                    </div>
                </div>
                <div class="main-content">
                    <div class="sidebar">
                        <div class="sidebar-header">📋 Clientes ({{ total }})</div>
                        <div class="sidebar-search">
                            <input type="text" id="sidebarSearch" placeholder="Pesquisar cliente..." oninput="filterSidebar(this.value)">
                        </div>
                        <div class="sidebar-list" id="sidebarList">{{ sidebar_html|safe }}</div>
                    </div>
                    <div class="map-container">{{ body_html|safe }}</div>
                </div>
                <footer>&copy; MGP Air Switch</footer>
                <script>
                    {{ script|safe }}
                    function filterSidebar(query) {
                        var items = document.querySelectorAll('.sidebar-item');
                        query = query.toLowerCase();
                        items.forEach(function(item) {
                            item.style.display = item.textContent.toLowerCase().includes(query) ? 'block' : 'none';
                        });
                    }
                </script>
            </body>
        </html>
    """, header=header, body_html=body_html, script=script, sidebar_html=sidebar_html_items, total=len(sidebar_items), current_user=current_user)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    nome = request.form['nomeForm']
    senha = request.form['senhaForm']
    user = db.session.query(Usuario).filter_by(nome=nome, senha=hash(senha)).first()
    if not user:
        return 'Nome ou senha incorreta'
    login_user(user)
    return redirect(url_for('home'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

ALLOWED_TO_REGISTER = {'admin123456', 'miguel.pereira'}

@app.route('/registrar', methods=['GET', 'POST'])
@login_required
def registrar():
    if current_user.nome not in ALLOWED_TO_REGISTER:
        return redirect(url_for('perfil'))
    if request.method == 'GET':
        return redirect(url_for('perfil'))
    nome = request.form.get('nomeForm')
    senha = request.form.get('senhaForm')
    is_admin = request.form.get('is_admin') == 'on'
    if nome and senha:
        if not db.session.query(Usuario).filter_by(nome=nome).first():
            novo_usuario = Usuario(nome=nome, senha=hash(senha), is_admin=is_admin)
            db.session.add(novo_usuario)
            db.session.commit()
    return redirect(url_for('perfil'))

@app.route('/delete_user/<int:id>', methods=['POST'])
@login_required
def delete_user(id):
    if current_user.nome not in ALLOWED_TO_REGISTER:
        return redirect(url_for('perfil'))
    user = db.session.query(Usuario).filter_by(id=id).first()
    if user and user.nome != 'admin123456':
        db.session.delete(user)
        db.session.commit()
    return redirect(url_for('perfil'))

def converter_data(d):
    if d:
        try:
            return datetime.strptime(d, '%Y-%m-%d').strftime('%d/%m/%Y')
        except:
            return d
    return None

@app.route('/test', methods=['GET', 'POST'])
@login_required
def nova_pagina():
    if request.method == 'POST':
        nome = request.form.get('nome')
        contacto = request.form.get('contacto')
        num_maquinas = request.form.get('num_maquinas')
        marca = request.form.get('marca')
        data_instalacao = request.form.get('data_instalacao')
        proxima_manutencao = request.form.get('proxima_manutencao')
        morada = request.form.get('morada')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        if nome:
            novo_registo = Registo(
                nome=nome,
                contacto=contacto,
                num_maquinas=int(num_maquinas) if num_maquinas else None,
                marca=marca,
                data_instalacao=converter_data(data_instalacao),
                proxima_manutencao=converter_data(proxima_manutencao),
                morada=morada,
                latitude=float(latitude) if latitude else None,
                longitude=float(longitude) if longitude else None
            )
            db.session.add(novo_registo)
            db.session.commit()
    registos = db.session.query(Registo).order_by(Registo.id.desc()).all()
    return render_template('test.html', registos=registos)

@app.route('/test/edit/<int:id>', methods=['POST'])
@login_required
def edit_registo(id):
    r = db.session.query(Registo).filter_by(id=id).first()
    if r:
        r.nome = request.form.get('nome', r.nome)
        r.contacto = request.form.get('contacto', r.contacto)
        r.num_maquinas = int(request.form.get('num_maquinas')) if request.form.get('num_maquinas') else r.num_maquinas
        r.marca = request.form.get('marca', r.marca)
        r.data_instalacao = request.form.get('data_instalacao', r.data_instalacao)
        r.proxima_manutencao = request.form.get('proxima_manutencao', r.proxima_manutencao)
        r.morada = request.form.get('morada', r.morada)
        lat = request.form.get('latitude')
        lon = request.form.get('longitude')
        r.latitude = float(lat) if lat else r.latitude
        r.longitude = float(lon) if lon else r.longitude
        db.session.commit()
    return redirect(url_for('nova_pagina'))

@app.route('/test/delete/<int:id>', methods=['POST'])
@login_required
def delete_registo(id):
    registo = db.session.query(Registo).filter_by(id=id).first()
    if registo:
        db.session.delete(registo)
        db.session.commit()
    return redirect(url_for('nova_pagina'))

@app.route('/perfil')
@login_required
def perfil():
    todos_usuarios = db.session.query(Usuario).all() if current_user.nome in ALLOWED_TO_REGISTER or current_user.is_admin else []
    registos = db.session.query(Registo).all() if current_user.nome in ALLOWED_TO_REGISTER or current_user.is_admin else []
    registos_json = json.dumps([{
        'data_instalacao': r.data_instalacao
    } for r in registos])
    return render_template('perfil.html',
        user=current_user,
        usuarios=todos_usuarios,
        registos=registos,
        registos_json=registos_json
    )

@app.route('/toggle_admin/<int:id>', methods=['POST'])
@login_required
def toggle_admin(id):
    if current_user.nome not in ALLOWED_TO_REGISTER:
        return redirect(url_for('perfil'))
    u = db.session.query(Usuario).filter_by(id=id).first()
    if u and u.nome not in ALLOWED_TO_REGISTER:
        u.is_admin = not u.is_admin
        db.session.commit()
    return redirect(url_for('perfil'))

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx', 'xlsx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/faturas', methods=['GET', 'POST'])
@login_required
def faturas():
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    if request.method == 'POST':
        local = request.form.get('local')
        valor = request.form.get('valor')
        data = request.form.get('data')
        nota = request.form.get('nota')
        ficheiro_path = None

        file = request.files.get('ficheiro')
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(f"{current_user.id}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            ficheiro_path = filename

        if local and valor and data:
            nova = Fatura(
                user_id=current_user.id,
                local=local,
                valor=float(valor),
                data=data,
                nota=nota,
                ficheiro=ficheiro_path
            )
            db.session.add(nova)
            db.session.commit()

    if current_user.nome in ALLOWED_TO_REGISTER or current_user.is_admin:
        todas = db.session.query(Fatura, Usuario).join(
            Usuario, Fatura.user_id == Usuario.id
        ).order_by(Fatura.id.desc()).all()
    else:
        todas = db.session.query(Fatura, Usuario).join(
            Usuario, Fatura.user_id == Usuario.id
        ).filter(Fatura.user_id == current_user.id).order_by(Fatura.id.desc()).all()

    usuarios = db.session.query(Usuario).all()
    total = sum(f.valor for f, u in todas)
    return render_template('faturas.html', faturas=todas, total=total, usuarios=usuarios)

@app.route('/faturas/delete/<int:id>', methods=['POST'])
@login_required
def delete_fatura(id):
    fatura = db.session.query(Fatura).filter_by(id=id).first()
    if fatura and (fatura.user_id == current_user.id or current_user.is_admin or current_user.nome in ALLOWED_TO_REGISTER):
        if fatura.ficheiro:
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], fatura.ficheiro))
            except:
                pass
        db.session.delete(fatura)
        db.session.commit()
    return redirect(url_for('faturas'))

@app.route('/ferias', methods=['GET', 'POST'])
@login_required
def ferias():
    if request.method == 'POST':
        data_inicio = request.form.get('data_inicio')
        data_fim = request.form.get('data_fim')
        nota = request.form.get('nota')
        if data_inicio and data_fim:
            nova = Ferias(
                user_id=current_user.id,
                data_inicio=converter_data(data_inicio),
                data_fim=converter_data(data_fim),
                nota=nota
            )
            db.session.add(nova)
            db.session.commit()

    is_admin = current_user.nome in ALLOWED_TO_REGISTER or current_user.is_admin

    if is_admin:
        todos = db.session.query(Ferias, Usuario).join(
            Usuario, Ferias.user_id == Usuario.id
        ).order_by(Ferias.id.desc()).all()
    else:
        todos = db.session.query(Ferias, Usuario).join(
            Usuario, Ferias.user_id == Usuario.id
        ).filter(Ferias.user_id == current_user.id).order_by(Ferias.id.desc()).all()

    return render_template('ferias.html', ferias=todos, is_admin=is_admin)

@app.route('/ferias/responder/<int:id>', methods=['POST'])
@login_required
def responder_ferias(id):
    if not (current_user.nome in ALLOWED_TO_REGISTER or current_user.is_admin):
        return redirect(url_for('ferias'))
    f = db.session.query(Ferias).filter_by(id=id).first()
    if f:
        f.estado = request.form.get('estado')
        f.comentario_admin = request.form.get('comentario')
        f.aprovado_por = current_user.nome
        db.session.commit()
    return redirect(url_for('ferias'))

@app.route('/ferias/delete/<int:id>', methods=['POST'])
@login_required
def delete_ferias(id):
    f = db.session.query(Ferias).filter_by(id=id).first()
    if f and (f.user_id == current_user.id or current_user.is_admin or current_user.nome in ALLOWED_TO_REGISTER):
        db.session.delete(f)
        db.session.commit()
    return redirect(url_for('ferias'))

############################################
def criar_admin():
    with app.app_context():
        db.create_all()
        try:
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE faturas ADD COLUMN ficheiro VARCHAR(300)'))
                conn.commit()
        except:
            pass
        if not db.session.query(Usuario).filter_by(nome='admin123456').first():
            admin = Usuario(nome='admin123456', senha=hash('admin123456'), is_admin=True)
            db.session.add(admin)
            db.session.commit()

if __name__ == "__main__":
    criar_admin()
    app.run(host="0.0.0.0", port=3000, debug=True)