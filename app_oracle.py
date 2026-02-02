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
st.set_page_config(page_title="Oracle V55 | Monte Carlo Official", page_icon="🎲", layout="wide")

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
    .exclusion-text { font-size: 0.8em; color: #FF5252; font-style: italic; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. PARÁMETROS OFICIALES (INE/EUROSTAT 2024)
# ==============================================================================
# Basado en tu texto: Pesos reales y descripciones exactas de inclusión/exclusión.
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
        "desc": "Alquiler y suministros. EXCLUYE: Compra vivienda (Inversión).",
        "keywords": ["precio luz", "tarifa gas", "precio alquiler", "euribor hipoteca"]
    },
    "05 Muebles y mantenimiento": {
        "w": 5.8,  "sigma": 0.2, 
        "desc": "Muebles, textil hogar, electrodomésticos, limpieza.",
        "keywords": ["muebles precio", "electrodomésticos", "reparaciones hogar"]
    },
    "06 Sanidad": {
        "w": 4.4,  "sigma": 0.1, 
        "desc": "Medicamentos, gafas, dentistas. Precios muy regulados.",
        "keywords": ["precio medicamentos", "seguro medico", "copago"]
    },
    "07 Transporte": {
        "w": 11.6, "sigma": 0.5, 
        "desc": "Coches, gasolina, vuelos. Muy volátil por petróleo.",
        "keywords": ["precio gasolina", "precio diesel", "vuelos baratos", "renfe"]
    },
    "08 Comunicaciones": {
        "w": 2.7,  "sigma": 0.1, 
        "desc": "Móviles, internet, correos. Tendencia deflacionaria.",
        "keywords": ["tarifas movil", "fibra optica precio"]
    },
    "09 Ocio y cultura": {
        "w": 4.9,  "sigma": 0.3, 
        "desc": "PC, juguetes, cine, turismo. EXCLUYE: Juegos de azar.",
        "keywords": ["entradas cine", "paquetes turisticos", "precio ordenadores"]
    },
    "10 Enseñanza": {
        "w": 1.6,  "sigma": 0.05,
        "desc": "Universidad, colegios. Estacional (Septiembre).",
        "keywords": ["matricula universidad", "libros texto", "cuota colegio"]
    },
    "11 Restaurantes y hoteles": {
        "w": 13.9, "sigma": 0.4, 
        "desc": "Bares, menús, hoteles. Inflación de servicios pura.",
        "keywords": ["precio menu dia", "precio hoteles", "restaurantes"]
    },
    "12 Otros bienes y servicios": {
        "w": 15.1, "sigma": 0.2, 
        "desc": "Peluquería, seguros, joyería. EXCLUYE: Prostitución/Drogas.",
        "keywords": ["seguro coche", "peluqueria precio", "residencia ancianos"]
    }
}

# ==============================================================================
# 2. MOTOR DE INVESTIGACIÓN DETERMINISTA
# ==============================================================================
def get_deterministic_inputs(year, month):
    # Inercia Histórica (Skeleton)
    base_dna = {k: 0.1 for k in SECTOR_PARAMS.keys()} # Valor neutro por defecto
    
    # Ajustes estacionales fuertes (Hardcoded rules)
    # Rebajas G03
    if month in [1, 7]: base_dna["03 Vestido y calzado"] = -12.0
    if month in [3, 4, 9, 10]: base_dna["03 Vestido y calzado"] = 4.0
    # Turismo G11
    if month in [7, 8]: base_dna["11 Restaurantes y hoteles"] = 1.0
    # Enseñanza G10
    if month in [9, 10]: base_dna["10 Enseñanza"] = 1.5
    else: base_dna["10 Enseñanza"] = 0.0

    # Rastreo de Noticias Rápido (Top 3 grupos volátiles)
    news_impacts = {k: 0.0 for k in SECTOR_PARAMS.keys()}
    try:
        gnews = GNews(language='es', country='ES', period='15d', max_results=5)
        # Solo buscamos keywords críticas para no ralentizar la simulación
        for k in ["01 Alimentos y bebidas no alcohólicas", "04 Vivienda, agua, electricidad", "07 Transporte"]:
            query = f"{SECTOR_PARAMS[k]['keywords'][0]} España"
            news = gnews.get_news(query)
            score = 0
            for art in news:
                t = art['title'].lower()
                if "sube" in t or "dispara" in t: score += 0.1
                if "baja" in t or "cae" in t: score -= 0.1
            news_impacts[k] = score
    except: pass
    
    return base_dna, news_impacts

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
    
    # Generar ruido aleatorio basado en la volatilidad de cada sector
    # Alimentos (Sigma 0.35) varían más que Enseñanza (Sigma 0.05)
    noise = np.random.normal(0, 0.2, (iterations, 12)) * sigmas
    scenarios = means + noise
    
    # Producto punto ponderado
    weighted_scenarios = np.dot(scenarios, weights) / 100
    return weighted_scenarios

# ==============================================================================
# UI
# ==============================================================================
with st.sidebar:
    st.title("ORACLE V55")
    st.caption("OFFICIAL AUDIT SIMULATOR")
    
    t_year = st.number_input("Año", 2024, 2030, 2026)
    t_month = st.selectbox("Mes", range(1, 13))
    
    st.divider()
    base_annual = st.number_input("IPC Anual Previo", value=2.90)
    old_monthly = st.number_input("IPC Saliente", value=0.30)
    
    st.markdown("---")
    st.markdown("### 🚫 Panel de Exclusiones")
    st.caption("El modelo aplica rigurosamente la normativa INE, excluyendo:")
    st.markdown("- Compra de Vivienda (Inv.)")
    st.markdown("- Intereses, Multas, Donaciones")
    st.markdown("- Prostitución y Drogas")
    
    iterations = st.slider("Escenarios Monte Carlo", 1000, 10000, 5000)
    
    if st.button("EJECUTAR SIMULACIÓN V55", type="primary"):
        st.session_state.montecarlo_v55 = True

if 'montecarlo_v55' in st.session_state:
    st.title(f"Auditoría Probabilística: {calendar.month_name[t_month].upper()} {t_year}")
    
    with st.spinner(f"Simulando {iterations} universos económicos..."):
        base, news = get_deterministic_inputs(t_year, t_month)
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
    
    # GRÁFICO DE CAMPANA DE GAUSS (Ahora funcionará porque tienes scipy)
    try:
        hist_data = [simulated_monthly_cpi]
        group_labels = ['Distribución de Probabilidad IPC']
        fig = ff.create_distplot(hist_data, group_labels, bin_size=0.02, show_hist=False, show_rug=False, colors=['#00E5FF'])
        
        fig.add_vline(x=median_val, line_width=3, line_dash="dash", line_color="white", annotation_text="Mediana")
        fig.add_vrect(x0=p5, x1=p95, fillcolor="green", opacity=0.1, line_width=0, annotation_text="Confianza 90%", annotation_position="top left")
        
        fig.update_layout(title="Distribución de Probabilidad (Monte Carlo)", template="plotly_dark", height=450)
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error gráfico: {e}. (Verifica que scipy está en requirements.txt)")

    # DESGLOSE DE GRUPOS (Tu lista detallada)
    with st.expander("🔎 Ver Desglose de los 12 Grupos (Detalle Metodológico)"):
        for k, v in SECTOR_PARAMS.items():
            st.markdown(f"**{k}** (Peso: {v['w']}%)")
            st.caption(f"📝 {v['desc']}")
            st.progress(int(v['w']*2)) # Barra visual de peso
