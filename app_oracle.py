import streamlit as st
from gnews import GNews
import calendar
import datetime
import plotly.graph_objects as go
import pandas as pd
import time
import numpy as np

# --- CONFIGURACIÓN FORENSE ---
st.set_page_config(page_title="Oracle V53 | Deep News Scraper", page_icon="🗞️", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #1E1E1E; color: #E0E0E0; }
    h1, h2, h3 { font-family: 'Georgia', serif; color: #FFD700; }
    .news-box { 
        border-left: 3px solid #FFD700; 
        background-color: #2C2C2C; 
        padding: 10px; 
        margin-bottom: 5px; 
        font-size: 0.9em;
    }
    .sentiment-pos { color: #FF6B6B; font-weight: bold; } /* Inflacionario */
    .sentiment-neg { color: #4ECDC4; font-weight: bold; } /* Deflacionario */
    div[data-testid="stMetric"] { background-color: #252526; border: 1px solid #3E3E42; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. DICCIONARIO DE BÚSQUEDA EXHAUSTIVA (12 GRUPOS)
# ==============================================================================
# Cada grupo tiene palabras clave específicas para "forzar" a Google a darnos datos.
ECOICOP_KEYWORDS = {
    "01 Alimentos": ["precio aceite oliva", "precio fruta verdura", "cesta compra", "precio carne pescado", "subida leche huevos"],
    "02 Alcohol/Tabaco": ["precio tabaco", "impuesto alcohol", "subida cigarrillos"],
    "03 Vestido": ["rebajas ropa", "nueva temporada moda", "precio ropa calzado"],
    "04 Vivienda": ["precio luz hoy", "tarifa gas", "tope gas", "precio alquiler vivienda", "euribor hipoteca"],
    "05 Menaje": ["precio electrodomésticos", "muebles hogar", "reparaciones casa"],
    "06 Medicina": ["precio medicamentos", "copago farmacia", "seguro médico"],
    "07 Transporte": ["precio gasolina", "precio diesel", "precio coches", "vuelos baratos", "renfe"],
    "08 Comunicaciones": ["tarifas movil", "fibra optica precio", "oferta telefonia"],
    "09 Ocio": ["entradas cine teatro", "precio ordenadores", "paquetes turisticos", "libros texto"],
    "10 Enseñanza": ["precio matricula universidad", "cuota colegio", "academia idiomas"],
    "11 Hoteles": ["precio menu dia", "restaurantes subida", "precio hoteles vacaciones"],
    "12 Otros": ["precio peluqueria", "seguro coche subida", "residencia ancianos", "joyeria oro"]
}

PESOS_INE = {
    "01 Alimentos": 19.6, "02 Alcohol/Tabaco": 3.9, "03 Vestido": 3.8, "04 Vivienda": 12.7,
    "05 Menaje": 5.8, "06 Medicina": 4.4, "07 Transporte": 11.6, "08 Comunicaciones": 2.7,
    "09 Ocio": 4.9, "10 Enseñanza": 1.6, "11 Hoteles": 13.9, "12 Otros": 15.1
}

# ==============================================================================
# 2. MOTOR DE "CRAWLING" TEMPORAL
# ==============================================================================
def deep_news_audit(year, month):
    """
    Escanea Google News limitando estrictamente las fechas al mes objetivo.
    Devuelve: Impacto numérico y lista de titulares por grupo.
    """
    
    # Configurar fechas límite (El "Muro de Tiempo")
    last_day = calendar.monthrange(year, month)[1]
    start_date = (year, month, 1)
    end_date = (year, month, last_day)
    
    # Comprobar si es futuro (si es futuro, miramos los últimos 30 días como proyección)
    is_future = datetime.datetime(year, month, 1) > datetime.datetime.now()
    if is_future:
        period = '30d'
        s_date = None; e_date = None
    else:
        period = None
        s_date = start_date; e_date = end_date

    results = {}
    total_headlines = 0
    
    # Barra de progreso en UI
    progress_text = st.empty()
    bar = st.progress(0)
    
    i = 0
    for group, keywords in ECOICOP_KEYWORDS.items():
        i += 1
        bar.progress(int((i / 12) * 100))
        progress_text.text(f"🗞️ Analizando prensa para: {group}...")
        
        # Instancia GNews
        google_news = GNews(language='es', country='ES', period=period, start_date=s_date, end_date=e_date, max_results=10)
        
        group_score = 0
        group_articles = []
        
        # Búsqueda Iterativa (Keyword a Keyword)
        # Para no saturar, elegimos las 2 mejores keywords de cada grupo
        for query in keywords[:2]: 
            try:
                full_query = f"{query} España"
                news = google_news.get_news(full_query)
                
                for article in news:
                    title = article['title'].lower()
                    
                    # ANÁLISIS DE SENTIMIENTO (NLP Básico)
                    val = 0
                    if "sube" in title or "dispara" in title or "récord" in title or "alza" in title or "caro" in title:
                        val = 1.0
                    elif "baja" in title or "cae" in title or "desciende" in title or "barato" in title or "oferta" in title:
                        val = -1.0
                    elif "iva" in title and "baja" in title:
                        val = -2.0 # Impacto fiscal fuerte
                    
                    if val != 0:
                        # Evitar duplicados
                        if title not in [a['title'] for a in group_articles]:
                            group_score += val
                            group_articles.append({'title': article['title'], 'val': val, 'link': article['url']})
                            
                time.sleep(0.1) # Pequeña pausa para evitar bloqueo IP
            except Exception as e:
                pass

        # NORMALIZACIÓN DEL SENTIMIENTO
        # Si encontramos 10 noticias y score es +5, el impacto es medio-alto.
        count = len(group_articles)
        total_headlines += count
        
        final_impact = 0.0
        if count > 0:
            # Fórmula: (Score Neto / Noticias Totales) * Factor Sensibilidad
            # Factor: Alimentos/Energía (0.1) mueven más que Ocio (0.05)
            sensitivity = 0.12 if group in ["01 Alimentos", "04 Vivienda", "07 Transporte"] else 0.06
            avg_sentiment = group_score / count
            final_impact = avg_sentiment * sensitivity
        
        results[group] = {
            "impact": final_impact,
            "headlines": group_articles,
            "count": count
        }
        
    bar.empty()
    progress_text.empty()
    
    return results, total_headlines

# ==============================================================================
# 3. BASE HISTÓRICA (INE BACKBONE)
# ==============================================================================
def get_historical_inertia(month, year):
    # Tendencia base sin noticias (Rebajas, Cosechas, etc.)
    base = {
        "01 Alimentos": 0.2, "02 Alcohol/Tabaco": 0.0, 
        "03 Vestido": -12.0 if month in [1, 7] else (4.0 if month in [3,4,9,10] else 0.0),
        "04 Vivienda": 0.3, "05 Menaje": 0.1, "06 Medicina": 0.0,
        "07 Transporte": 0.4 if month in [7,8] else 0.0,
        "08 Comunicaciones": -0.1, "09 Ocio": 0.5 if month in [7,8,12] else -0.5,
        "10 Enseñanza": 1.5 if month in [9,10] else 0.0,
        "11 Hoteles": 1.0 if month in [7,8] else 0.0, "12 Otros": 0.2
    }
    
    # Ajuste Pascua
    a=year%19;b=year//100;c=year%100;d=b//4;e=b%4;f=(b+8)//25;g=(b-f+1)//3;h=(19*a+b-d-g+15)%30;i=c//4;k=c%4;l=(32*2*e+2*i-h-k)%7;m_p=(a+11*h+22*l)//451;easter=(h+l-7*m_p+114)//31
    if month == easter:
        base["11 Hoteles"] += 1.0; base["09 Ocio"] += 0.5
        
    return base

# ==============================================================================
# UI PRINCIPAL
# ==============================================================================
with st.sidebar:
    st.title("ORACLE V53")
    st.caption("CRAWLER DE NOTICIAS HISTÓRICO")
    
    st.markdown("### 🗓️ Configuración de Rastreo")
    t_year = st.number_input("Año", 2024, 2030, 2025)
    t_month = st.selectbox("Mes", range(1, 13))
    
    st.markdown("### 📊 Datos Base")
    base_annual = st.number_input("IPC Anual Previo", value=2.80)
    old_monthly = st.number_input("IPC Saliente", value=0.30)
    
    st.warning("⚠️ Nota: El análisis tarda unos 30-40 segundos debido a la descarga masiva de datos.")
    
    if st.button("INICIAR ESCANEO PROFUNDO", type="primary"):
        st.session_state.deep_scan = True

if 'deep_scan' in st.session_state:
    st.title(f"Reporte Forense de Prensa: {calendar.month_name[t_month].upper()} {t_year}")
    
    # 1. EJECUCIÓN DEL CRAWLER
    news_data, total_news = deep_news_audit(t_year, t_month)
    inertia_data = get_historical_inertia(t_month, t_year)
    
    total_monthly_cpi = 0.0
    breakdown = []
    
    # 2. PROCESAMIENTO
    col_res, col_chart = st.columns([4, 3])
    
    with col_res:
        st.subheader(f"🗃️ Evidencia Recopilada ({total_news} artículos)")
        
        for group, w in PESOS_INE.items():
            # Cálculo: Inercia + (Impacto Noticias)
            n_impact = news_data[group]["impact"]
            i_impact = inertia_data.get(group, 0.0)
            
            total_var = i_impact + n_impact
            contribution = total_var * (w / 100)
            total_monthly_cpi += contribution
            
            # Estilos
            headlines = news_data[group]["headlines"]
            count = news_data[group]["count"]
            icon = "🔴" if total_var > 0.1 else "🟢" if total_var < -0.1 else "⚪"
            
            with st.expander(f"{icon} {group} ({count} noticias) | Var: {total_var:+.2f}%"):
                c1, c2 = st.columns(2)
                c1.metric("Impacto Prensa", f"{n_impact:+.3f}%")
                c2.metric("Inercia Base", f"{i_impact:+.3f}%")
                
                if headlines:
                    st.markdown("**Titulares detectados:**")
                    for h in headlines:
                        color = "sentiment-pos" if h['val'] > 0 else "sentiment-neg"
                        st.markdown(f"- <span class='{color}'>{h['title']}</span>", unsafe_allow_html=True)
                else:
                    st.caption("No se encontraron noticias específicas. Se usa solo inercia histórica.")
            
            breakdown.append({"Grupo": group, "Aporte": contribution})
            
    # 3. RESULTADO
    f_base = 1 + base_annual/100
    f_out = 1 + old_monthly/100
    f_in = 1 + total_monthly_cpi/100
    final_annual = ((f_base / f_out) * f_in - 1) * 100
    
    with col_chart:
        st.markdown("""
        <div style="background-color: #2C2C2C; padding: 20px; border-radius: 8px; border: 1px solid #FFD700; text-align: center;">
            <h2 style="color: #FFD700; margin:0;">PREDICCIÓN FINAL</h2>
        </div>
        """, unsafe_allow_html=True)
        
        st.metric("IPC MENSUAL", f"{total_monthly_cpi:+.2f}%")
        st.metric("IPC ANUAL", f"{final_annual:.2f}%", f"{final_annual-base_annual:+.2f}%", delta_color="inverse")
        
        st.markdown("---")
        
        # Gráfico
        fig = go.Figure(go.Bar(
            x=[d["Aporte"] for d in breakdown],
            y=[d["Grupo"] for d in breakdown],
            orientation='h',
            marker=dict(color=['#FF6B6B' if x > 0 else '#4ECDC4' for x in [d["Aporte"] for d in breakdown]])
        ))
        fig.update_layout(title="Contribución por Grupo (Noticias + Inercia)", template="plotly_dark", height=500)
        st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Configura la fecha y pulsa INICIAR para descargar y analizar las noticias.")
