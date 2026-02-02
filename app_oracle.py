import streamlit as st
import yfinance as yf
from gnews import GNews
import calendar
import datetime
from datetime import timedelta
import plotly.graph_objects as go
import pandas as pd
import time

# --- CONFIGURACIÓN UI ---
st.set_page_config(page_title="Oracle V39 | Active Hunting", page_icon="🐕", layout="wide")
st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    h1, h2, h3 { font-family: 'Roboto Mono', monospace; color: #58a6ff; }
    .sector-box { 
        background-color: #161b22; 
        border: 1px solid #30363d; 
        border-radius: 6px; 
        padding: 15px; 
        margin-bottom: 10px;
    }
    .highlight { color: #58a6ff; font-weight: bold; }
    div[data-testid="stStatusWidget"] { background-color: #161b22; }
</style>
""", unsafe_allow_html=True)

# --- 1. ESTRUCTURA DE PESOS (INE) ---
SECTOR_WEIGHTS = {
    "Alimentos": 0.20,
    "Energía/Vivienda": 0.13,
    "Transporte": 0.12,
    "Turismo/Ocio": 0.15,
    "Core (Ropa/Servicios)": 0.40
}

# --- 2. CONFIGURACIÓN DE LOS "SABUESOS" (BUSCADORES ESPECÍFICOS) ---
# Cada sector tiene su propia "Query" de búsqueda para obligar a Google a darnos datos.
SECTOR_QUERIES = {
    "Alimentos": "precio alimentos cesta compra aceite fruta supermercado España",
    "Energía/Vivienda": "precio luz gas electricidad tarifa regulada tope gas España",
    "Transporte": "precio gasolina diesel carburantes surtidor transporte España",
    "Turismo/Ocio": "precio hoteles vacaciones vuelos restaurantes semana santa España",
    "Core (Ropa/Servicios)": "rebajas ropa inflación servicios ipc subyacente España"
}

# Palabras clave de sentimiento
SENTIMENT_MAP = {
    "subida": 1, "alza": 1, "dispara": 1.5, "caro": 1, "récord": 1.5,
    "bajada": -1, "descenso": -1, "desploma": -1.5, "barato": -1, "oferta": -0.5,
    "frena": -0.5, "modera": -0.5 # Inversión de tendencia
}

# --- 3. ESTACIONALIDAD BASE (Reloj Biológico del IPC) ---
def get_seasonality(month, year):
    # Cálculo Pascua
    a = year % 19; b = year // 100; c = year % 100; d = b // 4; e = b % 4
    f = (b + 8) // 25; g = (b - f + 1) // 3; h = (19 * a + b - d - g + 15) % 30
    i = c // 4; k = c % 4; l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    easter_m = (h + l - 7 * m + 114) // 31
    
    # Matriz Base (Ajustada para clavar Enero)
    base = {
        1: {"Alimentos": 0.2, "Energía/Vivienda": 0.6, "Transporte": 0.1, "Turismo/Ocio": -0.5, "Core (Ropa/Servicios)": -1.9},
        2: {"Alimentos": 0.2, "Energía/Vivienda": 0.0, "Transporte": 0.2, "Turismo/Ocio": 0.2, "Core (Ropa/Servicios)": 0.2},
        3: {"Alimentos": 0.1, "Energía/Vivienda": -0.2, "Transporte": 0.3, "Turismo/Ocio": 0.3, "Core (Ropa/Servicios)": 0.9},
        4: {"Alimentos": 0.1, "Energía/Vivienda": 0.0, "Transporte": 0.2, "Turismo/Ocio": 0.1, "Core (Ropa/Servicios)": 0.5},
        5: {"Alimentos": -0.4, "Energía/Vivienda": -0.1, "Transporte": 0.1, "Turismo/Ocio": 0.2, "Core (Ropa/Servicios)": 0.1},
        6: {"Alimentos": 0.1, "Energía/Vivienda": 0.4, "Transporte": 0.2, "Turismo/Ocio": 0.6, "Core (Ropa/Servicios)": 0.1},
        7: {"Alimentos": 0.0, "Energía/Vivienda": 0.5, "Transporte": 0.3, "Turismo/Ocio": 0.9, "Core (Ropa/Servicios)": -1.8},
        8: {"Alimentos": 0.1, "Energía/Vivienda": 0.1, "Transporte": 0.1, "Turismo/Ocio": 0.2, "Core (Ropa/Servicios)": 0.1},
        9: {"Alimentos": -0.1, "Energía/Vivienda": 0.0, "Transporte": -0.2, "Turismo/Ocio": -1.5, "Core (Ropa/Servicios)": 1.2},
        10:{"Alimentos": 0.2, "Energía/Vivienda": 0.4, "Transporte": -0.1, "Turismo/Ocio": -0.5, "Core (Ropa/Servicios)": 1.8},
        11:{"Alimentos": 0.1, "Energía/Vivienda": 0.2, "Transporte": 0.0, "Turismo/Ocio": -0.2, "Core (Ropa/Servicios)": 0.1},
        12:{"Alimentos": 0.5, "Energía/Vivienda": 0.3, "Transporte": 0.1, "Turismo/Ocio": 0.5, "Core (Ropa/Servicios)": 0.2}
    }
    
    current = base.get(month, base[1]).copy()
    
    # Ajuste Pascua
    if month == easter_m: current["Turismo/Ocio"] += 1.2
    elif month == easter_m - 1: current["Turismo/Ocio"] += 0.4
        
    return current

# --- 4. MOTOR DE CAZA ACTIVA (ACTIVE HUNTING) ---
def hunt_news_per_sector(year, month):
    impacts = {}
    evidence = {}
    
    # Determinamos fechas
    dt_target = datetime.datetime(year, month, 1)
    is_future = dt_target > datetime.datetime.now()
    
    if is_future:
        # Si es futuro, buscamos noticias RECIENTES (últimos 10 días) para ver tendencia actual
        period = '10d'
        start_d = None; end_d = None
    else:
        last = calendar.monthrange(year, month)[1]
        start_d = (year, month, 1)
        end_d = (year, month, last)
        period = None

    # Inicializamos barra de progreso visual en el frontend
    status_msg = st.status("🐕 Soltando a los sabuesos de noticias...", expanded=True)
    
    for sector, query in SECTOR_QUERIES.items():
        status_msg.write(f"🔍 Buscando datos para: **{sector}**...")
        
        try:
            gnews = GNews(language='es', country='ES', period=period, start_date=start_d, end_date=end_d, max_results=15)
            # Añadimos el año a la query para contexto si es pasado
            full_query = f"{query} {year}" if not is_future else query
            
            news = gnews.get_news(full_query)
            
            score = 0.0
            found_headlines = []
            
            for art in news:
                t = art['title'].lower()
                val = 0
                for w, v in SENTIMENT_MAP.items():
                    if w in t:
                        val += v
                
                # IVA es especial
                if "iva" in t and "baja" in t: val -= 2.0
                if "iva" in t and "sube" in t: val += 2.0
                
                if val != 0:
                    score += val
                    if len(found_headlines) < 2: found_headlines.append(f"{art['title']}")
            
            # Normalización del sector (Sensibilidad)
            # Alimentos y Energía son muy sensibles, Turismo menos por noticias
            sensitivity = 0.03 if sector == "Core (Ropa/Servicios)" else 0.05
            
            # Calculamos promedio del sentimiento
            if len(news) > 0:
                avg_score = score / max(len(news), 1)
                final_sector_impact = avg_score * sensitivity
            else:
                final_sector_impact = 0.0
                found_headlines = ["(Sin datos específicos, usando inercia)"]
            
            impacts[sector] = final_sector_impact
            evidence[sector] = found_headlines
            
            time.sleep(0.2) # Pequeña pausa para no saturar Google
            
        except Exception as e:
            impacts[sector] = 0.0
            evidence[sector] = [f"Error de conexión: {str(e)}"]
            
    status_msg.update(label="✅ Caza de noticias completada", state="complete", expanded=False)
    return impacts, evidence

# --- 5. MOTOR MERCADO (HARD DATA) ---
def get_market_data(year, month):
    dt_target = datetime.datetime(year, month, 1)
    if dt_target > datetime.datetime.now():
        end = datetime.datetime.now()
        start = end - timedelta(days=30)
    else:
        last = calendar.monthrange(year, month)[1]
        start = dt_target; end = datetime.datetime(year, month, last)
        
    adjustments = {k: 0.0 for k in SECTOR_WEIGHTS.keys()}
    
    tickers = {"BRENT": ("CL=F", "Transporte"), "GAS": ("NG=F", "Energía/Vivienda")}
    
    try:
        for name, (sym, sector) in tickers.items():
            df = yf.download(sym, start=start, end=end, progress=False, auto_adjust=True)
            if not df.empty:
                op = float(df.iloc[0]['Open']); cl = float(df.iloc[-1]['Close'])
                change = ((cl - op) / op) * 100
                
                # Filtro de Ruido (>4%)
                if abs(change) > 4.0:
                    impact = change * 0.015 # Transmisión
                    adjustments[sector] += impact
    except: pass
    
    return adjustments

# --- FRONTEND ---
with st.sidebar:
    st.title("ORACLE V39")
    st.caption("Active Sectorial Hunting")
    
    col_y, col_m = st.columns(2)
    t_year = col_y.number_input("Año", 2024, 2030, 2026)
    t_month = col_m.selectbox("Mes", range(1, 13))
    
    st.divider()
    base_annual = st.number_input("IPC Anual Previo", value=2.90)
    old_monthly = st.number_input("IPC Saliente (-1 año)", value=-0.20)
    
    if st.button("INICIAR RASTREO"):
        st.session_state.hunting = True

if 'hunting' in st.session_state:
    st.title(f"Informe de Inteligencia: {calendar.month_name[t_month]} {t_year}")
    
    # 1. ESTACIONALIDAD
    seasonal_data = get_seasonality(t_month, t_year)
    
    # 2. CAZA DE NOTICIAS (ACTIVE HUNTING)
    news_impacts, news_evidence = hunt_news_per_sector(t_year, t_month)
    
    # 3. DATOS MERCADO
    mkt_impacts = get_market_data(t_year, t_month)
    
    # 4. FUSIÓN
    total_monthly = 0.0
    sector_results = {}
    
    col_left, col_right = st.columns([3, 2])
    
    with col_left:
        st.subheader("🧩 Desglose por Sector")
        
        for sector, weight in SECTOR_WEIGHTS.items():
            # Suma de factores
            s_base = seasonal_data.get(sector, 0.0)
            s_news = news_impacts.get(sector, 0.0)
            s_mkt = mkt_impacts.get(sector, 0.0)
            
            # Valor final del sector
            sector_val = s_base + s_news + s_mkt
            
            # Contribución al IPC General (Valor * Peso)
            contribution = sector_val * weight
            total_monthly += contribution
            
            sector_results[sector] = contribution
            
            # Visualización
            headlines_html = "".join([f"<li>{h}</li>" for h in news_evidence[sector][:2]])
            
            # Color según si sube o baja
            color_border = "#58a6ff" if contribution > 0 else "#3fb950" 
            
            st.markdown(f"""
            <div class="sector-box" style="border-left: 4px solid {color_border}">
                <div style="display:flex; justify-content:space-between;">
                    <span style="font-weight:bold; font-size:1.1em;">{sector}</span>
                    <span style="color:{color_border}; font-weight:bold;">{sector_val:+.2f}% (Aporta {contribution:+.3f})</span>
                </div>
                <div style="font-size:0.8em; color:#8b949e; margin-top:5px;">
                    <i>Inercia: {s_base}% | Noticias: {s_news:.3f}% | Mercado: {s_mkt:.3f}%</i>
                </div>
                <ul style="font-size:0.8em; margin-top:5px; padding-left:20px; color:#c9d1d9;">
                    {headlines_html}
                </ul>
            </div>
            """, unsafe_allow_html=True)

    # 5. CÁLCULO ANUAL
    f_base = 1 + base_annual/100
    f_out = 1 + old_monthly/100
    f_in = 1 + total_monthly/100
    final_annual = ((f_base / f_out) * f_in - 1) * 100
    
    with col_right:
        st.subheader("📈 Resultado Consolidado")
        
        c1, c2 = st.columns(2)
        c1.metric("IPC MENSUAL", f"{total_monthly:+.2f}%", "Suma Ponderada")
        c2.metric("IPC ANUAL", f"{final_annual:.2f}%", f"{final_annual-base_annual:+.2f}% vs Previo")
        
        # Gráfico Donut
        labels = list(sector_results.keys())
        values = [abs(v) for v in sector_results.values()]
        
        fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.6)])
        fig.update_layout(title="Peso en la Variación", template="plotly_dark", height=300, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        
        st.info(f"""
        **Análisis de Impacto:**
        La inflación anual se sitúa en **{final_annual:.2f}%**.
        Esto se debe principalmente al comportamiento del sector **{max(sector_results, key=sector_results.get)}**, 
        que ha aportado **{max(sector_results.values()):+.3f}%** al índice general.
        """)

else:
    st.info("Configura el año y mes a la izquierda para liberar a los sabuesos.")
