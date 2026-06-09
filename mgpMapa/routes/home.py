import os
from datetime import datetime

import folium
from flask import Blueprint, redirect, render_template_string, url_for
from flask_login import current_user, login_required
from folium.plugins import Fullscreen, Geocoder, TagFilterButton
from sqlalchemy.orm import joinedload

from db import db
from models import Organizacao, Registo

home_bp = Blueprint('home', __name__)

MAPBOX_TOKEN = os.getenv('MAPBOX_TOKEN', '')


@home_bp.route('/')
@login_required
def home():
    org = db.session.query(Organizacao).filter_by(id=current_user.org_id).first()
    org_nome = org.nome if org else 'A minha Organização'

    if org and getattr(org, 'tipo_negocio', 'cliente') == 'espaco':
        return redirect(url_for('obras.marcacoes'))

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
    ).options(joinedload(Registo.servicos)).all()

    sidebar_items = []
    current_date = datetime.now().date()

    for r in registos:
        def parse_date(d):
            try:
                return datetime.strptime(d, '%d/%m/%Y')
            except Exception:
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
            except Exception:
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
                    <span style="color:white;font-size:15px;font-weight:600;">{r.nome}</span>
                    <span style="background:rgba(255,255,255,0.2);color:white;font-size:10px;font-weight:600;padding:3px 10px;border-radius:20px;text-transform:uppercase;">{status_label}</span>
                </div>
                <div style="color:rgba(255,255,255,0.7);font-size:11px;margin-top:4px;">{tipo_display}</div>
            </div>
            <div style="background:white;padding:14px 18px;">
                <table style="width:100%;border-collapse:collapse;font-size:12px;">
                    <tr><td style="color:#888;padding:4px 0;width:40%;">Contacto</td><td style="color:#222;font-weight:500;">{r.contacto or 'N/A'}</td></tr>
                    <tr><td style="color:#888;padding:4px 0;">Marca</td><td style="color:#222;font-weight:500;">{marca_display}</td></tr>
                    <tr><td style="color:#888;padding:4px 0;">Nº Máquinas</td><td style="color:#222;font-weight:500;">{num_maq_display}</td></tr>
                    <tr><td style="color:#888;padding:4px 0;">Último serviço</td><td style="color:#222;font-weight:500;">{data_ref or 'N/A'}</td></tr>
                    <tr><td style="color:#888;padding:4px 0;">Próx. manutenção</td><td style="color:{color};font-weight:600;">{next_maintenance_display}</td></tr>
                </table>
                {f'<div style="margin-top:10px;padding-top:10px;border-top:1px solid #f0f0f0;"><div style="font-size:10px;color:#aaa;text-transform:uppercase;margin-bottom:6px;">Histórico ({num_servicos} serviços)</div>{historico_html}</div>' if num_servicos > 0 else ''}
                <div style="margin-top:12px;">
                    <a href="tel:{r.contacto}" style="display:block;text-align:center;background:{color};color:white;padding:9px;border-radius:6px;text-decoration:none;font-size:12px;font-weight:600;">Ligar</a>
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
                    div.style.cssText = 'background:white;padding:12px 16px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.12);font-size:12px;';
                    div.innerHTML =
                        '<div style="font-weight:600;margin-bottom:8px;font-size:12px;color:#333;text-transform:uppercase;">Estado</div>' +
                        '<div style="display:flex;align-items:center;gap:8px;margin:5px 0;"><div style="width:10px;height:10px;border-radius:50%;background:#4a6fa5;"></div><span style="color:#555;">Em dia (&lt; 8 meses)</span></div>' +
                        '<div style="display:flex;align-items:center;gap:8px;margin:5px 0;"><div style="width:10px;height:10px;border-radius:50%;background:#c47c2b;"></div><span style="color:#555;">Atenção (8–10 meses)</span></div>' +
                        '<div style="display:flex;align-items:center;gap:8px;margin:5px 0;"><div style="width:10px;height:10px;border-radius:50%;background:#a33b3b;"></div><span style="color:#555;">Urgente (&gt; 10 meses)</span></div>';
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
                <title>{{ org_nome }} - Mapa de Serviços</title>
                <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
                {{ header|safe }}
                <style>
                    * { box-sizing: border-box; margin: 0; padding: 0; }
                    html, body { height: 100%; font-family: 'DM Sans', sans-serif !important; background-color: #f0f2f5; display: flex; flex-direction: column; overflow: hidden; }
                    .page-header { background: linear-gradient(135deg, #2d3a6e, #4a5fa8) !important; padding: 14px 24px !important; display: flex !important; align-items: center !important; justify-content: space-between !important; flex-shrink: 0 !important; box-shadow: 0 2px 8px rgba(0,0,0,0.2) !important; font-family: 'DM Sans', sans-serif !important; }
                    .page-header .subtitle { all: unset; display: block; font-size: 0.8em; color: rgba(255,255,255,0.75); font-family: 'DM Sans', sans-serif; }
                    .page-header h1 { all: unset; display: block; font-size: 1.4em; color: white; font-weight: 700; letter-spacing: 0.3px; margin-top: 3px; font-family: 'DM Sans', sans-serif; }
                    .main-content { display: flex; flex: 1; min-height: 0; gap: 10px; padding: 10px; overflow: hidden; }
                    .sidebar { width: 260px; flex-shrink: 0; background: white; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); display: flex; flex-direction: column; overflow: hidden; }
                    .sidebar-header { background: #2d3a6e; color: white; padding: 12px 16px; font-size: 14px; font-weight: 600; flex-shrink: 0; }
                    .sidebar-search { padding: 8px 10px; border-bottom: 1px solid #eee; flex-shrink: 0; }
                    .sidebar-search input { width: 100%; padding: 6px 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px; outline: none; }
                    .sidebar-list { overflow-y: auto; flex: 1; }
                    .sidebar-item { padding: 10px 14px; border-bottom: 1px solid #f0f0f0; cursor: pointer; transition: background 0.15s; }
                    .sidebar-item:hover { background-color: #f8f8f8; }
                    .map-container { flex: 1; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); overflow: hidden; min-width: 0; position: relative; }
                    .map-container > div { position: absolute !important; top: 0 !important; left: 0 !important; width: 100% !important; height: 100% !important; }
                    .folium-map { width: 100% !important; height: 100% !important; }
                    footer { flex-shrink: 0; text-align: center; padding: 7px; background: #2d3a6e; color: rgba(255,255,255,0.8); font-size: 12px; }
                    @media only screen and (max-width: 767px) { .sidebar { display: none; } .main-content { padding: 6px; } .page-header h1 { font-size: 1em !important; } }
                </style>
            </head>
            <body>
                <div class="page-header">
                    <div style="display:flex;align-items:center;gap:12px;">
                        <img src="/static/icons/logo-dark.png" alt="Logo" style="height:40px;width:40px;object-fit:contain;filter:brightness(0) invert(1);">
                        <div>
                            <div class="subtitle">{{ org_nome }}</div>
                            <h1>Mapa de Serviços</h1>
                        </div>
                    </div>
                    <div style="display:flex;align-items:center;gap:10px;margin-left:auto;">
                        <a href="/registos" style="padding:9px 20px;background:white;color:#2d3a6e;text-decoration:none;border-radius:6px;font-size:14px;font-weight:600;box-shadow:0 1px 4px rgba(0,0,0,0.15);white-space:nowrap;">Registos</a>
                        <a href="/perfil" style="padding:9px 16px;background:rgba(255,255,255,0.15);color:white;text-decoration:none;border-radius:6px;font-size:14px;font-weight:600;border:1px solid rgba(255,255,255,0.3);white-space:nowrap;">{{ current_user.nome }}</a>
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
                <footer>&copy; GestãoPro</footer>
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