import streamlit as st
import yfinance as yf
from gnews import GNews
import calendar
import datetime
from datetime import timedelta
import plotly.graph_objects as go
import pandas as pd
import numpy as np

# --- CONFIGURACIÓN DE LA AUDITORÍA ---
st.set_page_config(page_title="Oracle V52 | Audit Master", page_icon="⚖️", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #050505; color: #E0E0E0; }
    h1, h2, h3 { font-family: 'Helvetica', sans-serif; color: #4CAF50; letter-spacing: 0.5px; }
    .audit-card { 
        background-color: #121212; 
        border-left: 4px solid #4CAF50; 
        padding: 15px; 
        margin-bottom: 10px;
        border-radius: 4px;
    }
    .component-text { font-size: 0.8em; color: #888; font-style: italic; }
    .exclusion-box { border: 1px dashed #F44336; padding: 10px; color: #EF9A9A; font-size: 0.8em; }
    div[data-testid="stMetric"] { background-color: #1E1E1E; border: 1px solid #333; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. LA ESTRUCTURA MAESTRA (BASE METODOLÓGICA)
# ==============================================================================
# Contiene Pesos (W), Componentes (Info), Tickers (Hard Data) y Keywords (Soft Data)
MASTER_DATA = {
    "01 Alimentos y bebidas no alcohólicas": {
        "w": 19.6,
        "desc": "Pan, cereales, carne, pescado, aceite oliva, frutas, legumbres...",
        "tickers": ["ZW=F", "LE=F", "KC=F", "SB=F"], # Trigo, Ganado, Café, Azúcar
        "keywords": ["precio aceite oliva", "cesta compra", "precio fruta", "subida carne", "sequía"],
        "seasonal": [0.3, 0.2, 0.0, 0.1, -0.2, 0.3, 0.0, 0.1, -0.1, 0.4, 0.2, 0.7] # Dic fuerte
    },
    "02 Bebidas alcohólicas y tabaco": {
        "w": 3.9,
        "desc": "Espirituosos, vino, cerveza, cigarrillos (Precios Regulados).",
        "tickers": [], 
        "keywords": ["impuesto alcohol", "precio tabaco", "tasa impuestos"],
        "seasonal": [0.8, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.1] # Ene subidas admin
    },
    "03 Vestido y calzado": {
        "w": 3.8,
        "desc": "Ropa hombre/mujer/niño, calzado, reparaciones.",
        "tickers": [],
        "keywords": ["rebajas ropa", "nueva colección", "moda precio"],
        "seasonal": [-13.0, -2.0, 4.0, 9.0, 1.0, -1.0, -12.5, -2.0, 5.0, 9.0, 0.5, -1.0] # Rebajas Ene/Jul
    },
    "04 Vivienda (Luz, Agua, Gas)": {
        "w": 12.7,
        "desc": "Alquiler (no compra), mantenimiento, electricidad, gas, calefacción.",
        "tickers": ["NG=F"], # Gas Natural (Proxy marginalista luz)
        "keywords": ["precio luz", "tope gas", "alquiler vivienda", "euribor hipoteca"],
        "seasonal": [0.6, -0.2, -0.5, -0.2, -0.1, 0.4, 0.6, 0.5, 0.2, 0.5, 0.3, 0.7] # Invierno/Verano
    },
    "05 Muebles y hogar": {
        "w": 5.8,
        "desc": "Muebles, textil hogar, electrodomésticos, herramientas.",
        "tickers": ["HG=F"], # Cobre (Proxy manufactura)
        "keywords": ["precio muebles", "electrodomésticos", "reformas"],
        "seasonal": [-0.3, 0.1, 0.2, 0.2, 0.1, 0.1, -0.4, 0.0, 0.2, 0.3, 0.1, 0.2]
    },
    "06 Sanidad": {
        "w": 4.4,
        "desc": "Medicamentos, gafas, dentistas, servicios privados.",
        "tickers": [],
        "keywords": ["precio medicamentos", "seguro médico", "copago"],
        "seasonal": [0.2, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0] # Muy estable
    },
    "07 Transporte": {
        "w": 11.6,
        "desc": "Compra vehículos, gasolina/diesel, transporte público, vuelos.",
        "tickers": ["BZ=F", "CL=F"], # Brent, WTI
        "keywords": ["gasolina", "diesel", "precio coches", "vuelos", "renfe"],
        "seasonal": [0.3, 0.2, 0.5, 0.8, 0.4, 0.5, 0.9, 0.6, -0.5, -0.2, -0.3, 0.2] # Semana Santa/Verano
    },
    "08 Comunicaciones": {
        "w": 2.7,
        "desc": "Teléfonos, tarifas internet/móvil, correos.",
        "tickers": [],
        "keywords": ["tarifa movil", "fibra optica", "subida telefonica"],
        "seasonal": [-0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1] # Deflación tecno
    },
    "09 Ocio y cultura": {
        "w": 4.9,
        "desc": "TV, ordenadores, juguetes, mascotas, cine, libros, paquetes turísticos.",
        "tickers": [],
        "keywords": ["paquetes turísticos", "entradas concierto", "electrónica", "libros"],
        "seasonal": [-0.8, 0.1, 0.4, 0.2, -0.5, 0.4, 1.2, 1.2, -1.5, -0.5, -0.2, 1.0] # Navidad/Verano
    },
    "10 Enseñanza": {
        "w": 1.6,
        "desc": "Educación reglada (primaria a universidad) y no reglada (idiomas).",
        "tickers": [],
        "keywords": ["precio matrícula", "colegios concertados", "libros texto"],
        "seasonal": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.8, 1.2, 0.0, 0.0] # Solo Sept/Oct
    },
    "11 Restaurantes y hoteles": {
        "w": 13.9,
        "desc": "Bares, cafeterías, menús, hoteles, campings.",
        "tickers": [],
        "keywords": ["precio menú", "hotel verano", "semana santa", "restaurantes"],
        "seasonal": [-0.5, 0.2, 0.5, 0.4, 0.5, 1.0, 2.5, 2.0, -1.0, -0.5, -0.4, 0.8] # Muy estacional
    },
    "12 Otros bienes y servicios": {
        "w": 15.1,
        "desc": "Peluquería, higiene, joyas, seguros, gastos financieros.",
        "tickers": [],
        "keywords": ["seguro coche", "peluquería", "residencia ancianos", "joyería"],
        "seasonal": [0.9, 0.2, 0.2, 0.1, 0.1, 0.1, 0.1, 0.0, 0.1, 0.1, 0.0, 0.1] # Ene (Seguros)
    }
}

# ==============================================================================
# 2. MOTORES DE CÁLCULO (AUDIT ENGINES)
# ==============================================================================

def get_base_dna(group, month, year):
    """Extrae la tendencia histórica base y ajusta por Pascua"""
    # Algoritmo Pascua
    a=year%19;b=year//100;c=year%100;d=b//4;e=b%4;f=(b+8)//25;g=(b-f+1)//3;h=(19*a+b-d-g+15)%30;i=c//4;k=c%4;l=(32*2*e+2*i-h-k)%7;m_p=(a+11*h+22*l)//451;easter=(h+l-7*m_p+114)//31
    
    val = MASTER_DATA[group]["seasonal"][month-1]
    
    # Ajuste Dinámico de Pascua (Afecta a G11 y G09)
    if group in ["11 Restaurantes y hoteles", "09 Ocio y cultura"]:
        if month == easter: val += 1.0 # Boost semana santa
        if month == easter - 1: val += 0.3 # Pre-boost
        
    return val

def audit_hard_data(group, year, month):
    """Consulta mercados financieros (Chicago/NY/Londres)"""
    tickers = MASTER_DATA[group]["tickers"]
    if not tickers: return 0.0, []
    
    dt_t = datetime.datetime(year, month, 1)
    if dt_t > datetime.datetime.now(): end=datetime.datetime.now(); start=end-timedelta(days=30)
    else: last=calendar.monthrange(year, month)[1]; start=dt_t; end=datetime.datetime(year, month, last)
    
    impact = 0.0
    logs = []
    
    for t in tickers:
        try:
            df = yf.download(t, start=start, end=end, progress=False, auto_adjust=True)
            if not df.empty:
                op = float(df.iloc[0]['Open']); cl = float(df.iloc[-1]['Close'])
                change = ((cl - op) / op) * 100
                
                # FACTOR DE TRANSMISIÓN (Pass-through)
                # Alimentos (01) tardan más en subir que la Gasolina (07)
                factor = 0.15 if "07" in group else 0.05
                if "04" in group: factor = 0.10 # Energía hogar
                
                if abs(change) > 2.5: # Filtro ruido
                    val = change * factor
                    impact += val
                    logs.append(f"{t}: {change:+.1f}% (Impacto {val:+.3f}%)")
        except: pass
        
    # Promedio si hay varios tickers
    if len(tickers) > 1: impact /= len(tickers)
    return impact, logs

def audit_soft_data(group, year, month):
    """Consulta noticias y BOE"""
    keywords = MASTER_DATA[group]["keywords"]
    gnews = GNews(language='es', country='ES', period='15d', max_results=10)
    
    impact = 0.0
    evidence = []
    
    # Query optimizada
    q = f"{keywords[0]} precio españa"
    try:
        news = gnews.get_news(q)
        score = 0
        modifiers = {"sube": 1, "dispara": 1.5, "baja": -1, "descenso": -1, "iva": 2}
        
        for art in news:
            t = art['title'].lower()
            found_mod = False
            for mod, val in modifiers.items():
                if mod in t:
                    score += val
                    found_mod = True
            
            # Detección específica (ej: Aceite)
            if "aceite" in t and "01" in group and "sube" in t: score += 1 # Boost extra
            
            if found_mod and len(evidence) < 1: evidence.append(art['title'])
            
        if len(news) > 0:
            impact = (score / len(news)) * 0.08 # Sensibilidad
    except: pass
    
    return max(min(impact, 0.5), -0.5), evidence

# ==============================================================================
# UI
# ==============================================================================
with st.sidebar:
    st.title("ORACLE V52")
    st.caption("AUDIT MASTER EDITION")
    
    st.markdown("### 📅 Parámetros Temporales")
    t_year = st.number_input("Año", 2024, 2030, 2026)
    t_month = st.selectbox("Mes", range(1, 13))
    
    st.markdown("### 📊 Calibración")
    base_annual = st.number_input("IPC Anual Previo", value=2.90)
    old_monthly = st.number_input("IPC Mensual Saliente (-1 año)", value=0.30)
    
    st.divider()
    
    st.markdown("### 🚫 Panel de Exclusiones")
    st.info("""
    **Metodología INE aplicada:**
    Se han excluido del cálculo:
    - Compra de vivienda (Inversión)
    - Intereses de préstamos
    - Donaciones, Multas y Juegos de Azar
    - Drogas y Prostitución
    """)
    
    if st.button("EJECUTAR AUDITORÍA COMPLETA", type="primary"):
        st.session_state.run_v52 = True

if 'run_v52' in st.session_state:
    st.title(f"Auditoría IPC: {calendar.month_name[t_month].upper()} {t_year}")
    
    total_monthly_cpi = 0.0
    breakdown = []
    
    # BARRA DE PROGRESO DE AUDITORÍA
    audit_bar = st.progress(0)
    status_text = st.empty()
    
    col_main, col_summary = st.columns([7, 3])
    
    with col_main:
        idx = 0
        for group, data in MASTER_DATA.items():
            idx += 1
            audit_bar.progress(int((idx/12)*100))
            status_text.text(f"Auditando Grupo {group[:2]}...")
            
            # 1. CÁLCULO FACTORES
            s_val = get_base_dna(group, t_month, t_year)
            m_val, m_logs = audit_hard_data(group, t_year, t_month)
            n_val, n_logs = audit_soft_data(group, t_year, t_month)
            
            total_var = s_val + m_val + n_val
            contribution = total_var * (data["w"] / 100)
            total_monthly_cpi += contribution
            
            # 2. VISUALIZACIÓN TARJETA
            # Color coding
            border_color = "#4CAF50" # Verde (Neutro/Bajo)
            if total_var > 0.5: border_color = "#FF5252" # Rojo (Inflacionario)
            if total_var < -0.5: border_color = "#2196F3" # Azul (Deflacionario)
            
            with st.expander(f"{group} | Var: {total_var:+.2f}% | Peso: {data['w']}%"):
                st.markdown(f"*{data['desc']}*")
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Estacionalidad", f"{s_val:+.2f}%", "Histórico")
                c2.metric("Mercado", f"{m_val:+.2f}%", "Futuros")
                c3.metric("Noticias", f"{n_val:+.2f}%", "Sentimiento")
                c4.metric("APORTE IPC", f"{contribution:+.3f} pp", "Impacto Final")
                
                if m_logs or n_logs:
                    st.markdown("---")
                    if m_logs: st.caption(f"📈 **Mercado:** {m_logs[0]}")
                    if n_logs: st.caption(f"📰 **Noticias:** {n_logs[0]}")

            breakdown.append({"Grupo": group[:20], "Aporte": contribution})

    audit_bar.empty()
    status_text.empty()
    
    # CÁLCULO ANUAL FINAL
    f_base = 1 + base_annual/100
    f_out = 1 + old_monthly/100
    f_in = 1 + total_monthly_cpi/100
    final_annual = ((f_base / f_out) * f_in - 1) * 100
    
    with col_summary:
        st.markdown("""
        <div style="background-color: #121212; border: 1px solid #333; padding: 20px; border-radius: 10px; text-align: center;">
            <h2 style="color: #4CAF50; margin:0;">DICTAMEN</h2>
            <p style="color: #888;">Proyección Oficial</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.metric("IPC MENSUAL", f"{total_monthly_cpi:+.2f}%")
        st.metric("IPC ANUAL", f"{final_annual:.2f}%", f"{final_annual-base_annual:+.2f}% vs Base", delta_color="inverse")
        
        st.markdown("---")
        st.caption("**Metodología:** Suma ponderada de variaciones estacionales, financieras y mediáticas sobre la base ECOICOP 2024.")
        
        # Gráfico Waterfall
        fig = go.Figure(go.Waterfall(
            orientation = "v",
            measure = ["relative"] * 12 + ["total"],
            x = [d["Grupo"] for d in breakdown] + ["TOTAL"],
            y = [d["Aporte"] for d in breakdown] + [total_monthly_cpi],
            connector = {"line":{"color":"#555"}},
            decreasing = {"marker":{"color":"#2196F3"}},
            increasing = {"marker":{"color":"#FF5252"}},
            totals = {"marker":{"color":"#4CAF50"}}
        ))
        fig.update_layout(title="Contribución al IPC (Puntos)", template="plotly_dark", height=400, margin=dict(l=0,r=0))
        st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Sistema Audit Master Listo. Inicie el proceso.")
