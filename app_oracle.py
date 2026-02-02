import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import numpy as np
import calendar
from datetime import datetime, timedelta

# --- CONFIGURACIÓN MINIMALISTA ---
st.set_page_config(page_title="ORACLE ZERO | Structural", page_icon="Ø", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    h1, h2, h3 { font-family: 'Helvetica', sans-serif; color: #FFFFFF; letter-spacing: -1px; }
    .big-kpi { font-size: 3em; font-weight: bold; color: #FFF; line-height: 1; }
    .sub-kpi { font-size: 0.9em; color: #888; text-transform: uppercase; letter-spacing: 1px; }
    .card { background-color: #111; padding: 20px; border-radius: 10px; border: 1px solid #333; }
    div[data-testid="stMetric"] { background-color: #111; border: 1px solid #333; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. LA LEY DE HIERRO (ESTACIONALIDAD HISTÓRICA DE ESPAÑA)
# ==============================================================================
# Promedios reales aproximados del IPC mensual en España (2010-2023)
# Enero y Julio son negativos por las REBAJAS. Esto es la base inamovible.
SEASONAL_BASELINE = {
    1: -0.60,  # Enero: Rebajas invierno (-0.5 a -1.0)
    2: 0.10,   # Feb: Rebote técnico
    3: 0.40,   # Mar: Nueva temporada ropa / Semana Santa
    4: 0.50,   # Abr: Continuación temporada
    5: 0.20,   # May: Calma
    6: 0.30,   # Jun: Pre-verano
    7: -0.50,  # Jul: Rebajas verano
    8: 0.20,   # Ago: Turismo
    9: 0.10,   # Sep: Fin rebajas
    10: 0.70,  # Oct: Ropa invierno (El mes más inflacionista)
    11: 0.20,  # Nov: Calma
    12: 0.30   # Dic: Navidad / Alimentos
}

# ==============================================================================
# 2. MOTOR DE DATOS REALES (MERCADO)
# ==============================================================================
def get_market_drift(year, month):
    """
    Calcula cuánto se desvía el mercado HOY respecto a lo 'normal'.
    Si el petróleo suele estar plano pero sube un 10%, añadimos presión.
    """
    # Tickers clave
    tickers = {
        "Petróleo (Brent)": "BZ=F",
        "Gas Natural": "NG=F",
        "Trigo (Alimentos)": "ZW=F"
    }
    
    # Fechas
    dt_target = datetime(year, month, 1)
    if dt_target > datetime.now():
        end = datetime.now()
        start = end - timedelta(days=30)
    else:
        last_day = calendar.monthrange(year, month)[1]
        start = dt_target
        end = datetime(year, month, last_day)
        
    market_data = {}
    
    for name, sym in tickers.items():
        try:
            df = yf.download(sym, start=start, end=end, progress=False, auto_adjust=True)
            if not df.empty:
                open_p = df.iloc[0]['Open'].item()
                close_p = df.iloc[-1]['Close'].item()
                chg = ((close_p - open_p) / open_p) * 100
                market_data[name] = chg
            else:
                market_data[name] = 0.0
        except:
            market_data[name] = 0.0
            
    return market_data

# ==============================================================================
# 3. INTERFAZ DE CONTROL (HUMAN IN THE LOOP)
# ==============================================================================
with st.sidebar:
    st.title("ORACLE ZERO")
    st.caption("STRUCTURAL LOGIC ENGINE")
    
    st.header("1. Coordenadas")
    t_year = st.number_input("Año", 2024, 2030, 2026)
    t_month = st.selectbox("Mes", range(1, 13))
    
    st.header("2. Punto de Partida")
    # Datos críticos para el cálculo anual
    base_annual = st.number_input("IPC Anual Previo (t-1)", value=2.90, format="%.2f")
    old_monthly = st.number_input("IPC Mensual Saliente (Año pasado)", value=-0.20, format="%.2f", help="Dato del mismo mes el año pasado")
    
    st.divider()
    
    # OBTENER DATOS DE MERCADO AUTOMÁTICOS
    market_real = get_market_drift(t_year, t_month)
    
    st.header("3. Calibración de Motores")
    st.caption("Ajusta las desviaciones respecto a lo 'Normal'.")
    
    # MOTOR 1: ENERGÍA (Petróleo/Gas)
    # Sugerencia basada en dato real
    sug_energy = market_real.get("Petróleo (Brent)", 0) * 0.1 + market_real.get("Gas Natural", 0) * 0.05
    energy_drift = st.slider(f"⚡ Desvío Energía ({sug_energy:+.1f}%)", -2.0, 2.0, float(sug_energy/10), 0.01, help="Si el petróleo sube mucho, mueve esto a la derecha.")
    
    # MOTOR 2: ALIMENTOS
    sug_food = market_real.get("Trigo (Alimentos)", 0) * 0.05
    food_drift = st.slider(f"🍎 Desvío Alimentos ({sug_food:+.1f}%)", -1.0, 1.0, float(sug_food/10), 0.01)
    
    # MOTOR 3: CORE / SUBYACENTE
    core_drift = st.slider("👕 Desvío Subyacente (Servicios/Ropa)", -0.5, 0.5, 0.0, 0.01, help="Usa esto para ajustar si las rebajas son más o menos agresivas de lo normal.")

# ==============================================================================
# 4. MOTOR DE CÁLCULO ESTRUCTURAL
# ==============================================================================

# A. Base Histórica (La gravedad)
base_seasonal = SEASONAL_BASELINE[t_month]

# B. Pesos del IPC (Aproximados INE)
W_ENERGY = 0.12
W_FOOD = 0.20
W_CORE = 0.68

# C. Cálculo de la Predicción Mensual
# Fórmula: Base + (Impacto Energía * Peso) + (Impacto Comida * Peso) + (Impacto Core * Peso)
# Nota: La base ya incluye el comportamiento "normal". Los drifts son el EXCESO sobre lo normal.
monthly_prediction = base_seasonal + (energy_drift * W_ENERGY) + (food_drift * W_FOOD) + (core_drift * W_CORE)

# D. Cálculo Anual (Chain Linking)
# IPC Anual = ((1 + IPC_Anual_Previo) / (1 + IPC_Mensual_Saliente)) * (1 + IPC_Mensual_Entrante) - 1
f_base = 1 + (base_annual / 100)
f_out = 1 + (old_monthly / 100)
f_in = 1 + (monthly_prediction / 100)

annual_prediction = ((f_base / f_out) * f_in - 1) * 100

# ==============================================================================
# 5. VISUALIZACIÓN
# ==============================================================================
st.title(f"Proyección Estructural: {calendar.month_name[t_month].upper()} {t_year}")

# --- TARJETAS PRINCIPALES ---
c1, c2, c3 = st.columns(3)

with c1:
    color = "#4CAF50" if monthly_prediction < 0 else "#FF5252"
    st.markdown(f"""
    <div class="card">
        <div class="sub-kpi">IPC MENSUAL ESTIMADO</div>
        <div class="big-kpi" style="color:{color}">{monthly_prediction:+.2f}%</div>
        <div style="color:#666; margin-top:5px;">Base Histórica: {base_seasonal:+.2f}%</div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    # Lógica de color Anual: Si baja respecto al anterior, verde.
    color_ann = "#4CAF50" if annual_prediction < base_annual else "#FF5252"
    diff = annual_prediction - base_annual
    st.markdown(f"""
    <div class="card">
        <div class="sub-kpi">IPC ANUAL PROYECTADO</div>
        <div class="big-kpi" style="color:{color_ann}">{annual_prediction:.2f}%</div>
        <div style="color:#666; margin-top:5px;">Variación: {diff:+.2f}%</div>
    </div>
    """, unsafe_allow_html=True)

with c3:
    # Efecto Escalón
    step_effect = monthly_prediction - old_monthly
    color_step = "#4CAF50" if step_effect < 0 else "#FF5252"
    st.markdown(f"""
    <div class="card">
        <div class="sub-kpi">DINÁMICA DE FLUJO</div>
        <div class="big-kpi" style="color:{color_step}">{step_effect:+.2f}%</div>
        <div style="color:#666; margin-top:5px;">Entra vs Sale ({old_monthly}%)</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# --- ANÁLISIS DE CAUSALIDAD (WATERFALL LIMPIO) ---
col_chart, col_data = st.columns([2, 1])

with col_chart:
    st.subheader("¿Cómo se construye este dato?")
    
    # Valores para el gráfico
    v_base = base_seasonal
    v_energy = energy_drift * W_ENERGY
    v_food = food_drift * W_FOOD
    v_core = core_drift * W_CORE
    
    fig = go.Figure(go.Waterfall(
        name = "IPC", orientation = "v",
        measure = ["relative", "relative", "relative", "relative", "total"],
        x = ["Base Estacional", "Shock Energía", "Shock Alimentos", "Ajuste Core", "PREDICCIÓN"],
        textposition = "outside",
        text = [f"{v_base:+.2f}", f"{v_energy:+.2f}", f"{v_food:+.2f}", f"{v_core:+.2f}", f"{monthly_prediction:+.2f}"],
        y = [v_base, v_energy, v_food, v_core, monthly_prediction],
        connector = {"line":{"color":"#555"}},
        decreasing = {"marker":{"color":"#4CAF50"}},
        increasing = {"marker":{"color":"#FF5252"}},
        totals = {"marker":{"color":"#2196F3"}}
    ))
    fig.update_layout(template="plotly_dark", height=400, margin=dict(t=30, b=20, l=20, r=20))
    st.plotly_chart(fig, use_container_width=True)

with col_data:
    st.subheader("Datos de Mercado (Tiempo Real)")
    for name, val in market_real.items():
        color = "red" if val > 0 else "green"
        st.markdown(f"""
        <div style="padding:10px; border-bottom:1px solid #333;">
            <span style="color:#aaa">{name}</span>
            <span style="float:right; color:{color}; font-weight:bold;">{val:+.2f}%</span>
        </div>
        """, unsafe_allow_html=True)
        
    st.info("""
    **Filosofía Oracle Zero:**
    Partimos de la estacionalidad innegociable (Ej: Enero siempre baja por rebajas).
    Solo sumamos presión si los mercados muestran anomalías reales hoy.
    """)
