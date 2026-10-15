import streamlit as st
import requests
import math
import folium
from streamlit_folium import st_folium

st.set_page_config(layout="wide", page_title="Consulta Viento CTE DB SE-AE")

st.title("🌪️ Calculadora de Carga de Viento (CTE DB SE-AE)")
st.caption("Auto-geolocalización de Zona Eólica mediante OpenStreetMap y topografía SRTM/Open-Meteo.")

# --- CONSTANTES CTE ---
ZONAS_CTE = {
    'C': ['Coruña', 'Cádiz', 'Cantabria', 'Huelva', 'Illes Balears', 'Baleares', 'Las Palmas', 'Lugo', 'Ourense', 'Orense', 'Pontevedra', 'Santa Cruz de Tenerife', 'Tenerife', 'Tarragona', 'Galicia', 'Canarias'],
    'B': ['Alicante', 'Almería', 'Barcelona', 'Castellón', 'Girona', 'Gerona', 'Málaga', 'Murcia', 'Valencia', 'Comunidad Valenciana', 'Andalucía']
}

PARAMS_ENTORNO = {
    'I':   {'k': 0.156, 'L': 0.003, 'Z': 1, 'desc': 'I - Borde del mar, lagos'},
    'II':  {'k': 0.170, 'L': 0.010, 'Z': 1, 'desc': 'II - Terreno llano sin obstáculos'},
    'III': {'k': 0.190, 'L': 0.050, 'Z': 2, 'desc': 'III - Zona rural con obstáculos aislados'},
    'IV':  {'k': 0.220, 'L': 0.300, 'Z': 5, 'desc': 'IV - Zona urbana, industrial o forestal'},
    'V':   {'k': 0.240, 'L': 1.000, 'Z': 10, 'desc': 'V - Centros de negocio de grandes ciudades'}
}

# --- ESTADO DE SESIÓN ---
if "lat" not in st.session_state:
    st.session_state.lat = 40.416700  # Madrid por defecto
if "lng" not in st.session_state:
    st.session_state.lng = -3.703700

col_inputs, col_mapa = st.columns([1.5, 2])

# --- FUNCIONES DE CÁLCULO Y API ---
def obtener_datos_geograficos(lat, lng):
    """Obtiene provincia (OSM) y altitud (Open-Meteo) a partir de coordenadas."""
    headers = {'User-Agent': 'AppVientoStreamlit/1.0'}
    
    # 1. Reverse Geocoding OSM
    url_osm = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lng}&zoom=10&addressdetails=1"
    
    # 2. Elevación Open-Meteo
    url_alt = f"https://api.open-meteo.com/v1/elevation?latitude={lat}&longitude={lng}"
    
    try:
        res_osm = requests.get(url_osm, headers=headers, timeout=5)
        res_osm.raise_for_status()
        data_osm = res_osm.json()
        
        address = data_osm.get('address', {})
        region = address.get('province') or address.get('state') or address.get('region') or "Desconocida"
        country_code = address.get('country_code', '')
        
        if country_code != 'es' and country_code != '':
            return None, "Las coordenadas seleccionadas no están en España."

        # Asignar Zona
        zona_asignada = 'A'
        for zona, provincias in ZONAS_CTE.items():
            if any(p.lower() in region.lower() for p in provincias):
                zona_asignada = zona
                break
                
        # Altitud
        res_alt = requests.get(url_alt, timeout=5)
        res_alt.raise_for_status()
        altitud = res_alt.json().get('elevation', [0])[0]
        
        return {
            'region': region,
            'zona': zona_asignada,
            'altitud': altitud
        }, None
        
    except Exception as e:
        return None, f"Error conectando con los servicios geográficos: {e}"

def calcular_viento(zona, z, entorno_key):
    """Aplica el Anejo D del CTE DB SE-AE."""
    vb = 29 if zona == 'C' else (27 if zona == 'B' else 26)
    qb = (0.5 * 1.25 * (vb ** 2)) / 1000
    
    p = PARAMS_ENTORNO[entorno_key]
    z_calc = max(z, p['Z'])
    F = p['k'] * math.log(z_calc / p['L'])
    ce = F * (F + 7 * p['k'])
    qe = qb * ce
    
    return vb, qb, ce, qe

