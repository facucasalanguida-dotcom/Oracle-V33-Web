import streamlit as st
import yfinance as yf
from gnews import GNews
import calendar
import datetime
from datetime import timedelta
import plotly.graph_objects as go
import pandas as pd

# --- CONFIGURACIÓN UI ---
st.set_page_config(page_title="Oracle V38 | Sectorial AI", page_icon="🧬", layout="wide")
st.markdown("""
<style>
    .stApp { background-color: #080808; color: #e0e0e0; }
    h1, h2, h3 { font-family: 'Segoe UI', sans-serif; color: #4facfe; }
    div[data-testid="stMetric"] { background-color: #1a1a1a; border: 1px solid #333; border-radius: 8px; }
    .sector-card { padding: 10px; background-color: #121212; border-left: 3px solid #4facfe; margin-bottom: 5px; }
</style>
""", unsafe_allow_html=True)

# --- 1. CONFIGURACIÓN DE PESOS INE (La Estructura Real del País) ---
# Estos son los pesos oficiales aproximados del IPC de España.
SECTOR_WEIGHTS = {
    "Alimentos": 0.20,      # 20% del gasto
    "Energía/Vivienda": 0.13, # 13% (Luz, Gas, Agua)
    "Transporte": 0.12,     # 12% (Gasolina, Coches)
    "Turismo/Ocio": 0.15,   # 15% (Hoteles, Restaurantes)
    "Core/Resto": 0.40      # 40% (Ropa, Muebles, Servicios, etc.)
}

# --- 2. DICCIONARIO SEMÁNTICO SECTORIAL (El "Cerebro") ---
# La IA busca estos conceptos específicos para saber QUÉ parte de la economía se mueve.
SECTOR_KEYWORDS = {
    "Alimentos": {
        "subida": ["sequía", "aceite", "fruta", "carne", "cesta", "subida alimentos", "inflación alimentos"],
        "bajada": ["bajada iva", "supermercado baja", "oferta alimentos", "cosecha récord"],
        "impacto": 0.08 # Sensibilidad alta (Alimentos son volátiles)
    },
    "Energía/Vivienda": {
        "subida": ["luz sube", "gas dispara", "factura", "tope gas", "invierno", "calefacción"],
        "bajada": ["luz baja", "excepción ibérica", "bajada impuestos luz", "gas natural baja"],
        "impacto": 0.15 # Sensibilidad muy alta
    },
    "Transporte": {
        "subida": ["gasolina", "diesel", "surtidor", "petróleo", "barril", "transporte"],
        "bajada": ["subsidio", "ayuda combustible", "bajada gasolina"],
        "impacto": 0.10
    },
    "Turismo/Ocio": {
        "subida": ["hotel", "vuelos", "vacaciones", "restaurantes", "semana santa", "verano"],
        "bajada": ["fin temporada", "hoteles baratos", "baja ocupación"],
        "impacto": 0.12
    },
    "Core/Resto": {
        "subida": ["nueva colección", "inflación subyacente", "servicios"],
        "bajada": ["rebajas", "descuentos", "black friday", "promociones"],
        "impacto": 0.05
    }
}

