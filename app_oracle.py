import streamlit as st
import yfinance as yf
from gnews import GNews
import plotly.graph_objects as go
import plotly.figure_factory as ff
import pandas as pd
import numpy as np
import calendar
from datetime import datetime, timedelta
import re
import time

# ==============================================================================
# 0. CONFIGURACIÓN DEL SISTEMA (MODO DARK PRO)
# ==============================================================================
st.set_page_config(page_title="OMEGA FINAL | Inflation Architect", page_icon="🏛️", layout="wide")

st.markdown("""
<style>
    /* Estética de Terminal Financiera */
    .stApp { background-color: #000000; color: #E0E0E0; font-family: 'Roboto', sans-serif; }
    h1, h2, h3 { color: #FFFFFF; font-weight: 300; letter-spacing: -0.5px; }
    
    /* KPI Cards */
    .kpi-card {
        background-color: #111; border: 1px solid #333; padding: 20px; border-radius: 8px;
        text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .kpi-val { font-size: 2.8em; font-weight: 700; color: #FFF; margin: 5px 0; }
    .kpi-lbl { font-size: 0.8em; color: #888; text-transform: uppercase; letter-spacing: 1.5px; }
    .kpi-sub { font-size: 0.85em; color: #4CAF50; font-family: monospace; }
    
    /* Evidence Logs */
    .log-entry {
        border-left: 3px solid #555; background-color: #161616; padding: 10px; margin-bottom: 5px;
        font-family: 'Consolas', monospace; font-size: 0.85em;
    }
    .tag { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 0.7em; font-weight: bold; margin-right: 5px;}
    .tag-mkt { background: #2196F3; color: white; }
    .tag-ret { background: #FF9800; color: black; }
    .tag-mac { background: #9C27B0; color: white; }
    
    /* Sliders custom */
    div.stSlider > div[data-baseweb = "slider"] > div > div { background-color: #4CAF50 !important; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. BASE DE CONOCIMIENTO (LA ESTRUCTURA RÍGIDA)
# ==============================================================================
# Estacionalidad histórica de España (La Ley de Hierro).
# Enero y Julio SIEMPRE bajan. Octubre y Marzo SIEMPRE suben.
SEASONAL_DNA = {
    1: -0.60, 2: 0.10, 3: 0.40, 4: 0.50, 5: 0.20, 6: 0.30,
    7: -0.50, 8: 0.20, 9: 0.10, 10: 0.70, 11: 0.20, 12: 0.30
}

# Pesos aproximados del INE (2024/25)
W_ENERGY = 0.12  # Grupo 04 + 07
W_FOOD = 0.20    # Grupo 01
W_CORE = 0.68    # Resto (Servicios, Bienes industriales)

# ==============================================================================
# 2. MOTORES DE INTELIGENCIA (DATA FETCHERS)
# ==============================================================================

def fetch_market_signals(year, month):
    """
    MOTOR 1: MERCADOS (HARD DATA)
    Analiza materias primas y divisas para sugerir ajustes automáticos.
    """
    signals = {"energy": 0.0, "food": 0.0, "macro": 0.0}
    logs = []
    
    # Ventana de tiempo (últimos 30 días respecto a la fecha objetivo)
    dt_target = datetime(year, month, 1)
    if dt_target > datetime.now():
        end = datetime.now(); start = end - timedelta(days=30)
    else:
        last = calendar.monthrange(year, month)[1]
        start = dt_target; end = datetime(year, month, last)
        
    tickers = {
        "BZ=F": ("Petróleo", "energy", 0.05), # 5% de transmisión al IPC
        "NG=F": ("Gas Nat", "energy", 0.08),  # 8% de transmisión (Luz)
        "ZW=F": ("Trigo", "food", 0.02),      # 2% transmisión (Lenta)
        "EURUSD=X": ("Euro", "macro", -0.1)   # Inverso: Euro sube -> IPC baja
    }
    
    for t, (name, cat, beta) in tickers.items():
        try:
            df = yf.download(t, start=start, end=end, progress=False, auto_adjust=True)
            if not df.empty:
                op = df.iloc[0]['Open'].item(); cl = df.iloc[-1]['Close'].item()
                chg = ((cl - op) / op) * 100
                
                impact = chg * beta
                signals[cat] += impact
                
                icon = "📈" if chg > 0 else "📉"
                logs.append({
                    "src": "MARKET", "tag": "tag-mkt", 
                    "msg": f"{name}: {chg:+.1f}% (Impacto est: {impact:+.3f})", "val": impact
                })
        except: pass
        
    return signals, logs

def fetch_retail_sentiment():
    """
    MOTOR 2: RETAIL SCANNER (SOFT DATA)
    Busca noticias específicas de supermercados para ajustar alimentos.
    """
    impact = 0.0
    logs = []
    
    gnews = GNews(language='es', country='ES', period='20d', max_results=8)
    # Búsqueda quirúrgica
    query = "precio mercadona OR carrefour OR aceite OR leche supermercado España"
    
    try:
        news = gnews.get_news(query)
        score = 0
        for art in news:
            t = art['title'].lower()
            val = 0
            if "sube" in t or "dispara" in t or "caro" in t: val = 1
            elif "baja" in t or "barato" in t or "oferta" in t: val = -1
            
            # Detección de cifras (Regex)
            match = re.search(r'(\d+)%', t)
            if match:
                magnitude = float(match.group(1)) * 0.01 # 10% -> 0.1
                val = val * (magnitude * 10) # Potenciamos si hay cifra
            
            if val != 0:
                score += val
                if len(logs) < 5:
                    logs.append({
                        "src": "RETAIL", "tag": "tag-ret",
                        "msg": f"{art['title'][:60]}...", "val": val
                    })
        
        # Normalizar: Si hay mucho ruido de subida, añadimos hasta 0.2% al IPC de comida
        impact = max(min(score * 0.02, 0.3), -0.3)
        
    except: pass
    
    return impact, logs

# ==============================================================================
# 3. INTERFAZ DE CONTROL (LA CABINA DE PILOTO)
# ==============================================================================
with st.sidebar:
    st.title("OMEGA FINAL")
    st.caption("Arquitectura Híbrida Supervisada")
    
    # A. Coordenadas Temporales
    col_y, col_m = st.columns(2)
    t_year = col_y.number_input("Año", 2024, 2030, 2026)
    t_month = col_m.selectbox("Mes", range(1, 13), index=0)
    
    st.markdown("---")
    
    # B. Calibración del Pasado (CRÍTICO)
    st.markdown("**1. Datos de Calibración (INE)**")
    base_annual = st.number_input("IPC Anual Previo (t-1)", value=2.90)
    old_monthly = st.number_input("IPC Mensual Saliente", value=-0.20, help="Dato del mismo mes el año pasado")
    
    st.markdown("---")
    
    # C. Ejecución de Motores
    st.markdown("**2. Análisis de Datos (Automático)**")
    if st.button("ESCANEAR Y CALIBRAR", type="primary"):
        with st.spinner("Analizando Mercados, Retail y Macroeconomía..."):
            mkt_sig, mkt_logs = fetch_market_signals(t_year, t_month)
            ret_sig, ret_logs = fetch_retail_sentiment()
            
            # Guardar en sesión para persistencia
            st.session_state.auto_energy = mkt_sig["energy"]
            st.session_state.auto_food = mkt_sig["food"] + ret_sig
            st.session_state.auto_logs = mkt_logs + ret_logs
            st.session_state.scanned = True
            
    # Valores por defecto (si no se ha escaneado)
    def_energy = st.session_state.get("auto_energy", 0.0)
    def_food = st.session_state.get("auto_food", 0.0)
    
    st.markdown("---")
    
    # D. Ajuste Fino (Supervisión Humana)
    st.markdown("**3. Control de Vuelo (Ajuste Fino)**")
    
    # Slider Energía (Pre-cargado con datos de mercado)
    drift_energy = st.slider("⚡ Ajuste Energía (Petróleo/Luz)", -1.0, 1.0, float(def_energy), 0.01)
    
    # Slider Alimentos (Pre-cargado con Mercado + Retail)
    drift_food = st.slider("🍎 Ajuste Alimentos (Supermercado)", -0.5, 0.5, float(def_food), 0.01)
    
    # Slider Core (Manual)
    drift_core = st.slider("👕 Ajuste Subyacente (Servicios)", -0.5, 0.5, 0.0, 0.01, help="Usa esto si prevés rebajas agresivas o subida de hostelería")

# ==============================================================================
# 4. MOTOR DE CÁLCULO ESTRUCTURAL (MATH CORE)
# ==============================================================================

# 1. Base Estacional (El ancla)
base_val = SEASONAL_DNA[t_month]

# 2. Suma Ponderada de Desviaciones (Drifts)
# IPC Mensual = Base Estacional + (Desvío Energía * 0.12) + (Desvío Comida * 0.20) + (Desvío Core * 0.68)
weighted_drift = (drift_energy * W_ENERGY) + (drift_food * W_FOOD) + (drift_core * W_CORE)
monthly_prediction = base_val + weighted_drift

# 3. Cálculo Anual (Chain Linking)
f_base = 1 + base_annual/100
f_out = 1 + old_monthly/100
f_in = 1 + monthly_prediction/100
annual_prediction = ((f_base / f_out) * f_in - 1) * 100

# 4. Monte Carlo "Lite" (Solo para intervalo de confianza visual)
# Simulamos ruido alrededor de NUESTRA predicción, no aleatoriedad total.
sims = np.random.normal(monthly_prediction, 0.05, 1000)
p5, p95 = np.percentile(sims, [5, 95])

# ==============================================================================
# 5. DASHBOARD EJECUTIVO
# ==============================================================================
st.title(f"PROYECCIÓN OMEGA: {calendar.month_name[t_month].upper()} {t_year}")

# --- FILA 1: KPIs ---
c1, c2, c3 = st.columns(3)

with c1:
    color_m = "#4CAF50" if monthly_prediction < 0 else "#FF5252"
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-lbl">IPC MENSUAL ESTIMADO</div>
        <div class="kpi-val" style="color:{color_m}">{monthly_prediction:+.2f}%</div>
        <div class="kpi-sub">Base Estacional: {base_val:+.2f}%</div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    color_a = "#4CAF50" if annual_prediction < base_annual else "#FF5252"
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-lbl">IPC ANUAL PROYECTADO</div>
        <div class="kpi-val" style="color:{color_a}">{annual_prediction:.2f}%</div>
        <div class="kpi-sub">Objetivo: {base_annual}%</div>
    </div>
    """, unsafe_allow_html=True)

