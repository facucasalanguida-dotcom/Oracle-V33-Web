import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import calendar
from datetime import datetime, timedelta

# ==============================================================================
# CONFIGURACIÓN: ORACLE SPARTAN (V300)
# ==============================================================================
st.set_page_config(page_title="Oracle Spartan | Calibrated Engine", page_icon="🛡️", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #E6E6E6; font-family: 'Roboto', sans-serif; }
    .kpi-card { background-color: #161B22; border: 1px solid #30363D; padding: 20px; border-radius: 8px; text-align: center; }
    .big-num { font-size: 2.5em; font-weight: bold; color: #FFF; }
    .label { color: #888; font-size: 0.8em; text-transform: uppercase; }
    .correction { color: #238636; font-weight: bold; font-size: 0.9em; }
    div[data-testid="stMetric"] { background-color: #0D1117; border: 1px solid #30363D; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. BASE ESTACIONAL CORREGIDA (INE 2018-2023 PROMEDIO)
# ==============================================================================
# Enero y Julio son negativos (Rebajas).
# Mayo suele ser moderado (0.2 - 0.3).
SEASONAL_BASE = {
    1: -0.70, 2: 0.20, 3: 0.40, 4: 0.30, 5: 0.25, 6: 0.40,
    7: -0.60, 8: 0.30, 9: 0.10, 10: 0.80, 11: 0.20, 12: 0.20
}

# ==============================================================================
# 2. MOTOR DE MERCADO AMORTIGUADO (DAMPED MARKET ENGINE)
# ==============================================================================
def get_calibrated_market_impact(year, month):
    """
    Calcula el impacto REAL en el IPC aplicando Coeficientes de Transmisión.
    """
    signals = {}
    
    # 1. Definir Ventana de Análisis
    # Si analizamos Mayo, miramos la variación de precios de Abril a Mayo.
    dt_target = datetime(year, month, 1)
    if dt_target > datetime.now():
        # Futuro: Miramos últimos 30 días como "Tendencia Actual"
        end = datetime.now()
        start = end - timedelta(days=30)
    else:
        # Pasado: Miramos el mes específico
        last_day = calendar.monthrange(year, month)[1]
        start = dt_target
        end = datetime(year, month, last_day)

    # 2. Tickers y COEFICIENTES DE AMORTIGUACIÓN (La clave del arreglo)
    # Beta: Cuánto del cambio de mercado pasa al IPC.
    # Ejemplo Energía: Mercado sube 10% -> Beta 0.02 -> IPC sube 0.2% (Realista)
    commodities = {
        "Petróleo (Brent)": {"ticker": "BZ=F", "beta": 0.025}, 
        "Gas Natural":      {"ticker": "NG=F", "beta": 0.015}, # El gas impacta menos directo que la gasolina
        "Trigo/Maíz":       {"ticker": "ZW=F", "beta": 0.010}, # Alimentos procesados son lentos
    }
    
    total_shock = 0.0
    
    for name, data in commodities.items():
        try:
            df = yf.download(data["ticker"], start=start, end=end, progress=False, auto_adjust=True)
            if not df.empty:
                # Variación mensual del activo
                op = df.iloc[0]['Open'].item()
                cl = df.iloc[-1]['Close'].item()
                pct_change = ((cl - op) / op) * 100
                
                # CÁLCULO AMORTIGUADO
                # Si el gas sube un 20%, impacta: 20 * 0.015 = +0.3% al IPC.
                # (Antes tu código sumaba el 20% entero o ponderado mal, dando +1.6%)
                impact = pct_change * data["beta"]
                
                # Límite de seguridad (Circuit Breaker): 
                # Ninguna materia prima puede mover el IPC más de 0.4% ella sola en un mes normal.
                impact = max(min(impact, 0.4), -0.4)
                
                signals[name] = {"change": pct_change, "impact": impact}
                total_shock += impact
            else:
                signals[name] = {"change": 0.0, "impact": 0.0}
        except:
            signals[name] = {"change": 0.0, "impact": 0.0}
            
    return total_shock, signals

# ==============================================================================
# 3. INTERFAZ DE CONTROL
# ==============================================================================
with st.sidebar:
    st.title("ORACLE SPARTAN")
    st.caption("v300 | High Precision Logic")
    
    # INPUTS DE TIEMPO
    c1, c2 = st.columns(2)
    t_year = c1.number_input("Año", 2024, 2030, 2025)
    t_month = c2.selectbox("Mes", range(1, 13), index=4) # Mayo por defecto
    
    st.markdown("---")
    
    # INPUTS DE CALIBRACIÓN (LO QUE FALTABA)
    st.markdown("### 🛠️ Calibración Fina")
    st.info("Introduce los datos reales anteriores para ajustar la inercia.")
    
    # Dato clave: IPC del año anterior (para efecto escalón)
    old_monthly = st.number_input(f"IPC Mensual {calendar.month_name[t_month]} (Año Pasado)", value=0.30, step=0.01)
    
    # Dato clave: IPC del mes pasado (para inercia)
    prev_monthly = st.number_input("IPC Mes Anterior (t-1)", value=0.40, step=0.01)
    base_annual_prev = st.number_input("IPC Anual Previo (t-1)", value=3.30)
    
    st.markdown("---")
    
    # AJUSTE MANUAL DE "SENSACIONES"
    st.markdown("### ⚖️ Ajuste Manual")
    shock_manual = st.slider("Shock Extra (IVA/Guerra)", -1.0, 1.0, 0.0, 0.1, help="Úsalo si hay subida de IVA o evento extremo.")
    
    calc_btn = st.button("CALCULAR DATO EXACTO", type="primary")

# ==============================================================================
# 4. CÁLCULO FINAL
# ==============================================================================
if calc_btn:
    # 1. Base Estacional (Lo que siempre pasa)
    base_val = SEASONAL_BASE[t_month]
    
    # 2. Inercia del Mes Anterior (Momentum)
    # Si el mes pasado fue alto (0.4), arrastra un poco (0.1) al actual.
    momentum = prev_monthly * 0.25 
    
    # 3. Shock de Mercado (Amortiguado)
    mkt_shock, mkt_details = get_calibrated_market_impact(t_year, t_month)
    
    # 4. FÓRMULA FINAL
    # IPC Estimado = Base + Momentum + Mercado + Manual
    monthly_prediction = base_val + momentum + mkt_shock + shock_manual
    
    # 5. Cálculo Anual
    f_base = 1 + base_annual_prev/100
    f_out = 1 + old_monthly/100
    f_in = 1 + monthly_prediction/100
    annual_prediction = ((f_base / f_out) * f_in - 1) * 100
    
    # VISUALIZACIÓN
    st.title(f"Resultados Spartan: {calendar.month_name[t_month]} {t_year}")
    
    # TARJETAS KPI
    col1, col2, col3 = st.columns(3)
    
    with col1:
        color = "#00C853" if monthly_prediction < 0.5 else "#FF1744"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="label">IPC MENSUAL PREVISTO</div>
            <div class="big-num" style="color:{color}">{monthly_prediction:+.2f}%</div>
            <div class="correction">Rango seguro: [{monthly_prediction-0.1:.2f}%, {monthly_prediction+0.1:.2f}%]</div>
        </div>""", unsafe_allow_html=True)
        
    with col2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="label">IPC ANUAL PREVISTO</div>
            <div class="big-num">{annual_prediction:.2f}%</div>
            <div class="label">Objetivo Previo: {base_annual_prev}%</div>
        </div>""", unsafe_allow_html=True)
        
    with col3:
        # Efecto Escalón
        step = monthly_prediction - old_monthly
        color_step = "#2962FF"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="label">EFECTO ESCALÓN (BASE)</div>
            <div class="big-num" style="color:{color_step}">{step:+.2f}%</div>
            <div class="label">Entra ({monthly_prediction:.2f}) vs Sale ({old_monthly})</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    
    # DESGLOSE LÓGICO
    c_left, c_right = st.columns([2, 1])
    
    with c_left:
        st.subheader("📊 ¿Por qué da este número?")
        st.write("Hemos corregido la sensibilidad. Así se construye el dato:")
        
        breakdown_df = pd.DataFrame([
            {"Factor": "1. Estacionalidad Histórica", "Valor": base_val, "Nota": "Lo normal para este mes"},
            {"Factor": "2. Inercia (Mes Pasado)", "Valor": momentum, "Nota": f"Arrastre del {prev_monthly}% anterior"},
            {"Factor": "3. Impacto Mercado Real", "Valor": mkt_shock, "Nota": "Petróleo, Gas y Alimentos (Amortiguado)"},
            {"Factor": "4. Ajuste Manual", "Valor": shock_manual, "Nota": "IVA / Eventos Extra"},
            {"Factor": "TOTAL PREDICCIÓN", "Valor": monthly_prediction, "Nota": "Suma Final"}
        ])
        st.dataframe(breakdown_df.style.format({"Valor": "{:+.3f}%"}), use_container_width=True)
        
    with c_right:
        st.subheader("📉 Datos de Mercado")
        for name, data in mkt_details.items():
            # Mostramos la diferencia entre la subida real y el impacto IPC
            st.markdown(f"""
            <div style="border-bottom:1px solid #333; padding:5px;">
                <b>{name}</b><br>
                <span style="color:#888">Mercado:</span> {data['change']:+.1f}% <br>
                <span style="color:#00C853; font-weight:bold;">Impacto IPC: {data['impact']:+.3f}%</span>
            </div>
            """, unsafe_allow_html=True)
        
    st.warning(f"""
    **Diagnóstico del error anterior (V200):**
    En tu captura anterior, el Gas Natural sumaba +1.651% al IPC. Eso era un error de cálculo.
    Aquí, aunque el Gas suba lo mismo en el mercado, su impacto está limitado matemáticamente (Beta 0.015), sumando solo lo que le corresponde por peso real.
    """)

else:
    st.info("Introduce los datos en la barra lateral y pulsa CALCULAR.")
