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

# --- CONFIGURACIÓN "GOVERNMENT LEVEL" ---
st.set_page_config(page_title="Oracle V42 | Unrestricted", page_icon="🔓", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #000000; color: #E0E0E0; }
    h1, h2, h3 { font-family: 'Courier New', monospace; color: #00FF00; text-transform: uppercase; }
    .audit-box { border: 1px solid #333; padding: 10px; margin-bottom: 5px; background-color: #111; font-family: 'Courier New'; font-size: 0.8em; }
    div[data-testid="stMetric"] { background-color: #0a0a0a; border: 1px solid #222; }
    /* Hacer los inputs más visibles */
    input { color: #00FF00 !important; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- 1. CESTAS DE ACTIVOS (BASKETS) ---
COMMODITY_BASKETS = {
    "Alimentos": [
        {"name": "Trigo (Pan/Harinas)", "sym": "ZW=F", "weight": 0.3},
        {"name": "Maíz (Piensos/Carne)", "sym": "ZC=F", "weight": 0.2},
        {"name": "Ganado Vivo (Carne)", "sym": "LE=F", "weight": 0.3},
        {"name": "Azúcar (Procesados)", "sym": "SB=F", "weight": 0.1},
        {"name": "Café (Hostelería)", "sym": "KC=F", "weight": 0.1}
    ],
    "Energía": [
        {"name": "Brent (Refencia EU)", "sym": "BZ=F", "weight": 0.4},
        {"name": "Crudo WTI", "sym": "CL=F", "weight": 0.2},
        {"name": "Gas Natural", "sym": "NG=F", "weight": 0.3},
        {"name": "Gasolina RBOB", "sym": "RB=F", "weight": 0.1}
    ],
    "Core/Industria": [
        {"name": "Cobre (Construcción)", "sym": "HG=F", "weight": 0.3},
        {"name": "EUR/USD (Importación)", "sym": "EURUSD=X", "weight": 0.4},
        {"name": "Oro (Refugio)", "sym": "GC=F", "weight": 0.1},
        {"name": "Bonos 10Y (Macro)", "sym": "^TNX", "weight": 0.2}
    ]
}

SECTOR_WEIGHTS = {
    "Alimentos": 0.20,
    "Energía": 0.13,
    "Transporte": 0.12,
    "Turismo": 0.15,
    "Core": 0.40
}

# --- 2. MOTOR AUDITORÍA FINANCIERA ---
def audit_financial_markets(year, month):
    dt_target = datetime.datetime(year, month, 1)
    if dt_target > datetime.datetime.now():
        end = datetime.datetime.now()
        start = end - timedelta(days=30)
    else:
        last = calendar.monthrange(year, month)[1]
        start = dt_target; end = datetime.datetime(year, month, last)
    
    audit_results = {k: 0.0 for k in SECTOR_WEIGHTS.keys()}
    evidence_tables = {} 
    
    for sector_key, assets in COMMODITY_BASKETS.items():
        sector_impact = 0.0
        row_data = []
        for asset in assets:
            try:
                df = yf.download(asset["sym"], start=start, end=end, progress=False, auto_adjust=True)
                if not df.empty:
                    op = float(df.iloc[0]['Open']); cl = float(df.iloc[-1]['Close'])
                    change = ((cl - op) / op) * 100
                    if asset["sym"] == "EURUSD=X": change = -change 
                    
                    impact = 0.0
                    if abs(change) > 2.0:
                        impact = change * 0.02 * asset["weight"]
                    
                    sector_impact += impact
                    row_data.append({"Activo": asset["name"], "Ticker": asset["sym"], "Variación": f"{change:+.2f}%", "Impacto IPC": f"{impact:+.4f}%"})
                else:
                    row_data.append({"Activo": asset["name"], "Ticker": asset["sym"], "Variación": "N/D", "Impacto IPC": "0.00%"})
            except: pass

        if sector_key == "Alimentos": audit_results["Alimentos"] = sector_impact
        if sector_key == "Energía": 
            audit_results["Energía"] = sector_impact * 0.7 
            audit_results["Transporte"] = sector_impact * 0.3 
        if sector_key == "Core/Industria": audit_results["Core"] = sector_impact
        
        evidence_tables[sector_key] = pd.DataFrame(row_data)
        
    return audit_results, evidence_tables

# --- 3. AUDITORÍA DOCUMENTAL ---
def audit_documents(year, month):
    gnews = GNews(language='es', country='ES', period='10d', max_results=20)
    try:
        news = gnews.get_news("economía gobierno españa decreto precios")
        score = 0.0
        docs_found = []
        for art in news:
            t = art['title'].lower()
            impact = 0
            if "iva" in t and "baja" in t: impact = -0.1
            if "iva" in t and "sube" in t: impact = +0.1
            if "ayuda" in t or "cheque" in t: impact = -0.05
            if impact != 0:
                score += impact
                docs_found.append(f"📜 DOC: {art['title']} ({impact:+})")
        return score, docs_found
    except: return 0.0, []

# --- 4. ESQUELETO INE ---
def get_skeleton(m, y):
    # Ajuste fino Enero (-0.6) para cuadrar
    base = {1: -0.60, 2: 0.20, 3: 0.30, 4: 0.35, 5: 0.10, 6: 0.50, 7: -0.50, 8: 0.20, 9: -0.30, 10: 0.60, 11: 0.15, 12: 0.30}
    a=y%19;b=y//100;c=y%100;d=b//4;e=b%4;f=(b+8)//25;g=(b-f+1)//3;h=(19*a+b-d-g+15)%30;i=c//4;k=c%4;l=(32*2*e+2*i-h-k)%7;m_p=(a+11*h+22*l)//451;easter=(h+l-7*m_p+114)//31
    val = base.get(m, 0.2)
    if m == easter: val += 0.3
    if m == easter - 1: val += 0.1
    return val

# --- UI GUBERNAMENTAL (INPUTS LIBRES) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/921/921513.png", width=60)
    st.title("MINISTERIO DE DATOS")
    st.caption("ORACLE V42 | UNRESTRICTED")
    
    st.header("1. FECHA DE ANÁLISIS")
    # Año libre, incluso futuro lejano o pasado
    t_year = st.number_input("EJERCICIO FISCAL (Año)", min_value=1900, max_value=2100, value=2025)
    t_month = st.selectbox("PERIODO (Mes)", range(1, 13))
    
    st.header("2. DATOS DE CONTEXTO")
    st.markdown("Introduce los datos históricos exactos para el cálculo:")
    
    # INPUTS TOTALMENTE LIBRES
    # Ejemplo: Si calculas Mayo 2025, el "Base" es Abril 2025 anual (ej 2.8)
    base_annual = st.number_input("IPC BASE ANUAL (Mes Anterior)", value=2.80, step=0.10, format="%.2f")
    
    # Ejemplo: Si calculas Mayo 2025, el "Saliente" es Mayo 2024 mensual (ej 0.3)
    old_monthly = st.number_input("IPC MENSUAL SALIENTE (Hace 1 año)", value=0.30, step=0.10, format="%.2f")
    
    st.caption(f"Fórmula: ((1+{base_annual})/((1+{old_monthly})/100))...")
    
    if st.button("INICIAR AUDITORÍA NACIONAL"):
        st.session_state.audit = True

if 'audit' in st.session_state:
    st.title(f"📂 EXPEDIENTE: {calendar.month_name[t_month].upper()} {t_year}")
    
    # Ejecución
    skeleton = get_skeleton(t_month, t_year)
    fin_impacts, fin_tables = audit_financial_markets(t_year, t_month)
    doc_impact, doc_logs = audit_documents(t_year, t_month)
    
    # Agregación
    total_monthly = skeleton + doc_impact
    for sect, w in SECTOR_WEIGHTS.items():
        f_imp = 0.0
        if "Alimentos" in sect: f_imp = fin_impacts.get("Alimentos", 0)
        elif "Energía" in sect: f_imp = fin_impacts.get("Energía", 0)
        elif "Transporte" in sect: f_imp = fin_impacts.get("Transporte", 0)
        elif "Core" in sect: f_imp = fin_impacts.get("Core", 0)
        total_monthly += f_imp 
    
    # Ajuste Manual final (skeleton + impacts)
    final_monthly_val = skeleton + sum(fin_impacts.values()) + doc_impact

    # CÁLCULO ANUAL EXACTO
    f_base = 1 + base_annual/100
    f_out = 1 + old_monthly/100
    f_in = 1 + final_monthly_val/100
    final_annual = ((f_base / f_out) * f_in - 1) * 100
    
    # VISUALIZACIÓN
    c1, c2, c3 = st.columns(3)
    c1.metric("IPC MENSUAL (AUDITADO)", f"{final_monthly_val:+.2f}%", f"Esqueleto: {skeleton}%")
    
    # Color dinámico: Verde si baja la inflación, Rojo si sube
    delta_val = final_annual - base_annual
    c2.metric("IPC ANUAL (OFICIAL)", f"{final_annual:.2f}%", f"{delta_val:+.2f}% vs Base ({base_annual}%)", delta_color="inverse")
    
    c3.metric("IMPACTO EXTERNO", f"{sum(fin_impacts.values()) + doc_impact:+.3f}%", "Mercados + BOE")
    
    st.markdown("---")
    st.subheader("🔎 EVIDENCIA DOCUMENTAL Y FINANCIERA")
    
    tab1, tab2, tab3 = st.tabs(["🛒 CESTA ALIMENTOS", "⚡ ENERGÍA E INDUSTRIA", "📜 BOLETÍN OFICIAL"])
    
    with tab1:
        st.dataframe(fin_tables["Alimentos"], use_container_width=True, hide_index=True)
    with tab2:
        c_a, c_b = st.columns(2)
        with c_a: st.dataframe(fin_tables["Energía"], use_container_width=True, hide_index=True)
        with c_b: st.dataframe(fin_tables["Core/Industria"], use_container_width=True, hide_index=True)
    with tab3:
        if not doc_logs: st.info("No se han detectado decretos ley.")
        for d in doc_logs: st.code(d)

    # GRÁFICO TACHÓMETRO
    st.markdown("---")
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = final_annual,
        title = {'text': "Proyección Anual"},
        delta = {'reference': base_annual},
        gauge = {'axis': {'range': [0, 10]}, 'bar': {'color': "#00FF00"}, 'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 2.0}}))
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Sistema listo. Introduzca los parámetros a la izquierda.")
