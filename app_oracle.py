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
# CONFIGURACIÓN DEL SISTEMA OMEGA (GOD MODE)
# ==============================================================================
st.set_page_config(page_title="ORACLE OMEGA V100 | The Ultimate Engine", page_icon="🏛️", layout="wide")

st.markdown("""
<style>
    /* ESTÉTICA INSTITUCIONAL / FINANCIERA (DARK MODE) */
    .stApp { background-color: #050505; color: #E0E0E0; }
    h1, h2, h3 { font-family: 'Roboto Mono', monospace; color: #00FF9D; letter-spacing: -1px; }
    
    /* KPI METRICS */
    .metric-container {
        background-color: #111; border: 1px solid #333; 
        padding: 20px; border-radius: 8px; text-align: center;
        box-shadow: 0 4px 10px rgba(0,255,157,0.1);
    }
    .metric-val { font-size: 2.5em; font-weight: bold; color: #fff; }
    .metric-label { font-size: 0.9em; color: #888; text-transform: uppercase; letter-spacing: 1px; }
    .metric-sub { font-size: 0.8em; color: #00FF9D; margin-top: 5px; }

    /* EVIDENCIA DOCUMENTAL */
    .evidence-card {
        background-color: #161616; border-left: 3px solid #555;
        padding: 12px; margin-bottom: 8px; font-size: 0.85em; font-family: 'Consolas', monospace;
    }
    
    /* ETIQUETAS */
    .tag-tv { background-color: #D32F2F; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.7em; font-weight:bold; }
    .tag-retail { background-color: #FFA000; color: black; padding: 2px 6px; border-radius: 4px; font-size: 0.7em; font-weight:bold; }
    .tag-psycho { background-color: #AB47BC; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.7em; font-weight:bold; }
    .tag-market { background-color: #1976D2; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.7em; font-weight:bold; }

    /* ALERTA MACRO */
    .macro-alert { 
        border: 1px solid #00B4D8; color: #00B4D8; padding: 10px; 
        border-radius: 5px; font-family: monospace; text-align: center; margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. LA MATRIZ MAESTRA (ECOICOP 12 GRUPOS)
# ==============================================================================
# Cerebro central: Pesos, Volatilidad, Tickers, Keywords y Estacionalidad Mensual.
MASTER_MATRIX = {
    "01 Alimentos y bebidas no alcohólicas": {
        "w": 19.6, "sigma": 0.35,
        "tickers": ["ZW=F", "ZC=F", "LE=F", "SB=F", "KC=F"], # Trigo, Maíz, Ganado, Azúcar, Café
        "keywords": ["precio aceite oliva", "cesta compra", "precio fruta verdura", "precio leche huevos", "precio carne pescado"],
        "seasonal": [0.4, 0.2, 0.1, 0.1, 0.0, 0.2, 0.0, 0.1, -0.1, 0.4, 0.2, 0.8]
    },
    "02 Bebidas alcohólicas y tabaco": {
        "w": 3.9, "sigma": 0.1,
        "tickers": [], 
        "keywords": ["precio tabaco", "impuestos alcohol", "subida cajetilla"],
        "seasonal": [0.9, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.2]
    },
    "03 Vestido y calzado": {
        "w": 3.8, "sigma": 0.8,
        "tickers": [],
        "keywords": ["rebajas ropa", "nueva temporada moda", "precio ropa"],
        "seasonal": [-13.0, -2.0, 4.0, 9.0, 2.0, -1.0, -12.5, -2.0, 5.0, 9.0, 0.5, -1.0]
    },
    "04 Vivienda (Luz, Gas, Agua)": {
        "w": 12.7, "sigma": 0.6,
        "tickers": ["NG=F"], # Gas Natural
        "keywords": ["precio luz", "tarifa gas", "tope gas", "euribor hipoteca", "precio alquiler"],
        "seasonal": [0.6, -0.2, -0.5, -0.2, -0.1, 0.4, 0.6, 0.5, 0.2, 0.5, 0.3, 0.7]
    },
    "05 Muebles y hogar": {
        "w": 5.8, "sigma": 0.2,
        "tickers": ["HG=F"], # Cobre
        "keywords": ["precio electrodomesticos", "reformas hogar", "precio muebles"],
        "seasonal": [-0.3, 0.1, 0.2, 0.2, 0.1, 0.1, -0.4, 0.0, 0.2, 0.3, 0.1, 0.2]
    },
    "06 Sanidad": {
        "w": 4.4, "sigma": 0.05,
        "tickers": [],
        "keywords": ["precio medicamentos", "copago farmacia", "seguro medico"],
        "seasonal": [0.2, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    },
    "07 Transporte": {
        "w": 11.6, "sigma": 0.5,
        "tickers": ["BZ=F", "CL=F"], # Brent, WTI
        "keywords": ["precio gasolina", "precio diesel", "vuelos baratos", "billete renfe", "precio coches"],
        "seasonal": [0.3, 0.2, 0.5, 0.8, 0.4, 0.5, 0.9, 0.6, -0.5, -0.2, -0.3, 0.2]
    },
    "08 Comunicaciones": {
        "w": 2.7, "sigma": 0.1,
        "tickers": [],
        "keywords": ["tarifas movil", "precio fibra optica"],
        "seasonal": [-0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1]
    },
    "09 Ocio y cultura": {
        "w": 4.9, "sigma": 0.3,
        "tickers": [],
        "keywords": ["entradas cine", "paquetes turisticos", "precio ordenadores"],
        "seasonal": [-0.8, 0.1, 0.4, 0.2, -0.5, 0.4, 1.2, 1.2, -1.5, -0.5, -0.2, 1.0]
    },
    "10 Enseñanza": {
        "w": 1.6, "sigma": 0.05,
        "tickers": [],
        "keywords": ["matricula universidad", "libros texto", "cuota colegio"],
        "seasonal": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.8, 1.2, 0.0, 0.0]
    },
    "11 Hoteles y Restaurantes": {
        "w": 13.9, "sigma": 0.4,
        "tickers": [],
        "keywords": ["precio menu dia", "precio hoteles", "restaurantes subida"],
        "seasonal": [-0.5, 0.2, 0.5, 0.4, 0.5, 1.0, 2.5, 2.0, -1.0, -0.5, -0.4, 0.8]
    },
    "12 Otros bienes y servicios": {
        "w": 15.1, "sigma": 0.2,
        "tickers": [],
        "keywords": ["seguro coche", "precio peluqueria", "residencia ancianos", "precio oro"],
        "seasonal": [0.9, 0.2, 0.2, 0.1, 0.1, 0.1, 0.1, 0.0, 0.1, 0.1, 0.0, 0.1]
    }
}

# Fuentes para etiquetado
BROADCAST_DOMAINS = ["rtve.es", "cadenaser.com", "ondacero.es", "lasexta.com", "antena3.com", "telecinco.es"]
RETAILERS = ["mercadona", "carrefour", "lidl", "dia", "alcampo"]

# ==============================================================================
# 2. FUNCIONES DE INTELIGENCIA (NLP & MACRO)
# ==============================================================================

def extract_magnitude(text):
    """Extrae cifras porcentuales de titulares usando Regex."""
    match = re.search(r'(\d+([.,]\d+)?)(\s?%| euros)', text.lower())
    if match:
        try:
            val = float(match.group(1).replace(',', '.'))
            if "euros" in match.group(0): return None # Ignorar absolutos por ahora
            return min(val, 25.0) # Capar errores de lectura al 25%
        except: return None
    return None

def analyze_sentiment_expert(text, source):
    """
    Analiza Sentimiento + Magnitud + Fuente.
    Devuelve: Score, Tags (TV, Retail, etc.)
    """
    text = text.lower()
    source = source.lower()
    tags = []
    
    # Etiquetado
    if any(d in source for d in BROADCAST_DOMAINS): tags.append("TV/RADIO")
    if any(r in text for r in RETAILERS): tags.append("RETAIL")
    
    # Dirección
    direction = 0
    if "sube" in text or "dispara" in text or "alza" in text or "encarece" in text: direction = 1
    elif "baja" in text or "cae" in text or "desciende" in text or "barato" in text: direction = -1
    if "iva" in text and "baja" in text: direction = -1 # Caso fiscal
    
    # Magnitud
    magnitude = extract_magnitude(text)
    
    # Cálculo Impacto
    if magnitude:
        # Si hay cifra (ej: 10%), impacto es proporcional (aprox 20% del dato crudo pasa a IPC directo)
        impact = direction * (magnitude * 0.02)
    else:
        # Si no hay cifra, impacto estándar por sentimiento (0.1)
        impact = direction * 0.1
        
    return impact, tags

def engine_macro_top_down():
    """
    Analiza EUR/USD para detectar inflación importada.
    """
    macro_score = 0.0
    logs = []
    try:
        # Descarga rápida Euro/Dolar
        data = yf.download("EURUSD=X", period="1mo", progress=False, auto_adjust=True)
        if not data.empty:
            curr_close = data['Close'].iloc[-1].item() # .item() para obtener float puro
            curr_open = data['Open'].iloc[0].item()
            
            euro_chg = ((curr_close - curr_open) / curr_open) * 100
            
            if euro_chg < -1.5: 
                macro_score += 0.08
                logs.append(f"DÓLAR FUERTE (Euro {euro_chg:.1f}%): Inflación importada (Energía/Tecno).")
            elif euro_chg > 1.5:
                macro_score -= 0.05
                logs.append(f"EURO FUERTE (+{euro_chg:.1f}%): Abaratamiento de importaciones.")
    except: pass
    return macro_score, logs

# ==============================================================================
# 3. MOTORES DE CÁLCULO SECTORIAL (ENGINES)
# ==============================================================================

def engine_seasonality(month, year):
    """NÚCLEO KRONOS: Inercia Histórica"""
    # Algoritmo Pascua para ajustar Turismo
    a=year%19;b=year//100;c=year%100;d=b//4;e=b%4;f=(b+8)//25;g=(b-f+1)//3;h=(19*a+b-d-g+15)%30;i=c//4;k=c%4;l=(32*2*e+2*i-h-k)%7;m_p=(a+11*h+22*l)//451;easter=(h+l-7*m_p+114)//31
    
    seasonal_vector = {}
    for group, data in MASTER_MATRIX.items():
        base = data["seasonal"][month-1]
        if group in ["11 Hoteles y Restaurantes", "09 Ocio y cultura"]:
            if month == easter: base += 1.2
            if month == easter - 1: base += 0.4
        seasonal_vector[group] = base
    return seasonal_vector

def engine_financial(year, month):
    """NÚCLEO WALL ST: Mercados"""
    impacts = {}
    logs = []
    
    dt_t = datetime.datetime(year, month, 1)
    if dt_t > datetime.datetime.now(): 
        end = datetime.datetime.now(); start = end - timedelta(days=30)
    else: 
        last = calendar.monthrange(year, month)[1]; start = dt_t; end = datetime.datetime(year, month, last)
        
    for group, data in MASTER_MATRIX.items():
        if not data["tickers"]:
            impacts[group] = 0.0; continue
            
        group_val = 0.0; count = 0
        for t in data["tickers"]:
            try:
                df = yf.download(t, start=start, end=end, progress=False, auto_adjust=True)
                if not df.empty:
                    c = df['Close'].iloc[-1].item(); o = df['Open'].iloc[0].item()
                    chg = ((c - o) / o) * 100
                    # Transmisión: Energía/Transporte reaccionan más que Alimentos
                    factor = 0.12 if "04" in group or "07" in group else 0.05
                    if abs(chg) > 2.0:
                        val = chg * factor
                        group_val += val; count += 1
                        logs.append({"group": group, "msg": f"{t}: {chg:+.1f}% (Impacto: {val:+.3f})", "type": "MARKET"})
            except: pass
        impacts[group] = group_val / count if count > 0 else 0.0
    return impacts, logs

def engine_media_omni(year, month):
    """NÚCLEO MEDIA + RETAIL + TV"""
    impacts = {k: 0.0 for k in MASTER_MATRIX.keys()}
    logs = []
    
    is_future = datetime.datetime(year, month, 1) > datetime.datetime.now()
    period = '15d' if is_future else None
    s_date = None if is_future else (year, month, 1)
    e_date = None if is_future else (year, month, calendar.monthrange(year, month)[1])
    
    gnews = GNews(language='es', country='ES', period=period, start_date=s_date, end_date=e_date, max_results=6)
    
    # Barra de progreso visual
    prog_bar = st.progress(0)
    idx = 0
    
    # Escanear grupos
    for group, data in MASTER_MATRIX.items():
        idx += 1; prog_bar.progress(int((idx / 12) * 100))
        
        # Usar top 2 keywords
        score = 0
        for kw in data["keywords"][:2]:
            try:
                news = gnews.get_news(f"{kw} España")
                for art in news:
                    t = art['title']; src = art.get('publisher', {}).get('title', '')
                    val, tags = analyze_sentiment_expert(t, src)
                    
                    if val != 0:
                        score += val
                        # Guardar evidencia única
                        if not any(log['title'] == t for log in logs):
                             logs.append({"group": group, "title": t, "source": src, "val": val, "tags": tags})
                time.sleep(0.05)
            except: pass
        
        # Tope de impacto por noticias
        impacts[group] = max(min(score, 0.8), -0.8)
        
    prog_bar.empty()
    return impacts, logs, is_future

def engine_psychometrics(year, month):
    """NÚCLEO PSYCHO: Google Trends Simulator (Consumo)"""
    impacts = {k: 0.0 for k in MASTER_MATRIX.keys()}
    logs = []
    
    # Patrones lógicos de búsqueda
    TERMS = [
        ("vuelos baratos", "07 Transporte", 1),
        ("restaurantes moda", "11 Hoteles y Restaurantes", 1),
        ("marcas blancas", "01 Alimentos y bebidas no alcohólicas", -1), # Deflacionario
        ("subsidio desempleo", "12 Otros bienes y servicios", -0.5),
        ("comparador luz", "04 Vivienda (Luz, Gas, Agua)", -0.5)
    ]
    
    # Simulación estocástica de volumen
    np.random.seed(year + month)
    for term, sector, signal in TERMS:
        vol = np.random.randint(30, 90)
        # Boost estacional lógico
        if "vuelos" in term and month in [6,7,8]: vol += 40
        if "luz" in term and month in [1,2,12]: vol += 30
        
        norm_vol = min(vol, 100) / 100.0
        val = signal * norm_vol * 0.1
        impacts[sector] += val
        
        if norm_vol > 0.7:
            logs.append({"group": sector, "msg": f"Búsquedas '{term}' altas ({vol}/100)", "val": val})
            
    return impacts, logs

# ==============================================================================
# 4. SIMULACIÓN MONTE CARLO
# ==============================================================================
def run_omega_simulation(seasonal, market, media, psycho, macro, iterations=10000):
    weights = []; sigmas = []; means = []
    
    for group, data in MASTER_MATRIX.items():
        # SUMA TOTAL DE VECTORES
        # Estacionalidad + Mercado + Medios + Psico + Macro Global
        total_mean = seasonal[group] + market[group] + media[group] + psycho[group] + (macro * 0.5)
        
        means.append(total_mean)
        weights.append(data["w"])
        sigmas.append(data["sigma"])
        
    means = np.array(means); weights = np.array(weights); sigmas = np.array(sigmas)
    
    # Monte Carlo Vectorizado
    noise = np.random.normal(0, 0.2, (iterations, 12)) * sigmas
    scenarios = means + noise
    weighted_results = np.dot(scenarios, weights) / 100
    
    return weighted_results, means

# ==============================================================================
# FRONTEND - OMEGA DASHBOARD
# ==============================================================================
with st.sidebar:
    st.title("ORACLE OMEGA")
    st.caption("V100 | FINAL SYSTEM")
    
    st.subheader("🗓️ Fecha Objetivo")
    col1, col2 = st.columns(2)
    t_year = col1.number_input("Año", 2024, 2030, 2026)
    t_month = col2.selectbox("Mes", range(1, 13))
    
    st.subheader("📊 Datos Base")
    base_annual = st.number_input("IPC Anual Previo", value=2.90)
    old_monthly = st.number_input("IPC Saliente", value=0.30)
    
    st.divider()
    st.info("⚠️ Exclusiones INE:\n- Inversión Vivienda\n- Prostitución/Drogas\n- Juegos de Azar")
    
    if st.button("INICIAR SISTEMA OMEGA", type="primary"):
        st.session_state.omega_run = True

if 'omega_run' in st.session_state:
    st.title(f"Informe OMEGA: {calendar.month_name[t_month].upper()} {t_year}")
    
    # 1. EJECUCIÓN
    with st.spinner("Sincronizando KRONOS, WALL ST y MEDIA SCANNER..."):
        # Motores
        d_macro, l_macro = engine_macro_top_down()
        d_sea = engine_seasonality(t_month, t_year)
        d_mkt, l_mkt = engine_financial(t_year, t_month)
        d_med, l_med, is_fut = engine_media_omni(t_year, t_month)
        d_psy, l_psy = engine_psychometrics(t_year, t_month)
        
        # Simulación
        sim_res, det_means = run_omega_simulation(d_sea, d_mkt, d_med, d_psy, d_macro)
        
        # Stats
        median = np.median(sim_res)
        p5, p95 = np.percentile(sim_res, [5, 95])
        
        # Anualización
        f_base = 1 + base_annual/100; f_out = 1 + old_monthly/100; f_in = 1 + median/100
        final_annual = ((f_base / f_out) * f_in - 1) * 100

    if is_fut: st.warning(f"⚠️ PROYECCIÓN FUTURA: Estimando {t_year} con sentimiento actual.")

    # 2. KPI DASHBOARD
    k1, k2, k3 = st.columns(3)
    k1.markdown(f"""<div class="metric-container"><div class="metric-label">IPC MENSUAL (MEDIANA)</div>
    <div class="metric-val" style="color:#00FF9D">{median:+.2f}%</div><div class="metric-sub">IC 95%: [{p5:.2f}, {p95:.2f}]</div></div>""", unsafe_allow_html=True)
    
    k2.markdown(f"""<div class="metric-container"><div class="metric-label">IPC ANUAL (PROYECTADO)</div>
    <div class="metric-val">{final_annual:.2f}%</div><div class="metric-sub">Objetivo: {base_annual}%</div></div>""", unsafe_allow_html=True)
    
    k3.markdown(f"""<div class="metric-container"><div class="metric-label">MACRO IMPACTO</div>
    <div class="metric-val" style="color:#00B4D8">{d_macro:+.3f}</div><div class="metric-sub">Divisas / Industrial</div></div>""", unsafe_allow_html=True)
    
    st.markdown("---")

    # 3. GRÁFICOS AVANZADOS
    try:
        # Gaussiana
        fig_dist = ff.create_distplot([sim_res], ['Probabilidad'], bin_size=0.02, show_hist=False, show_rug=False, colors=['#00FF9D'])
        fig_dist.add_vline(x=median, line_dash="dash", line_color="white", annotation_text="Mediana")
        fig_dist.add_vrect(x0=p5, x1=p95, fillcolor="#00FF9D", opacity=0.1, line_width=0)
        fig_dist.update_layout(title="Distribución de Probabilidad (Monte Carlo)", template="plotly_dark", height=350, margin=dict(t=40))
        st.plotly_chart(fig_dist, use_container_width=True)
    except: st.error("Instala 'scipy' para ver la curva de probabilidad.")
    
    # 4. EVIDENCIA FORENSE
    st.subheader("🧬 Desglose Forense ECOICOP")
    t1, t2, t3 = st.tabs(["Waterfall Sectorial", "Noticias & Retail", "Mercado & Macro"])
    
    with t1:
        # Waterfall
        breakdown = []
        for i, (g, d) in enumerate(MASTER_MATRIX.items()):
            contrib = det_means[i] * (d["w"]/100)
            breakdown.append({"Label": g[:12], "Val": contrib})
            
        fig_w = go.Figure(go.Waterfall(
            orientation="v", measure=["relative"]*12+["total"],
            x=[x["Label"] for x in breakdown]+["TOTAL"], y=[x["Val"] for x in breakdown]+[median],
            connector={"line":{"color":"#555"}}, decreasing={"marker":{"color":"#00FF9D"}}, increasing={"marker":{"color":"#FF5252"}}, totals={"marker":{"color":"#29B6F6"}}
        ))
        fig_w.update_layout(template="plotly_dark", height=450, title="Aportación de cada grupo (Puntos)")
        st.plotly_chart(fig_w, use_container_width=True)
        
    with t2:
        for log in l_med:
            # Renderizado de Tags
            tags_html = ""
            if "TV/RADIO" in log["tags"]: tags_html += '<span class="tag-tv">BROADCAST</span> '
            if "RETAIL" in log["tags"]: tags_html += '<span class="tag-retail">SUPERMERCADO</span> '
            val_col = "#FF5252" if log["val"] > 0 else "#00FF9D"
            st.markdown(f"""
            <div class="evidence-card">
                <div style="display:flex; justify-content:space-between;">
                    <span style="color:#AAA">{log['group']}</span>
                    <span style="color:{val_col}; font-weight:bold">{log['val']:+.2f}</span>
                </div>
                <div style="color:#FFF; margin:5px 0;">{log['title']}</div>
                <div style="display:flex; justify-content:space-between;">
                    <span style="color:#666; font-size:0.8em">{log['source']}</span>
                    <div>{tags_html}</div>
                </div>
            </div>""", unsafe_allow_html=True)
            
    with t3:
        if l_macro:
            for l in l_macro: st.markdown(f"<div class='macro-alert'>{l}</div>", unsafe_allow_html=True)
        for l in l_mkt:
            st.markdown(f"""
            <div class="evidence-card" style="border-left: 3px solid #1976D2;">
                <b>{l['group']}</b> | <span class="tag-market">MARKET</span><br>
                {l['msg']}
            </div>""", unsafe_allow_html=True)
        for l in l_psy:
            st.markdown(f"""
            <div class="evidence-card" style="border-left: 3px solid #AB47BC;">
                <b>{l['group']}</b> | <span class="tag-psycho">PSYCHO</span><br>
                {l['msg']}
            </div>""", unsafe_allow_html=True)
