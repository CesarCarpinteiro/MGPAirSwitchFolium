from flask import Flask, render_template, request, redirect, url_for, render_template_string, jsonify, session as flask_session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import Usuario, Registo, Servico, TipoServico, Fatura, Ferias, Mensagem, HorasTrabalhadas, Orcamento, Organizacao
from folium.plugins import Geocoder, TagFilterButton, Fullscreen
from dotenv import load_dotenv
from db import db
import hashlib
import folium
from datetime import datetime
import json
import os
from werkzeug.utils import secure_filename
import smtplib
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'fallback-secret-key')
lm = LoginManager(app)
lm.login_view = 'login'
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///database.db')
db.init_app(app)

GMAIL_USER = os.getenv('GMAIL_USER', '')
GMAIL_PASS = os.getenv('GMAIL_PASS', '')
MAPBOX_TOKEN = os.getenv('MAPBOX_TOKEN', '')


def send_welcome_email(to_email, nome, org_nome, username, password_temp, codigo=None, criado_por=None):
    try:
        msg = MIMEMultipart('alternative')
        msg["Subject"] = f"Bem-vindo à plataforma {org_nome}"
        msg["From"] = formataddr((str(Header("GestãoPro", "utf-8")), GMAIL_USER))
        msg["To"] = to_email
        criado_por_block = (
            f'<div style="background:#e8f0fe;border:1px solid #b3c6f7;border-radius:8px;padding:10px 14px;margin-bottom:20px;">'
            f'<p style="font-size:13px;color:#3c5a99;margin:0;">Conta criada pelo administrador <strong>{criado_por}</strong>.</p>'
            f'</div>'
        ) if criado_por else ""
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;">
            <div style="background:#2e7d32;padding:28px 32px;text-align:center;">
                <p style="color:white;font-size:20px;font-weight:bold;margin:0 0 4px;">Bem-vindo à plataforma</p>
                <p style="color:rgba(255,255,255,0.75);font-size:13px;margin:0;">{org_nome}</p>
            </div>
            <div style="background:white;padding:28px 32px;">
                <p style="font-size:15px;color:#1a1a1a;margin:0 0 12px;">Olá <strong>{nome}</strong>,</p>
                <p style="font-size:14px;color:#555;line-height:1.6;margin:0 0 20px;">A tua conta foi criada com sucesso na plataforma <strong>{org_nome}</strong>. Aqui estão os teus dados de acesso:</p>
                <div style="background:#eaf3de;border:1px solid #c0dd97;border-radius:8px;padding:20px 24px;margin-bottom:20px;">
                    <p style="font-size:11px;color:#639922;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 4px;">Utilizador</p>
                    <p style="font-size:20px;font-weight:bold;color:#2e7d32;margin:0 0 16px;">{username}</p>
                    <p style="font-size:11px;color:#639922;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 4px;">Password temporária</p>
                    <p style="font-size:20px;font-weight:bold;color:#2e7d32;margin:0;">{password_temp}</p>
                </div>
                {f'<div style="background:#e8f0fe;border:1px solid #b3c6f7;border-radius:8px;padding:20px 24px;margin-bottom:20px;"><p style="font-size:11px;color:#3c5a99;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 8px;">Código de verificação</p><p style="font-size:32px;font-weight:bold;color:#1a3a8f;margin:0;letter-spacing:8px;">' + (codigo or '') + '</p></div>' if codigo else ''}
                <div style="background:#faeeda;border:1px solid #fac775;border-radius:8px;padding:10px 14px;margin-bottom:20px;">
                    <p style="font-size:13px;color:#854f0b;margin:0;">Por segurança, altera a tua password no primeiro login.</p>
                </div>
                {criado_por_block}
                <p style="font-size:14px;color:#555;line-height:1.6;margin:0;">Se tiveres alguma questão, responde a este email.<br>Bem-vindo à equipa!</p>
            </div>
            <div style="background:#f8f8f8;border-top:1px solid #eee;padding:16px 32px;text-align:center;">
                <p style="font-size:12px;color:#aaa;margin:0;">© {org_nome} — Plataforma de Gestão</p>
            </div>
        </div>
        """
        msg.attach(MIMEText(html, 'html'))
        with smtplib.SMTP("smtp.gmail.com", 587) as connection:
            connection.starttls()
            connection.login(user=GMAIL_USER, password=GMAIL_PASS)
            connection.send_message(msg)
        print(f"Email enviado para {to_email}")
    except Exception as e:
        print(f"Erro email: {e}")


def hash(txt):
    return hashlib.sha256(txt.encode('utf-8')).hexdigest()


@lm.user_loader
def user_loader(id):
    return db.session.query(Usuario).filter_by(id=id).first()


@app.context_processor
def inject_org():
    try:
        if current_user.is_authenticated and current_user.org_id:
            org = db.session.query(Organizacao).filter_by(id=current_user.org_id).first()
            tipo = getattr(org, 'tipo_negocio', 'cliente') if org else 'cliente'
            return dict(
                org_nome=org.nome if org else 'A minha Organização',
                org=org,
                tem_mapa=tipo != 'espaco'
            )
        return dict(org_nome='A minha Organização', org=None, tem_mapa=True)
    except:
        return dict(org_nome='A minha Organização', org=None, tem_mapa=True)


@app.route('/')
@login_required
def home():
    org = db.session.query(Organizacao).filter_by(id=current_user.org_id).first()
    org_nome = org.nome if org else 'A minha Organização'

    if org and getattr(org, 'tipo_negocio', 'cliente') == 'espaco':
        return redirect(url_for('nova_pagina'))

    m = folium.Map(
        location=[41.545448, -8.426507],
        zoom_start=10,
        zoom_control=False,
        tiles=f'https://api.mapbox.com/styles/v1/mapbox/streets-v12/tiles/{{z}}/{{x}}/{{y}}?access_token={MAPBOX_TOKEN}',
        attr='© <a href="https://www.mapbox.com/">Mapbox</a>'
    )

    Fullscreen(position='bottomright').add_to(m)
    Geocoder(position='topright').add_to(m)
    TagFilterButton(['Em dia', 'Atenção', 'Urgente'], name='Filtrar').add_to(m)

    registos = db.session.query(Registo).filter(
        Registo.org_id == current_user.org_id,
        Registo.latitude.isnot(None),
        Registo.longitude.isnot(None)
    ).all()

    sidebar_items = []
    current_date = datetime.now().date()

    for r in registos:
        def parse_date(d):
            try:
                return datetime.strptime(d, '%d/%m/%Y')
            except:
                return datetime.min

        servicos_ordenados = sorted(
            [s for s in r.servicos if s.data_servico],
            key=lambda s: parse_date(s.data_servico),
            reverse=True
        )
        ultimo = servicos_ordenados[0] if servicos_ordenados else None

        data_ref = (ultimo.data_servico if ultimo else r.data_instalacao) or ''
        next_maintenance_display = (ultimo.proxima_manutencao if ultimo else r.proxima_manutencao) or 'N/A'
        tipo_display = (ultimo.tipo_servico if ultimo else r.tipo_servico) or '—'
        marca_display = (ultimo.marca if ultimo else r.marca) or 'N/A'
        num_maq_display = (ultimo.num_maquinas if ultimo else r.num_maquinas) or 'N/A'

        months_passed = 0
        if data_ref:
            try:
                ref_date = datetime.strptime(data_ref, '%d/%m/%Y').date()
                months_passed = (current_date.year - ref_date.year) * 12 + (current_date.month - ref_date.month)
            except:
                pass

        if months_passed <= 8:
            color = '#4a6fa5'; filter_value = 'Em dia'; status_label = 'Em dia'
        elif 8 < months_passed <= 10:
            color = '#c47c2b'; filter_value = 'Atenção'; status_label = 'Atenção'
        else:
            color = '#a33b3b'; filter_value = 'Urgente'; status_label = 'Urgente'

        num_servicos = len(r.servicos)
        historico_html = ''
        for s in servicos_ordenados[:3]:
            historico_html += f'''
            <div style="display:flex;justify-content:space-between;align-items:center;padding:5px 0;border-bottom:1px solid #f0f0f0;">
                <span style="font-size:11px;color:#555;">{s.tipo_servico or '—'}</span>
                <span style="font-size:11px;color:#888;">{s.data_servico or '—'}</span>
            </div>'''

        popup_html = f"""
        <div style="font-family:'Segoe UI',Arial,sans-serif;width:300px;border-radius:10px;overflow:hidden;box-shadow:0 4px 16px rgba(0,0,0,0.15);">
            <div style="background:{color};padding:14px 18px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="color:white;font-size:15px;font-weight:600;letter-spacing:0.2px;">{r.nome}</span>
                    <span style="background:rgba(255,255,255,0.2);color:white;font-size:10px;font-weight:600;padding:3px 10px;border-radius:20px;letter-spacing:0.5px;text-transform:uppercase;">{status_label}</span>
                </div>
                <div style="color:rgba(255,255,255,0.7);font-size:11px;margin-top:4px;letter-spacing:0.3px;">{tipo_display}</div>
            </div>
            <div style="background:white;padding:14px 18px;">
                <table style="width:100%;border-collapse:collapse;font-size:12px;">
                    <tr><td style="color:#888;padding:4px 0;width:40%;">Contacto</td><td style="color:#222;font-weight:500;">{r.contacto or 'N/A'}</td></tr>
                    <tr><td style="color:#888;padding:4px 0;">Marca</td><td style="color:#222;font-weight:500;">{marca_display}</td></tr>
                    <tr><td style="color:#888;padding:4px 0;">Nº Máquinas</td><td style="color:#222;font-weight:500;">{num_maq_display}</td></tr>
                    <tr><td style="color:#888;padding:4px 0;">Último serviço</td><td style="color:#222;font-weight:500;">{data_ref or 'N/A'}</td></tr>
                    <tr><td style="color:#888;padding:4px 0;">Próx. manutenção</td><td style="color:{color};font-weight:600;">{next_maintenance_display}</td></tr>
                </table>
                {f'<div style="margin-top:10px;padding-top:10px;border-top:1px solid #f0f0f0;"><div style="font-size:10px;color:#aaa;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">Histórico ({num_servicos} serviços)</div>{historico_html}</div>' if num_servicos > 0 else ''}
                <div style="margin-top:12px;">
                    <a href="tel:{r.contacto}" style="display:block;text-align:center;background:{color};color:white;padding:9px;border-radius:6px;text-decoration:none;font-size:12px;font-weight:600;letter-spacing:0.3px;">Ligar</a>
                </div>
            </div>
        </div>"""

        svg_icon = f"""
        <div style="position:relative;width:32px;height:42px;">
            <svg xmlns="http://www.w3.org/2000/svg" width="32" height="42" viewBox="0 0 32 42">
                <path d="M16 0 C7.163 0 0 7.163 0 16 C0 28 16 42 16 42 C16 42 32 28 32 16 C32 7.163 24.837 0 16 0 Z"
                      fill="{color}" stroke="rgba(255,255,255,0.4)" stroke-width="1.5"/>
                <circle cx="16" cy="16" r="5" fill="white" opacity="0.9"/>
            </svg>
        </div>"""

        icon = folium.DivIcon(html=svg_icon, icon_size=(32, 42), icon_anchor=(16, 42), popup_anchor=(0, -42))
        folium.Marker(
            location=[r.latitude, r.longitude],
            popup=folium.Popup(popup_html, max_width=320),
            icon=icon, tags=[filter_value]
        ).add_to(m)

        sidebar_items.append({
            'cliente': r.nome, 'status': status_label, 'dot_color': color,
            'next_maintenance': next_maintenance_display,
            'lat': r.latitude, 'lng': r.longitude, 'months': months_passed
        })

    sidebar_items.sort(key=lambda x: x['months'], reverse=True)

    sidebar_html_items = ''
    for item in sidebar_items:
        sidebar_html_items += f"""
        <div class="sidebar-item" onclick="flyTo({item['lat']}, {item['lng']})"
             style="border-left: 4px solid {item['dot_color']};">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <strong style="font-size:13px;">{item['cliente']}</strong>
                <span style="font-size:11px;color:{item['dot_color']};font-weight:600;">{item['status']}</span>
            </div>
            <div style="font-size:12px;color:#666;margin-top:3px;">Próx. manutenção: {item['next_maintenance']}</div>
        </div>"""

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
                    div.style.cssText = 'background:white;padding:12px 16px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.12);font-size:12px;font-family:Segoe UI,Arial,sans-serif;';
                    div.innerHTML =
                        '<div style="font-weight:600;margin-bottom:8px;font-size:12px;color:#333;letter-spacing:0.3px;text-transform:uppercase;">Estado</div>' +
                        '<div style="display:flex;align-items:center;gap:8px;margin:5px 0;"><div style="width:10px;height:10px;border-radius:50%;background:#4a6fa5;flex-shrink:0;"></div><span style="color:#555;">Em dia (&lt; 8 meses)</span></div>' +
                        '<div style="display:flex;align-items:center;gap:8px;margin:5px 0;"><div style="width:10px;height:10px;border-radius:50%;background:#c47c2b;flex-shrink:0;"></div><span style="color:#555;">Atenção (8–10 meses)</span></div>' +
                        '<div style="display:flex;align-items:center;gap:8px;margin:5px 0;"><div style="width:10px;height:10px;border-radius:50%;background:#a33b3b;flex-shrink:0;"></div><span style="color:#555;">Urgente (&gt; 10 meses)</span></div>';
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
    </script>"""

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
                <title>{{ org_nome }} - Mapa de Serviços Executados</title>
                <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
                {{ header|safe }}
                <style>
                    * { box-sizing: border-box; margin: 0; padding: 0; }
                    html, body { height: 100%; font-family: 'DM Sans', sans-serif !important; background-color: #f0f2f5; display: flex; flex-direction: column; overflow: hidden; }
                    .page-header { background: linear-gradient(135deg, #2e7d32, #4CAF50) !important; padding: 18px 24px !important; display: flex !important; align-items: center !important; justify-content: space-between !important; flex-shrink: 0 !important; box-shadow: 0 2px 8px rgba(0,0,0,0.2) !important; font-family: 'DM Sans', sans-serif !important; }
                    .page-header .subtitle { all: unset; display: block; font-size: 0.8em; color: rgba(255,255,255,0.75); font-family: 'DM Sans', sans-serif; }
                    .page-header h1 { all: unset; display: block; font-size: 1.4em; color: white; font-weight: 700; letter-spacing: 0.3px; margin-top: 3px; font-family: 'DM Sans', sans-serif; }
                    .header-actions { display: flex !important; align-items: center !important; gap: 10px !important; margin-left: auto !important; }
                    .header-actions a { all: unset; padding: 9px 20px; background: white; color: #2e7d32; text-decoration: none; border-radius: 6px; font-size: 0.9em; font-weight: 600; white-space: nowrap; box-shadow: 0 1px 4px rgba(0,0,0,0.15); transition: background 0.2s; cursor: pointer; font-family: 'DM Sans', sans-serif; display: inline-block; }
                    .header-actions a:hover { background: #f0f0f0; color: #2e7d32; text-decoration: none; }
                    .header-actions a.user-pill { all: unset; padding: 9px 16px; background: rgba(255,255,255,0.15); color: white; border: 1px solid rgba(255,255,255,0.3); border-radius: 6px; font-size: 0.85em; font-weight: 500; white-space: nowrap; cursor: pointer; font-family: 'DM Sans', sans-serif; display: flex; align-items: center; gap: 8px; box-shadow: none; text-decoration: none; }
                    .header-actions a.user-pill:hover { background: rgba(255,255,255,0.25); color: white; text-decoration: none; }
                    .main-content { display: flex; flex: 1; min-height: 0; gap: 10px; padding: 10px; overflow: hidden; }
                    .sidebar { width: 260px; flex-shrink: 0; background: white; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); display: flex; flex-direction: column; overflow: hidden; }
                    .sidebar-header { background: #2e7d32; color: white; padding: 12px 16px; font-size: 14px; font-weight: 600; flex-shrink: 0; font-family: 'DM Sans', sans-serif; }
                    .sidebar-search { padding: 8px 10px; border-bottom: 1px solid #eee; flex-shrink: 0; }
                    .sidebar-search input { width: 100%; padding: 6px 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px; outline: none; font-family: 'DM Sans', sans-serif; }
                    .sidebar-list { overflow-y: auto; flex: 1; }
                    .sidebar-item { padding: 10px 14px; border-bottom: 1px solid #f0f0f0; cursor: pointer; transition: background 0.15s; }
                    .sidebar-item:hover { background-color: #f8f8f8; }
                    .map-container { flex: 1; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); overflow: hidden; min-width: 0; position: relative; }
                    .map-container > div { position: absolute !important; top: 0 !important; left: 0 !important; width: 100% !important; height: 100% !important; }
                    .folium-map { width: 100% !important; height: 100% !important; }
                    footer { flex-shrink: 0; text-align: center; padding: 7px; background: #2e7d32; color: rgba(255,255,255,0.8); font-size: 12px; font-family: 'DM Sans', sans-serif; }
                    @media only screen and (max-width: 767px) { .sidebar { display: none; } .main-content { padding: 6px; } .page-header h1 { font-size: 1em !important; } }
                </style>
            </head>
            <body>
                <div class="page-header">
                    <div>
                        <div class="subtitle">Gestão de Serviços</div>
                        <h1>{{ org_nome }} — Mapa de Serviços Executados</h1>
                    </div>
                    <div class="header-actions">
                        <a href="/test">+ Registo</a>
                        <a href="/perfil" class="user-pill">👤 {{ current_user.nome }}</a>
                    </div>
                </div>
                <div class="main-content">
                    <div class="sidebar">
                        <div class="sidebar-header">Clientes ({{ total }})</div>
                        <div class="sidebar-search">
                            <input type="text" id="sidebarSearch" placeholder="Pesquisar cliente..." oninput="filterSidebar(this.value)">
                        </div>
                        <div class="sidebar-list" id="sidebarList">{{ sidebar_html|safe }}</div>
                    </div>
                    <div class="map-container">{{ body_html|safe }}</div>
                </div>
                <footer>&copy; {{ org_nome }}</footer>
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
    """, header=header, body_html=body_html, script=script,
         sidebar_html=sidebar_html_items, total=len(sidebar_items),
         current_user=current_user, org_nome=org_nome)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html', error=False)
    nome = request.form.get('nomeForm', '').strip()
    senha = request.form.get('senhaForm', '').strip()
    if not nome or not senha:
        return render_template('login.html', error=True)
    user = db.session.query(Usuario).filter_by(nome=nome, senha=hash(senha)).first()
    if not user:
        return render_template('login.html', error=True)
    login_user(user)
    return redirect(url_for('home'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if request.method == 'POST':
        if request.form.get('step') == 'verify':
            code_input = request.form.get('codigo', '').strip()
            if code_input == flask_session.get('setup_code'):
                flask_session.pop('setup_code', None)
                return redirect(url_for('home'))
            else:
                return render_template('setup.html', error=False, show_popup=True, code_error=True)

        nome = request.form.get('nomeForm')
        senha = request.form.get('senhaForm')
        email = request.form.get('email')
        telefone = request.form.get('telefone')
        nome_completo = request.form.get('nome_completo')
        cargo = request.form.get('cargo')
        org_nome = request.form.get('org_nome')
        pais = request.form.get('pais')
        org_telefone = request.form.get('org_telefone')
        tipo_negocio = request.form.get('tipo_negocio', 'cliente')

        if nome and senha:
            if db.session.query(Usuario).filter_by(nome=nome).first():
                return render_template('setup.html', error=True, show_popup=False)

            try:
                resp = requests.get('http://www.randomnumberapi.com/api/v1.0/random?min=100000&max=999999&count=1', timeout=5)
                code = str(resp.json()[0])
            except:
                import random
                code = str(random.randint(100000, 999999))

            org = Organizacao(nome=org_nome, pais=pais, telefone=org_telefone,
                              created_at=datetime.now().strftime('%d/%m/%Y'),
                              tipo_negocio=tipo_negocio)
            db.session.add(org)
            db.session.flush()
            admin = Usuario(nome=nome, senha=hash(senha), email=email, telefone=telefone,
                            nome_completo=nome_completo, cargo=cargo, is_admin=True, org_id=org.id)
            db.session.add(admin)
            db.session.commit()

            tipos_default = ['Instalação AC', 'Limpeza / Manutenção AC']
            for t in tipos_default:
                db.session.add(TipoServico(nome=t, org_id=org.id))
            db.session.commit()

            login_user(admin)
            flask_session['setup_code'] = code

            if email:
                try:
                    send_welcome_email(
                        to_email=email,
                        nome=nome_completo or nome,
                        org_nome=org_nome or 'A minha Organização',
                        username=nome,
                        password_temp=senha,
                        codigo=code
                    )
                except Exception as e:
                    print(f'Erro email setup: {e}')

            return render_template('setup.html', error=False, show_popup=True, code_error=False)

    return render_template('setup.html', error=False, show_popup=False)


@app.route('/registrar', methods=['GET', 'POST'])
@login_required
def registrar():
    if not current_user.is_admin:
        return jsonify({'ok': False, 'error': 'Sem permissão'})
    if request.method == 'GET':
        return redirect(url_for('perfil'))
    data = request.get_json()
    nome = data.get('nomeForm', '').strip()
    senha = data.get('senhaForm', '').strip()
    email = data.get('emailForm', '').strip()
    telefone = data.get('telefoneForm', '').strip()
    is_admin_user = data.get('is_admin', False)

    if not nome or not senha:
        return jsonify({'ok': False, 'error': 'Nome e password são obrigatórios'})

    if db.session.query(Usuario).filter_by(nome=nome).first():
        return jsonify({'ok': False, 'error': 'Este nome de utilizador já existe'})

    novo_usuario = Usuario(nome=nome, senha=hash(senha), is_admin=is_admin_user,
                           email=email, telefone=telefone, org_id=current_user.org_id)
    db.session.add(novo_usuario)
    db.session.commit()

    if email:
        try:
            org = db.session.query(Organizacao).filter_by(id=current_user.org_id).first()
            send_welcome_email(
                to_email=email,
                nome=nome,
                org_nome=org.nome if org else 'A minha Organização',
                username=nome,
                password_temp=senha,
                criado_por=current_user.nome_completo or current_user.nome
            )
        except Exception as e:
            print(f'Erro email registar: {e}')

    return jsonify({
        'ok': True,
        'id': novo_usuario.id,
        'nome': novo_usuario.nome,
        'email': email or '—',
        'telefone': telefone or '—',
        'is_admin': is_admin_user
    })


@app.route('/delete_user/<int:id>', methods=['POST'])
@login_required
def delete_user(id):
    if not current_user.is_admin:
        return jsonify({'ok': False})
    user = db.session.query(Usuario).filter_by(id=id, org_id=current_user.org_id).first()
    if user and user.id != current_user.id:
        db.session.delete(user)
        db.session.commit()
        return jsonify({'ok': True})
    return jsonify({'ok': False})


@app.route('/toggle_admin/<int:id>', methods=['POST'])
@login_required
def toggle_admin(id):
    if not current_user.is_admin:
        return jsonify({'ok': False})
    u = db.session.query(Usuario).filter_by(id=id, org_id=current_user.org_id).first()
    if u and u.id != current_user.id:
        u.is_admin = not u.is_admin
        db.session.commit()
        return jsonify({'ok': True, 'is_admin': u.is_admin})
    return jsonify({'ok': False})


@app.route('/perfil')
@login_required
def perfil():
    is_admin = current_user.is_admin
    todos_usuarios = db.session.query(Usuario).filter_by(org_id=current_user.org_id).all() if is_admin else []
    registos = db.session.query(Registo).filter_by(org_id=current_user.org_id).all() if is_admin else []
    servicos = db.session.query(Servico).filter_by(org_id=current_user.org_id).all() if is_admin else []
    registos_json = json.dumps([{
        'data_instalacao': r.data_instalacao,
        'valor_pago': r.valor_pago,
        'morada': r.morada or ''
    } for r in registos])
    servicos_json = json.dumps([{
        'data_servico': s.data_servico,
        'tipo_servico': s.tipo_servico or '',
        'valor_pago': s.valor_pago or 0,
        'marca': s.marca or '',
        'num_maquinas': s.num_maquinas or 0
    } for s in servicos])
    org = db.session.query(Organizacao).filter_by(id=current_user.org_id).first()
    tipos_servico = db.session.query(TipoServico).filter_by(org_id=current_user.org_id).all() if is_admin else []

    total_clientes = len(registos)
    total_servicos = len(servicos)
    receita_total = sum(s.valor_pago or 0 for s in servicos)
    media_maquinas = round(sum(s.num_maquinas or 0 for s in servicos) / total_servicos, 1) if total_servicos else 0

    from datetime import datetime as dt
    now = dt.now()
    urgentes = 0
    atencao = 0
    em_dia = 0
    for r in registos:
        svcs = sorted([s for s in r.servicos if s.data_servico], key=lambda x: x.data_servico, reverse=True)
        if svcs:
            try:
                d = dt.strptime(svcs[0].data_servico, '%d/%m/%Y')
                months = (now.year - d.year) * 12 + (now.month - d.month)
                if months > 10: urgentes += 1
                elif months > 8: atencao += 1
                else: em_dia += 1
            except:
                pass

    return render_template('perfil.html', user=current_user, usuarios=todos_usuarios,
                           registos=registos, registos_json=registos_json, servicos_json=servicos_json,
                           is_admin=is_admin, org=org, tipos_servico=tipos_servico,
                           total_clientes=total_clientes, total_servicos=total_servicos,
                           receita_total=receita_total, media_maquinas=media_maquinas,
                           urgentes=urgentes, atencao=atencao, em_dia=em_dia)


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
    is_admin = current_user.is_admin
    if request.method == 'POST':
        nome = request.form.get('nome')
        contacto = request.form.get('contacto')
        num_maquinas = request.form.get('num_maquinas')
        tipo_servico = request.form.get('tipo_servico')
        marca = request.form.get('marca')
        data_instalacao = request.form.get('data_instalacao')
        morada = request.form.get('morada')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        valor_pago = request.form.get('valor_pago') if is_admin else None
        if nome:
            novo_registo = Registo(
                org_id=current_user.org_id, nome=nome, contacto=contacto,
                morada=morada,
                latitude=float(latitude) if latitude else None,
                longitude=float(longitude) if longitude else None,
            )
            db.session.add(novo_registo)
            db.session.flush()

            _ds2 = converter_data(data_instalacao)
            _prox2 = None
            if _ds2:
                try:
                    _d2 = datetime.strptime(_ds2, '%d/%m/%Y')
                    _prox2 = _d2.replace(year=_d2.year + 1).strftime('%d/%m/%Y')
                except:
                    pass
            _dur2 = request.form.get('duracao_horas')
            primeiro_servico = Servico(
                registo_id=novo_registo.id,
                org_id=current_user.org_id,
                tipo_servico=tipo_servico,
                data_servico=_ds2,
                proxima_manutencao=_prox2,
                num_maquinas=int(num_maquinas) if num_maquinas else None,
                marca=marca,
                valor_pago=float(valor_pago) if valor_pago else None,
                duracao_horas=float(_dur2) if _dur2 else None
            )
            db.session.add(primeiro_servico)
            db.session.commit()

    page = request.args.get('page', 1, type=int)
    per_page = 25
    base_query = db.session.query(Registo).filter_by(org_id=current_user.org_id)
    total_registos = base_query.count()
    total_pages = (total_registos + per_page - 1) // per_page
    registos = base_query.order_by(Registo.id.desc()).offset((page - 1) * per_page).limit(per_page).all()
    tipos_servico = db.session.query(TipoServico).filter_by(org_id=current_user.org_id).all()
    return render_template('test.html', registos=registos, current_user=current_user, is_admin=is_admin,
                           page=page, total_pages=total_pages, total_registos=total_registos,
                           tipos_servico=tipos_servico)


@app.route('/test/add_servico/<int:registo_id>', methods=['POST'])
@login_required
def add_servico(registo_id):
    r = db.session.query(Registo).filter_by(id=registo_id, org_id=current_user.org_id).first()
    if r:
        is_admin = current_user.is_admin
        _ds = converter_data(request.form.get('data_servico'))
        _prox = None
        if _ds:
            try:
                _d = datetime.strptime(_ds, '%d/%m/%Y')
                _prox = _d.replace(year=_d.year + 1).strftime('%d/%m/%Y')
            except:
                pass
        _dur = request.form.get('duracao_horas')
        novo = Servico(
            registo_id=r.id,
            org_id=current_user.org_id,
            tipo_servico=request.form.get('tipo_servico'),
            data_servico=_ds,
            proxima_manutencao=_prox,
            num_maquinas=int(request.form.get('num_maquinas')) if request.form.get('num_maquinas') else None,
            marca=request.form.get('marca'),
            valor_pago=float(request.form.get('valor_pago')) if request.form.get('valor_pago') and is_admin else None,
            notas=request.form.get('notas'),
            duracao_horas=float(_dur) if _dur else None
        )
        db.session.add(novo)
        db.session.commit()
    return redirect(url_for('nova_pagina', page=request.args.get('page', 1)))


@app.route('/test/edit/<int:id>', methods=['POST'])
@login_required
def edit_registo(id):
    r = db.session.query(Registo).filter_by(id=id, org_id=current_user.org_id).first()
    if r:
        r.nome = request.form.get('nome', r.nome)
        r.contacto = request.form.get('contacto', r.contacto)
        r.morada = request.form.get('morada', r.morada)
        lat = request.form.get('latitude')
        lon = request.form.get('longitude')
        r.latitude = float(lat) if lat else r.latitude
        r.longitude = float(lon) if lon else r.longitude
        db.session.commit()
    return redirect(url_for('nova_pagina', page=request.args.get('page', 1)))


@app.route('/test/delete/<int:id>', methods=['POST'])
@login_required
def delete_registo(id):
    registo = db.session.query(Registo).filter_by(id=id, org_id=current_user.org_id).first()
    if registo:
        db.session.delete(registo)
        db.session.commit()
    return redirect(url_for('nova_pagina'))


@app.route('/servico/delete/<int:id>', methods=['POST'])
@login_required
def delete_servico(id):
    s = db.session.query(Servico).filter_by(id=id, org_id=current_user.org_id).first()
    if s:
        db.session.delete(s)
        db.session.commit()
    return redirect(url_for('nova_pagina'))


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
            nova = Fatura(org_id=current_user.org_id, user_id=current_user.id,
                          local=local, valor=float(valor), data=data, nota=nota, ficheiro=ficheiro_path)
            db.session.add(nova)
            db.session.commit()
    if current_user.is_admin:
        todas = db.session.query(Fatura, Usuario).join(Usuario, Fatura.user_id == Usuario.id).filter(
            Fatura.org_id == current_user.org_id).order_by(Fatura.id.desc()).all()
    else:
        todas = db.session.query(Fatura, Usuario).join(Usuario, Fatura.user_id == Usuario.id).filter(
            Fatura.org_id == current_user.org_id, Fatura.user_id == current_user.id).order_by(Fatura.id.desc()).all()
    usuarios = db.session.query(Usuario).filter_by(org_id=current_user.org_id).all()
    total = sum(f.valor for f, u in todas)
    return render_template('faturas.html', faturas=todas, total=total, usuarios=usuarios)


@app.route('/faturas/delete/<int:id>', methods=['POST'])
@login_required
def delete_fatura(id):
    fatura = db.session.query(Fatura).filter_by(id=id, org_id=current_user.org_id).first()
    if fatura and (fatura.user_id == current_user.id or current_user.is_admin):
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
            try:
                from datetime import date, timedelta
                d1 = datetime.strptime(data_inicio, '%d/%m/%Y')
                d2 = datetime.strptime(data_fim, '%d/%m/%Y')
                year = d1.year
                feriados_pt = []
                for mes, dia in [(1,1),(4,25),(5,1),(6,10),(8,15),(10,5),(11,1),(12,1),(12,8),(12,25)]:
                    try: feriados_pt.append(date(year, mes, dia))
                    except: pass
                a=year%19; b=year//100; c=year%100
                d=b//4; e=b%4; f_=(b+8)//25
                g=(b-f_+1)//3; h=(19*a+b-d-g+15)%30
                i=c//4; k=c%4; l=(32+2*e+2*i-h-k)%7
                m_=(a+11*h+22*l)//451
                em=(h+l-7*m_+114)//31; ed=(h+l-7*m_+114)%31+1
                easter=date(year, em, ed)
                feriados_pt += [easter, easter-timedelta(days=2), easter+timedelta(days=60)]
                num_dias = 0
                cur = d1
                while cur <= d2:
                    if cur.weekday() < 5 and cur.date() not in feriados_pt:
                        num_dias += 1
                    cur += timedelta(days=1)
            except:
                num_dias = 0
            nova = Ferias(org_id=current_user.org_id, user_id=current_user.id,
                        data_inicio=data_inicio, data_fim=data_fim, nota=nota, num_dias=num_dias)
            db.session.add(nova)
            db.session.commit()
    is_admin = current_user.is_admin
    usuarios = db.session.query(Usuario).filter_by(org_id=current_user.org_id).all() if is_admin else []
    if is_admin:
        todos = db.session.query(Ferias, Usuario).join(Usuario, Ferias.user_id == Usuario.id).filter(
            Ferias.org_id == current_user.org_id).order_by(Ferias.id.desc()).all()
    else:
        todos = db.session.query(Ferias, Usuario).join(Usuario, Ferias.user_id == Usuario.id).filter(
            Ferias.org_id == current_user.org_id, Ferias.user_id == current_user.id).order_by(Ferias.id.desc()).all()
    ferias_json = json.dumps([{'user_nome': u.nome, 'estado': f.estado, 'data_inicio': f.data_inicio,
                               'data_fim': f.data_fim, 'num_dias': f.num_dias or 0} for f, u in todos])
    return render_template('ferias.html', ferias=todos, ferias_json=ferias_json, is_admin=is_admin,
                       usuarios=usuarios, current_user=current_user, now=datetime.now())


@app.route('/ferias/responder/<int:id>', methods=['POST'])
@login_required
def responder_ferias(id):
    if not current_user.is_admin:
        return redirect(url_for('ferias'))
    f = db.session.query(Ferias).filter_by(id=id, org_id=current_user.org_id).first()
    if f:
        estado = request.form.get('estado')
        comentario = request.form.get('comentario', '')
        f.estado = estado
        f.comentario_admin = comentario
        f.aprovado_por = current_user.nome
        db.session.commit()

        user = db.session.query(Usuario).filter_by(id=f.user_id).first()
        org = db.session.query(Organizacao).filter_by(id=current_user.org_id).first()
        if user and user.email:
            try:
                estado_label = 'aprovadas' if estado == 'aprovado' else 'recusadas'
                cor = '#2e7d32' if estado == 'aprovado' else '#c62828'
                bg = '#eaf3de' if estado == 'aprovado' else '#fef2f2'
                brd = '#c0dd97' if estado == 'aprovado' else '#fecaca'
                admin_nome = current_user.nome_completo or current_user.nome
                org_nome_str = org.nome if org else 'A minha Organização'
                acao = 'aprovou' if estado == 'aprovado' else 'recusou'
                comentario_block = ''
                if comentario:
                    comentario_block = (
                        '<div style="background:#f5f5f5;border-radius:8px;padding:12px 16px;margin-bottom:16px;">'
                        '<p style="font-size:12px;color:#888;margin:0 0 4px;">Comentário do administrador</p>'
                        f'<p style="font-size:14px;color:#333;margin:0;">{comentario}</p>'
                        '</div>'
                    )
                periodo = f'{f.data_inicio} a {f.data_fim} ({f.num_dias} dia(s))'
                html_ferias = (
                    '<div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;">'
                    f'<div style="background:{cor};padding:28px 32px;text-align:center;">'
                    '<p style="color:white;font-size:20px;font-weight:bold;margin:0 0 4px;">Pedido de Férias</p>'
                    f'<p style="color:rgba(255,255,255,0.8);font-size:13px;margin:0;">{org_nome_str}</p>'
                    '</div>'
                    '<div style="background:white;padding:28px 32px;">'
                    f'<p style="font-size:15px;color:#1a1a1a;margin:0 0 16px;">Olá <strong>{user.nome_completo or user.nome}</strong>,</p>'
                    f'<p style="font-size:14px;color:#555;margin:0 0 20px;">O seu administrador <strong>{admin_nome}</strong> {acao} o seu pedido de férias.</p>'
                    f'<div style="background:{bg};border:1px solid {brd};border-radius:8px;padding:16px 20px;margin-bottom:20px;">'
                    '<p style="font-size:12px;color:#888;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 8px;">Período</p>'
                    f'<p style="font-size:16px;font-weight:bold;color:{cor};margin:0;">{periodo}</p>'
                    '</div>'
                    f'{comentario_block}'
                    '<p style="font-size:13px;color:#888;margin:0;">Se tiver questões, contacte o seu administrador.</p>'
                    '</div>'
                    '<div style="background:#f8f8f8;border-top:1px solid #eee;padding:16px 32px;text-align:center;">'
                    f'<p style="font-size:12px;color:#aaa;margin:0;">© {org_nome_str} — Plataforma de Gestão</p>'
                    '</div>'
                    '</div>'
                )
                msg_ferias = MIMEMultipart('alternative')
                msg_ferias["Subject"] = f"As suas férias foram {estado_label}"
                msg_ferias["From"] = formataddr((str(Header("GestãoPro", "utf-8")), GMAIL_USER))
                msg_ferias["To"] = user.email
                msg_ferias.attach(MIMEText(html_ferias, 'html'))
                with smtplib.SMTP("smtp.gmail.com", 587) as conn:
                    conn.starttls()
                    conn.login(user=GMAIL_USER, password=GMAIL_PASS)
                    conn.send_message(msg_ferias)
            except Exception as e:
                print(f'Erro email ferias: {e}')

    return redirect(url_for('ferias'))


@app.route('/ferias/delete/<int:id>', methods=['POST'])
@login_required
def delete_ferias(id):
    f = db.session.query(Ferias).filter_by(id=id, org_id=current_user.org_id).first()
    if f and (f.user_id == current_user.id or current_user.is_admin):
        db.session.delete(f)
        db.session.commit()
    return redirect(url_for('ferias'))


@app.route('/orcamentos', methods=['GET', 'POST'])
@login_required
def orcamentos():
    is_admin = current_user.is_admin
    if request.method == 'POST':
        cliente = request.form.get('cliente')
        descricao = request.form.get('descricao')
        num_maquinas = request.form.get('num_maquinas', type=int)
        valor = request.form.get('valor', type=float)
        if cliente:
            novo = Orcamento(org_id=current_user.org_id, user_id=current_user.id, cliente=cliente,
                             descricao=descricao, num_maquinas=num_maquinas, valor=valor,
                             estado='Pendente', created_at=datetime.now().strftime('%d/%m/%Y'))
            db.session.add(novo)
            db.session.commit()
    if is_admin:
        todos = db.session.query(Orcamento, Usuario).join(Usuario, Orcamento.user_id == Usuario.id).filter(
            Orcamento.org_id == current_user.org_id).order_by(Orcamento.id.desc()).all()
    else:
        todos = db.session.query(Orcamento, Usuario).join(Usuario, Orcamento.user_id == Usuario.id).filter(
            Orcamento.org_id == current_user.org_id, Orcamento.user_id == current_user.id).order_by(Orcamento.id.desc()).all()
    return render_template('orcamentos.html', orcamentos=todos, is_admin=is_admin)


@app.route('/orcamentos/delete/<int:id>', methods=['POST'])
@login_required
def delete_orcamento(id):
    o = db.session.query(Orcamento).filter_by(id=id, org_id=current_user.org_id).first()
    if o and (o.user_id == current_user.id or current_user.is_admin):
        db.session.delete(o)
        db.session.commit()
    return redirect(url_for('orcamentos'))


@app.route('/orcamentos/estado/<int:id>', methods=['POST'])
@login_required
def update_estado_orcamento(id):
    if not current_user.is_admin:
        return redirect(url_for('orcamentos'))
    o = db.session.query(Orcamento).filter_by(id=id, org_id=current_user.org_id).first()
    if o:
        o.estado = request.form.get('estado')
        db.session.commit()
    return redirect(url_for('orcamentos'))


@app.route('/mensagens')
@login_required
def mensagens():
    is_admin = current_user.is_admin
    if is_admin:
        todas = db.session.query(Mensagem, Usuario).join(Usuario, Mensagem.user_id == Usuario.id).filter(
            Mensagem.org_id == current_user.org_id).order_by(Mensagem.id.desc()).all()
    else:
        todas = db.session.query(Mensagem, Usuario).join(Usuario, Mensagem.user_id == Usuario.id).filter(
            Mensagem.org_id == current_user.org_id, Mensagem.user_id == current_user.id).order_by(Mensagem.id.desc()).all()
    return render_template('mensagens.html', mensagens=todas, is_admin=is_admin)


@app.route('/horas', methods=['GET', 'POST'])
@login_required
def horas():
    mes = request.args.get('mes', datetime.now().month, type=int)
    ano = request.args.get('ano', datetime.now().year, type=int)
    is_admin = current_user.is_admin
    if is_admin:
        registos = db.session.query(HorasTrabalhadas).filter_by(
            org_id=current_user.org_id, mes=mes, ano=ano).order_by(HorasTrabalhadas.dia).all()
    else:
        registos = db.session.query(HorasTrabalhadas).filter_by(
            org_id=current_user.org_id, user_id=current_user.id, mes=mes, ano=ano).order_by(HorasTrabalhadas.dia).all()
    usuarios = db.session.query(Usuario).filter_by(org_id=current_user.org_id).all() if is_admin else []
    return render_template('horas.html', registos=registos, mes=mes, ano=ano, is_admin=is_admin,
                           usuarios=usuarios, current_user=current_user, today_dia=datetime.now().day)


@app.route('/horas/add', methods=['POST'])
@login_required
def horas_add():
    mes = request.form.get('mes', type=int)
    ano = request.form.get('ano', type=int)
    dia = request.form.get('dia', type=int)
    manha = request.form.get('manha', 0, type=float)
    tarde = request.form.get('tarde', 0, type=float)
    extra = request.form.get('extra', 0, type=float)
    observacoes = request.form.get('observacoes', '')
    local = request.form.get('local', '')
    novo = HorasTrabalhadas(org_id=current_user.org_id, user_id=current_user.id, user_nome=current_user.nome,
                            mes=mes, ano=ano, dia=dia, manha=manha, tarde=tarde, extra=extra,
                            total=manha + tarde + extra, observacoes=observacoes, local=local)
    db.session.add(novo)
    db.session.commit()
    return redirect(url_for('horas', mes=mes, ano=ano))


@app.route('/horas/edit/<int:id>', methods=['POST'])
@login_required
def horas_edit(id):
    registo = db.session.query(HorasTrabalhadas).filter_by(id=id, org_id=current_user.org_id).first()
    if registo and (registo.user_id == current_user.id or current_user.is_admin):
        registo.manha = request.form.get('manha', 0, type=float)
        registo.tarde = request.form.get('tarde', 0, type=float)
        registo.extra = request.form.get('extra', 0, type=float)
        registo.total = registo.manha + registo.tarde + registo.extra
        registo.observacoes = request.form.get('observacoes', '')
        registo.local = request.form.get('local', '')
        db.session.commit()
    return redirect(url_for('horas', mes=registo.mes, ano=registo.ano))


@app.route('/horas/delete/<int:id>', methods=['POST'])
@login_required
def horas_delete(id):
    registo = db.session.query(HorasTrabalhadas).filter_by(id=id, org_id=current_user.org_id).first()
    mes, ano = registo.mes, registo.ano
    if registo and (registo.user_id == current_user.id or current_user.is_admin):
        db.session.delete(registo)
        db.session.commit()
    return redirect(url_for('horas', mes=mes, ano=ano))


@app.route('/tipos_servico/add', methods=['POST'])
@login_required
def add_tipo_servico():
    if not current_user.is_admin:
        return jsonify({'ok': False})
    nome = request.get_json().get('nome', '').strip()
    if not nome:
        return jsonify({'ok': False, 'error': 'Nome vazio'})
    existing = db.session.query(TipoServico).filter_by(nome=nome, org_id=current_user.org_id).first()
    if existing:
        return jsonify({'ok': False, 'error': 'Já existe'})
    novo = TipoServico(nome=nome, org_id=current_user.org_id)
    db.session.add(novo)
    db.session.commit()
    return jsonify({'ok': True, 'id': novo.id, 'nome': novo.nome})


@app.route('/tipos_servico/delete/<int:id>', methods=['POST'])
@login_required
def delete_tipo_servico(id):
    if not current_user.is_admin:
        return jsonify({'ok': False})
    t = db.session.query(TipoServico).filter_by(id=id, org_id=current_user.org_id).first()
    if t:
        db.session.delete(t)
        db.session.commit()
    return jsonify({'ok': True})


@app.route('/tipos_servico/edit/<int:id>', methods=['POST'])
@login_required
def edit_tipo_servico(id):
    if not current_user.is_admin:
        return jsonify({'ok': False})
    t = db.session.query(TipoServico).filter_by(id=id, org_id=current_user.org_id).first()
    if not t:
        return jsonify({'ok': False})
    nome = request.get_json().get('nome', '').strip()
    if nome:
        t.nome = nome
        db.session.commit()
    return jsonify({'ok': True, 'nome': t.nome})


@app.route('/forgot_password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    email = data.get('email', '').strip()
    user = db.session.query(Usuario).filter_by(email=email).first()
    if not user:
        return jsonify({'ok': False, 'error': 'Email não encontrado.'})

    try:
        resp = requests.get('http://www.randomnumberapi.com/api/v1.0/random?min=100000&max=999999&count=1', timeout=5)
        code = str(resp.json()[0])
    except:
        import random
        code = str(random.randint(100000, 999999))

    flask_session['reset_code'] = code
    flask_session['reset_user_id'] = user.id

    try:
        msg = MIMEMultipart('alternative')
        msg["Subject"] = "Recuperação de password"
        msg["From"] = formataddr((str(Header("GestãoPro", "utf-8")), GMAIL_USER))
        msg["To"] = email
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;">
            <div style="background:#2e7d32;padding:28px 32px;text-align:center;">
                <p style="color:white;font-size:20px;font-weight:bold;margin:0;">Recuperação de Password</p>
            </div>
            <div style="background:white;padding:28px 32px;">
                <p style="font-size:15px;color:#1a1a1a;margin:0 0 16px;">Olá {user.nome},</p>
                <p style="font-size:14px;color:#555;margin:0 0 20px;">Recebemos um pedido para redefinir a tua password. Usa o código abaixo:</p>
                <div style="background:#e8f0fe;border:1px solid #b3c6f7;border-radius:8px;padding:24px;text-align:center;margin-bottom:20px;">
                    <p style="font-size:11px;color:#3c5a99;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 8px;">Código de verificação</p>
                    <p style="font-size:36px;font-weight:bold;color:#1a3a8f;margin:0;letter-spacing:10px;">{code}</p>
                </div>
                <p style="font-size:13px;color:#888;margin:0;">Se não pediste esta alteração, ignora este email.</p>
            </div>
            <div style="background:#f8f8f8;border-top:1px solid #eee;padding:16px 32px;text-align:center;">
                <p style="font-size:12px;color:#aaa;margin:0;">Plataforma de Gestão de Serviços</p>
            </div>
        </div>
        """
        msg.attach(MIMEText(html, 'html'))
        with smtplib.SMTP("smtp.gmail.com", 587) as connection:
            connection.starttls()
            connection.login(user=GMAIL_USER, password=GMAIL_PASS)
            connection.send_message(msg)
    except Exception as e:
        print(f'Erro email reset: {e}')

    return jsonify({'ok': True})


@app.route('/reset_password', methods=['POST'])
def reset_password():
    data = request.get_json()
    code = data.get('code', '').strip()
    new_password = data.get('password', '')

    if code != flask_session.get('reset_code'):
        return jsonify({'ok': False, 'error': 'Código incorreto. Tenta novamente.'})

    user_id = flask_session.get('reset_user_id')
    user = db.session.query(Usuario).filter_by(id=user_id).first()
    if not user:
        return jsonify({'ok': False, 'error': 'Utilizador não encontrado.'})

    user.senha = hash(new_password)
    db.session.commit()
    flask_session.pop('reset_code', None)
    flask_session.pop('reset_user_id', None)

    return jsonify({'ok': True})


def criar_admin():
    with app.app_context():
        db.create_all()

        try:
            with db.engine.connect() as conn:
                conn.execute(db.text("ALTER TABLE organizacao ADD COLUMN tipo_negocio VARCHAR(20) DEFAULT 'cliente'"))
                conn.commit()
        except:
            pass

        try:
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE servicos ADD COLUMN duracao_horas FLOAT'))
                conn.commit()
        except:
            pass

        try:
            registos_sem_servico = db.session.query(Registo).filter(
                ~Registo.servicos.any()
            ).all()
            for r in registos_sem_servico:
                if r.data_instalacao or r.tipo_servico:
                    s = Servico(
                        registo_id=r.id,
                        org_id=r.org_id,
                        tipo_servico=r.tipo_servico or 'Instalação AC',
                        data_servico=r.data_instalacao,
                        proxima_manutencao=r.proxima_manutencao,
                        num_maquinas=r.num_maquinas,
                        marca=r.marca,
                        valor_pago=r.valor_pago
                    )
                    db.session.add(s)
            db.session.commit()
        except Exception as e:
            print(f'Migração: {e}')
            db.session.rollback()


if __name__ == "__main__":
    criar_admin()
    app.run(host="0.0.0.0", port=3000, debug=False)