# --- 3. ESTACIONALIDAD SECTORIAL (El "Reloj" del País) ---
# Cada sector tiene su propio ritmo biológico durante el año.
def get_sectorial_seasonality(month, year):
    # Detección Pascua
    a = year % 19; b = year // 100; c = year % 100; d = b // 4; e = b % 4
    f = (b + 8) // 25; g = (b - f + 1) // 3; h = (19 * a + b - d - g + 15) % 30
    i = c // 4; k = c % 4; l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    easter_month = (h + l - 7 * m + 114) // 31
    
    # Matriz Base (Mes: {Sector: Valor})
    seasonality = {
        # ENERO: Rebajas fuertes en Core (Ropa), subida en Energía (frío)
        1: {"Alimentos": 0.3, "Energía/Vivienda": 0.5, "Transporte": 0.0, "Turismo/Ocio": -0.4, "Core/Resto": -1.8}, 
        # FEBRERO: Rebote técnico
        2: {"Alimentos": 0.2, "Energía/Vivienda": 0.0, "Transporte": 0.2, "Turismo/Ocio": 0.1, "Core/Resto": 0.2},
        # MARZO: Transición
        3: {"Alimentos": 0.1, "Energía/Vivienda": -0.2, "Transporte": 0.3, "Turismo/Ocio": 0.3, "Core/Resto": 0.8},
        # MAYO: Valle Alimentos
        5: {"Alimentos": -0.4, "Energía/Vivienda": -0.1, "Transporte": 0.1, "Turismo/Ocio": 0.2, "Core/Resto": 0.1},
        # JULIO: Rebajas verano
        7: {"Alimentos": 0.0, "Energía/Vivienda": 0.4, "Transporte": 0.3, "Turismo/Ocio": 0.8, "Core/Resto": -1.8},
        # OCTUBRE: Ropa invierno
        10:{"Alimentos": 0.1, "Energía/Vivienda": 0.3, "Transporte": -0.1, "Turismo/Ocio": -0.5, "Core/Resto": 1.5},
        # DEFAULT
        "default": {"Alimentos": 0.1, "Energía/Vivienda": 0.1, "Transporte": 0.1, "Turismo/Ocio": 0.1, "Core/Resto": 0.1}
    }
    
    current = seasonality.get(month, seasonality["default"]).copy()
    
    # Ajuste Dinámico de Pascua
    if month == easter_month:
        current["Turismo/Ocio"] += 1.5 # Boost fuerte
    elif month == easter_month - 1:
        current["Turismo/Ocio"] += 0.5 # Pre-boost
        
    return current

# --- 4. MOTOR NLP SECTORIAL (Deep Learning Simulado) ---
def analyze_news_by_sector(year, month):
    try:
        # Búsqueda amplia para captar todo el ruido económico
        gnews = GNews(language='es', country='ES', period='15d', max_results=30)
        news = gnews.get_news("economía precios España")
        
        sector_scores = {k: 0.0 for k in SECTOR_WEIGHTS.keys()}
        evidence = {k: [] for k in SECTOR_WEIGHTS.keys()}
        
        for art in news:
            text = art['title'].lower()
            
            # Clasificación por Sector
            for sector, rules in SECTOR_KEYWORDS.items():
                impact_val = 0.0
                
                # Check Subidas
                for kw in rules["subida"]:
                    if kw in text:
                        # Modificadores de intensidad
                        multiplier = 1.0
                        if "dispara" in text or "fuerte" in text: multiplier = 1.5
                        if "leve" in text or "frena" in text: multiplier = 0.2
                        
                        impact_val = rules["impacto"] * multiplier
                        evidence[sector].append(f"🔴 {art['title']}")
                        break
                
                # Check Bajadas
                if impact_val == 0:
                    for kw in rules["bajada"]:
                        if kw in text:
                            impact_val = -rules["impacto"]
                            evidence[sector].append(f"🟢 {art['title']}")
                            break
                
                sector_scores[sector] += impact_val
        
        # Normalización (Topes lógicos por sector)
        for s in sector_scores:
            sector_scores[s] = max(min(sector_scores[s], 1.5), -1.5)
            
        return sector_scores, evidence
    except:
        return {k: 0.0 for k in SECTOR_WEIGHTS.keys()}, {}

# --- 5. MOTOR DE MERCADO (Hard Data) ---
def get_market_inputs(year, month):
    # Esto afecta principalmente a Energía y Transporte
    tickers = {"BRENT": "CL=F", "GAS": "NG=F"}
    
    # Fechas
    dt_target = datetime.datetime(year, month, 1)
    if dt_target > datetime.datetime.now():
        end = datetime.datetime.now()
        start = end - timedelta(days=30)
    else:
        last = calendar.monthrange(year, month)[1]
        start = dt_target; end = datetime.datetime(year, month, last)
        
    adjustments = {"Energía/Vivienda": 0.0, "Transporte": 0.0}
    logs = []
    
    try:
        for name, sym in tickers.items():
            df = yf.download(sym, start=start, end=end, progress=False, auto_adjust=True)
            if not df.empty:
                op = df.iloc[0]['Open']; cl = df.iloc[-1]['Close']
                change = ((cl - op) / op) * 100
                
                # Transmisión a IPC (Solo si es significativo >3%)
                if abs(change) > 3.0:
                    impact = change * 0.02 # Coeficiente de pase
                    if name == "BRENT": adjustments["Transporte"] += impact
                    if name == "GAS": adjustments["Energía/Vivienda"] += impact
                    logs.append(f"{name}: {change:+.1f}% -> Impacto {impact:+.2f}%")
    except: pass
    
    return adjustments, logs

