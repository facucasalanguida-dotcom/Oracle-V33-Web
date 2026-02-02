import streamlit as st
from gnews import GNews
import calendar
import datetime
import plotly.graph_objects as go
import plotly.figure_factory as ff
import pandas as pd
import numpy as np
import yfinance as yf
import re # Para extraer números exactos del texto

# --- CONFIGURACIÓN TÉCNICA ---
st.set_page_config(page_title="Oracle V59 | Macro-Hybrid", page_icon="🌐", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #E6E6E6; }
    h1, h2, h3 { font-family: 'Roboto', sans-serif; color: #00B4D8; }
    .metric-card { 
        background-color: #1E2329; border: 1px solid #30363D; 
        padding: 15px; border-radius: 8px; text-align: center;
    }
    .macro-alert { 
        color: #FF9F1C; font-weight: bold; border: 1px solid #FF9F1C; 
        padding: 5px; border-radius: 5px; font-size: 0.8em; margin-bottom: 5px;
    }
    .headline-extracted { font-family: monospace; font-size: 0.85em; color: #4ECDC4; }
    div[data-testid="stMetric"] { background-color: #161B22; border: 1px solid #30363D; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. PARÁMETROS OFICIALES
# ==============================================================================
SECTOR_PARAMS = {
    "01 Alimentos": {"w": 19.6, "sigma": 0.35, "keywords": ["precio aceite", "cesta compra", "precio fruta", "leche huevos"]},
    "02 Alcohol/Tabaco": {"w": 3.9, "sigma": 0.1, "keywords": ["precio tabaco", "impuestos alcohol"]},
    "03 Vestido": {"w": 3.8, "sigma": 0.8, "keywords": ["rebajas ropa", "moda precios"]},
    "04 Vivienda": {"w": 12.7, "sigma": 0.6, "keywords": ["precio luz", "tarifa gas", "tope gas", "alquiler"]},
    "05 Menaje": {"w": 5.8, "sigma": 0.2, "keywords": ["electrodomesticos", "reformas"]},
    "06 Sanidad": {"w": 4.4, "sigma": 0.1, "keywords": ["medicamentos", "copago"]},
    "07 Transporte": {"w": 11.6, "sigma": 0.5, "keywords": ["gasolina", "diesel", "renfe", "vuelos"]},
    "08 Comunicaciones": {"w": 2.7, "sigma": 0.1, "keywords": ["tarifas movil", "fibra optica"]},
    "09 Ocio": {"w": 4.9, "sigma": 0.3, "keywords": ["cine", "paquetes turisticos"]},
    "10 Enseñanza": {"w": 1.6, "sigma": 0.05, "keywords": ["matricula universidad", "libros texto"]},
    "11 Hoteles": {"w": 13.9, "sigma": 0.4, "keywords": ["menu dia", "precio hoteles"]},
    "12 Otros": {"w": 15.1, "sigma": 0.2, "keywords": ["seguros", "peluqueria"]}
}

# ==============================================================================
# 2. MOTOR MACROECONÓMICO (TOP-DOWN)
# ==============================================================================
def get_macro_pressure():
    """
    Analiza EUR/USD (Importaciones) y Cobre (Demanda Industrial) para calcular
    la presión base sobre todo el sistema.
    """
    macro_score = 0.0
    logs = []
    
    try:
        # Descarga de datos
        tickers = ["EURUSD=X", "HG=F"] # Euro y Cobre
        data = yf.download(tickers, period="1mo", progress=False, auto_adjust=True)
        
        if not data.empty:
            # 1. ANÁLISIS DIVISA (Si el Euro cae, inflación sube)
            curr_close = data['Close']['EURUSD=X'].iloc[-1]
            curr_open = data['Open']['EURUSD=X'].iloc[0]
            euro_chg = ((curr_close - curr_open) / curr_open) * 100
            
            # Lógica inversa: Euro baja (-2%) -> Inflación sube (+0.05%)
            if euro_chg < -1.0: 
                macro_score += 0.08
                logs.append(f"💶 EURO DÉBIL ({euro_chg:.1f}%): Presión inflacionaria importada.")
            elif euro_chg > 1.0:
                macro_score -= 0.05
                logs.append(f"💶 EURO FUERTE (+{euro_chg:.1f}%): Abarata importaciones.")
                
            # 2. ANÁLISIS INDUSTRIAL (Cobre como termómetro)
            copper_chg = ((data['Close']['HG=F'].iloc[-1] - data['Open']['HG=F'].iloc[0]) / data['Open']['HG=F'].iloc[0]) * 100
            if copper_chg > 3.0:
                macro_score += 0.05
                logs.append(f"🏭 COSTES INDUSTRIALES ({copper_chg:.1f}%): Presión en bienes duraderos.")
                
    except:
        logs.append("⚠️ Sin datos Macro en tiempo real.")
        
    return macro_score, logs

# ==============================================================================
# 3. MOTOR NLP CUANTITATIVO (EXTRAE NÚMEROS)
# ==============================================================================
def extract_number_from_text(text):
    # Busca patrones como "sube un 10%", "cae 5.5 puntos", "20 euros"
    match = re.search(r'(\d+([.,]\d+)?)(\s?%| euros| puntos)', text.lower())
    if match:
        num_str = match.group(1).replace(',', '.')
        return float(num_str)
    return None

def hunt_hybrid_data(year, month):
    impacts = {k: 0.0 for k in SECTOR_PARAMS.keys()}
    evidence_log = []
    
    # 1. Configuración Temporal
    is_future = datetime.datetime(year, month, 1) > datetime.datetime.now()
    period = '20d' if is_future else None
    s_date = None if is_future else (year, month, 1)
    e_date = None if is_future else (year, month, calendar.monthrange(year, month)[1])
    
    gnews = GNews(language='es', country='ES', period=period, start_date=s_date, end_date=e_date, max_results=8)
    
    # Barra de progreso
    prog_bar = st.progress(0)
    
    # Solo escaneamos sectores volátiles para eficiencia
    target_sectors = ["01 Alimentos", "04 Vivienda", "07 Transporte", "11 Hoteles", "03 Vestido"]
    
    for i, sector in enumerate(target_sectors):
        prog_bar.progress(int((i/len(target_sectors))*100))
        
        keyword = SECTOR_PARAMS[sector]["keywords"][0]
        query = f"{keyword} España"
        
        try:
            news = gnews.get_news(query)
            sector_val = 0.0
            
            for art in news:
                t = art['title'].lower()
                val = 0
                
                # A. Detección de Dirección
                if "sube" in t or "dispara" in t or "alza" in t: direction = 1
                elif "baja" in t or "cae" in t or "desploma" in t: direction = -1
                else: direction = 0
                
                if direction != 0:
                    # B. Detección de MAGNITUD (La novedad V59)
                    magnitude = extract_number_from_text(t)
                    
                    if magnitude:
                        # Si dice "sube 10%", aplicamos un factor amortiguado
                        # Regla: 10% noticia ~ 0.2% impacto IPC directo (aprox)
                        val = direction * (magnitude * 0.02)
                        note = f"(Dato extraído: {magnitude}%)"
                    else:
                        # Si no hay número, usamos estándar 0.1
                        val = direction * 0.1
                        note = "(Sentimiento puro)"
                    
                    sector_val += val
                    if len(evidence_log) < 6:
                        evidence_log.append(f"{sector[:10]}..: {art['title']} {note}")
            
            # Tope de seguridad +/- 0.8%
            impacts[sector] = max(min(sector_val, 0.8), -0.8)
            
        except: pass
        
    prog_bar.empty()
    return impacts, evidence_log

# ==============================================================================
# 4. SIMULACIÓN MONTE CARLO (CON FACTOR MACRO)
# ==============================================================================
def run_simulation(base_dna, news_inputs, macro_pressure, iterations=5000):
    weights = np.array([v["w"] for v in SECTOR_PARAMS.values()])
    sigmas = np.array([v["sigma"] for v in SECTOR_PARAMS.values()])
    
    means = []
    for k in SECTOR_PARAMS.keys():
        # Fórmula Maestra V59:
        # Media = Inercia + Noticias (Cuantitativas) + Presión Macro Global
        val = base_dna[k] + news_inputs.get(k, 0.0) + (macro_pressure * 0.5) 
        means.append(val)
        
    means = np.array(means)
    
    # Generar Ruido
    noise = np.random.normal(0, 0.15, (iterations, 12)) * sigmas
    scenarios = means + noise
    
    weighted_scenarios = np.dot(scenarios, weights) / 100
    return weighted_scenarios

# ==============================================================================
# UI
# ==============================================================================
with st.sidebar:
    st.title("ORACLE V59")
    st.caption("MACRO-HYBRID ENGINE")
    
    t_year = st.number_input("Año", 2024, 2030, 2026)
    t_month = st.selectbox("Mes", range(1, 13))
    
    st.divider()
    base_annual = st.number_input("IPC Anual Previo", value=2.90)
    old_monthly = st.number_input("IPC Saliente", value=0.30)
    
    st.markdown("### 🌐 Capas de Análisis")
    st.checkbox("Macroeconomía (Divisas/Ind)", value=True, disabled=True)
    st.checkbox("NLP Cuantitativo (Extracción Cifras)", value=True, disabled=True)
    st.checkbox("Microsimulación Sectorial", value=True, disabled=True)
    
    if st.button("EJECUTAR ANÁLISIS HÍBRIDO", type="primary"):
        st.session_state.run_v59 = True

if 'run_v59' in st.session_state:
    st.title(f"Predicción Macro-Híbrida: {calendar.month_name[t_month].upper()} {t_year}")
    
    # 1. OBTENER FACTOR MACRO (TOP-DOWN)
    macro_val, macro_logs = get_macro_pressure()
    
    # 2. OBTENER DATOS MICRO (BOTTOM-UP)
    # Definir Inercia Base
    base_dna = {k: 0.1 for k in SECTOR_PARAMS.keys()}
    if t_month in [1, 7]: base_dna["03 Vestido"] = -12.0
    if t_month in [3, 4, 9, 10]: base_dna["03 Vestido"] = 4.0
    if t_month in [7, 8]: base_dna["11 Hoteles"] = 1.0
    
    # Escanear Noticias con Regex
    micro_impacts, micro_logs = hunt_hybrid_data(t_year, t_month)
    
    # 3. SIMULACIÓN FINAL
    sim_results = run_simulation(base_dna, micro_impacts, macro_val, 5000)
    
    # Estadísticas
    median = np.median(sim_results)
    std = np.std(sim_results)
    p5, p95 = np.percentile(sim_results, [5, 95])
    
    # Anual
    f_base = 1 + base_annual/100
    f_out = 1 + old_monthly/100
    f_in = 1 + median/100
    final_annual = ((f_base / f_out) * f_in - 1) * 100
    
    # --- VISUALIZACIÓN ---
    
    # KPI BOARD
    c1, c2, c3 = st.columns(3)
    c1.metric("IPC MENSUAL", f"{median:+.2f}%", f"Macro Impact: {macro_val:+.3f}")
    c2.metric("IPC ANUAL", f"{final_annual:.2f}%", f"Objetivo: {base_annual}%")
    c3.metric("CONFIANZA (95%)", f"[{p5:.2f}%, {p95:.2f}%]", "Rango Probable")
    
    st.markdown("---")
    
    col_macro, col_micro = st.columns(2)
    
    with col_macro:
        st.subheader("🌐 Contexto Macroeconómico")
        if macro_logs:
            for l in macro_logs:
                st.markdown(f"<div class='macro-alert'>{l}</div>", unsafe_allow_html=True)
        else:
            st.info("Sin presión macroeconómica externa relevante.")
            
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number", value = macro_val,
            title = {'text': "Presión Importada"},
            gauge = {'axis': {'range': [-0.5, 0.5]}, 'bar': {'color': "#00B4D8"}}
        ))
        fig_gauge.update_layout(height=250, margin=dict(l=20,r=20,t=30,b=20), paper_bgcolor="#161B22", font={'color': "white"})
        st.plotly_chart(fig_gauge, use_container_width=True)

    with col_micro:
        st.subheader("📰 Datos Extraídos (NLP)")
        if micro_logs:
            for log in micro_logs:
                st.markdown(f"<div class='headline-extracted'>• {log}</div>", unsafe_allow_html=True)
        else:
            st.caption("No se hallaron cifras porcentuales explícitas en titulares recientes.")

    # GRÁFICO PROBABILIDAD
    st.markdown("---")
    try:
        hist_data = [sim_results]
        fig = ff.create_distplot(hist_data, ['Probabilidad Híbrida'], bin_size=0.02, show_hist=False, show_rug=False, colors=['#00B4D8'])
        fig.add_vline(x=median, line_dash="dash", annotation_text="Mediana Escenario")
        fig.add_vrect(x0=p5, x1=p95, fillcolor="#00B4D8", opacity=0.1, line_width=0)
        fig.update_layout(title="Distribución de Probabilidad Final", template="plotly_dark", height=400)
        st.plotly_chart(fig, use_container_width=True)
    except: pass