# --- UI: COLUMNA IZQUIERDA (INPUTS) ---
with col_inputs:
    st.subheader("📍 Parámetros Estructurales")
    
    col_coord1, col_coord2 = st.columns(2)
    lat_input = col_coord1.number_input("Latitud", value=st.session_state.lat, format="%.6f", step=0.0001, disabled=True)
    lng_input = col_coord2.number_input("Longitud", value=st.session_state.lng, format="%.6f", step=0.0001, disabled=True)
    st.caption("Selecciona el punto exacto haciendo clic en el mapa interactivo.")
    
    st.write("---")
    altura_input = st.number_input("Altura del edificio / Punto z (metros)", min_value=1.0, value=10.0, step=0.5)
    
    opciones_entorno = {k: v['desc'] for k, v in PARAMS_ENTORNO.items()}
    entorno_seleccionado = st.selectbox("Grado de Aspereza del Entorno", options=list(opciones_entorno.keys()), format_func=lambda x: opciones_entorno[x], index=1)
    
    if st.button("🚀 Calcular Carga de Viento CTE", type="primary", use_container_width=True):
        with st.spinner("Consultando bases de datos OSM y SRTM..."):
            geo_data, error = obtener_datos_geograficos(st.session_state.lat, st.session_state.lng)
            
            if error:
                st.error(error)
            else:
                vb, qb, ce, qe = calcular_viento(geo_data['zona'], altura_input, entorno_seleccionado)
                
                st.session_state.resultado = {
                    'geo': geo_data,
                    'vb': vb, 'qb': qb, 'ce': ce, 'qe': qe,
                    'z': altura_input, 'entorno': opciones_entorno[entorno_seleccionado]
                }

# --- UI: COLUMNA DERECHA (MAPA) ---
with col_mapa:
    st.subheader("Ubicación Seleccionada")
    m = folium.Map(
        location=[st.session_state.lat, st.session_state.lng],
        zoom_start=6,
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Street Map"
    )
    folium.Marker([st.session_state.lat, st.session_state.lng], tooltip="Punto de cálculo").add_to(m)
    map_data = st_folium(m, width="100%", height=400)

    # Actualizar coordenadas al hacer clic en el mapa
    if map_data and map_data.get("last_clicked"):
        click_lat = round(map_data["last_clicked"]["lat"], 6)
        click_lng = round(map_data["last_clicked"]["lng"], 6)
        if click_lat != st.session_state.lat or click_lng != st.session_state.lng:
            st.session_state.lat = click_lat
            st.session_state.lng = click_lng
            # Limpiar resultado anterior al cambiar de punto
            if "resultado" in st.session_state:
                del st.session_state.resultado
            st.rerun()

# --- RESULTADOS ---
if "resultado" in st.session_state:
    st.divider()
    res = st.session_state.resultado
    geo = res['geo']
    
    st.subheader("📊 Resultados del Cálculo")
    
    # Fila 1: Datos Geográficos
    col_g1, col_g2, col_g3 = st.columns(3)
    with col_g1:
        st.info(f"**Provincia/Región:** {geo['region']}")
    with col_g2:
        st.info(f"**Altitud SRTM:** {geo['altitud']} m.s.n.m.")
    with col_g3:
        color_zona = "#c0392b" if geo['zona'] == 'C' else ("#d35400" if geo['zona'] == 'B' else "#27ae60")
        st.markdown(f"<div style='background-color:{color_zona}; color:white; padding:10px; border-radius:5px; text-align:center;'><b>Zona Eólica: {geo['zona']}</b></div>", unsafe_allow_html=True)

    st.write("")
    
    # Fila 2: Cálculos Estructurales
    col_r1, col_r2, col_r3 = st.columns(3)
    
    with col_r1:
        st.markdown(f"""
        <div style="background-color: #f0f2f6; padding: 15px; border-radius: 8px; border-left: 5px solid #6c757d;">
            <span style="font-size: 13px; color: #555;">Velocidad Básica (v<sub>b</sub>)</span><br>
            <span style="font-size: 22px; font-weight: bold; color: #111;">{res['vb']:.1f} m/s</span>
        </div>
        """, unsafe_allow_html=True)
        
    with col_r2:
        st.markdown(f"""
        <div style="background-color: #f0f2f6; padding: 15px; border-radius: 8px; border-left: 5px solid #007bff;">
            <span style="font-size: 13px; color: #555;">Presión Dinámica Básica (q<sub>b</sub>)</span><br>
            <span style="font-size: 22px; font-weight: bold; color: #111;">{res['qb']:.2f} kN/m²</span>
        </div>
        """, unsafe_allow_html=True)

    with col_r3:
        st.markdown(f"""
        <div style="background-color: #e8f4f8; padding: 15px; border-radius: 8px; border-left: 5px solid #28a745;">
            <span style="font-size: 13px; color: #555;">Coef. de Exposición (c<sub>e</sub>)</span><br>
            <span style="font-size: 22px; font-weight: bold; color: #111;">{res['ce']:.2f}</span>
        </div>
        """, unsafe_allow_html=True)

    st.write("")
    st.markdown(f"""
    <div style="background-color: #2c3e50; padding: 20px; border-radius: 8px; text-align: center; color: white;">
        <span style="font-size: 16px; opacity: 0.9;">PRESIÓN DINÁMICA FINAL (q<sub>e</sub>)</span><br>
        <span style="font-size: 32px; font-weight: bold; color: #f1c40f;">{res['qe']:.2f} kN/m²</span><br>
        <span style="font-size: 12px; opacity: 0.7;">Para z = {res['z']}m | {res['entorno']}</span>
    </div>
    """, unsafe_allow_html=True)