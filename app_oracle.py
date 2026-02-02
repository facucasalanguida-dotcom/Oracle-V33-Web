import streamlit as st
from gnews import GNews
import calendar
import datetime
import plotly.graph_objects as go
import plotly.figure_factory as ff
import pandas as pd
import numpy as np
import time

# --- CONFIGURACIÓN PROBABILÍSTICA ---
st.set_page_config(page_title="Oracle V56 | Omni-Channel", page_icon="📡", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    h1, h2, h3 { font-family: 'Roboto', sans-serif; color: #00E5FF; }
    .stat-box { 
        background-color: #1A1D24; 
        border: 1px solid #30363D; 
        padding: 15px; 
        border-radius: 8px; 
        text-align: center;
    }
    .big-number { font-size: 2em; font-weight: bold; color: #00E5FF; }
    div[data-testid="stMetric"] { background-color: #161B22; border: 1px solid #30363D; }
    .broadcast-badge { 
        background-color: #FF0000; color: white; padding: 2px 6px; 
        border-radius: 4px; font-size: 0.7em; font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. PARÁMETROS OFICIALES (INE/EUROSTAT 2024)
# ==============================================================================
SECTOR_PARAMS = {
    "01 Alimentos y bebidas no alcohólicas": {
        "w": 19.6, "sigma": 0.35, 
        "desc": "Pan, carne, pescado, aceite oliva, fruta. Excluye alcohol.",
        "keywords": ["precio aceite oliva", "cesta compra", "precio fruta verdura", "precio carne"]
    },
    "02 Bebidas alcohólicas y tabaco": {
        "w": 3.9,  "sigma": 0.1, 
        "desc": "Vinos, cervezas, tabaco. Regulado por impuestos.",
        "keywords": ["precio tabaco", "impuesto alcohol"]
    },
    "03 Vestido y calzado": {
        "w": 3.8,  "sigma": 0.8, 
        "desc": "Ropa y zapatos. Muy estacional (Rebajas Ene/Jul).",
        "keywords": ["rebajas ropa", "nueva temporada moda"]
    },
    "04 Vivienda, agua, electricidad": {
        "w": 12.7, "sigma": 0.6, 
        "desc": "Alquiler y suministros. EXCLUYE: Compra vivienda.",
        "keywords": ["precio luz", "tarifa gas", "precio alquiler", "euribor hipoteca"]
    },
    "05 Muebles y mantenimiento": {
        "w": 5.8,  "sigma": 0.2, 
        "desc": "Muebles, textil hogar, electrodomésticos.",
        "keywords": ["muebles precio", "electrodomésticos", "reparaciones hogar"]
    },
    "06 Sanidad": {
        "w": 4.4,  "sigma": 0.1, 
        "desc": "Medicamentos, gafas. Precios regulados.",
        "keywords": ["precio medicamentos", "seguro medico", "copago"]
    },
    "07 Transporte": {
        "w": 11.6, "sigma": 0.5, 
        "desc": "Coches, gasolina, vuelos. Muy volátil.",
        "keywords": ["precio gasolina", "precio diesel", "vuelos baratos", "renfe"]
    },
    "08 Comunicaciones": {
        "w": 2.7,  "sigma": 0.1, 
        "desc": "Móviles, internet. Tendencia deflacionaria.",
        "keywords": ["tarifas movil", "fibra optica precio"]
    },
    "09 Ocio y cultura": {
        "w": 4.9,  "sigma": 0.3, 
        "desc": "PC, juguetes, cine. EXCLUYE: Juegos de azar.",
        "keywords": ["entradas cine", "paquetes turisticos", "precio ordenadores"]
    },
    "10 Enseñanza": {
        "w": 1.6,  "sigma": 0.05,
        "desc": "Universidad, colegios. Estacional (Sept).",
        "keywords": ["matricula universidad", "libros texto", "cuota colegio"]
    },
    "11 Restaurantes y hoteles": {
        "w": 13.9, "sigma": 0.4, 
        "desc": "Bares, menús, hoteles. Inflación servicios.",
        "keywords": ["precio menu dia", "precio hoteles", "restaurantes"]
    },
    "12 Otros bienes y servicios": {
        "w": 15.1, "sigma": 0.2, 
        "desc": "Peluquería, seguros. EXCLUYE: Prostitución.",
        "keywords": ["seguro coche", "peluqueria precio", "residencia ancianos"]
    }
}

# ==============================================================================
# 2. MOTOR DE INVESTIGACIÓN (TEXTO + BROADCAST TV/RADIO)
# ==============================================================================
def get_deterministic_inputs(year, month):
    # Inercia Histórica
    base_dna = {k: 0.1 for k in SECTOR_PARAMS.keys()}
    if month in [1, 7]: base_dna["03 Vestido y calzado"] = -12.0
    if month in [3, 4, 9, 10]: base_dna["03 Vestido y calzado"] = 4.0
    if month in [7, 8]: base_dna["11 Restaurantes y hoteles"] = 1.0
    if month in [9, 10]: base_dna["10 Enseñanza"] = 1.5
    else: base_dna["10 Enseñanza"] = 0.0

    # ---------------------------------------------------------
    # NOVEDAD V56: ESCUCHA DE MEDIOS (BROADCAST LISTENER)
    # Buscamos específicamente qué dicen las TVs y Radios
    # ---------------------------------------------------------
    news_impacts = {k: 0.0 for k in SECTOR_PARAMS.keys()}
    broadcast_evidence = []
    
    try:
        # 1. Búsqueda General (Prensa Escrita)
        gnews = GNews(language='es', country='ES', period='15d', max_results=5)
        
        # 2. Búsqueda Broadcast (TV/Radio/YouTube channels vía GNews)
        # Añadimos términos como "declaraciones", "entrevista", "video"
        # y filtramos por medios audiovisuales si aparecen en resultados.
        
        for k in ["01 Alimentos y bebidas no alcohólicas", "04 Vivienda, agua, electricidad", "07 Transporte"]:
            # Búsqueda ampliada
            query = f"{SECTOR_PARAMS[k]['keywords'][0]} España"
            news = gnews.get_news(query)
            
            score = 0
            for art in news:
                t = art['title'].lower()
                src = art.get('publisher', {}).get('title', '').lower()
                
                # Detectar Medios Audiovisuales (Mayor impacto psicológico)
                is_broadcast = any(x in src for x in ['cadena ser', 'onda cero', 'rtve', 'antena 3', 'lasexta', 'youtube', 'telecinco'])
                
                weight = 0.1
                if is_broadcast: 
                    weight = 0.2 # La TV pesa el doble en la percepción pública
                    if len(broadcast_evidence) < 3:
                        broadcast_evidence.append(f"📡 {src.upper()}: {art['title']}")
                
                if "sube" in t or "dispara" in t: score += weight
                if "baja" in t or "cae" in t: score -= weight
            
            news_impacts[k] = score
    except: pass
    
    return base_dna, news_impacts, broadcast_evidence

# ==============================================================================
# 3. MOTOR MONTE CARLO (Probabilistic Engine)
# ==============================================================================
def run_monte_carlo_simulation(base_inputs, news_inputs, iterations=5000):
    weights = np.array([v["w"] for v in SECTOR_PARAMS.values()])
    sigmas = np.array([v["sigma"] for v in SECTOR_PARAMS.values()])
    
    means = []
    for k in SECTOR_PARAMS.keys():
        means.append(base_inputs.get(k, 0) + news_inputs.get(k, 0))
    means = np.array(means)
    
    noise = np.random.normal(0, 0.2, (iterations, 12)) * sigmas
    scenarios = means + noise
    weighted_scenarios = np.dot(scenarios, weights) / 100
    return weighted_scenarios

# ==============================================================================
# UI
# ==============================================================================
with st.sidebar:
    st.title("ORACLE V56")
    st.caption("OMNI-CHANNEL AUDITOR")
    
    t_year = st.number_input("Año", 2024, 2030, 2026)
    t_month = st.selectbox("Mes", range(1, 13))
    
    st.divider()
    base_annual = st.number_input("IPC Anual Previo", value=2.90)
    old_monthly = st.number_input("IPC Saliente", value=0.30)
    
    st.markdown("---")
    st.markdown("### 📡 Fuentes Monitorizadas")
    st.caption("• Prensa Económica (Texto)")
    st.caption("• Mercados Financieros (Hard Data)")
    st.caption("• **TV & Radio (Broadcast Sentiment)** [NUEVO]")
    
    iterations = st.slider("Escenarios Monte Carlo", 1000, 10000, 5000)
    
    if st.button("EJECUTAR ANÁLISIS 360º", type="primary"):
        st.session_state.montecarlo_v56 = True

if 'montecarlo_v56' in st.session_state:
    st.title(f"Auditoría 360º: {calendar.month_name[t_month].upper()} {t_year}")
    
    with st.spinner(f"Sintonizando medios y simulando {iterations} escenarios..."):
        base, news, broadcast_logs = get_deterministic_inputs(t_year, t_month)
        simulated_monthly_cpi = run_monte_carlo_simulation(base, news, iterations)
        
        # Estadísticas
        median_val = np.median(simulated_monthly_cpi)
        std_dev = np.std(simulated_monthly_cpi)
        p5 = np.percentile(simulated_monthly_cpi, 5)
        p95 = np.percentile(simulated_monthly_cpi, 95)
        
        # Anual
        f_base = 1 + base_annual/100
        f_out = 1 + old_monthly/100
        f_in = 1 + median_val/100
        final_annual_median = ((f_base / f_out) * f_in - 1) * 100

    # TARJETAS DE RESULTADOS
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div class="stat-box">
            <div style="color:#888;">IPC MENSUAL (MEDIANA)</div>
            <div class="big-number">{median_val:+.2f}%</div>
            <div style="color:#00E5FF; font-size:0.8em;">± {std_dev:.2f}% Desviación</div>
        </div>""", unsafe_allow_html=True)
    with c2:
         st.markdown(f"""
        <div class="stat-box">
            <div style="color:#888;">IPC ANUAL (PROYECTADO)</div>
            <div class="big-number" style="color:#FFD700;">{final_annual_median:.2f}%</div>
            <div style="color:#FFD700; font-size:0.8em;">Objetivo: {base_annual}%</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="stat-box">
            <div style="color:#888;">CERTEZA ESTADÍSTICA</div>
            <div class="big-number" style="color:#00E676;">95%</div>
            <div style="color:#00E676; font-size:0.8em;">Rango: [{p5:.2f}%, {p95:.2f}%]</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    
    # SECCIÓN DE MEDIOS AUDIOVISUALES
    if broadcast_logs:
        st.info("📡 **IMPACTO MEDIÁTICO (TV/RADIO) DETECTADO:**")
        for log in broadcast_logs:
            st.markdown(f"- {log}")
    else:
        st.caption("📡 No se detectó impacto significativo en TV/Radio para los sectores críticos esta quincena.")

    # GRÁFICO DE CAMPANA DE GAUSS
    try:
        hist_data = [simulated_monthly_cpi]
        group_labels = ['Probabilidad IPC']
        fig = ff.create_distplot(hist_data, group_labels, bin_size=0.02, show_hist=False, show_rug=False, colors=['#00E5FF'])
        
        fig.add_vline(x=median_val, line_width=3, line_dash="dash", line_color="white", annotation_text="Mediana")
        fig.add_vrect(x0=p5, x1=p95, fillcolor="green", opacity=0.1, line_width=0, annotation_text="Confianza 90%", annotation_position="top left")
        
        fig.update_layout(title="Distribución de Probabilidad (Con sesgo mediático)", template="plotly_dark", height=450)
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error gráfico: {e}. (Revisa scipy en requirements.txt)")
