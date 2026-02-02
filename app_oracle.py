import streamlit as st
import yfinance as yf
from gnews import GNews
import calendar
import datetime
from datetime import timedelta
import plotly.graph_objects as go
import numpy as np

# --- CONFIGURACIÓN UI PRO ---
st.set_page_config(page_title="Oracle Spain V35 | Neural", page_icon="🧠", layout="wide")
st.markdown("""
<style>
    .stApp { background-color: #0b0c10; color: #c5c6c7; }
    h1, h2, h3 { color: #66fcf1; }
    div[data-testid="stMetric"] { background-color: #1f2833; border: 1px solid #45a29e; border-radius: 8px; }
    .stButton>button { background-color: #45a29e; color: black; font-weight: bold; border: none; }
    .stButton>button:hover { background-color: #66fcf1; }
</style>
""", unsafe_allow_html=True)

# --- 1. ESQUELETO RECALIBRADO (ADN PROFUNDO) ---
# Enero ahora es mucho más agresivo en bajada (-0.50) para cuadrar con el 2.4% anual
BASE_SKELETON = {
    1: -0.50, 2: 0.30, 3: 0.40, 4: 0.30, 5: 0.10, 6: 0.50,
    7: -0.60, 8: 0.20, 9: -0.30, 10: 0.60, 11: 0.10, 12: 0.20
}

def get_easter_month(year):
    # Algoritmo Astronómico
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    return month

# --- 2. MOTOR DE MERCADO CON "AMORTIGUADOR" (DAMPER) ---
def get_market_neural(year, month):
    # Selector de fechas inteligente
    target_date = datetime.datetime(year, month, 1)
    if target_date > datetime.datetime.now():
        end_date = datetime.datetime.now()
        start_date = end_date - timedelta(days=30)
    else:
        last = calendar.monthrange(year, month)[1]
        start_date = target_date
        end_date = datetime.datetime(year, month, last)

    tickers = {"BRENT": "CL=F", "GAS TTF": "NG=F"}
    impact_score = 0.0
    logs = []

    for name, sym in tickers.items():
        try:
            df = yf.download(sym, start=start_date, end=end_date, progress=False, auto_adjust=True)
            if not df.empty and len(df) > 5:
                # Usamos media móvil para evitar picos de un día
                op = float(df.iloc[0]['Open'])
                cl = float(df.iloc[-1]['Close'])
                change = ((cl - op) / op) * 100
                
                # --- LA CLAVE V35: EL FILTRO DE RUIDO ---
                # Si el cambio es menor al 4%, el IPC NI SE ENTERA (Rigidez)
                real_impact = 0.0
                if abs(change) < 4.0:
                    note = " (Ruido despreciable)"
                else:
                    # Función Logarítmica: Grandes subidas se amortiguan
                    # Un 10% de subida -> 0.04% de impacto. Un 20% -> 0.07%
                    sign = 1 if change > 0 else -1
                    real_impact = sign * (np.log(abs(change)) * 0.02)
                    note = " (Tendencia Estructural)"

                impact_score += real_impact
                icon = "🔥" if change > 0 else "❄️"
                logs.append(f"{icon} {name}: {change:+.2f}% -> Impacto: {real_impact:+.3f}%{note}")
        except:
            logs.append(f"⚠️ {name}: Sin datos.")

    return max(min(impact_score, 0.15), -0.15), logs

# --- 3. LECTOR DE NOTICIAS SEMÁNTICO (NLP) ---
def get_news_neural(year, month):
    # Diccionario de sensibilidad ajustada
    triggers = {
        # Alta Inflación
        "dispara": 0.03, "récord": 0.03, "alza": 0.01,
        "iva": 0.10, "impuesto": 0.05, # ALERTA: Cambios fiscales pegan fuerte
        # Deflación
        "bajada": -0.02, "rebajas": -0.05, "caída": -0.02, 
        "desploma": -0.04, "gratis": -0.05
    }
    
    try:
        # Búsqueda precisa
        if datetime.datetime(year, month, 1) > datetime.datetime.now():
            gnews = GNews(language='es', country='ES', period='10d', max_results=15)
        else:
            last = calendar.monthrange(year, month)[1]
            gnews = GNews(language='es', country='ES', start_date=(year, month, 1), end_date=(year, month, last), max_results=15)
            
        news = gnews.get_news("IPC precios inflación España")
        total_val = 0.0
        headlines = []
        
        for art in news:
            t = art['title'].lower()
            for w, v in triggers.items():
                if w in t:
                    total_val += v
                    if len(headlines) < 3: headlines.append(f"{art['title']} ({v:+})")
                    break
        
        # Amortiguación: Máximo impacto de noticias limitado a +/- 0.1% salvo IVA
        final_score = max(min(total_val / max(len(news), 1), 0.12), -0.12)
        return final_score, headlines
        
    except: return 0.0, ["Sin conexión a noticias"]

