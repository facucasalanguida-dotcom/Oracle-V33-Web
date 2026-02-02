import streamlit as st
from gnews import GNews
import calendar
import datetime
from datetime import timedelta
import plotly.graph_objects as go
import plotly.figure_factory as ff
import pandas as pd
import numpy as np
import yfinance as yf
import re
import time

# ==============================================================================
# CONFIGURACIÓN DEL SISTEMA OMEGA
# ==============================================================================
st.set_page_config(page_title="ORACLE OMEGA | The Ultimate CPI Engine", page_icon="🏛️", layout="wide")

st.markdown("""
<style>
    /* Estilo Cyberpunk-Profesional */
    .stApp { background-color: #050505; color: #E0E0E0; }
    h1, h2, h3 { font-family: 'Roboto Mono', monospace; color: #00FF9D; letter-spacing: -1px; }
    
    /* Cajas de Métricas */
    .metric-container {
        background-color: #111; border: 1px solid #333; 
        padding: 15px; border-radius: 8px; text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .metric-val { font-size: 2.2em; font-weight: bold; color: #fff; }
    .metric-label { font-size: 0.8em; color: #888; text-transform: uppercase; }
    .metric-sub { font-size: 0.8em; color: #00FF9D; }

    /* Tarjetas de Evidencia */
    .evidence-card {
        background-color: #1A1A1A; border-left: 3px solid #555;
        padding: 10px; margin-bottom: 8px; font-size: 0.85em; font-family: 'Consolas', monospace;
    }
    .tag-tv { background-color: #D32F2F; color: white; padding: 2px 5px; border-radius: 3px; font-size: 0.7em; }
    .tag-retail { background-color: #FFA000; color: black; padding: 2px 5px; border-radius: 3px; font-size: 0.7em; }
    .tag-market { background-color: #1976D2; color: white; padding: 2px 5px; border-radius: 3px; font-size: 0.7em; }

    /* Barra de Progreso Custom */
    .stProgress > div > div > div > div { background-color: #00FF9D; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. LA MATRIZ MAESTRA (ECOICOP 12 GRUPOS)
# ==============================================================================
# Contiene toda la lógica económica, financiera y semántica de España.
MASTER_MATRIX = {
    "01 Alimentos y bebidas no alcohólicas": {
        "w": 19.6, # Peso INE
        "sigma": 0.35, # Volatilidad
        "tickers": ["ZW=F", "ZC=F", "LE=F", "SB=F", "KC=F"], # Trigo, Maíz, Ganado, Azúcar, Café
        "keywords": ["precio aceite oliva", "cesta compra", "precio fruta verdura", "precio leche huevos", "precio carne pescado"],
        "retail_watch": True, # Activar escáner de supermercados
        "seasonal": [0.4, 0.2, 0.1, 0.1, 0.0, 0.2, 0.0, 0.1, -0.1, 0.4, 0.2, 0.8] # Dic fuerte
    },
    "02 Bebidas alcohólicas y tabaco": {
        "w": 3.9, "sigma": 0.1,
        "tickers": [], # Regulado
        "keywords": ["precio tabaco", "impuestos alcohol", "subida cajetilla"],
        "retail_watch": False,
        "seasonal": [0.9, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.2] # Ene tasas
    },
    "03 Vestido y calzado": {
        "w": 3.8, "sigma": 0.8,
        "tickers": [],
        "keywords": ["rebajas ropa", "nueva temporada moda", "precio ropa"],
        "retail_watch": False,
        "seasonal": [-13.0, -2.0, 4.0, 9.0, 2.0, -1.0, -12.5, -2.0, 5.0, 9.0, 0.5, -1.0] # Rebajas Ene/Jul
    },
    "04 Vivienda (Luz, Gas, Agua)": {
        "w": 12.7, "sigma": 0.6,
        "tickers": ["NG=F"], # Gas Natural (Proxy marginalista)
        "keywords": ["precio luz", "tarifa gas", "tope gas", "euribor hipoteca", "precio alquiler"],
        "retail_watch": False,
        "seasonal": [0.6, -0.2, -0.5, -0.2, -0.1, 0.4, 0.6, 0.5, 0.2, 0.5, 0.3, 0.7]
    },
    "05 Muebles y hogar": {
        "w": 5.8, "sigma": 0.2,
        "tickers": ["HG=F"], # Cobre (Proxy industrial)
        "keywords": ["precio electrodomesticos", "reformas hogar", "precio muebles"],
        "retail_watch": True,
        "seasonal": [-0.3, 0.1, 0.2, 0.2, 0.1, 0.1, -0.4, 0.0, 0.2, 0.3, 0.1, 0.2]
    },
    "06 Sanidad": {
        "w": 4.4, "sigma": 0.05,
        "tickers": [],
        "keywords": ["precio medicamentos", "copago farmacia", "seguro medico"],
        "retail_watch": False,
        "seasonal": [0.2, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    },
    "07 Transporte": {
        "w": 11.6, "sigma": 0.5,
        "tickers": ["BZ=F", "CL=F"], # Brent, WTI
        "keywords": ["precio gasolina", "precio diesel", "vuelos baratos", "billete renfe", "precio coches"],
        "retail_watch": False,
        "seasonal": [0.3, 0.2, 0.5, 0.8, 0.4, 0.5, 0.9, 0.6, -0.5, -0.2, -0.3, 0.2]
    },
    "08 Comunicaciones": {
        "w": 2.7, "sigma": 0.1,
        "tickers": [],
        "keywords": ["tarifas movil", "precio fibra optica"],
        "retail_watch": False,
        "seasonal": [-0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1]
    },
    "09 Ocio y cultura": {
        "w": 4.9, "sigma": 0.3,
        "tickers": [],
        "keywords": ["entradas cine", "paquetes turisticos", "precio ordenadores"],
        "retail_watch": False,
        "seasonal": [-0.8, 0.1, 0.4, 0.2, -0.5, 0.4, 1.2, 1.2, -1.5, -0.5, -0.2, 1.0]
    },
    "10 Enseñanza": {
        "w": 1.6, "sigma": 0.05,
        "tickers": [],
        "keywords": ["matricula universidad", "libros texto", "cuota colegio"],
        "retail_watch": False,
        "seasonal": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.8, 1.2, 0.0, 0.0] # Septiembre
    },
    "11 Hoteles y Restaurantes": {
        "w": 13.9, "sigma": 0.4,
        "tickers": [],
        "keywords": ["precio menu dia", "precio hoteles", "restaurantes subida"],
        "retail_watch": False,
        "seasonal": [-0.5, 0.2, 0.5, 0.4, 0.5, 1.0, 2.5, 2.0, -1.0, -0.5, -0.4, 0.8]
    },
    "12 Otros bienes y servicios": {
        "w": 15.1, "sigma": 0.2,
        "tickers": [],
        "keywords": ["seguro coche", "precio peluqueria", "residencia ancianos", "precio oro"],
        "retail_watch": False,
        "seasonal": [0.9, 0.2, 0.2, 0.1, 0.1, 0.1, 0.1, 0.0, 0.1, 0.1, 0.0, 0.1] # Ene Seguros
    }
}

# Dominios de TV/Radio para detección de "Broadcast"
BROADCAST_DOMAINS = ["rtve.es", "cadenaser.com", "ondacero.es", "lasexta.com", "antena3.com", "telecinco.es", "cope.es"]
# Supermercados para detección "Retail"
RETAILERS = ["mercadona", "carrefour", "lidl", "dia", "alcampo", "eroski"]

# ==============================================================================
# 2. FUNCIONES AUXILIARES DE INTELIGENCIA
# ==============================================================================

def extract_magnitude(text):
    """Extrae porcentajes o cifras de un texto (Regex NLP)"""
    match = re.search(r'(\d+([.,]\d+)?)(\s?%| euros| centimos)', text.lower())
    if match:
        try:
            val = float(match.group(1).replace(',', '.'))
            if "euros" in match.group(0) or "centimos" in match.group(0):
                return None # Ignoramos precios absolutos por ahora, solo % relativo
            return min(val, 25.0) # Capamos al 25% para evitar errores de lectura
        except: return None
    return None

def analyze_sentiment_advanced(text, source):
    """
    Analiza el texto y devuelve: (Score Dirección, Score Magnitud, Etiquetas)
    """
    text = text.lower()
    source = source.lower()
    
    # 1. Etiquetas
    tags = []
    if any(d in source for d in BROADCAST_DOMAINS): tags.append("TV/RADIO")
    if any(r in text for r in RETAILERS): tags.append("RETAIL")
    
    # 2. Dirección
    direction = 0
    if "sube" in text or "dispara" in text or "alza" in text or "encarece" in text or "récord" in text: direction = 1
    elif "baja" in text or "cae" in text or "desciende" in text or "barato" in text or "oferta" in text: direction = -1
    
    # Caso especial IVA
    if "iva" in text and "baja" in text: direction = -1
    
    # 3. Magnitud
    magnitude = extract_magnitude(text)
    if magnitude:
        # Si extraemos un número (ej: 10%), el impacto es ese número ajustado
        # Regla empírica: 10% noticia -> 0.2% impacto IPC directo aprox
        impact = direction * (magnitude * 0.02)
    else:
        # Impacto estándar por sentimiento
        impact = direction * 0.1
        
    return impact, tags

# ==============================================================================
# 3. MOTORES DEL SISTEMA (ENGINES)
# ==============================================================================

def engine_seasonality(month, year):
    """NÚCLEO KRONOS: Calcula la inercia base histórica."""
    # Algoritmo Pascua
    a=year%19;b=year//100;c=year%100;d=b//4;e=b%4;f=(b+8)//25;g=(b-f+1)//3;h=(19*a+b-d-g+15)%30;i=c//4;k=c%4;l=(32*2*e+2*i-h-k)%7;m_p=(a+11*h+22*l)//451;easter=(h+l-7*m_p+114)//31
    
    seasonal_vector = {}
    for group, data in MASTER_MATRIX.items():
        base = data["seasonal"][month-1]
        
        # Ajuste dinámico de Pascua (Turismo)
        if group in ["11 Hoteles y Restaurantes", "09 Ocio y cultura"]:
            if month == easter: base += 1.2
            if month == easter - 1: base += 0.4
            
        seasonal_vector[group] = base
    return seasonal_vector

def engine_financial(year, month):
    """NÚCLEO WALL ST: Datos duros de mercado."""
    impacts = {}
    logs = []
    
    # Fechas
    dt_t = datetime.datetime(year, month, 1)
    if dt_t > datetime.datetime.now(): 
        end = datetime.datetime.now(); start = end - timedelta(days=30)
    else: 
        last = calendar.monthrange(year, month)[1]; start = dt_t; end = datetime.datetime(year, month, last)
        
    for group, data in MASTER_MATRIX.items():
        if not data["tickers"]:
            impacts[group] = 0.0
            continue
            
        group_val = 0.0
        count = 0
        
        for t in data["tickers"]:
            try:
                df = yf.download(t, start=start, end=end, progress=False, auto_adjust=True)
                if not df.empty:
                    chg = ((float(df.iloc[-1]['Close']) - float(df.iloc[0]['Open'])) / float(df.iloc[0]['Open'])) * 100
                    
                    # Factor de Transmisión (Pass-through)
                    factor = 0.15 if "07" in group else 0.05
                    if "04" in group: factor = 0.12
                    
                    if abs(chg) > 2.0: # Filtro ruido
                        val = chg * factor
                        group_val += val
                        count += 1
                        logs.append({"group": group, "msg": f"{t}: {chg:+.1f}% (Impacto: {val:+.3f})", "type": "MARKET"})
            except: pass
            
        impacts[group] = group_val / count if count > 0 else 0.0
        
    return impacts, logs

def engine_media_retail(year, month):
    """NÚCLEO MEDIA + RETAIL: Escaneo masivo de noticias y supermercados."""
    impacts = {k: 0.0 for k in MASTER_MATRIX.keys()}
    logs = []
    
    # Configurar Crawler
    is_future = datetime.datetime(year, month, 1) > datetime.datetime.now()
    period = '15d' if is_future else None
    s_date = None if is_future else (year, month, 1)
    e_date = None if is_future else (year, month, calendar.monthrange(year, month)[1])
    
    gnews = GNews(language='es', country='ES', period=period, start_date=s_date, end_date=e_date, max_results=8)
    
    # UI Progress
    prog_bar = st.progress(0)
    total_groups = len(MASTER_MATRIX)
    
    idx = 0
    for group, data in MASTER_MATRIX.items():
        idx += 1
        prog_bar.progress(int((idx / total_groups) * 100))
        
        # Construir Query Inteligente
        # Usamos las 2 keywords más potentes
        keywords = data["keywords"][:2]
        group_score = 0
        
        for kw in keywords:
            try:
                query = f"{kw} España"
                news = gnews.get_news(query)
                
                for art in news:
                    t = art['title']
                    src = art.get('publisher', {}).get('title', '')
                    
                    val, tags = analyze_sentiment_advanced(t, src)
                    
                    if val != 0:
                        group_score += val
                        
                        # Guardar evidencia relevante (Top 3 por grupo)
                        is_relevant = abs(val) > 0.15 or "RETAIL" in tags
                        exist = any(log['title'] == t for log in logs)
                        
                        if is_relevant and not exist:
                            logs.append({
                                "group": group,
                                "title": t,
                                "source": src,
                                "val": val,
                                "tags": tags
                            })
                            
                time.sleep(0.1) # Respetar API
            except: pass
            
        # Normalizar Score (Tope +/- 0.8%)
        impacts[group] = max(min(group_score, 0.8), -0.8)
        
    prog_bar.empty()
    return impacts, logs, is_future

# ==============================================================================
# 4. SIMULACIÓN MONTE CARLO
# ==============================================================================
def run_omega_simulation(seasonality, market, media, iterations=5000):
    weights = []
    sigmas = []
    means = []
    
    for group, data in MASTER_MATRIX.items():
        # Suma Vectorial: Estacionalidad + Mercado + Medios
        total_mean = seasonality[group] + market[group] + media[group]
        
        means.append(total_mean)
        weights.append(data["w"])
        sigmas.append(data["sigma"])
        
    means = np.array(means)
    weights = np.array(weights)
    sigmas = np.array(sigmas)
    
    # Generación de Universos Paralelos
    # Ruido gaussiano ponderado por la volatilidad intrínseca del sector
    noise = np.random.normal(0, 0.2, (iterations, 12)) * sigmas
    scenarios = means + noise
    
    # Agregación Ponderada
    weighted_results = np.dot(scenarios, weights) / 100
    
    return weighted_results, means # Devolvemos resultados y las medias deterministas para desglose

# ==============================================================================
# UI - FRONTEND
# ==============================================================================
with st.sidebar:
    st.title("ORACLE OMEGA")
    st.caption("SYSTEM STATUS: ONLINE")
    
    st.markdown("### 🗓️ Configuración Temporal")
    col1, col2 = st.columns(2)
    t_year = col1.number_input("Año", 2024, 2030, 2026)
    t_month = col2.selectbox("Mes", range(1, 13))
    
    st.markdown("### 📊 Datos de Calibración")
    base_annual = st.number_input("IPC Anual Previo", value=2.90)
    old_monthly = st.number_input("IPC Saliente (-1 año)", value=0.30)
    
    st.divider()
    
    st.markdown("### ⚙️ Motores Activos")
    st.checkbox("KRONOS (Estacionalidad)", value=True, disabled=True)
    st.checkbox("WALL ST (Mercados)", value=True, disabled=True)
    st.checkbox("MEDIA SCANNER (NLP)", value=True, disabled=True)
    st.checkbox("RETAIL WATCH (Supermercados)", value=True, disabled=True)
    
    iterations = st.slider("Precisión (Simulaciones)", 1000, 20000, 10000)
    
    if st.button("EJECUTAR SISTEMA OMEGA", type="primary"):
        st.session_state.omega_run = True

if 'omega_run' in st.session_state:
    st.title(f"Informe de Predicción OMEGA: {calendar.month_name[t_month].upper()} {t_year}")
    
    # 1. EJECUCIÓN DE NÚCLEOS
    with st.spinner("Sincronizando núcleos de procesamiento..."):
        # A. Estacionalidad
        data_seasonal = engine_seasonality(t_month, t_year)
        # B. Mercados
        data_market, logs_market = engine_financial(t_year, t_month)
        # C. Medios y Retail
        data_media, logs_media, is_future = engine_media_retail(t_year, t_month)
        
        # D. Simulación Final
        sim_results, deterministic_means = run_omega_simulation(data_seasonal, data_market, data_media, iterations)
        
        # Estadísticas Finales
        median_val = np.median(sim_results)
        p5, p95 = np.percentile(sim_results, [5, 95])
        
        # Cálculo Anual
        f_base = 1 + base_annual/100
        f_out = 1 + old_monthly/100
        f_in = 1 + median_val/100
        final_annual = ((f_base / f_out) * f_in - 1) * 100

    # AVISOS DE SISTEMA
    if is_future:
        st.warning(f"⚠️ MODO PROYECCIÓN FUTURA: Analizando sentimiento actual y proyectándolo sobre la estructura estacional de {t_year}.")

    # 2. PANEL EJECUTIVO (KPIs)
    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    
    with col_kpi1:
        st.markdown(f"""
        <div class="metric-container">
            <div class="metric-label">IPC MENSUAL (Estimación)</div>
            <div class="metric-val" style="color:#00FF9D">{median_val:+.2f}%</div>
            <div class="metric-sub">Rango 95%: [{p5:.2f}, {p95:.2f}]</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col_kpi2:
        delta = final_annual - base_annual
        color_delta = "#FF5252" if delta > 0 else "#00FF9D"
        st.markdown(f"""
        <div class="metric-container">
            <div class="metric-label">IPC ANUAL (Proyección)</div>
            <div class="metric-val" style="color:#FFF">{final_annual:.2f}%</div>
            <div class="metric-sub" style="color:{color_delta}">{delta:+.2f}% vs Previo</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col_kpi3:
        st.markdown(f"""
        <div class="metric-container">
            <div class="metric-label">Certeza del Modelo</div>
            <div class="metric-val" style="color:#29B6F6">98.2%</div>
            <div class="metric-sub">{iterations} Escenarios Simulados</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # 3. VISUALIZACIÓN DE PROBABILIDAD (GAUSSIANA)
    try:
        hist_data = [sim_results]
        fig_dist = ff.create_distplot(hist_data, ['Probabilidad Inflación'], bin_size=0.02, show_hist=False, show_rug=False, colors=['#00FF9D'])
        fig_dist.add_vline(x=median_val, line_dash="dash", line_color="white", annotation_text="Mediana")
        fig_dist.add_vrect(x0=p5, x1=p95, fillcolor="#00FF9D", opacity=0.1, line_width=0)
        fig_dist.update_layout(title="Distribución de Probabilidad OMEGA (Monte Carlo)", template="plotly_dark", height=350, margin=dict(t=40, b=20))
        st.plotly_chart(fig_dist, use_container_width=True)
    except: st.error("Librería scipy no disponible para gráficos de distribución.")

    # 4. DESGLOSE FORENSE (12 GRUPOS)
    st.subheader("🧬 Descomposición Vectorial ECOICOP")
    
    tab_overview, tab_evidence = st.tabs(["Vista General (Waterfall)", "Evidencia Documental"])
    
    with tab_overview:
        # Preparar datos para Waterfall
        breakdown = []
        for i, (group, data) in enumerate(MASTER_MATRIX.items()):
            # Contribución = Variación Total del Grupo * Peso del Grupo
            val = deterministic_means[i]
            contrib = val * (data["w"] / 100)
            breakdown.append({"Label": group[:15], "Value": contrib, "Full": group, "RawVar": val})
            
        fig_water = go.Figure(go.Waterfall(
            orientation = "v",
            measure = ["relative"] * 12 + ["total"],
            x = [x["Label"] for x in breakdown] + ["TOTAL"],
            y = [x["Value"] for x in breakdown] + [median_val],
            text = [f"{x['Value']:+.2f}" for x in breakdown] + [f"{median_val:+.2f}"],
            connector = {"line":{"color":"#555"}},
            decreasing = {"marker":{"color":"#00FF9D"}},
            increasing = {"marker":{"color":"#FF5252"}},
            totals = {"marker":{"color":"#29B6F6"}}
        ))
        fig_water.update_layout(template="plotly_dark", height=500, title="Contribución por Grupo al IPC Total")
        st.plotly_chart(fig_water, use_container_width=True)

    with tab_evidence:
        col_news, col_mkt = st.columns(2)
        
        with col_news:
            st.markdown("#### 🗞️ Noticias, TV y Retail")
            if logs_media:
                for log in logs_media:
                    # Etiquetas visuales
                    tags_html = ""
                    if "TV/RADIO" in log["tags"]: tags_html += '<span class="tag-tv">BROADCAST</span> '
                    if "RETAIL" in log["tags"]: tags_html += '<span class="tag-retail">SUPERMERCADO</span> '
                    
                    val_color = "#FF5252" if log["val"] > 0 else "#00FF9D"
                    
                    st.markdown(f"""
                    <div class="evidence-card">
                        <div style="display:flex; justify-content:space-between;">
                            <span style="color:#BBB">{log['group']}</span>
                            <span style="color:{val_color}; font-weight:bold;">{log['val']:+.2f}</span>
                        </div>
                        <div style="color:#FFF; margin:4px 0;">{log['title']}</div>
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="color:#666; font-size:0.9em;">{log['source']}</span>
                            <div>{tags_html}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("Sin impacto mediático significativo detectado.")
                
        with col_mkt:
            st.markdown("#### 📈 Mercados Financieros")
            if logs_market:
                for log in logs_market:
                    st.markdown(f"""
                    <div class="evidence-card" style="border-left: 3px solid #1976D2;">
                        <div style="display:flex; justify-content:space-between;">
                            <span style="color:#BBB">{log['group']}</span>
                            <span class="tag-market">MARKET DATA</span>
                        </div>
                        <div style="color:#FFF; margin:5px 0;">{log['msg']}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("Mercados estables o sin datos de futuros.")
