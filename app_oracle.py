import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import calendar
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE TABLERO DE MANDO ---
st.set_page_config(page_title="CPI Control Panel", page_icon="🎛️", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #E0E0E0; }
    .metric-card { background-color: #1A1C24; border: 1px solid #333; padding: 15px; border-radius: 8px; text-align: center; }
    .big-num { font-size: 2em; font-weight: bold; }
    .positive { color: #FF5252; }
    .negative { color: #00E676; }
    .neutral { color: #888; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. BASE DE DATOS ESTRUCTURAL (INE HISTÓRICO)
# ==============================================================================
# Comportamiento MEDIO del IPC mensual en España (2015-2023)
SEASONAL_DNA = {
    1: -0.7,  # Enero: Rebajas fuertes
    2: 0.2,   # Feb: Rebote técnico
    3: 0.4,   # Mar: Cambio temporada / Semana Santa
    4: 0.3,   # Abr: Restauración/Turismo
    5: 0.2,   # May: Transición
    6: 0.4,   # Jun: Inicio verano
    7: -0.6,  # Jul: Rebajas verano
    8: 0.3,   # Ago: Turismo fuerte
    9: 0.1,   # Sep: Vuelta al cole / Fin rebajas
    10: 0.8,  # Oct: Ropa invierno (Mes más fuerte)
    11: 0.2,  # Nov: Calma
    12: 0.2   # Dic: Navidad (Alimentos suben)
}

# ==============================================================================
# 2. MOTOR DE DATOS DE MERCADO (EN TIEMPO REAL)
# ==============================================================================
def get_market_data(year, month):
    # Definir ventana de tiempo del mes seleccionado
    dt_target = datetime(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    
    if dt_target > datetime.now():
        end = datetime.now()
        start = end - timedelta(days=30)
    else:
        start = dt_target
        end = datetime(year, month, last_day)

    # Tickers clave (Usamos BZ=F para Europa, y proxies globales)
    tickers = {
        "Petróleo (Brent)": "BZ=F",
        "Divisa (EUR/USD)": "EURUSD=X",
        "Gas Natural": "NG=F", 
        "Alimentación (Futuros)": "ZW=F"
    }
    
    data_panel = {}
    
    for name, sym in tickers.items():
        try:
            df = yf.download(sym, start=start, end=end, progress=False, auto_adjust=True)
            if not df.empty:
                op = df.iloc[0]['Open'].item()
                cl = df.iloc[-1]['Close'].item()
                chg = ((cl - op) / op) * 100
                data_panel[name] = chg
            else:
                data_panel[name] = 0.0
        except:
            data_panel[name] = 0.0
            
    return data_panel

# ==============================================================================
# INTERFAZ
# ==============================================================================
with st.sidebar:
    st.title("🎛️ CPI COCKPIT")
    st.caption("Herramienta de Asistencia al Analista")
    
    # 1. FECHA
    c1, c2 = st.columns(2)
    t_year = c1.number_input("Año", 2024, 2030, 2026)
    t_month = c2.selectbox("Mes", range(1, 13), index=0) # Enero por defecto
    
    st.divider()
    
    # 2. DATOS PREVIOS (Para cálculo anual)
    base_annual = st.number_input("IPC Anual Previo", value=2.90)
    old_monthly = st.number_input("IPC Mensual Saliente (Año pasado)", value=-0.20, help="Dato clave para el efecto escalón")
    
    st.divider()
    
    # 3. SENSIBILIDAD (TU CONTROL)
    st.markdown("### 🎚️ Ajuste Fino")
    st.info("La máquina propone, tú dispones.")
    
    # Carga datos de mercado para referencia visual
    mk_data = get_market_data(t_year, t_month)
    
    # Sliders de corrección sobre la base estacional
    # Si el petróleo sube un 10%, tú decides si sumas 0.1 o 0.2 al IPC.
    drift_energy = st.slider(f"Energía (Petróleo: {mk_data.get('Petróleo (Brent)',0):.1f}%)", -0.5, 0.5, 0.0, 0.05)
    drift_food = st.slider(f"Alimentos (Futuros: {mk_data.get('Alimentación (Futuros)',0):.1f}%)", -0.3, 0.3, 0.0, 0.05)
    drift_fiscal = st.slider("Shock Fiscal / Eventos", -1.0, 1.0, 0.0, 0.1)


# ==============================================================================
# CÁLCULO CENTRAL
# ==============================================================================
st.title(f"Tablero de Control: {calendar.month_name[t_month]} {t_year}")

# 1. Base Estacional (El ancla)
base_seasonal = SEASONAL_DNA[t_month]

# 2. Tu Predicción
monthly_prediction = base_seasonal + drift_energy + drift_food + drift_fiscal

# 3. Cálculo Anual
f_base = 1 + base_annual/100
f_out = 1 + old_monthly/100
f_in = 1 + monthly_prediction/100
annual_prediction = ((f_base / f_out) * f_in - 1) * 100

# VISUALIZACIÓN
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div style="color:#888;">BASE HISTÓRICA</div>
        <div class="big-num neutral">{base_seasonal:+.2f}%</div>
        <div style="font-size:0.8em;">Lo "normal" este mes</div>
    </div>""", unsafe_allow_html=True)

with col2:
    color_m = "positive" if monthly_prediction > 0 else "negative"
    st.markdown(f"""
    <div class="metric-card" style="border-color: #38BDF8;">
        <div style="color:#38BDF8;">TU PREDICCIÓN (MENSUAL)</div>
        <div class="big-num {color_m}">{monthly_prediction:+.2f}%</div>
        <div style="font-size:0.8em;">Ajustada por ti</div>
    </div>""", unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div style="color:#888;">PROYECCIÓN ANUAL</div>
        <div class="big-num">{annual_prediction:.2f}%</div>
        <div style="font-size:0.8em;">Objetivo: {base_annual}%</div>
    </div>""", unsafe_allow_html=True)

with col4:
    step = monthly_prediction - old_monthly
    color_s = "positive" if step > 0 else "negative"
    st.markdown(f"""
    <div class="metric-card">
        <div style="color:#888;">EFECTO ESCALÓN</div>
        <div class="big-num {color_s}">{step:+.2f}%</div>
        <div style="font-size:0.8em;">Entra vs Sale ({old_monthly})</div>
    </div>""", unsafe_allow_html=True)

st.markdown("---")

# DATOS DE MERCADO PARA AYUDARTE A DECIDIR
st.subheader("📡 Datos en Vivo para tu Decisión")
c_m1, c_m2, c_m3, c_m4 = st.columns(4)

def render_kpi(label, val):
    color = "red" if val > 0 else "green"
    return f"**{label}**<br><span style='color:{color}; font-size:1.2em'>{val:+.2f}%</span>"

c_m1.markdown(render_kpi("Petróleo (Brent)", mk_data.get('Petróleo (Brent)', 0)), unsafe_allow_html=True)
c_m2.markdown(render_kpi("Gas Natural", mk_data.get('Gas Natural', 0)), unsafe_allow_html=True)
c_m3.markdown(render_kpi("Alimentos (Global)", mk_data.get('Alimentación (Futuros)', 0)), unsafe_allow_html=True)
c_m4.markdown(render_kpi("EUR/USD (Divisa)", mk_data.get('Divisa (EUR/USD)', 0)), unsafe_allow_html=True)

st.info("""
**Cómo usar esto para NO fallar:**
1.  **Mira la 'Base Histórica':** Si es Enero, verás -0.70%. Ese es tu punto de partida.
2.  **Mira los Datos en Vivo:** ¿El petróleo sube un +5%? Eso es inflacionista.
3.  **Mueve el Slider:** Mueve 'Energía' un poco a la derecha (ej: +0.10).
4.  **Resultado:** Tu predicción será -0.60%. Sensata, lógica y probable.
""")
