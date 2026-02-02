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

# --- CONFIGURACIÓN "OMNI-AUDIT" ---
st.set_page_config(page_title="Oracle V44 | ECOICOP Audit", page_icon="🏛️", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #CBD5E1; }
    h1, h2, h3 { font-family: 'Roboto Mono', monospace; color: #38BDF8; }
    .ecoicop-box { 
        background-color: #1E293B; 
        border-left: 4px solid #38BDF8; 
        padding: 10px; 
        margin-bottom: 8px;
        font-family: 'Consolas', monospace;
        font-size: 0.9em;
    }
    .audit-log { font-size: 0.8em; color: #94A3B8; }
    div[data-testid="stMetric"] { background-color: #1E293B; border: 1px solid #334155; }
</style>
""", unsafe_allow_html=True)

# --- 1. ESTRUCTURA OFICIAL ECOICOP (PESOS INE 2024 REALES) ---
ECOICOP_STRUCTURE = {
    "01 Alimentos y bebidas no alcohólicas": {"w": 0.196, "type": "Volatile", "driver": "Soft+Hard"},
    "02 Bebidas alcohólicas y tabaco":       {"w": 0.039, "type": "Regulated", "driver": "Tax"},
    "03 Vestido y calzado":                  {"w": 0.038, "type": "Seasonal",  "driver": "Calendar"},
    "04 Vivienda (Luz/Agua/Gas)":            {"w": 0.127, "type": "Volatile", "driver": "Hard"},
    "05 Menaje y muebles":                   {"w": 0.058, "type": "Core",      "driver": "Soft"},
    "06 Medicina":                           {"w": 0.044, "type": "Regulated", "driver": "None"},
    "07 Transporte":                         {"w": 0.116, "type": "Volatile", "driver": "Hard"},
    "08 Comunicaciones":                     {"w": 0.027, "type": "Deflation", "driver": "None"},
    "09 Ocio y cultura":                     {"w": 0.049, "type": "Seasonal",  "driver": "Soft"},
    "10 Enseñanza":                          {"w": 0.016, "type": "Fixed",     "driver": "Calendar"},
    "11 Hoteles, cafés y restaurantes":      {"w": 0.139, "type": "Service",   "driver": "Soft"},
    "12 Otros bienes y servicios (Seguros)": {"w": 0.151, "type": "Sticky",    "driver": "Soft"}
}

# --- 2. MOTORES DE AUDITORÍA ESPECIALIZADOS ---

def audit_hard_markets(year, month):
    """Audita materias primas para G01, G04, G07"""
    dt_target = datetime.datetime(year, month, 1)
    if dt_target > datetime.datetime.now():
        end = datetime.datetime.now(); start = end - timedelta(days=30)
    else:
        last = calendar.monthrange(year, month)[1]
        start = dt_target; end = datetime.datetime(year, month, last)
        
    adjustments = {"01": 0.0, "04": 0.0, "07": 0.0}
    
    # Tickers Clave
    tickers = {
        "BZ=F": ("07", 0.4), # Brent -> Transporte
        "NG=F": ("04", 0.3), # Gas -> Vivienda
        "ZW=F": ("01", 0.15),# Trigo -> Alimentos
        "LE=F": ("01", 0.20) # Ganado -> Alimentos
    }
    
    logs = []
    try:
        for sym, (group, w) in tickers.items():
            df = yf.download(sym, start=start, end=end, progress=False, auto_adjust=True)
            if not df.empty:
                op = float(df.iloc[0]['Open']); cl = float(df.iloc[-1]['Close'])
                change = ((cl - op) / op) * 100
                if abs(change) > 2.5: # Filtro ruido
                    impact = change * 0.02 * w
                    adjustments[group[:2]] += impact # Usamos clave parcial "01", "04"...
                    logs.append(f"MARKET: {sym} {change:+.1f}% -> Impacta G{group[:2]}")
    except: pass
    
    # Asignar a claves completas
    final_adj = {}
    for k, v in ECOICOP_STRUCTURE.items():
        prefix = k[:2]
        final_adj[k] = adjustments.get(prefix, 0.0)
        
    return final_adj, logs

def audit_soft_news(year, month):
    """Busca decretos y tendencias para G02, G05, G11, G12"""
    impacts = {k: 0.0 for k in ECOICOP_STRUCTURE.keys()}
    evidence = []
    
    gnews = GNews(language='es', country='ES', period='15d', max_results=20)
    
    # Búsqueda inteligente agrupada
    queries = [
        ("02", "tabaco alcohol impuestos subida"),
        ("11", "precio hoteles restaurantes menú subida"),
        ("12", "precio seguros peluquería servicios"),
        ("05", "muebles electrodomésticos precio")
    ]
    
    try:
        for prefix, q in queries:
            news = gnews.get_news(q)
            score = 0
            for art in news:
                t = art['title'].lower()
                if "sube" in t or "encarece" in t: score += 1
                if "baja" in t or "descenso" in t: score -= 1
                if "iva" in t: score *= 2 # Impuestos pesan doble
            
            # Normalización
            if len(news) > 0:
                val = (score / len(news)) * 0.08 # Sensibilidad media
                # Asignar a la key correcta
                for k in impacts.keys():
                    if k.startswith(prefix):
                        impacts[k] = val
                        if val != 0: evidence.append(f"NEWS G{prefix}: Tendencia detectada ({val:+.3f})")
    except: pass
    
    return impacts, evidence

def audit_seasonality_rules(month, year):
    """Aplica las reglas rígidas del calendario (Rebajas, Colegios)"""
    seasonal_impacts = {k: 0.0 for k in ECOICOP_STRUCTURE.keys()}
    logs = []
    
    # G03 VESTIDO (Rebajas)
    if month in [1, 7]: 
        seasonal_impacts["03 Vestido y calzado"] = -12.0 # Rebajas agresivas masivas (deflación sectorial)
        logs.append("G03: Rebajas de temporada activas (-12% sectorial)")
    elif month in [3, 4, 9, 10]:
        seasonal_impacts["03 Vestido y calzado"] = 4.0 # Nueva colección
        logs.append("G03: Entrada nueva colección")
        
    # G10 ENSEÑANZA (Solo Sept/Oct)
    if month in [9, 10]:
        seasonal_impacts["10 Enseñanza"] = 1.5
        logs.append("G10: Inicio curso académico")
    else:
        seasonal_impacts["10 Enseñanza"] = 0.0 # Plano resto del año
        
    # G11 TURISMO (Semana Santa/Verano)
    # Calc Pascua
    a=year%19;b=year//100;c=year%100;d=b//4;e=b%4;f=(b+8)//25;g=(b-f+1)//3;h=(19*a+b-d-g+15)%30;i=c//4;k=c%4;l=(32*2*e+2*i-h-k)%7;m_p=(a+11*h+22*l)//451;easter=(h+l-7*m_p+114)//31
    
    if month == easter:
        seasonal_impacts["11 Hoteles, cafés y restaurantes"] = 1.2
        logs.append("G11: Efecto Semana Santa")
    elif month in [7, 8]:
        seasonal_impacts["11 Hoteles, cafés y restaurantes"] = 0.8
        logs.append("G11: Temporada Alta Verano")
        
    # G08 COMUNICACIONES (Deflación tecnológica)
    seasonal_impacts["08 Comunicaciones"] = -0.1 # Tendencia secular a bajar
    
    return seasonal_impacts, logs

# --- 3. MOTOR MACRO (IPRI LAG) ---
def get_macro_push(prev_annual):
    """
    Si la inflación previa es alta, los servicios (G12) tienden a subir 
    por 'efecto segunda ronda' (salarios, alquileres indexados).
    """
    push = 0.0
    if prev_annual > 3.0:
        push = 0.1 # Presión inflacionaria inercial
    elif prev_annual < 1.0:
        push = -0.05
    return push

# --- FRONTEND ---
with st.sidebar:
    st.title("ORACLE V44")
    st.caption("ECOICOP OMNI-AUDIT SYSTEM")
    
    t_year = st.number_input("Año Fiscal", 2024, 2030, 2026)
    t_month = st.selectbox("Mes", range(1, 13))
    
    st.divider()
    st.markdown("### 📉 Datos Base")
    base_annual = st.number_input("IPC Anual Anterior", value=2.80)
    old_monthly = st.number_input("IPC Mensual Saliente", value=0.30)
    
    if st.button("INICIAR AUDITORÍA 12 PILARES"):
        st.session_state.audit_eco = True

if 'audit_eco' in st.session_state:
    st.title(f"Informe ECOICOP: {calendar.month_name[t_month].upper()} {t_year}")
    
    # 1. EJECUCIÓN DE MOTORES
    hard_data, hard_logs = audit_hard_markets(t_year, t_month)
    soft_data, soft_logs = audit_soft_news(t_year, t_month)
    seasonal_data, season_logs = audit_seasonality_rules(t_month, t_year)
    macro_push = get_macro_push(base_annual)
    
    total_monthly_cpi = 0.0
    breakdown = []
    
    # Visualización de Progreso
    status_text = st.empty()
    bar = st.progress(0)
    
    # 2. BUCLE PRINCIPAL (12 GRUPOS)
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.subheader("🕵️ Auditoría Desglosada (12 Grupos)")
        
        idx = 0
        for group, props in ECOICOP_STRUCTURE.items():
            idx += 1
            bar.progress(int((idx/12)*100))
            
            # Cálculo del Valor del Grupo
            # Base inercial pequeña (0.1) + Estacionalidad + Mercado + Noticias + Macro (solo servicios)
            
            # Base inercial genérica
            val_group = 0.1 
            
            # Sumar Estacionalidad (Es lo más fuerte en G03 y G11)
            val_group += seasonal_data[group]
            
            # Sumar Mercado (G01, G04, G07)
            val_group += hard_data[group]
            
            # Sumar Noticias (G02, G05, G11, G12)
            val_group += soft_data[group]
            
            # Sumar Macro Inercia (Solo G12 Servicios y G11)
            if props["type"] in ["Service", "Sticky"]:
                val_group += macro_push
            
            # PONDERACIÓN AL IPC GENERAL
            contribution = val_group * props["w"]
            total_monthly_cpi += contribution
            
            # Visualización
            icon = "🔹"
            if contribution > 0.05: icon = "🔺"
            if contribution < -0.05: icon = "🔻"
            
            # Color coding
            color = "#38BDF8"
            if "Alimentos" in group: color = "#4ADE80" # Verde
            if "Vivienda" in group or "Transporte" in group: color = "#F87171" # Rojo
            if "Vestido" in group: color = "#A78BFA" # Morado
            
            with st.expander(f"{icon} {group[:30]}... | Aporte: {contribution:+.3f}%"):
                c_a, c_b = st.columns(2)
                with c_a:
                    st.markdown(f"**Variación Sectorial:** {val_group:+.2f}%")
                    st.caption(f"Peso Oficial: {props['w']*100:.1f}%")
                    st.caption(f"Tipo: {props['type']}")
                with c_b:
                    if seasonal_data[group] != 0: st.markdown(f"📅 Estacionalidad: {seasonal_data[group]:+.2f}%")
                    if hard_data[group] != 0: st.markdown(f"📈 Mercado: {hard_data[group]:+.2f}%")
                    if soft_data[group] != 0: st.markdown(f"📰 Noticias: {soft_data[group]:+.2f}%")

    bar.empty()
    
    # 3. RESULTADO FINAL
    f_base = 1 + base_annual/100
    f_out = 1 + old_monthly/100
    f_in = 1 + total_monthly_cpi/100
    final_annual = ((f_base / f_out) * f_in - 1) * 100
    
    with col2:
        st.markdown("""
        <div style="background-color: #1E293B; padding: 20px; border-radius: 10px; border: 1px solid #334155;">
            <h2 style="text-align: center; color: white;">DICTAMEN FINAL</h2>
        </div>
        """, unsafe_allow_html=True)
        
        st.metric("IPC MENSUAL PREVISTO", f"{total_monthly_cpi:+.2f}%", "Suma Ponderada ECOICOP")
        st.metric("IPC ANUAL PREVISTO", f"{final_annual:.2f}%", f"{final_annual-base_annual:+.2f}% vs Base", delta_color="inverse")
        
        st.markdown("---")
        st.subheader("📝 Bitácora de Auditoría")
        
        # Logs consolidados
        all_logs = hard_logs + soft_logs + season_logs
        if not all_logs: st.caption("Sin incidencias notables. Inercia estándar aplicada.")
        for log in all_logs:
            st.code(log, language="text")
            
    # GRÁFICO TREEMAP (Lo mejor para ver pesos)
    # Preparamos datos para Treemap
    labels = list(ECOICOP_STRUCTURE.keys())
    # Necesitamos valores absolutos para el tamaño, color para el signo
    values_contribution = []
    colors = []
    
    for k in labels:
        # Recalcular rápido para el gráfico
        val = 0.1 + seasonal_data[k] + hard_data[k] + soft_data[k]
        if ECOICOP_STRUCTURE[k]["type"] in ["Service", "Sticky"]: val += macro_push
        contr = val * ECOICOP_STRUCTURE[k]["w"]
        values_contribution.append(abs(contr) + 0.0001) # Evitar ceros
        colors.append(contr)
        
    fig = go.Figure(go.Treemap(
        labels = [l[:20] for l in labels],
        parents = ["IPC Total"] * 12,
        values = values_contribution,
        textinfo = "label+value",
        marker=dict(
            colors=colors,
            colorscale='RdBu_r', # Rojo sube, Azul baja
            cmid=0
        )
    ))
    fig.update_layout(title="Mapa de Calor de la Inflación (Treemap)", template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Sistema ECOICOP listo. Configure fecha y base.")