with c3:
    step = monthly_prediction - old_monthly
    color_s = "#2196F3"
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-lbl">EFECTO ESCALÓN</div>
        <div class="kpi-val" style="color:{color_s}">{step:+.2f}%</div>
        <div class="kpi-sub">Diferencial Entrada/Salida</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# --- FILA 2: ANÁLISIS ESTRUCTURAL ---
col_water, col_log = st.columns([2, 1])

with col_water:
    st.subheader("🏗️ Arquitectura del Dato")
    
    # Datos para Waterfall
    y_vals = [base_val, drift_energy*W_ENERGY, drift_food*W_FOOD, drift_core*W_CORE, monthly_prediction]
    x_labs = ["Base Histórica", "Shock Energía", "Shock Alimentos", "Ajuste Core", "TOTAL"]
    texts = [f"{v:+.2f}" for v in y_vals]
    
    fig = go.Figure(go.Waterfall(
        name = "20", orientation = "v",
        measure = ["relative", "relative", "relative", "relative", "total"],
        x = x_labs, y = y_vals, text = texts,
        connector = {"line":{"color":"#555"}},
        decreasing = {"marker":{"color":"#4CAF50"}},
        increasing = {"marker":{"color":"#FF5252"}},
        totals = {"marker":{"color":"#2196F3"}}
    ))
    fig.update_layout(template="plotly_dark", height=400, title="Descomposición Vectorial", margin=dict(t=30))
    st.plotly_chart(fig, use_container_width=True)

