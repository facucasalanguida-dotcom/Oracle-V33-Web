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

# --- CONFIGURACIÓN "DEEP BASKET" ---
st.set_page_config(page_title="Oracle V43 | Deep Basket", page_icon="🧺", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #F0F2F6; color: #1F2937; } /* Modo Claro/Profesional */
    h1, h2, h3 { font-family: 'Segoe UI', sans-serif; color: #111827; }
    .category-card { 
        background-color: white; 
        padding: 15px; 
        border-radius: 10px; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.1); 
        margin-bottom: 10px;
        border-left: 5px solid #3B82F6;
    }
    .price-tag { font-size: 1.5em; font-weight: bold; color: #10B981; }
    .price-tag-neg { font-size: 1.5em; font-weight: bold; color: #EF4444; }
    div[data-testid="stMetric"] { background-color: white; border-radius: 8px; border: 1px solid #E5E7EB; }
</style>
""", unsafe_allow_html=True)

# --- 1. DEFINICIÓN DE LA "CESTA PROFUNDA" (PESOS INE 2024 REALES APROX) ---
DEEP_BASKET = {
    "Alimentos Frescos": {
        "weight": 0.08, # 8% Fruta, Verdura, Carne fresca
        "keywords": ["precio fruta verdura", "precio pescado lonja", "precio carne pollo", "sequía agricultura", "cosecha"],
        "tickers": ["LE=F"] # Ganado
    },
    "Despensa (Aceite/Leche)": {
        "weight": 0.12, # 12% Aceite, Leche, Huevos, Pan
        "keywords": ["precio aceite oliva", "precio leche huevos", "cesta compra", "azúcar sube", "supermercados mercadona"],
        "tickers": ["ZW=F", "SB=F"] # Trigo, Azúcar
    },
    "Vivienda & Energía": {
        "weight": 0.14, # 14% Luz, Gas, Alquiler
        "keywords": ["precio luz hora", "tarifa gas", "subida alquileres", "euribor hipoteca", "tope gas"],
        "tickers": ["NG=F"] # Gas Natural
    },
    "Transporte": {
        "weight": 0.13, # 13% Gasolina, Coches
        "keywords": ["precio gasolina diesel", "surtidor", "abono transporte", "precio coches nuevos"],
        "tickers": ["BZ=F", "CL=F"] # Brent, WTI
    },
    "Hostelería & Turismo": {
        "weight": 0.13, # 13% Bares, Hoteles
        "keywords": ["precio menú día", "restaurantes suben", "precio hoteles verano", "semana santa turismo"],
        "tickers": [] # No hay ticker directo, depende puramente de servicios
    },
    "Core (Ropa/Servicios)": {
        "weight": 0.40, # 40% Ropa, Seguros, Telefonía, Muebles
        "keywords": ["rebajas ropa", "subida seguros", "precio telefonía", "inflación servicios", "electrodomésticos"],
        "tickers": ["HG=F"] # Cobre (Proxy industrial)
    }
}

# --- 2. MOTOR DE ANÁLISIS HÍBRIDO (NOTICIAS + MERCADO) ---
def analyze_basket_category(category, data, year, month):
    # Fechas
    dt_target = datetime.datetime(year, month, 1)
    is_future = dt_target > datetime.datetime.now()
    
    if is_future:
        period = '10d' # Tendencia actual
        start = datetime.datetime.now() - timedelta(days=30)
        end = datetime.datetime.now()
        gnews_start = None; gnews_end = None
    else:
        period = None
        last_day = calendar.monthrange(year, month)[1]
        start = dt_target; end = datetime.datetime(year, month, last_day)
        gnews_start = (year, month, 1); gnews_end = (year, month, last_day)

    # 1. ANÁLISIS FINANCIERO (HARD DATA)
    fin_score = 0.0
    fin_evidence = []
    
    for ticker in data["tickers"]:
        try:
            df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
            if not df.empty:
                op = float(df.iloc[0]['Open']); cl = float(df.iloc[-1]['Close'])
                change = ((cl - op) / op) * 100
                
                # Aceite de Oliva Proxy: Si el futuro del TRIGO sube mucho, asumimos presión en alimentos global
                # pero corregimos sensibilidades.
                impact = 0.0
                if abs(change) > 3.0: # Filtro ruido
                    impact = change * 0.03 # Transmisión suave
                    fin_evidence.append(f"📈 {ticker}: {change:+.1f}%")
                fin_score += impact
        except: pass

    # 2. ANÁLISIS NOTICIAS (SOFT DATA - MUY ESPECÍFICO)
    news_score = 0.0
    news_evidence = []
    
    # Construir query específica
    query = f"{' '.join(data['keywords'][:3])} España"
    
    try:
        gnews = GNews(language='es', country='ES', period=period, start_date=gnews_start, end_date=gnews_end, max_results=10)
        news = gnews.get_news(query)
        
        score_acc = 0
        for art in news:
            t = art['title'].lower()
            val = 0
            # Diccionario Semántico Expandido
            if "sube" in t or "dispara" in t or "récord" in t or "caro" in t: val = 1
            if "baja" in t or "descenso" in t or "barato" in t or "oferta" in t: val = -1
            if "iva" in t and "baja" in t: val = -2 # IVA es clave
            
            # Aceite de Oliva (Keyword Crítica)
            if "aceite" in t and "sube" in t: val = 2 # Pesa doble
            
            if val != 0:
                score_acc += val
                if len(news_evidence) < 2: news_evidence.append(art['title'])
        
        # Normalización
        if len(news) > 0:
            avg_score = score_acc / max(len(news), 1)
            # Sensibilidad por categoría
            factor = 0.08 if "Energía" in category else 0.05
            news_score = avg_score * factor
            
    except:
        news_evidence.append("Sin datos de noticias.")

    # FUSIÓN: Promedio ponderado (Si hay datos financieros, mandan un 60%)
    if fin_score != 0:
        final_impact = (fin_score * 0.6) + (news_score * 0.4)
    else:
        final_impact = news_score # Si no hay ticker (ej: Turismo), 100% noticias

    return final_impact, fin_evidence + news_evidence

# --- 3. ESQUELETO INE (BASE) ---
def get_skeleton(m, y):
    # Base histórica ajustada
    base = {1: -0.60, 2: 0.15, 3: 0.35, 4: 0.40, 5: 0.10, 6: 0.45, 7: -0.55, 8: 0.25, 9: -0.25, 10: 0.65, 11: 0.20, 12: 0.35}
    a=y%19;b=y//100;c=y%100;d=b//4;e=b%4;f=(b+8)//25;g=(b-f+1)//3;h=(19*a+b-d-g+15)%30;i=c//4;k=c%4;l=(32*2*e+2*i-h-k)%7;m_p=(a+11*h+22*l)//451;easter=(h+l-7*m_p+114)//31
    val = base.get(m, 0.2)
    if m == easter: val += 0.3
    if m == easter - 1: val += 0.1
    return val

# --- UI ---
with st.sidebar:
    st.title("ORACLE V43")
    st.caption("DEEP BASKET ANALYSIS")
    
    st.header("1. Configuración")
    t_year = st.number_input("Año", 2024, 2030, 2026)
    t_month = st.selectbox("Mes", range(1, 13))
    
    st.header("2. Punto de Partida")
    base_annual = st.number_input("IPC Base Anual", value=2.80)
    old_monthly = st.number_input("IPC Saliente (-1 año)", value=0.30)
    
    st.divider()
    
    st.header("3. Ajuste Manual de Auditor")
    st.markdown("Corrige la IA si tienes datos mejores:")
    
    # Sliders manuales para corrección humana
    manual_adjustments = {}
    for cat in DEEP_BASKET.keys():
        manual_adjustments[cat] = st.slider(f"Ajuste {cat.split()[0]}", -0.5, 0.5, 0.0, 0.01)

    if st.button("CALCULAR CESTA COMPLETA"):
        st.session_state.deep_calc = True

if 'deep_calc' in st.session_state:
    st.title(f"🧾 TICKET DE INFLACIÓN: {calendar.month_name[t_month].upper()} {t_year}")
    
    # 1. CÁLCULO
    skeleton = get_skeleton(t_month, t_year)
    
    total_impact_accumulated = 0.0
    results_breakdown = {}
    
    # Barra de progreso para sensación de carga de datos masiva
    progress_bar = st.progress(0)
    
    col_main, col_ticket = st.columns([2, 1])
    
    with col_main:
        st.subheader("🛒 Desglose por Categoría")
        
        i = 0
        for cat, data in DEEP_BASKET.items():
            # Progreso visual
            i += 1
            progress_bar.progress(int((i / 6) * 100))
            
            # Algoritmo
            impact, evidence = analyze_basket_category(cat, data, t_year, t_month)
            
            # Sumar Inercia Base (Distribuida) + Impacto IA + Ajuste Manual
            base_share = skeleton * data["weight"]
            final_cat_val = base_share + (impact * data["weight"]) + (manual_adjustments[cat] * data["weight"])
            
            total_impact_accumulated += final_cat_val
            results_breakdown[cat] = final_cat_val
            
            # Renderizado de Tarjeta
            color_border = "#EF4444" if final_cat_val > 0 else "#10B981"
            icon = "📈" if final_cat_val > 0 else "📉"
            
            with st.expander(f"{icon} {cat} | Aporte: {final_cat_val:+.3f}%"):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown("**Evidencia detectada:**")
                    if not evidence: st.caption("Inercia histórica pura.")
                    for e in evidence: st.markdown(f"- {e}")
                with c2:
                    st.metric("Variación", f"{final_cat_val:+.3f}%")
                    st.caption(f"Peso IPC: {int(data['weight']*100)}%")

    progress_bar.empty()

    # CÁLCULO FINAL
    f_base = 1 + base_annual/100
    f_out = 1 + old_monthly/100
    f_in = 1 + total_impact_accumulated/100
    final_annual = ((f_base / f_out) * f_in - 1) * 100

    with col_ticket:
        st.markdown("""
        <div style="background-color: white; padding: 20px; border: 1px dashed #999; font-family: 'Courier New';">
            <h3 style="text-align: center;">SUPERMERCADO IPC</h3>
            <hr>
            <table style="width:100%">
        """, unsafe_allow_html=True)
        
        for cat, val in results_breakdown.items():
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; font-family: 'Courier New'; font-size: 0.9em;">
                <span>{cat[:15]}..</span>
                <span>{val:+.3f}</span>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown(f"""
            <hr>
            <div style="display:flex; justify-content:space-between; font-weight:bold; font-size: 1.2em;">
                <span>TOTAL MENSUAL</span>
                <span>{total_impact_accumulated:+.2f}%</span>
            </div>
            <br>
            <div style="background-color: #111; color: white; padding: 10px; text-align: center;">
                IPC ANUAL: {final_annual:.2f}%
            </div>
            <div style="text-align: center; font-size: 0.8em; margin-top: 10px;">
                {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    # GRÁFICO FINAL
    st.markdown("---")
    fig = go.Figure(go.Bar(
        x=list(results_breakdown.values()),
        y=list(results_breakdown.keys()),
        orientation='h',
        marker=dict(color=['#EF4444' if x > 0 else '#10B981' for x in results_breakdown.values()])
    ))
    fig.update_layout(title="Contribución Real por Cesta", height=400)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Configura la cesta a la izquierda y pulsa CALCULAR.")
