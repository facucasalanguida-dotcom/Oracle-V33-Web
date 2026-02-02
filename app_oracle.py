import streamlit as st
import yfinance as yf
from gnews import GNews
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import calendar
from datetime import datetime, timedelta
import re
import time

# ==============================================================================
# CONFIGURACIÓN DEL SISTEMA V200 (MOMENTUM ARCHITECT)
# ==============================================================================
st.set_page_config(page_title="ORACLE V200 | Momentum", page_icon="🧿", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #080808; color: #E0E0E0; font-family: 'Inter', sans-serif; }
    h1, h2, h3 { color: #FFFFFF; font-weight: 400; letter-spacing: -0.5px; }
    
    /* KPI Cards High Precision */
    .kpi-box {
        background: linear-gradient(145deg, #151515, #101010);
        border: 1px solid #333; padding: 20px; border-radius: 12px;
        text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    }
    .kpi-val { font-size: 3.2em; font-weight: 700; color: #FFF; line-height: 1.1; }
    .kpi-lbl { font-size: 0.85em; color: #888; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 10px; }
    .kpi-badge { background-color: #333; color: #CCC; padding: 4px 10px; border-radius: 10px; font-size: 0.75em; }
    
    /* Logs de Evidencia */
    .log-strip {
        border-left: 4px solid #555; background-color: #121212; padding: 12px; margin-bottom: 8px;
        font-family: 'Consolas', monospace; font-size: 0.9em; display: flex; justify-content: space-between;
    }
    .badge-momentum { background-color: #7C4DFF; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.7em;}
    .badge-market { background-color: #00B0FF; color: black; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.7em;}
    .badge-fiscal { background-color: #FF3D00; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.7em;}
    
    /* Ajustes UI */
    div.stSlider > div[data-baseweb = "slider"] > div > div { background-color: #00E676 !important; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. BASE DE CONOCIMIENTO MEJORADA (ESTACIONALIDAD + PESOS)
# ==============================================================================
# Base estacional histórica (Lo que "debería" pasar si no hay noticias)
# Ajustado para ser más sensible a los picos de verano/invierno
SEASONAL_DNA = {
    1: -0.65, 2: 0.15, 3: 0.45, 4: 0.55, 5: 0.25, 6: 0.35,
    7: -0.55, 8: 0.25, 9: 0.15, 10: 0.75, 11: 0.25, 12: 0.35
}

# Pesos IPC 2024/25 (Aprox)
WEIGHTS = {"Energy": 0.12, "Food": 0.20, "Services": 0.45, "Goods": 0.23}

# ==============================================================================
# 2. MOTORES DE ANÁLISIS (DATA FETCHERS)
# ==============================================================================

def fetch_market_momentum(year, month):
    """
    MOTOR 1: MERCADO REAL
    Analiza la variación de precios en la ventana exacta del mes seleccionado.
    """
    signals = {"Energy": 0.0, "Food": 0.0, "Goods": 0.0}
    logs = []
    
    # Definir ventana de análisis
    # Si analizamos Mayo 2025, queremos los datos de Abril-Mayo 2025.
    dt_target = datetime(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    
    if dt_target > datetime.now():
        # Futuro: Usamos los últimos 30 días como proxy de tendencia actual
        end = datetime.now()
        start = end - timedelta(days=30)
        is_projection = True
    else:
        # Pasado: Usamos los datos reales de ese mes
        start = dt_target
        end = datetime(year, month, last_day)
        is_projection = False

    tickers = {
        "BZ=F": ("Petróleo", "Energy", 0.06), # Transmisión directa
        "NG=F": ("Gas Nat", "Energy", 0.09),  # Transmisión a Electricidad
        "ZW=F": ("Trigo", "Food", 0.03),      # Transmisión lenta
        "HG=F": ("Cobre", "Goods", 0.02)      # Transmisión industrial
    }
    
    for t, (name, cat, beta) in tickers.items():
        try:
            df = yf.download(t, start=start, end=end, progress=False, auto_adjust=True)
            if not df.empty:
                op = df.iloc[0]['Open'].item()
                cl = df.iloc[-1]['Close'].item()
                chg = ((cl - op) / op) * 100
                
                impact = chg * beta
                signals[cat] += impact
                
                logs.append({
                    "src": "MERCADO", "tag": "badge-market",
                    "msg": f"{name}: {chg:+.1f}% (Impacto IPC: {impact:+.3f})", "val": impact
                })
        except: pass
        
    return signals, logs, is_projection

def fetch_media_alerts(year, month):
    """
    MOTOR 2: ALERTAS MEDIÁTICAS (Supermercados/Servicios)
    """
    impact = 0.0
    logs = []
    
    # Solo escaneamos si es fecha reciente o futura (GNews no tiene archivo histórico profundo fiable gratis)
    dt_target = datetime(year, month, 1)
    if (datetime.now() - dt_target).days > 60:
        return 0.0, [] # Si es muy antiguo, no buscamos noticias, confiamos en el mercado
        
    gnews = GNews(language='es', country='ES', period='20d', max_results=5)
    
    try:
        # Búsqueda centrada en "Subida de precios"
        news = gnews.get_news("subida precios mercadona OR luz OR gasolina España")
        score = 0
        for art in news:
            t = art['title'].lower()
            val = 0
            if "dispara" in t or "récord" in t: val = 0.05
            elif "baja" in t or "desciende" in t: val = -0.05
            
            if val != 0:
                score += val
                if len(logs) < 3:
                    logs.append({"src": "NOTICIAS", "tag": "badge-fiscal", "msg": art['title'][:70]+"...", "val": val})
                    
        impact = max(min(score, 0.3), -0.3)
    except: pass
    
    return impact, logs

# ==============================================================================
# 3. INTERFAZ DE MANDO (COCKPIT)
# ==============================================================================
with st.sidebar:
    st.title("ORACLE V200")
    st.caption("MOMENTUM ARCHITECT")
    
    # A. TIEMPO
    c1, c2 = st.columns(2)
    t_year = c1.number_input("Año", 2024, 2030, 2025)
    t_month = c2.selectbox("Mes", range(1, 13), index=4) # Por defecto Mayo (5) para tu prueba
    
    st.markdown("---")
    
    # B. CALIBRACIÓN DE INERCIA (LA CLAVE)
    st.markdown("### 🚀 Datos de Inercia")
    st.info("Para corregir el error de 0.7, necesitamos saber cómo venía la economía.")
    
    prev_monthly_cpi = st.number_input("IPC Mes Anterior (t-1)", value=0.40, step=0.01, help="Si el mes pasado fue alto, este tenderá a ser alto.")
    base_annual = st.number_input("IPC Anual Previo (t-1)", value=3.30)
    old_monthly = st.number_input("IPC Saliente (Año pasado)", value=0.30, help="El dato que 'caduca' este mes.")
    
    # C. SHOCK FISCAL (EL ARREGLO MANUAL)
    st.markdown("### ⚡ Eventos Fiscales")
    fiscal_shock = st.selectbox("¿Hay cambios de IVA/Regulación?", 
                                ["Sin cambios", "Fin Rebaja IVA (+Impacto)", "Subida Luz Regulada", "Rebaja Fiscal (-Impacto)"])
    
    fiscal_val = 0.0
    if fiscal_shock == "Fin Rebaja IVA (+Impacto)": fiscal_val = 0.6 # Típico impacto alimentos
    elif fiscal_shock == "Subida Luz Regulada": fiscal_val = 0.4
    elif fiscal_shock == "Rebaja Fiscal (-Impacto)": fiscal_val = -0.5

    st.markdown("---")
    
    if st.button("CALCULAR CON MOMENTUM", type="primary"):
        st.session_state.run_v200 = True

# ==============================================================================
# 4. MOTOR DE CÁLCULO FINAL
# ==============================================================================
if 'run_v200' in st.session_state:
    
    # 1. Obtener Datos
    mkt_sigs, mkt_logs, is_proj = fetch_market_momentum(t_year, t_month)
    med_imp, med_logs = fetch_media_alerts(t_year, t_month)
    
    # 2. Calcular Componentes
    
    # A. Estacionalidad Base
    base_val = SEASONAL_DNA[t_month]
    
    # B. Momentum (Inercia)
    # Si el mes anterior fue 0.4% y la base de ese mes era 0.2%, hay un "exceso" de 0.2%
    # Ese exceso suele arrastrarse un 50% al mes siguiente.
    # (Simplificación econométrica de series temporales AR1)
    momentum_factor = prev_monthly_cpi * 0.4 
    
    # C. Mercado (Energía + Comida)
    market_impact = mkt_sigs["Energy"] + mkt_sigs["Food"] + mkt_sigs["Goods"]
    
    # D. FÓRMULA MAESTRA V200
    # IPC = Base + (Mercado * Peso) + Momentum + Fiscal + Noticias
    predicted_monthly = base_val + market_impact + momentum_factor + fiscal_val + med_imp
    
    # Cálculo Anual
    f_base = 1 + base_annual/100
    f_out = 1 + old_monthly/100
    f_in = 1 + predicted_monthly/100
    predicted_annual = ((f_base / f_out) * f_in - 1) * 100
    
    # ==========================================================================
    # 5. RESULTADOS VISUALES
    # ==========================================================================
    st.title(f"PROYECCIÓN V200: {calendar.month_name[t_month].upper()} {t_year}")
    
    # --- KPIs ---
    col1, col2, col3 = st.columns(3)
    
    with col1:
        color = "#00E676" if predicted_monthly < 0.5 else "#FF1744"
        st.markdown(f"""
        <div class="kpi-box">
            <div class="kpi-lbl">IPC MENSUAL ESTIMADO</div>
            <div class="kpi-val" style="color:{color}">{predicted_monthly:+.2f}%</div>
            <div class="kpi-badge">Base: {base_val:+.2f}% | Momentum: {momentum_factor:+.2f}%</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown(f"""
        <div class="kpi-box">
            <div class="kpi-lbl">IPC ANUAL PROYECTADO</div>
            <div class="kpi-val">{predicted_annual:.2f}%</div>
            <div class="kpi-badge">Objetivo: {base_annual}%</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col3:
        step = predicted_monthly - old_monthly
        color_step = "#2979FF"
        st.markdown(f"""
        <div class="kpi-box">
            <div class="kpi-lbl">EFECTO ESCALÓN</div>
            <div class="kpi-val" style="color:{color_step}">{step:+.2f}%</div>
            <div class="kpi-badge">Dif. Entrada ({predicted_monthly:.2f}) vs Salida ({old_monthly})</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    
    # --- DESGLOSE DE LA PRECISIÓN (WATERFALL) ---
    c_chart, c_log = st.columns([2, 1])
    
    with c_chart:
        st.subheader("🛠️ ¿Cómo hemos corregido el dato?")
        
        # Datos Waterfall
        x_labs = ["Estacionalidad", "Inercia (t-1)", "Mercados", "Shock Fiscal", "Noticias", "PREDICCIÓN"]
        y_vals = [base_val, momentum_factor, market_impact, fiscal_val, med_imp, predicted_monthly]
        texts = [f"{v:+.2f}" for v in y_vals]
        
        fig = go.Figure(go.Waterfall(
            name = "20", orientation = "v",
            measure = ["relative", "relative", "relative", "relative", "relative", "total"],
            x = x_labs, y = y_vals, text = texts,
            connector = {"line":{"color":"#555"}},
            decreasing = {"marker":{"color":"#00E676"}},
            increasing = {"marker":{"color":"#FF1744"}},
            totals = {"marker":{"color":"#2979FF"}}
        ))
        fig.update_layout(template="plotly_dark", height=450, title="Arquitectura del Dato Final", margin=dict(t=40))
        st.plotly_chart(fig, use_container_width=True)
        
    with c_log:
        st.subheader("📝 Bitácora de Ajustes")
        
        # Log Momentum
        st.markdown(f"""
        <div class="log-strip" style="border-left-color: #7C4DFF;">
            <span>Inercia Mes Anterior ({prev_monthly_cpi}%)</span>
            <span class="badge-momentum">+{momentum_factor:.2f} IMPACTO</span>
        </div>""", unsafe_allow_html=True)
        
        # Log Fiscal
        if fiscal_val != 0:
            st.markdown(f"""
            <div class="log-strip" style="border-left-color: #FF3D00;">
                <span>{fiscal_shock}</span>
                <span class="badge-fiscal">{fiscal_val:+.2f} MANUAL</span>
            </div>""", unsafe_allow_html=True)
            
        # Logs Mercado
        for l in mkt_logs:
            st.markdown(f"""
            <div class="log-strip" style="border-left-color: #00B0FF;">
                <span>{l['msg'].split(':')[0]}</span>
                <span style="color:#FFF; font-weight:bold;">{l['val']:+.3f}</span>
            </div>""", unsafe_allow_html=True)

else:
    # Pantalla de bienvenida / Instrucciones
    st.info("👈 Configura el 'IPC Mes Anterior' en la barra lateral. Es clave para corregir el error de inercia.")
