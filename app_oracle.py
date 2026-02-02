import streamlit as st
import yfinance as yf
from gnews import GNews
import calendar
import datetime
from datetime import timedelta
import plotly.graph_objects as go
import pandas as pd
import numpy as np

# --- CONFIGURACIÓN DE NIVEL GUBERNAMENTAL ---
st.set_page_config(page_title="Oracle V51 | Synced Auditor", page_icon="🏛️", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0F1116; color: #C9D1D9; }
    h1, h2, h3 { font-family: 'Roboto', sans-serif; color: #58A6FF; text-transform: uppercase; letter-spacing: 1px; }
    .metric-card { background-color: #161B22; border: 1px solid #30363D; padding: 15px; border-radius: 6px; }
    div[data-testid="stMetric"] { background-color: #0D1117; border: 1px solid #30363D; }
    .positive { color: #FF7B72; font-weight: bold; } /* Rojo sube inflación */
    .negative { color: #7EE787; font-weight: bold; } /* Verde baja inflación */
    .neutral { color: #8B949E; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. LA CONSTITUCIÓN DEL IPC (PESOS Y ESTRUCTURA INE 2024)
# ==============================================================================
# IMPORTANTE: Estas CLAVES deben ser idénticas en todas las funciones.
ECOICOP_DATA = {
    "01 Alimentos y Bebidas": {
        "w": 19.6,
        "ticker": ["ZW=F", "ZC=F", "LE=F", "SB=F"], 
        "keywords": ["precio alimentos", "cesta compra", "aceite oliva", "fruta", "carne"]
    },
    "02 Alcohol y Tabaco": {
        "w": 3.9,
        "ticker": [], 
        "keywords": ["impuesto tabaco", "precio alcohol", "subida tasas"]
    },
    "03 Vestido y Calzado": {
        "w": 3.8,
        "ticker": [], 
        "keywords": ["rebajas ropa", "nueva colección", "moda precio"]
    },
    "04 Vivienda (Luz/Gas/Agua)": {
        "w": 12.7,
        "ticker": ["NG=F"], 
        "keywords": ["precio luz", "tarifa gas", "tope gas", "alquileres"]
    },
    "05 Menaje y Muebles": {
        "w": 5.8,
        "ticker": ["HG=F"], 
        "keywords": ["muebles", "electrodomésticos", "reparaciones hogar"]
    },
    "06 Medicina": {
        "w": 4.4,
        "ticker": [], 
        "keywords": ["precio medicamentos", "seguro salud", "copago"]
    },
    "07 Transporte": {
        "w": 11.6,
        "ticker": ["BZ=F", "CL=F"], 
        "keywords": ["gasolina", "diesel", "surtidor", "vuelos", "coches"]
    },
    "08 Comunicaciones": {
        "w": 2.7,
        "ticker": [], 
        "keywords": ["tarifas móvil", "fibra óptica", "telefónica"]
    },
    "09 Ocio y Cultura": {
        "w": 4.9,
        "ticker": [], 
        "keywords": ["paquetes turísticos", "entradas cine", "libros", "museos"]
    },
    "10 Enseñanza": {
        "w": 1.6,
        "ticker": [], 
        "keywords": ["matrícula universidad", "colegios concertados", "libros texto"]
    },
    "11 Hoteles y Restaurantes": {
        "w": 13.9,
        "ticker": [], 
        "keywords": ["menú del día", "precio hoteles", "turismo españa", "restaurantes"]
    },
    "12 Otros (Seguros/Cuidado)": {
        "w": 15.1,
        "ticker": [], 
        "keywords": ["seguros coche", "peluquería", "residencia ancianos", "joyería"]
    }
}

# ==============================================================================
# 2. MOTOR DE ESTACIONALIDAD MATRICIAL (SEASONAL DNA)
# ==============================================================================
def get_monthly_dna(month, year):
    # Detección de Pascua para Turismo
    a=year%19;b=year//100;c=year%100;d=b//4;e=b%4;f=(b+8)//25;g=(b-f+1)//3;h=(19*a+b-d-g+15)%30;i=c//4;k=c%4;l=(32*2*e+2*i-h-k)%7;m_p=(a+11*h+22*l)//451;easter=(h+l-7*m_p+114)//31
    
    m_idx = month - 1
    
    # LAS CLAVES AQUÍ AHORA SON IDÉNTICAS A ECOICOP_DATA
    matrix = {
        "01 Alimentos y Bebidas": [0.3, 0.2, 0.1, 0.1, 0.0, 0.2, 0.0, 0.1, -0.1, 0.4, 0.2, 0.6],
        "02 Alcohol y Tabaco":    [0.8, 0.1, 0.0, 0.0, 0.0, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.1],
        "03 Vestido y Calzado":   [-13.0, -2.0, 4.0, 9.0, 2.0, -1.0, -12.5, -2.0, 5.0, 9.0, 0.5, -1.0], 
        "04 Vivienda (Luz/Gas/Agua)": [0.5, -0.2, -0.5, -0.2, -0.1, 0.4, 0.6, 0.5, 0.2, 0.5, 0.3, 0.6],
        "05 Menaje y Muebles":    [-0.3, 0.1, 0.2, 0.2, 0.1, 0.1, -0.4, 0.0, 0.2, 0.3, 0.1, 0.2],
        "06 Medicina":            [0.2, 0.0, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "07 Transporte":          [0.2, 0.2, 0.4, 0.5, 0.3, 0.4, 0.9, 0.5, -0.4, -0.2, -0.3, 0.1],
        "08 Comunicaciones":      [-0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1],
        "09 Ocio y Cultura":      [-0.9, 0.1, 0.2, 0.0, -0.5, 0.4, 1.2, 1.2, -1.5, -0.5, -0.2, 0.9],
        "10 Enseñanza":           [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.8, 1.2, 0.0, 0.0],
        "11 Hoteles y Restaurantes": [-0.6, 0.1, 0.3, 0.2, 0.4, 0.8, 2.0, 1.8, -1.2, -0.5, -0.4, 0.8],
        "12 Otros (Seguros/Cuidado)": [0.8, 0.2, 0.2, 0.1, 0.1, 0.1, 0.1, 0.0, 0.1, 0.1, 0.0, 0.1]
    }
    
    dna = {}
    for k, v in matrix.items():
        val = v[m_idx]
        # Ajuste dinámico de Pascua
        if k in ["11 Hoteles y Restaurantes", "09 Ocio y Cultura"]:
            if month == easter: val += 1.0 
            if month == easter - 1: val += 0.3
        dna[k] = val
        
    return dna

# ==============================================================================
# 3. AUDITORÍA DE MERCADOS (HARD DATA)
# ==============================================================================
def audit_markets(year, month):
    impacts = {k: 0.0 for k in ECOICOP_DATA.keys()}
    
    dt_t = datetime.datetime(year, month, 1)
    if dt_t > datetime.datetime.now(): end=datetime.datetime.now(); start=end-timedelta(days=30)
    else: last=calendar.monthrange(year, month)[1]; start=dt_t; end=datetime.datetime(year, month, last)
    
    for group, data in ECOICOP_DATA.items():
        if not data["ticker"]: continue
        
        group_market_change = 0.0
        count = 0
        
        for t in data["ticker"]:
            try:
                df = yf.download(t, start=start, end=end, progress=False, auto_adjust=True)
                if not df.empty:
                    op = float(df.iloc[0]['Open']); cl = float(df.iloc[-1]['Close'])
                    change = ((cl - op) / op) * 100
                    
                    factor = 0.15 if "07" in group else 0.10 
                    if "01" in group: factor = 0.05 
                    
                    if abs(change) > 2.0:
                        group_market_change += (change * factor)
                        count += 1
            except: pass
            
        if count > 0:
            impacts[group] = group_market_change / count
            
    return impacts

# ==============================================================================
# 4. AUDITORÍA SEMÁNTICA (SOFT DATA)
# ==============================================================================
def audit_news(year, month):
    impacts = {k: 0.0 for k in ECOICOP_DATA.keys()}
    evidence = {k: [] for k in ECOICOP_DATA.keys()}
    
    gnews = GNews(language='es', country='ES', period='15d', max_results=15)
    modifiers = {"sube": 1, "alza": 1, "dispara": 1.5, "baja": -1, "descenso": -1, "desploma": -1.5, "iva": 2}
    
    try:
        news = gnews.get_news("precios ipc inflación españa")
        
        for art in news:
            title = art['title'].lower()
            
            for group, data in ECOICOP_DATA.items():
                matched = False
                for kw in data["keywords"]:
                    if kw in title:
                        matched = True
                        break
                
                if matched:
                    score = 0
                    for mod, val in modifiers.items():
                        if mod in title: score += val
                    
                    if score != 0:
                        final_val = score * 0.05
                        impacts[group] += final_val
                        if len(evidence[group]) < 1: evidence[group].append(art['title'])
    except: pass
    
    for k in impacts:
        impacts[k] = max(min(impacts[k], 0.5), -0.5)
        
    return impacts, evidence

# ==============================================================================
# UI PRINCIPAL
# ==============================================================================
with st.sidebar:
    st.title("ORACLE V51")
    st.caption("SYNCED AUDITOR EDITION")
    
    st.markdown("### 1. Parámetros Temporales")
    t_year = st.number_input("Año Fiscal", 2024, 2030, 2026)
    t_month = st.selectbox("Mes Auditado", range(1, 13))
    
    st.markdown("### 2. Datos de Calibración")
    base_annual = st.number_input("IPC Anual Previo", value=2.90)
    old_monthly = st.number_input("IPC Mensual Saliente (-1 año)", value=0.30)
    
    st.divider()
    if st.button("INICIAR AUDITORÍA TOTAL", type="primary"):
        st.session_state.run_v51 = True

if 'run_v51' in st.session_state:
    st.title(f"Informe de Auditoría IPC: {calendar.month_name[t_month].upper()} {t_year}")
    
    # 1. EJECUCIÓN (Ahora con claves sincronizadas)
    dna = get_monthly_dna(t_month, t_year)
    mkt = audit_markets(t_year, t_month)
    news, logs = audit_news(t_year, t_month)
    
    total_monthly_cpi = 0.0
    breakdown_data = []
    
    # 2. CÁLCULO PONDERADO
    col_l, col_r = st.columns([2, 1])
    
    with col_l:
        st.subheader("📋 Desglose por Grupo ECOICOP (12 Pilares)")
        
        for group, data in ECOICOP_DATA.items():
            # AQUÍ ES DONDE ANTES FALLABA: Ahora 'dna' tiene la clave exacta 'group'
            s_val = dna.get(group, 0.0)
            m_val = mkt.get(group, 0.0)
            n_val = news.get(group, 0.0)
            
            total_var = s_val + m_val + n_val
            contribution = total_var * (data["w"] / 100)
            total_monthly_cpi += contribution
            
            sign = "+" if total_var > 0 else ""
            
            with st.expander(f"{group} | Var: {sign}{total_var:.2f}% | Aporta: {contribution:+.3f} pp"):
                c1, c2, c3 = st.columns(3)
                c1.metric("Estacionalidad", f"{s_val:+.2f}%")
                c2.metric("Mercado", f"{m_val:+.2f}%")
                c3.metric("Noticias", f"{n_val:+.2f}%")
                if logs[group]: st.caption(f"📰 {logs[group][0]}")
            
            breakdown_data.append({"Grupo": group[:15], "Aporte": contribution})

    # 3. RESULTADOS
    f_base = 1 + base_annual/100
    f_out = 1 + old_monthly/100
    f_in = 1 + total_monthly_cpi/100
    final_annual = ((f_base / f_out) * f_in - 1) * 100
    
    with col_r:
        st.markdown("""
        <div style="background-color: #161B22; padding: 20px; border-radius: 8px; border: 1px solid #30363D;">
            <h3 style="text-align: center; color: white; margin: 0;">DICTAMEN OFICIAL</h3>
        </div>
        """, unsafe_allow_html=True)
        
        st.metric("IPC MENSUAL PREVISTO", f"{total_monthly_cpi:+.2f}%", "Suma Ponderada")
        st.metric("IPC ANUAL PREVISTO", f"{final_annual:.2f}%", f"{final_annual-base_annual:+.2f}% vs Base", delta_color="inverse")
        
        st.markdown("---")
        
        fig = go.Figure(go.Waterfall(
            name = "20", orientation = "v",
            measure = ["relative"] * 12 + ["total"],
            x = [d["Grupo"] for d in breakdown_data] + ["TOTAL"],
            textposition = "outside",
            text = [f"{d['Aporte']:.2f}" for d in breakdown_data] + [f"{total_monthly_cpi:.2f}"],
            y = [d["Aporte"] for d in breakdown_data] + [total_monthly_cpi],
            connector = {"line":{"color":"rgb(63, 63, 63)"}},
            decreasing = {"marker":{"color":"#7EE787"}},
            increasing = {"marker":{"color":"#FF7B72"}},
            totals = {"marker":{"color":"#58A6FF"}}
        ))
        fig.update_layout(title="Contribución por Grupo (Waterfall)", template="plotly_dark", height=450)
        st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Sistema V51 Sincronizado. Configure los parámetros a la izquierda.")