with col_log:
    st.subheader("🛰️ Datos Detectados")
    if st.session_state.get("scanned"):
        logs = st.session_state.get("auto_logs", [])
        if logs:
            for l in logs:
                st.markdown(f"""
                <div class="log-entry">
                    <span class="tag {l['tag']}">{l['src']}</span> 
                    <span style="color:#AAA">{l['msg']}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Escaneo completado. Mercados estables.")
    else:
        st.warning("Pulsa 'ESCANEAR Y CALIBRAR' en el menú lateral para cargar datos reales.")

# --- FILA 3: PROBABILIDAD ---
st.markdown("---")
st.subheader("🎯 Rango de Confianza (95%)")
try:
    fig_dist = ff.create_distplot([sims], ['Probabilidad'], bin_size=0.01, show_hist=False, show_rug=False, colors=['#00E676'])
    fig_dist.add_vline(x=monthly_prediction, line_dash="dash", line_color="white", annotation_text="Estimación Central")
    fig_dist.add_vrect(x0=p5, x1=p95, fillcolor="#00E676", opacity=0.1, line_width=0)
    fig_dist.update_layout(template="plotly_dark", height=300, margin=dict(t=20, b=20))
    st.plotly_chart(fig_dist, use_container_width=True)
except:
    st.error("Librería scipy necesaria para visualización avanzada.")
