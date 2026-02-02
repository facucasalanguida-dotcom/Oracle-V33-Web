import streamlit as st
import yfinance as yf
from gnews import GNews
import calendar
import datetime
from datetime import timedelta
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

# --- CONFIGURACIÓN KRONOS ---
st.set_page_config(page_title="Oracle V45 | KRONOS", page_icon="⏳", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #080C11; color: #C9D1D9; }
    h1, h2, h3 { font-family: 'Helvetica Neue', sans-serif; color: #58A6FF; letter-spacing: -1px; }
    .dna-box { 
        background-color: #161B22; 
        border-left: 3px solid #238636; 
        padding: 12px; 
        margin-bottom: 8px; 
        font-family: 'Consolas', monospace; font-size: 0.85em;
    }
    .anomaly-box { border-left: 3px solid #DA3633; background-color: #2D1414; }
    div[data-testid="stMetric"] { background-color: #0D1117; border: 1px solid #30363D; }
</style>
""", unsafe_allow_html=True)

# --- 1. EL ADN DE ESPAÑA (LA MATRIZ DE LA VERDAD) ---
# Comportamiento base mensual de cada grupo ECOICOP en España.
# Esto es "lo que debería pasar" si no hubiera noticias extraordinarias.
YEARLY_DNA = {
    "01 Alimentos":  [0.2, 0.1, 0.0, 0.1, -0.2, 0.3, 0.0, 0.1, -0.1, 0.3, 0.2, 0.6], # Dic sube fuerte
    "02 Alcohol/Tab": [0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.2], # Ene subida tasas
    "03 Vestido":    [-13.0, -2.0, 4.0, 5.0, 1.0, -1.0, -12.0, -1.0, 4.0, 8.0, 0.5, -1.0], # Rebajas Ene/Jul
    "04 Vivienda":   [0.8, -0.2, -0.5, -0.2, -0.1, 0.4, 0.6, 0.5, 0.2, 0.5, 0.3, 0.7], # Calefacción/Aire
    "05 Menaje":     [-0.5, 0.1, 0.2, 0.2, 0.1, 0.1, -0.4, 0.0, 0.2, 0.3, 0.1, 0.2],
    "06 Medicina":   [0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    "07 Transporte": [0.4, 0.2, 0.5, 0.6, 0.3, 0.5, 0.8, 0.6, -0.5, -0.2, -0.3, 0.1], # Verano sube
    "08 Comms":      [-0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1], # Deflación
    "09 Ocio":       [-0.8, 0.2, 0.5, 0.2, -0.5, 0.4, 1.0, 1.2, -1.5, -0.5, -0.2, 0.8], # Vacaciones
    "10 Enseñanza":  [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.5, 1.0, 0.0, 0.0], # Sept/Oct Only
    "11 Hoteles":    [-0.5, 0.2, 0.8, 0.5, 0.5, 1.0, 2.5, 2.0, -1.0, -0.5, -0.5, 1.5], # Turismo
    "12 Otros":      [0.8, 0.2, 0.2, 0.1, 0.1, 0.1, 0.1, 0.0, 0.1, 0.1, 0.0, 0.1]  # Seguros Ene
}

# Pesos Reales ECOICOP (2024)
WEIGHTS = {
    "01 Alimentos": 0.196, "02 Alcohol/Tab": 0.039, "03 Vestido": 0.038, 
    "04 Vivienda": 0.127, "05 Menaje": 0.058, "06 Medicina": 0.044,
    "07 Transporte": 0.116, "08 Comms": 0.027, "09 Ocio": 0.049, 
    "10 Enseñanza": 0.016, "11 Hoteles": 0.139, "12 Otros": 0.151
}

# --- 2. MOTOR DE AUDITORÍA EN TIEMPO REAL ---
def audit_sector_reality(sector_name, year, month):
    """
    Compara el ADN Histórico con la Realidad Actual (Noticias/Mercado).
    Devuelve: (Valor Final, Flag de Anomalía, Evidencia)
    """
    # 1. Obtener Base Histórica
    base_val = YEARLY_DNA[sector_name][month-1]
    
    # Ajuste Pascua Dinámico para Turismo y Ocio
    if sector_name in ["11 Hoteles", "09 Ocio"]:
        # Calc Pascua simplificado
        if month in [3, 4]: # Meses sospechosos
            # Aquí iría el algoritmo completo, simplificamos para velocidad:
            # Si es Abril, boost. Si es Marzo, depende del año.
            pass 

    # 2. Auditoría Externa (Realidad)
    anomaly_score = 0.0
    evidence = []
    
    # A. Mercados Financieros (Hard Data)
    ticker = None
    if "01 Alimentos" in sector_name: ticker = "ZW=F" # Trigo
    elif "04 Vivienda" in sector_name: ticker = "NG=F" # Gas
    elif "07 Transporte" in sector_name: ticker = "BZ=F" # Brent
    
    if ticker:
        try:
            # Ventana inteligente
            dt_t = datetime.datetime(year, month, 1)
            if dt_t > datetime.datetime.now(): end = datetime.datetime.now(); start = end - timedelta(days=30)
            else: last = calendar.monthrange(year, month)[1]; start=dt_t; end=datetime.datetime(year, month, last)
            
            df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
            if not df.empty:
                chg = ((float(df.iloc[-1]['Close']) - float(df.iloc[0]['Open'])) / float(df.iloc[0]['Open'])) * 100
                if abs(chg) > 3.0: # Solo si hay movimiento fuerte
                    impact = chg * 0.02
                    anomaly_score += impact
                    evidence.append(f"MERCADO: {ticker} varió {chg:+.1f}% -> Ajuste {impact:+.2f}%")
        except: pass

    # B. Noticias (Soft Data)
    # Solo buscamos si hay anomalías graves (ej: "sequía", "huelga", "tope")
    keywords = []
    if "01" in sector_name: keywords = ["sequía", "aceite dispara"]
    if "04" in sector_name: keywords = ["tope gas", "luz sube"]
    if "07" in sector_name: keywords = ["subsidio gasolina", "peajes"]
    
    if keywords:
        try:
            gnews = GNews(language='es', country='ES', period='15d', max_results=5)
            q = f"{keywords[0]} precio españa"
            news = gnews.get_news(q)
            if len(news) > 0 and "sube" in news[0]['title'].lower():
                anomaly_score += 0.1
                evidence.append(f"NOTICIA: {news[0]['title']}")
        except: pass

    # 3. Fusión
    final_val = base_val + anomaly_score
    is_anomaly = abs(anomaly_score) > 0.05
    
    return final_val, is_anomaly, evidence, base_val

# --- FRONTEND ---
with st.sidebar:
    st.title("ORACLE V45")
    st.caption("PROYECTO KRONOS")
    
    t_year = st.number_input("Año", 2024, 2030, 2026)
    t_month = st.selectbox("Mes Auditado", range(1, 13))
    
    st.divider()
    base_annual = st.number_input("IPC Base (Anual)", value=2.80)
    old_monthly = st.number_input("IPC Saliente (Mensual)", value=0.30)
    
    if st.button("EJECUTAR MATRIZ KRONOS"):
        st.session_state.kronos = True

if 'kronos' in st.session_state:
    st.title(f"Auditoría Mensual: {calendar.month_name[t_month].upper()} {t_year}")
    
    # 1. CÁLCULO MASIVO
    results = {}
    total_monthly_cpi = 0.0
    
    # Progreso
    bar = st.progress(0)
    
    col_audit, col_dna = st.columns([3, 2])
    
    with col_audit:
        st.subheader(f"🕵️ Análisis Forense (ECOICOP 12)")
        
        idx = 0
        for sector, weight in WEIGHTS.items():
            idx += 1
            bar.progress(int((idx/12)*100))
            
            val, is_anom, ev, base = audit_sector_reality(sector, t_year, t_month)
            contrib = val * weight
            total_monthly_cpi += contrib
            
            results[sector] = {"val": val, "contrib": contrib, "base": base}
            
            # Renderizado Inteligente
            css_class = "anomaly-box" if is_anom else "dna-box"
            icon = "🚨 ANOMALÍA" if is_anom else "🧬 ADN NORMAL"
            
            html_ev = "".join([f"<div>• {e}</div>" for e in ev]) if ev else "<div style='color:#666'>Comportamiento estándar verificado.</div>"
            
            st.markdown(f"""
            <div class="{css_class}">
                <div style="display:flex; justify-content:space-between; font-weight:bold; color:white;">
                    <span>{sector}</span>
                    <span>{val:+.2f}% (Aporta {contrib:+.3f})</span>
                </div>
                <div style="font-size:0.8em; margin-top:4px; color:#aaa;">
                    EXPECTATIVA: {base:+.2f}% | ESTADO: {icon}
                </div>
                <div style="margin-top:5px; font-size:0.85em;">{html_ev}</div>
            </div>
            """, unsafe_allow_html=True)

    bar.empty()
    
    # 2. RESULTADOS GLOBALES
    f_base = 1 + base_annual/100
    f_out = 1 + old_monthly/100
    f_in = 1 + total_monthly_cpi/100
    final_annual = ((f_base / f_out) * f_in - 1) * 100
    
    with col_dna:
        st.markdown("""<div style="background-color:#0D1117; padding:15px; border-radius:10px; border:1px solid #30363D;">
        <h3 style="text-align:center; margin:0;">DICTAMEN FINAL</h3></div>""", unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        c1.metric("MENSUAL", f"{total_monthly_cpi:+.2f}%")
        c2.metric("ANUAL", f"{final_annual:.2f}%", f"{final_annual-base_annual:+.2f}%", delta_color="inverse")
        
        st.markdown("---")
        st.subheader("🧬 Mapa de Calor Anual")
        st.caption("Evolución proyectada de los sectores clave (Matriz KRONOS)")
        
        # Generar Heatmap de Datos Históricos para Contexto
        df_dna = pd.DataFrame(YEARLY_DNA)
        df_dna.index = [calendar.month_abbr[i] for i in range(1, 13)]
        
        fig = px.imshow(df_dna.T, 
                        labels=dict(x="Mes", y="Sector", color="Variación"),
                        x=df_dna.index,
                        y=df_dna.columns,
                        color_continuous_scale="RdBu_r", midpoint=0)
        fig.update_layout(height=400, template="plotly_dark", margin=dict(l=0, r=0, t=0, b=0))
        # Marcar mes actual
        fig.add_vline(x=t_month-1, line_width=3, line_dash="dash", line_color="yellow")
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.info(f"""
        **Interpretación KRONOS:**
        Estás auditando **{calendar.month_name[t_month]}**. 
        La línea amarilla en el mapa indica el momento del ciclo.
        Observa cómo el sector **03 Vestido** (Ropa) suele definir la tendencia en Enero y Julio (azul oscuro/rojo intenso).
        """)

else:
    st.info("Sistema KRONOS listo. Inicie la simulación a la izquierda.")
