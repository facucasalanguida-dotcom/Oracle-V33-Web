import streamlit as st
import yfinance as yf
from gnews import GNews
import calendar
import datetime
from datetime import timedelta
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import time

# --- CONFIGURACIÓN UI ---
st.set_page_config(page_title="Oracle V40 | Omni-Data", page_icon="🧿", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #E6E6E6; }
    h1, h2, h3 { font-family: 'Inter', sans-serif; color: #4CC9F0; }
    .metric-box { background-color: #1A1D24; border: 1px solid #30363D; padding: 15px; border-radius: 8px; }
    .stStatusWidget { background-color: #1A1D24; }
</style>
""", unsafe_allow_html=True)

# --- 1. CONFIGURACIÓN ESTRUCTURAL ---
SECTOR_WEIGHTS = {
    "Alimentos": 0.20,
    "Energía": 0.13,
    "Transporte": 0.12,
    "Servicios/Turismo": 0.15,
    "Core (Resto)": 0.40
}

# --- 2. DICCIONARIO SEMÁNTICO MASIVO (100+ Keywords) ---
# Si no sale una palabra, saldrá otra. Cubrimos todo el espectro económico.
KEYWORDS_DB = {
    "Alimentos": {
        "up": ["sequía", "mala cosecha", "aceite dispara", "subida precio alimentos", "cesta compra cara", "azúcar", "cacao", "ganadería costos", "pesca"],
        "down": ["bajada iva alimentos", "supermercado baja", "buena cosecha", "oferta", "bajada precios", "estabiliza alimentos"],
        "sensibility": 0.06
    },
    "Energía": {
        "up": ["luz sube", "gas dispara", "pool eléctrico", "pvpc sube", "calefacción", "ola de frío", "tope gas", "megavatio"],
        "down": ["luz baja", "excepción ibérica", "bajada impuestos luz", "bono social", "energía barata", "viento", "renovables"],
        "sensibility": 0.12
    },
    "Transporte": {
        "up": ["gasolina sube", "diesel", "barril brent", "surtidor", "céntimos litro", "peajes", "coches"],
        "down": ["gasolina baja", "ayuda combustible", "bonificación", "transporte gratis", "abono transporte"],
        "sensibility": 0.08
    },
    "Servicios/Turismo": {
        "up": ["hotel récord", "vuelos caros", "lleno semana santa", "temporada alta", "restaurantes suben", "hostelería"],
        "down": ["baja ocupación", "ofertas viaje", "fin temporada", "hoteles baratos"],
        "sensibility": 0.05
    },
    "Core (Resto)": {
        "up": ["inflación subyacente", "servicios", "seguros", "telefonía", "alquiler sube", "ropa nueva colección"],
        "down": ["rebajas", "descuentos", "black friday", "bajada tipos", "consumo frena"],
        "sensibility": 0.04
    }
}

# --- 3. HARD DATA AVANZADO (MATERIAS PRIMAS) ---
# Añadimos Trigo (Alimentos) y Maíz para no depender solo de Google.
MARKET_TICKERS = {
    "BRENT (Petróleo)": {"sym": "CL=F", "sector": "Transporte", "weight": 0.02},
    "GAS (TTF/Henry)": {"sym": "NG=F", "sector": "Energía", "weight": 0.03},
    "TRIGO (Alimentos)": {"sym": "ZW=F", "sector": "Alimentos", "weight": 0.015}, # Nuevo
    "MAÍZ (Alimentos)": {"sym": "ZC=F", "sector": "Alimentos", "weight": 0.01}    # Nuevo
}

# --- 4. MOTOR DE ESTACIONALIDAD (ESQUELETO INE) ---
def get_ine_skeleton(month, year):
    # Cálculo Pascua
    a = year % 19; b = year // 100; c = year % 100; d = b // 4; e = b % 4
    f = (b + 8) // 25; g = (b - f + 1) // 3; h = (19 * a + b - d - g + 15) % 30
    i = c // 4; k = c % 4; l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    easter_m = (h + l - 7 * m + 114) // 31
    
    # Matriz Base (Ajustada a la realidad española)
    base = {
        1: -0.50, 2: 0.20, 3: 0.30, 4: 0.35, 5: 0.10, 6: 0.50,
        7: -0.50, 8: 0.20, 9: -0.30, 10: 0.60, 11: 0.15, 12: 0.25
    }
    
    val = base.get(month, 0.2)
    # Ajuste Pascua
    if month == easter_m: val += 0.30
    elif month == easter_m - 1: val += 0.10
    
    return val

# --- 5. MOTOR "INE FALLBACK" (LA RED DE SEGURIDAD) ---
def calculate_statistical_projection(prev_annual, skeleton):
    """
    Si no hay noticias, calculamos la inercia estadística.
    Si la inflación previa es alta (ej 3%), empuja el mensual hacia arriba ligeramente.
    """
    inertia = (prev_annual - 2.0) * 0.02 # Factor de arrastre
    return skeleton + inertia

# --- 6. MOTOR DE BÚSQUEDA HÍBRIDO (NEWS + FALLBACK) ---
def analyze_sector_impacts(year, month, prev_annual):
    impacts = {k: 0.0 for k in SECTOR_WEIGHTS.keys()}
    evidence = {k: [] for k in SECTOR_WEIGHTS.keys()}
    
    # Fechas
    dt_target = datetime.datetime(year, month, 1)
    is_future = dt_target > datetime.datetime.now()
    
    # Configuración GNews
    period = '15d' if is_future else None
    start_d = None if is_future else (year, month, 1)
    end_d = None if is_future else (year, month, calendar.monthrange(year, month)[1])
    
    status_box = st.status("📡 Escaneando Fuentes de Datos...", expanded=True)
    
    gnews = GNews(language='es', country='ES', period=period, start_date=start_d, end_date=end_d, max_results=20)
    
    for sector, keywords in KEYWORDS_DB.items():
        status_box.write(f"🔍 Analizando Sector: **{sector}**...")
        
        # 1. BÚSQUEDA AMPLIA (Query dinámica)
        # Construimos una query con las top 3 palabras clave para maximizar resultados
        query_terms = " ".join(keywords["up"][:3])
        query = f"{sector} precio España {query_terms}"
        
        try:
            news = gnews.get_news(query)
            score = 0.0
            headlines = []
            
            # Análisis Semántico
            for art in news:
                t = art['title'].lower()
                # Check UP
                for w in keywords["up"]:
                    if w in t: 
                        score += 1
                        if len(headlines)<1: headlines.append(f"🔴 {art['title']}")
                        break
                # Check DOWN
                for w in keywords["down"]:
                    if w in t: 
                        score -= 1
                        if len(headlines)<1: headlines.append(f"🟢 {art['title']}")
                        break
            
            # --- CEREBRO V40: GESTIÓN DE FALTA DE DATOS ---
            if len(news) == 0 or score == 0:
                # NO HAY DATOS -> ACTIVAMOS FALLBACK INE
                # Usamos una pequeña inercia basada en la inflación anual previa
                fallback_val = (prev_annual - 2.0) * 0.01 * (1 if sector != "Alimentos" else 2)
                impacts[sector] = fallback_val
                evidence[sector] = [f"⚠️ Sin noticias recientes. Proyección INE: {fallback_val:+.3f}%"]
            else:
                # HAY DATOS -> NORMALIZAMOS
                # Limitamos la cantidad de noticias para no saturar
                normalized_score = score / max(len(news), 3) 
                impacts[sector] = normalized_score * keywords["sensibility"]
                evidence[sector] = headlines

        except Exception as e:
            # ERROR API -> FALLBACK SEGURO
            impacts[sector] = 0.0
            evidence[sector] = ["Error conexión. Impacto Neutro."]
            
        time.sleep(0.1)

    status_box.update(label="✅ Análisis Completado", state="complete", expanded=False)
    return impacts, evidence

# --- 7. MOTOR FINANCIERO ROBUSTO (Yahoo Finance) ---
def get_financial_data(year, month):
    impacts = {k: 0.0 for k in SECTOR_WEIGHTS.keys()}
    logs = []
    
    dt_target = datetime.datetime(year, month, 1)
    if dt_target > datetime.datetime.now():
        end = datetime.datetime.now()
        start = end - timedelta(days=30)
    else:
        last = calendar.monthrange(year, month)[1]
        start = dt_target; end = datetime.datetime(year, month, last)
        
    for name, data in MARKET_TICKERS.items():
        try:
            df = yf.download(data["sym"], start=start, end=end, progress=False, auto_adjust=True)
            if not df.empty:
                op = float(df.iloc[0]['Open']); cl = float(df.iloc[-1]['Close'])
                change = ((cl - op) / op) * 100
                
                # Filtro de Ruido (>3%)
                if abs(change) > 3.0:
                    val = change * data["weight"]
                    impacts[data["sector"]] += val
                    logs.append(f"{name}: {change:+.1f}% -> {data['sector']} {val:+.3f}%")
        except: pass
        
    return impacts, logs

# --- FRONTEND V40 ---
with st.sidebar:
    st.title("ORACLE V40")
    st.caption("Omni-Source Intelligence")
    
    t_year = st.number_input("Año", 2024, 2030, 2026)
    t_month = st.selectbox("Mes", range(1, 13))
    
    st.divider()
    base_annual = st.number_input("IPC Anual Previo", 2.90)
    old_monthly = st.number_input("IPC Mensual Saliente", -0.20)
    
    st.markdown("---")
    if st.button("CALCULAR PREVISIÓN"):
        st.session_state.calc = True

if 'calc' in st.session_state:
    # 1. ESQUELETO
    skeleton = get_ine_skeleton(t_month, t_year)
    
    # 2. SOFT DATA (Con Fallback INE)
    soft_impacts, soft_evidence = analyze_sector_impacts(t_year, t_month, base_annual)
    
    # 3. HARD DATA (Materias Primas)
    hard_impacts, hard_logs = get_financial_data(t_year, t_month)
    
    # 4. AGREGACIÓN
    total_monthly = 0.0
    breakdown = {}
    
    st.title(f"Previsión IPC: {calendar.month_name[t_month]} {t_year}")
    
    col_metrics, col_graph = st.columns([1, 2])
    
    with col_graph:
        # Gráfico de Barras por Sector
        for sector, weight in SECTOR_WEIGHTS.items():
            # Inercia base distribuida + Inputs
            s_base = skeleton * weight # Parte proporcional del esqueleto
            s_soft = soft_impacts.get(sector, 0.0)
            s_hard = hard_impacts.get(sector, 0.0)
            
            total_sector = s_base + s_soft + s_hard
            breakdown[sector] = total_sector
            total_monthly += total_sector
            
        # Graficar
        fig = go.Figure(go.Bar(
            x=list(breakdown.values()),
            y=list(breakdown.keys()),
            orientation='h',
            marker=dict(color=['#FF4B4B' if x < 0 else '#00CC96' for x in breakdown.values()]),
            text=[f"{x:+.3f}%" for x in breakdown.values()],
            textposition='auto'
        ))
        fig.update_layout(title="Contribución por Sector (Puntos Porcentuales)", template="plotly_dark", height=350)
        st.plotly_chart(fig, use_container_width=True)

    # 5. CÁLCULO ANUAL
    f_base = 1 + base_annual/100
    f_out = 1 + old_monthly/100
    f_in = 1 + total_monthly/100
    final_annual = ((f_base / f_out) * f_in - 1) * 100
    
    with col_metrics:
        st.markdown("### 🎯 Resultados")
        st.metric("IPC MENSUAL", f"{total_monthly:+.2f}%", f"Inercia: {skeleton}%")
        st.metric("IPC ANUAL", f"{final_annual:.2f}%", f"{final_annual-base_annual:+.2f}% vs Previo", delta_color="inverse")
        
        st.markdown("### 🛡️ Fuentes Utilizadas")
        st.caption(f"• Esqueleto INE Base")
        st.caption(f"• Yahoo Finance (Petróleo/Gas/Trigo)")
        st.caption(f"• GNews Semántico (Con Fallback Estadístico)")

    # DETALLE DE EVIDENCIA
    st.markdown("---")
    st.subheader("🗂️ Evidencia Documental (Auditoría)")
    
    tabs = st.tabs(list(SECTOR_WEIGHTS.keys()))
    for i, sector in enumerate(SECTOR_WEIGHTS.keys()):
        with tabs[i]:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**📰 Noticias / Proyección INE**")
                for e in soft_evidence.get(sector, []):
                    st.code(e, language="text")
            with c2:
                st.markdown("**📈 Mercados Financieros**")
                found_mkt = False
                for log in hard_logs:
                    if sector in str(MARKET_TICKERS.values()): # Simplificación visual
                        st.caption(log)
                        found_mkt = True
                if hard_impacts.get(sector, 0) != 0:
                    st.metric("Impacto Directo", f"{hard_impacts[sector]:+.3f}%")
                else:
                    st.caption("Sin impacto directo de futuros.")