# --- FRONTEND ---
with st.sidebar:
    st.title("ORACLE V38")
    st.caption("Deep Sectorial Learning")
    
    t_year = st.number_input("Año", 2024, 2030, 2026)
    t_month = st.selectbox("Mes", range(1, 13))
    
    st.divider()
    base_annual = st.number_input("IPC Anual Previo", value=2.90)
    old_monthly = st.number_input("IPC Saliente (Año Pasado)", value=-0.20)
    
    if st.button("ALIMENTAR MODELO"):
        st.session_state.run = True

if 'run' in st.session_state:
    # 1. CARGA DE BASE ESTACIONAL
    seasonality = get_sectorial_seasonality(t_month, t_year)
    
    # 2. ANÁLISIS NOTICIAS (SOFT DATA)
    news_impacts, news_evidence = analyze_news_by_sector(t_year, t_month)
    
    # 3. ANÁLISIS MERCADO (HARD DATA)
    mkt_impacts, mkt_logs = get_market_inputs(t_year, t_month)
    
    # 4. FUSIÓN Y PONDERACIÓN
    final_monthly_cpi = 0.0
    sector_breakdown = {}
    
    st.title(f"Análisis Forense: {calendar.month_name[t_month]} {t_year}")
    
    col_main, col_detail = st.columns([1, 1])
    
    with col_main:
        st.subheader("🏗️ Construcción del Dato")
        
        for sector, weight in SECTOR_WEIGHTS.items():
            # Suma de factores por sector
            s_base = seasonality.get(sector, 0.1)
            s_news = news_impacts.get(sector, 0.0)
            s_mkt = mkt_impacts.get(sector, 0.0)
            
            total_sector_var = s_base + s_news + s_mkt
            weighted_contribution = total_sector_var * weight
            
            final_monthly_cpi += weighted_contribution
            sector_breakdown[sector] = weighted_contribution
            
            # Visualización Tarjeta Sector
            with st.container():
                st.markdown(f"""
                <div class="sector-card">
                    <b>{sector}</b> (Peso: {int(weight*100)}%)<br>
                    Variación: <span style="color:{'#00ff99' if total_sector_var>0 else '#ff4444'}">{total_sector_var:+.2f}%</span> 
                    (Aporta al IPC: {weighted_contribution:+.3f}%)
                </div>
                """, unsafe_allow_html=True)

    # 5. RESULTADOS FINALES
    f_base = 1 + base_annual/100
    f_out = 1 + old_monthly/100
    f_in = 1 + final_monthly_cpi/100
    final_annual = ((f_base / f_out) * f_in - 1) * 100
    
    with col_detail:
        st.subheader("🎯 Predicción Final")
        c1, c2 = st.columns(2)
        c1.metric("IPC MENSUAL", f"{final_monthly_cpi:+.2f}%")
        c2.metric("IPC ANUAL", f"{final_annual:.2f}%", f"{final_annual-base_annual:+.2f}%")
        
        st.markdown("---")
        st.subheader("📰 Evidencia Encontrada")
        
        tabs = st.tabs(list(SECTOR_WEIGHTS.keys()))
        for i, sector in enumerate(SECTOR_WEIGHTS.keys()):
            with tabs[i]:
                if sector in mkt_impacts and mkt_impacts[sector] != 0:
                    st.caption("FUTUROS:")
                    st.write(f"Impacto Mercado: {mkt_impacts[sector]:+.2f}%")
                    
                ev = news_evidence.get(sector, [])
                if ev:
                    for e in ev: st.caption(e)
                else:
                    st.caption("Sin noticias específicas detectadas.")
                    
    # GRÁFICO FINAL (DONUT DE APORTACIÓN)
    labels = list(sector_breakdown.keys())
    values = [abs(v) for v in sector_breakdown.values()] # Solo magnitud visual
    
    fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.5)])
    fig.update_layout(title="Peso de cada Sector en el Dato Final", height=300, template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)
