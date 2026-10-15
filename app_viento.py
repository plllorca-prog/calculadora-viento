import streamlit as st
import requests
import folium
import json
from streamlit_folium import st_folium

st.set_page_config(layout="wide", page_title="Consulta Viento API Externa")

st.title("🌪️ Extractor de Datos de Viento (Dlubal API)")
st.caption("Esta herramienta extrae los datos oficiales consultando la API interna de la web original.")

# --- BARRA LATERAL: AUTENTICACIÓN Y CONFIGURACIÓN ---
with st.sidebar:
    st.header("🔑 Configuración de la API")
    with st.expander("❓ ¿Cómo obtener los datos de conexión?", expanded=False):
        st.markdown("""
        **Pasos en la web original (Dlubal):**
        1. Entra en su mapa de viento del CTE.
        2. Abre las herramientas de desarrollador (**F12**).
        3. Ve a la pestaña **Network** (Red) y filtra por "Fetch/XHR".
        4. Haz clic en cualquier parte del mapa de España.
        5. Aparecerá una nueva petición en la lista (suele llamarse `GetData`, `ZoneTool` o similar).
        6. Haz clic en ella y copia:
           - La **URL** completa de la petición.
           - El **Token de Autorización** o las Cookies de la sección *Request Headers*.
        """)

    api_url = st.text_input("URL del Endpoint (API)", value="https://api.dlubal.com/geozone/...", help="Pega aquí la URL exacta que captura F12")
    auth_token = st.text_input("Token / Cookie", type="password", help="Pega aquí el Authorization token o la Cookie")

# --- ESTADO DE SESIÓN ---
if "lat" not in st.session_state:
    st.session_state.lat = 40.416700
if "lng" not in st.session_state:
    st.session_state.lng = -3.703700

col_inputs, col_mapa = st.columns([1.5, 2])

# --- FUNCIÓN DE CONSULTA A LA API ORIGINAL ---
def extraer_datos_dlubal(lat, lng, url, token):
    """Hace la petición directamente al servidor de la web original."""
    
    # Aquí definimos las cabeceras simulando ser un navegador real
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "origin": "https://www.dlubal.com",
        "referer": "https://www.dlubal.com/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Si requiere un token tipo Bearer o Cookie, lo inyectamos
    if token:
        # Ajusta esto dependiendo de si usan 'Authorization: Bearer...' o 'Cookie: session=...'
        headers["Authorization"] = f"Bearer {token}" 

    # El payload (cuerpo de la petición). ¡Atención! Deberás mirar en F12 cómo estructuran ellos el JSON que envían.
    payload = {
        "Latitude": float(lat),
        "Longitude": float(lng),
        "Standard": "CTE DB SE-AE" # Parámetro simulado, revisa el F12 real
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return response.json(), None
        else:
            return None, f"Error HTTP {response.status_code}: Probablemente el token ha caducado o detectó que eres un bot."
            
    except Exception as e:
        return None, f"Error de conexión: {str(e)}"


# --- UI: COLUMNA IZQUIERDA ---
with col_inputs:
    st.subheader("📍 Coordenadas de Consulta")
    lat_input = st.number_input("Latitud", value=st.session_state.lat, format="%.6f", step=0.0001)
    lng_input = st.number_input("Longitud", value=st.session_state.lng, format="%.6f", step=0.0001)
    
    st.info("Haz clic en el mapa para capturar las coordenadas automáticamente.")

    if st.button("🚀 Extraer Datos de la Web", type="primary", use_container_width=True):
        if not api_url or "api.dlubal.com" not in api_url:
            st.warning("⚠️ Recuerda configurar la URL real de la API en la barra lateral.")
            
        st.session_state.lat = round(lat_input, 6)
        st.session_state.lng = round(lng_input, 6)
        
        with st.spinner("Conectando con los servidores originales..."):
            datos, error = extraer_datos_dlubal(
                st.session_state.lat, 
                st.session_state.lng, 
                api_url, 
                auth_token
            )
            
            st.session_state.resultado = {
                "datos": datos,
                "error": error
            }

# --- UI: COLUMNA DERECHA (MAPA) ---
with col_mapa:
    st.subheader("Selección de Ubicación")
    m = folium.Map(
        location=[st.session_state.lat, st.session_state.lng],
        zoom_start=6,
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Street Map"
    )
    folium.Marker([st.session_state.lat, st.session_state.lng]).add_to(m)
    map_data = st_folium(m, width="100%", height=400)

    if map_data and map_data.get("last_clicked"):
        click_lat = round(map_data["last_clicked"]["lat"], 6)
        click_lng = round(map_data["last_clicked"]["lng"], 6)
        if click_lat != st.session_state.lat or click_lng != st.session_state.lng:
            st.session_state.lat = click_lat
            st.session_state.lng = click_lng
            st.rerun()

# --- RESULTADOS ---
if "resultado" in st.session_state:
    st.divider()
    res = st.session_state.resultado
    
    st.subheader("📥 Datos Extraídos de la API")
    
    if res["error"]:
        st.error(res["error"])
    else:
        st.success("¡Datos obtenidos con éxito!")
        
        # Como no sabemos la estructura exacta del JSON de Dlubal hasta que hagas el F12,
        # imprimimos el JSON crudo para que puedas investigar cómo extraer vb y qb.
        st.write("Respuesta cruda del servidor:")
        st.json(res["datos"])