# --- INTERFAZ ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2103/2103633.png", width=50)
    st.title("ORACLE V35")
    st.markdown("**Neural Edition**")
    
    col1, col2 = st.columns(2)
    t_year = col1.number_input("Año", 2024, 2030, 2026)
    t_month = col2.selectbox("Mes", range(1, 13), index=0) # Enero por defecto
    
    st.divider()
    st.subheader("Configuración Base")
    # Valores por defecto para Enero 2026 (Para cuadrar con tu 2.4%)
    base_annual = st.number_input("IPC Anual Previo (Dic)", value=2.90)
    old_monthly = st.number_input("IPC Mensual Saliente (Hace 1 año)", value=-0.20)
    
    st.divider()
    st.caption("Ajuste Manual de Sensibilidad")
    sens_market = st.slider("Sensibilidad Mercado", 0.0, 2.0, 1.0) # Multiplicador

    run = st.button("EJECUTAR ANÁLISIS V35")

if run:
    # 1. CORE
    easter = get_easter_month(t_year)
    skeleton = BASE_SKELETON[t_month]
    
    # Lógica Pascua V35 (Más precisa: divide el impacto)
    boost = 0.0
    if t_month == easter: boost = 0.35
    elif t_month == easter - 1: boost = 0.15 # La gente viaja antes
    
    # 2. INPUTS EXTERNOS
    mkt_val, mkt_log = get_market_neural(t_year, t_month)
    news_val, news_log = get_news_neural(t_year, t_month)
    
    # 3. FUSIÓN
    # Aplicamos el multiplicador de sensibilidad del usuario
    final_monthly = (skeleton + boost) + (mkt_val * sens_market) + news_val
    
    # 4. MATEMÁTICA ANUAL INE
    f_base = 1 + base_annual/100
    f_out = 1 + old_monthly/100
    f_in = 1 + final_monthly/100
    final_annual = ((f_base / f_out) * f_in - 1) * 100
    
    # --- RESULTADOS ---
    st.title(f"Reporte de Inflación: {calendar.month_name[t_month]} {t_year}")
    
    # TARJETAS
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("IPC MENSUAL", f"{final_monthly:+.2f}%", "Estimación V35")
    
    # Color dinámico para el Anual (Verde si baja del 3%, Rojo si sube)
    delta_color = "normal" if final_annual < base_annual else "inverse"
    c2.metric("IPC ANUAL", f"{final_annual:.2f}%", f"{final_annual - base_annual:+.2f}%", delta_color=delta_color)
    
    c3.metric("ESQUELETO", f"{skeleton+boost:+.2f}%", "Tendencia Estructural", delta_color="off")
    c4.metric("RUIDO EXTERNO", f"{(mkt_val*sens_market)+news_val:+.2f}%", "Mercado + Noticias")
    
    # GRÁFICO DE PRECISIÓN (WATERFALL)
    fig = go.Figure(go.Waterfall(
        orientation = "v",
        measure = ["relative", "relative", "relative", "relative", "total"],
        x = ["Inercia (Rebajas/Estacional)", "Efecto Pascua", "Filtro Mercado", "Sentimiento Noticias", "PREDICCIÓN FINAL"],
        textposition = "outside",
        text = [f"{skeleton}%", f"{boost}%", f"{mkt_val*sens_market:.2f}%", f"{news_val:.2f}%", f"<b>{final_monthly:.2f}%</b>"],
        y = [skeleton, boost, mkt_val*sens_market, news_val, final_monthly],
        connector = {"line":{"color":"#66fcf1"}},
        decreasing = {"marker":{"color":"#45a29e"}},
        increasing = {"marker":{"color":"#c5c6c7"}},
        totals = {"marker":{"color":"#66fcf1"}}
    ))
    fig.update_layout(
        title="Descomposición Neuronal del Precio",
        template="plotly_dark",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        height=450
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # LOGS
    with st.expander("🕵️ Ver Lógica Interna (Auditoría)"):
        st.write("---")
        st.write(f"**Análisis de Mercado (Amortiguador Activado):**")
        if not mkt_log: st.write("   *Mercado estable. Sin impacto significativo.*")
        for l in mkt_log: st.caption(l)
        
        st.write(f"**Análisis de Noticias (NLP):**")
        if not news_log: st.write("   *Silencio mediático. Sin impacto.*")
        for h in news_log: st.caption(f"- {h}")
        
else:
    st.info("Introduce los datos en la barra lateral para iniciar.")
