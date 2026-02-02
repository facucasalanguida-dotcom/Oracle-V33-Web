import streamlit as st
from gnews import GNews
import calendar
import datetime
import plotly.graph_objects as go
import plotly.figure_factory as ff
import pandas as pd
import numpy as np
import time

# --- CONFIGURACIÓN TÉCNICA ---
st.set_page_config(page_title="Oracle V58 | Equalizer", page_icon="⚖️", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    h1, h2, h3 { font-family: 'Roboto', sans-serif; color: #00E5FF; }
    .stat-box { 
        background-color: #1A1D24; border: 1px solid #30363D; 
        padding: 15px; border-radius: 8px; text-align: center;
    }
    .big-number { font-size: 2em; font-weight: bold; color: #00E5FF; }
    .news-card {
        background-color: #1F2937; border-left: 4px solid #3B82F6;
        padding: 10px; margin-bottom: 5px; font-size: 0.9em;
    }
    div[data-testid="stMetric"] { background-color: #161B22; border: 1px solid #30363D; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. PARÁMETROS OFICIALES (INE 2024)
# ==============================================================================
SECTOR_PARAMS = {
    "01 Alimentos y bebidas": { "w": 19.6, "sigma": 0.35, "keywords": ["precio aceite", "cesta compra", "precio fruta", "leche huevos"] },
    "02 Alcohol y tabaco": { "w": 3.9, "sigma": 0.1, "keywords": ["precio tabaco", "impuestos alcohol"] },
    "03 Vestido y calzado": { "w": 3.8, "sigma": 0.8, "keywords": ["rebajas ropa", "moda precios"] },
    "04 Vivienda (Luz/Gas)": { "w": 12.7, "sigma": 0.6, "keywords": ["precio luz", "tarifa gas", "tope gas", "alquiler"] },
    "05 Muebles/Hogar": { "w": 5.8, "sigma": 0.2, "keywords": ["electrodomesticos", "reformas"] },
    "06 Sanidad": { "w": 4.4, "sigma": 0.1, "keywords": ["medicamentos", "copago"] },
    "07 Transporte": { "w": 11.6, "sigma": 0.5, "keywords": ["gasolina", "diesel", "renfe", "vuelos"] },
    "08 Comunicaciones": { "w": 2.7, "sigma": 0.1, "keywords": ["tarifas movil", "fibra optica"] },
    "09 Ocio y cultura": { "w": 4.9, "sigma": 0.3, "keywords": ["cine", "paquetes turisticos"] },
    "10 Enseñanza": { "w": 1.6, "sigma": 0.05, "keywords": ["matricula universidad", "libros texto"] },
    "11 Hoteles/Rest.": { "w": 13.9, "sigma": 0.4, "keywords": ["menu dia", "precio hoteles"] },
    "12 Otros": { "w": 15.1, "sigma": 0.2, "keywords": ["seguros", "peluqueria"] }
}

# ==============================================================================
# 2. MOTOR DE BÚSQUEDA IGUALITARIO (EQUALIZER)
# ==============================================================================
def hunt_media_impact(year, month):
    """
    Busca noticias en todos los medios. 
    Aplica el mismo peso matemático (0.1) a TV, Radio y Prensa.
    """
    # Lista de dominios solo para etiquetado visual (NO afecta al cálculo)
    BROADCAST_DOMAINS = [
        "rtve.es", "cadenaser.com", "ondacero.es", "lasexta.com", 
        "antena3.com", "telecinco.es", "cope.es", "telemadrid.es"
    ]
    
    # Comprobar si es futuro
    is_future = datetime.datetime(year, month, 1) > datetime.datetime.now()
    
    if is_future:
        period = '15d'
        start_date = None; end_date = None
    else:
        period = None
        last_day = calendar.monthrange(year, month)[1]
        start_date = (year, month, 1)
        end_date = (year, month, last_day)

    impacts = {k: 0.0 for k in SECTOR_PARAMS.keys()}
    evidence_log = []
    
    gnews = GNews(language='es', country='ES', period=period, start_date=start_date, end_date=end_date, max_results=10)
    
    # Sectores críticos
    critical_sectors = ["01 Alimentos y bebidas", "04 Vivienda (Luz/Gas)", "07 Transporte"]
    
    status_bar = st.progress(0)
    
    for i, sector in enumerate(critical_sectors):
        status_bar.progress(int((i / len(critical_sectors)) * 100))
        
        keyword = SECTOR_PARAMS[sector]["keywords"][0]
        query = f"{keyword} España"
        
        try:
            news = gnews.get_news(query)
            sector_score = 0
            
            for art in news:
                title = art['title'].lower()
                source = art.get('publisher', {}).get('title', '').lower()
                link = art.get('url', '').lower()
                
                # Etiquetado Visual (Icono)
                is_tv_radio = any(d in link for d in BROADCAST_DOMAINS) or \
                              any(x in source for x in ['cadena', 'onda', 'rtve', 'sexta', 'antena'])
                
                icon = "📺" if is_tv_radio else "📰"
                
                # --- AQUÍ ESTÁ EL CAMBIO V58 ---
                # Peso estandarizado para TODOS. Ya no hay discriminación.
                weight = 0.1 
                # -------------------------------
                
                sentiment = 0
                if "sube" in title or "dispara" in title or "récord" in title: sentiment = 1
                elif "baja" in title or "cae" in title or "desciende" in title: sentiment = -1
                
                if sentiment != 0:
                    sector_score += (sentiment * weight)
                    if len(evidence_log) < 5: 
                        evidence_log.append(f"{icon} {source.upper()}: {art['title']}")
            
            # Normalización suave (tope +/- 0.5%)
            impacts[sector] = max(min(sector_score, 0.5), -0.5)
            
        except Exception as e:
            pass

    status_bar.empty()
    return impacts, evidence_log, is_future

# ==============================================================================
# 3. MOTOR MONTE CARLO + INERCIA
# ==============================================================================
def run_simulation(year, month, media_impacts, iterations=5000):
    # Base Inercial (Skeleton)
    base_dna = {k: 0.1 for k in SECTOR_PARAMS.keys()}
    # Ajustes estacionales
    if month in [1, 7]: base_dna["03 Vestido y calzado"] = -12.0
    if month in [3, 4, 9, 10]: base_dna["03 Vestido y calzado"] = 4.0
    if month in [7, 8]: base_dna["11 Hoteles/Rest."] = 1.0
    
    means = []
    weights = []
    sigmas = []
    
    for k, v in SECTOR_PARAMS.items():
        total_mean = base_dna[k] + media_impacts.get(k, 0.0)
        means.append(total_mean)
        weights.append(v["w"])
        sigmas.append(v["sigma"])
        
    means = np.array(means)
    weights = np.array(weights)
    sigmas = np.array(sigmas)
    
    noise = np.random.normal(0, 0.2, (iterations, 12)) * sigmas
    scenarios = means + noise
    weighted_scenarios = np.dot(scenarios, weights) / 100
    
    return weighted_scenarios

# ==============================================================================
# UI
# ==============================================================================
with st.sidebar:
    st.title("ORACLE V58")
    st.caption("EQUALIZER EDITION")
    
    t_year = st.number_input("Año", 2024, 2030, 2026)
    t_month = st.selectbox("Mes", range(1, 13))
    
    st.divider()
    base_annual = st.number_input("IPC Anual Previo", value=2.90)
    old_monthly = st.number_input("IPC Saliente", value=0.30)
    
    iterations = st.slider("Precisión (Iteraciones)", 1000, 10000, 5000)
    
    if st.button("EJECUTAR ANÁLISIS ESTANDARIZADO", type="primary"):
        st.session_state.run_v58 = True

if 'run_v58' in st.session_state:
    st.title(f"Auditoría Estandarizada: {calendar.month_name[t_month].upper()} {t_year}")
    
    with st.spinner("Procesando medios con peso equitativo..."):
        m_impacts, m_logs, is_fut = hunt_media_impact(t_year, t_month)
        
        sim_results = run_simulation(t_year, t_month, m_impacts, iterations)
        
        # Estadísticas
        median = np.median(sim_results)
        std = np.std(sim_results)
        p5, p95 = np.percentile(sim_results, [5, 95])
        
        f_base = 1 + base_annual/100
        f_out = 1 + old_monthly/100
        f_in = 1 + median/100
        final_annual = ((f_base / f_out) * f_in - 1) * 100

    if is_fut:
        st.warning(f"⚠️ Proyectando sentimiento actual sobre el futuro ({t_year}).")

    # TARJETAS
    c1, c2, c3 = st.columns(3)
    c1.metric("IPC MENSUAL (MEDIANA)", f"{median:+.2f}%", f"±{std:.2f}%")
    c2.metric("IPC ANUAL ESTIMADO", f"{final_annual:.2f}%", f"Objetivo: {base_annual}%")
    c3.metric("CONFIANZA", "95%", f"[{p5:.2f}%, {p95:.2f}%]")

    # EVIDENCIA DE MEDIOS
    st.markdown("---")
    st.subheader("📰 Titulares Detectados (Impacto: 0.1 estándar)")
    
    if m_logs:
        for log in m_logs:
            st.markdown(f"""
            <div class="news-card">
                {log}
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Sin noticias de alto impacto detectadas. Se aplica inercia histórica pura.")

    # GRÁFICO
    try:
        hist_data = [sim_results]
        group_labels = ['Distribución IPC']
        fig = ff.create_distplot(hist_data, group_labels, bin_size=0.02, show_hist=False, show_rug=False, colors=['#3B82F6'])
        fig.add_vline(x=median, line_dash="dash", annotation_text="Mediana")
        fig.update_layout(title="Probabilidad de Inflación (Pesos Equilibrados)", template="plotly_dark", height=400)
        st.plotly_chart(fig, use_container_width=True)
    except:
        st.warning("Instala 'scipy' para ver el gráfico de distribución.")
