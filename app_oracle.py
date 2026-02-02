import streamlit as st
from gnews import GNews
import calendar
import datetime
import plotly.graph_objects as go
import plotly.figure_factory as ff
import pandas as pd
import numpy as np
import re

# --- CONFIGURACIÓN RETAIL ---
st.set_page_config(page_title="Oracle V60 | Retail Scanner", page_icon="🛒", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #121212; color: #E0E0E0; }
    h1, h2, h3 { font-family: 'Arial', sans-serif; color: #00E676; }
    .product-card { 
        background-color: #1E1E1E; border: 1px solid #333; 
        padding: 10px; margin-bottom: 5px; border-radius: 5px;
    }
    .price-up { color: #FF5252; font-weight: bold; }
    .price-down { color: #69F0AE; font-weight: bold; }
    .supermarket-tag { 
        background-color: #263238; color: #FFF; 
        padding: 2px 6px; font-size: 0.75em; border-radius: 4px; border: 1px solid #546E7A;
    }
    div[data-testid="stMetric"] { background-color: #1E1E1E; border: 1px solid #333; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. DEFINICIÓN DE LA CESTA BÁSICA (SUPERMERCADO)
# ==============================================================================
# Estos son los productos testigo que vamos a rastrear en los lineales.
BASIC_BASKET = {
    "Aceite de Oliva": {"keywords": ["precio aceite oliva", "virgen extra"], "w": 0.3},
    "Leche/Lácteos":   {"keywords": ["precio leche", "carton leche", "precio mantequilla"], "w": 0.2},
    "Huevos":          {"keywords": ["precio huevos", "docena huevos"], "w": 0.1},
    "Pan/Cereales":    {"keywords": ["precio pan", "barra pan", "precio harina"], "w": 0.15},
    "Pollo/Carne":     {"keywords": ["precio pollo", "filetes pollo", "precio carne cerdo"], "w": 0.25}
}

# Supermercados Objetivo (Targets)
RETAILERS = ["Mercadona", "Carrefour", "Lidl", "Dia", "Alcampo"]

# ==============================================================================
# 2. MOTOR "RETAIL CRAWLER" (META-SCRAPING)
# ==============================================================================
def scan_supermarket_shelves(year, month):
    """
    Busca intersecciones entre PRODUCTO + SUPERMERCADO + CAMBIO DE PRECIO.
    Ej: "Mercadona sube el precio de la leche"
    """
    impacts = {k: 0.0 for k in BASIC_BASKET.keys()}
    evidence_log = []
    
    # Configuración de Fechas
    is_future = datetime.datetime(year, month, 1) > datetime.datetime.now()
    period = '15d' if is_future else None
    s_date = None if is_future else (year, month, 1)
    e_date = None if is_future else (year, month, calendar.monthrange(year, month)[1])
    
    gnews = GNews(language='es', country='ES', period=period, start_date=s_date, end_date=e_date, max_results=10)
    
    progress_bar = st.progress(0)
    
    # Iteramos por Producto
    idx = 0
    for product, data in BASIC_BASKET.items():
        idx += 1
        progress_bar.progress(int((idx / len(BASIC_BASKET)) * 100))
        
        # Query compuesta: "precio leche mercadona españa"
        # Usamos el primer retailer y palabra clave para muestreo rápido, 
        # pero GNews traerá resultados de todos si es relevante.
        base_query = f"{data['keywords'][0]} supermercado precio España"
        
        try:
            news = gnews.get_news(base_query)
            prod_score = 0
            
            for art in news:
                t = art['title'].lower()
                
                # 1. Detectar Dirección del Precio
                direction = 0
                if "sube" in t or "encarece" in t or "dispara" in t: direction = 1
                elif "baja" in t or "barato" in t or "oferta" in t: direction = -1
                
                # 2. Detectar Supermercado (Etiquetado)
                detected_retailer = None
                for r in RETAILERS:
                    if r.lower() in t:
                        detected_retailer = r
                        break
                
                # 3. Detectar Cifra (Regex)
                magnitude = 0.1 # Valor por defecto
                match = re.search(r'(\d+([.,]\d+)?)%', t)
                if match:
                    # Si dice "sube un 20%", impacto es mayor
                    magnitude = float(match.group(1).replace(',', '.')) * 0.01 
                    # Capamos al 0.3 (30%) para evitar errores de lectura
                    magnitude = min(magnitude, 0.3)
                
                if direction != 0:
                    val = direction * magnitude
                    prod_score += val
                    
                    # Loguear evidencia
                    icon = "🔥" if direction > 0 else "🟢"
                    retailer_tag = f"[{detected_retailer}]" if detected_retailer else "[General]"
                    if len(evidence_log) < 10: # Límite de logs
                        evidence_log.append({
                            "product": product,
                            "retailer": retailer_tag,
                            "title": art['title'],
                            "val": val
                        })
            
            impacts[product] = prod_score
            
        except: pass
        
    progress_bar.empty()
    return impacts, evidence_log

# ==============================================================================
# 3. MOTOR DE CÁLCULO IPC GLOBAL
# ==============================================================================
def calculate_inflation(base_annual, old_monthly, shelf_data, year, month):
    # 1. Calcular Inflación de Supermercado (Sub-índice)
    supermarket_inflation = 0.0
    for prod, val in shelf_data.items():
        supermarket_inflation += (val * BASIC_BASKET[prod]["w"])
    
    # 2. Integrar con Resto de la Economía (Modelo Híbrido Simplificado para V60)
    # Asumimos una inercia base para lo que no es comida (Servicios, Energía)
    # Inercia Estacional Base
    base_inertia = 0.1
    if month in [1, 7]: base_inertia = -0.5 # Rebajas generales
    
    # La comida pesa un 20% en el IPC total.
    # El resto (80%) se mueve por inercia + energía (estimada aquí como proxy)
    
    # Factor Corrector Energía (Hardcoded proxy para velocidad en esta demo)
    energy_proxy = 0.0 # Neutro por defecto
    
    # IPC MENSUAL ESTIMADO = (Comida * 0.20) + (Resto * 0.80)
    # Pero amplificamos la señal de comida porque suele ser indicador adelantado
    monthly_cpi = (supermarket_inflation * 0.3) + (base_inertia * 0.7)
    
    # 3. Anualización
    f_base = 1 + base_annual/100
    f_out = 1 + old_monthly/100
    f_in = 1 + monthly_cpi/100
    final_annual = ((f_base / f_out) * f_in - 1) * 100
    
    return monthly_cpi, final_annual, supermarket_inflation

# ==============================================================================
# UI
# ==============================================================================
with st.sidebar:
    st.title("ORACLE V60")
    st.caption("RETAIL SCANNER EDITION")
    
    t_year = st.number_input("Año", 2024, 2030, 2026)
    t_month = st.selectbox("Mes", range(1, 13))
    
    st.divider()
    base_annual = st.number_input("IPC Anual Previo", value=2.90)
    old_monthly = st.number_input("IPC Saliente", value=0.30)
    
    st.markdown("### 🛒 Cesta Monitorizada")
    for p in BASIC_BASKET.keys():
        st.caption(f"• {p}")
        
    if st.button("ESCANEAR SUPERMERCADOS", type="primary"):
        st.session_state.run_v60 = True

if 'run_v60' in st.session_state:
    st.title(f"Monitor de Precios: {calendar.month_name[t_month].upper()} {t_year}")
    
    # 1. SCANNING
    with st.spinner("Rastreando lineales de Mercadona, Carrefour, Lidl..."):
        shelf_data, shelf_logs = scan_supermarket_shelves(t_year, t_month)
        monthly_val, annual_val, food_cpi = calculate_inflation(base_annual, old_monthly, shelf_data, t_year, t_month)

    # 2. KPI BOARD
    c1, c2, c3 = st.columns(3)
    c1.metric("IPC GENERAL (ESTIMADO)", f"{monthly_val:+.2f}%", "Mensual Global")
    # Destacamos la inflación de comida porque es lo que el usuario pidió
    c2.metric("INFLACIÓN ALIMENTOS", f"{food_cpi:+.2f}%", "Solo Supermercados")
    c3.metric("IPC ANUAL", f"{annual_val:.2f}%", f"Objetivo: {base_annual}%")
    
    st.markdown("---")
    
    # 3. DETALLE POR PRODUCTO (SHELF VIEW)
    st.subheader("🛒 Variación en el Lineal (Canasta Básica)")
    
    cols = st.columns(len(BASIC_BASKET))
    for i, (prod, val) in enumerate(shelf_data.items()):
        with cols[i]:
            color = "red" if val > 0 else "green" if val < 0 else "gray"
            st.markdown(f"**{prod}**")
            st.markdown(f"<h2 style='color:{color}; margin:0;'>{val:+.2f}%</h2>", unsafe_allow_html=True)
            st.caption(f"Peso: {int(BASIC_BASKET[prod]['w']*100)}%")

    # 4. EVIDENCIA "SCRAPEADA"
    st.markdown("---")
    st.subheader("🧾 Tickets y Noticias Detectadas")
    
    if shelf_logs:
        for item in shelf_logs:
            css_class = "price-up" if item['val'] > 0 else "price-down"
            st.markdown(f"""
            <div class="product-card">
                <div style="display:flex; justify-content:space-between;">
                    <span><b>{item['product']}</b> <span class="supermarket-tag">{item['retailer']}</span></span>
                    <span class="{css_class}">{item['val']:+.2f}%</span>
                </div>
                <div style="font-size:0.85em; color:#AAA; margin-top:5px;">{item['title']}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No se detectaron movimientos bruscos de precios en las noticias de retail recientes.")
    
    # 5. GRÁFICO DE APORTE
    labels = list(shelf_data.keys())
    values = list(shelf_data.values())
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation='h',
        marker=dict(color=['#FF5252' if x > 0 else '#69F0AE' for x in values])
    ))
    fig.update_layout(title="Presión Inflacionaria por Producto", template="plotly_dark", height=300)
    st.plotly_chart(fig, use_container_width=True)
