import streamlit as st
import yfinance as yf
from gnews import GNews
import calendar
import datetime
from datetime import timedelta
import plotly.graph_objects as go
import pandas as pd

# --- CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Oracle Spain V34 | Scientific", page_icon="🏛️", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    div[data-testid="stMetric"] { background-color: #262730; border: 1px solid #41444C; padding: 10px; border-radius: 5px; }
    .stButton>button { width: 100%; background-color: #FF4B4B; color: white; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- BASE DE CONOCIMIENTO (INE) ---
BASE_SKELETON = {
    1: -0.20, 2: 0.35, 3: 0.10, 4: 0.20, 5: 0.10, 6: 0.60,
    7: -0.25, 8: 0.25, 9: -0.30, 10: 0.60, 11: 0.15, 12: 0.25
}

def get_easter_month(year):
    # Cálculo astronómico de Pascua
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

def get_market_data_robust(year, month):
    # Selector inteligente de fechas para evitar errores de "Futuro"
    target_date = datetime.datetime(year, month, 1)
    today = datetime.datetime.now()
    
    # Si buscamos una fecha futura, usamos los últimos 30 días reales como proxy
    if target_date > today:
        end_date = today
        start_date = today - timedelta(days=30)
    else:
        last_day = calendar.monthrange(year, month)[1]
        start_date = target_date
        end_date = datetime.datetime(year, month, last_day)

    tickers = {"BRENT (Crudo)": "CL=F", "GAS NATURAL": "NG=F"}
    total_impact = 0.0
    logs = []

    for name, sym in tickers.items():
        try:
            # Descarga optimizada para evitar MultiIndex corruptos
            df = yf.download(sym, start=start_date, end=end_date, progress=False, auto_adjust=True)
            
            if not df.empty and len(df) > 1:
                # Usamos iloc para asegurar acceso posicional sin importar el índice
                op = float(df.iloc[0]['Open'])
                cl = float(df.iloc[-1]['Close'])
                
                pct_change = ((cl - op) / op) * 100
                
                # FACTOR DE TRANSMISIÓN (V34): 
                # 0.005 significa que un 10% de subida en gas impacta +0.05% en IPC
                impact = pct_change * 0.005 
                
                total_impact += impact
                
                icon = "🔺" if pct_change > 0 else "🔻"
                logs.append(f"{icon} {name}: {pct_change:+.2f}% (Impacto: {impact:+.3f}%)")
            else:
                logs.append(f"⚠️ {name}: Sin datos suficientes en periodo.")
        except Exception as e:
            logs.append(f"❌ Error {name}: {str(e)}")
            
    # Tope de seguridad: El mercado no puede mover el IPC más de 0.15% solo
    return max(min(total_impact, 0.15), -0.15), logs

def get_news_robust(year, month):
    # Sin aleatoriedad. Si falla, es 0.
    try:
        if datetime.datetime(year, month, 1) > datetime.datetime.now():
            gnews = GNews(language='es', country='ES', period='15d', max_results=10)
        else:
            last = calendar.monthrange(year, month)[1]
            gnews = GNews(language='es', country='ES', start_date=(year, month, 1), end_date=(year, month, last), max_results=10)
            
        news = gnews.get_news(f"inflación precios IPC España")
        
        score = 0
        triggers = {"dispara": 0.05, "subida": 0.02, "bajada": -0.02, "caída": -0.02, "moderación": -0.01}
        headlines = []
        
        for art in news:
            t = art['title'].lower()
            for w, v in triggers.items():
                if w in t:
                    score += v
                    if len(headlines) < 3: headlines.append(art['title'])
                    break
        
        # Normalización suave
        if len(news) > 0: score = score / max(len(news), 1)
        return max(min(score, 0.1), -0.1), headlines
        
    except:
        return 0.0, ["(Sin conexión a API de Noticias)"]

# --- SIDEBAR ---
with st.sidebar:
    st.title("ORACLE V34")
    st.caption("Scientific Edition")
    
    st.header("1. Escenario Temporal")
    col_y, col_m = st.columns(2)
    target_year = col_y.number_input("Año", 2024, 2030, 2026)
    target_month = col_m.selectbox("Mes", range(1, 13), index=0)
    
    st.header("2. Datos Base (Efecto Escalón)")
    base_annual = st.number_input("IPC Anual Previo (%)", value=2.90, step=0.1)
    old_monthly = st.number_input("IPC Mensual Saliente (%)", value=-0.20, step=0.1, help="El dato del mismo mes el año pasado")

    st.header("3. Ajuste Fino (Expert Mode)")
    st.markdown("Si detectas anomalías, ajusta manualmente:")
    override_mkt = st.slider("Corrección Mercado", -0.15, 0.15, 0.0, 0.01)
    override_news = st.slider("Corrección Noticias", -0.10, 0.10, 0.0, 0.01)

    run = st.button("CALCULAR PREDICCIÓN")

# --- MAIN ---
st.title(f"Análisis IPC: {calendar.month_name[target_month]} {target_year}")

if run:
    # 1. ESQUELETO
    easter = get_easter_month(target_year)
    skeleton = BASE_SKELETON[target_month]
    boost_val = 0.0
    if target_month == easter: boost_val = 0.40
    elif target_month == easter - 1: boost_val = 0.10
    
    final_skeleton = skeleton + boost_val
    
    # 2. DATOS EXTERNOS
    raw_mkt, logs_mkt = get_market_data_robust(target_year, target_month)
    raw_news, logs_news = get_news_robust(target_year, target_month)
    
    # 3. TOTALES (Con Override Manual)
    final_mkt = raw_mkt + override_mkt
    final_news = raw_news + override_news
    
    # 4. RESULTADO
    pred_monthly = final_skeleton + final_mkt + final_news
    
    # 5. FÓRMULA INE (ANUAL)
    f_base = 1 + (base_annual/100)
    f_out = 1 + (old_monthly/100)
    f_in = 1 + (pred_monthly/100)
    pred_annual = ((f_base / f_out) * f_in - 1) * 100

    # --- KPI CARDS ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("IPC MENSUAL (V34)", f"{pred_monthly:+.2f}%", delta="Predicción")
    c2.metric("IPC ANUAL (INE)", f"{pred_annual:.2f}%", f"{pred_annual-base_annual:+.2f}% vs Previo")
    c3.metric("ESQUELETO", f"{final_skeleton:+.2f}%", "Base Histórica", delta_color="off")
    c4.metric("MERCADO + NEWS", f"{final_mkt+final_news:+.2f}%", "Impacto Exógeno")

    # --- WATERFALL CHART ---
    fig = go.Figure(go.Waterfall(
        orientation = "v",
        measure = ["relative", "relative", "relative", "relative", "total"],
        x = ["Inercia Histórica", "Efecto Pascua", "Mercados", "Noticias/Ajuste", "PREDICCIÓN"],
        textposition = "outside",
        text = [f"{skeleton}%", f"{boost_val}%", f"{final_mkt:.2f}%", f"{final_news:.2f}%", f"<b>{pred_monthly:.2f}%</b>"],
        y = [skeleton, boost_val, final_mkt, final_news, pred_monthly],
        connector = {"line":{"color":"white"}},
        decreasing = {"marker":{"color":"#FF4B4B"}},
        increasing = {"marker":{"color":"#00CC96"}},
        totals = {"marker":{"color":"#1E88E5"}}
    ))
    fig.update_layout(title="Descomposición de Factores", template="plotly_dark", height=400)
    st.plotly_chart(fig, use_container_width=True)

    # --- LOGS DETALLADOS ---
    with st.expander("📝 Ver Auditoría de Datos (Logs)"):
        st.write(f"**Cálculo Anual:** ( (1+{base_annual}/100) / (1+{old_monthly}/100) ) * (1+{pred_monthly:.4f}/100) - 1")
        st.write("---")
        st.write("**Mercados:**")
        for l in logs_mkt: st.caption(l)
        if override_mkt != 0: st.warning(f"Ajuste manual aplicado: {override_mkt:+.2f}%")
        
        st.write("**Noticias:**")
        for h in logs_news: st.caption(f"- {h}")
        if override_news != 0: st.warning(f"Ajuste manual aplicado: {override_news:+.2f}%")

else:
    st.info("Configura los datos a la izquierda y pulsa CALCULAR.")
