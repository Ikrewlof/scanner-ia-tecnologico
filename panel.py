import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import os

from io import StringIO
from datetime import datetime
from textblob import TextBlob
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator

# =========================================================
# CONFIGURACIÓN STREAMLIT
# =========================================================
st.set_page_config(page_title="Scanner IA Mercado USA", layout="wide")
st.title("🤖 Scanner IA de oportunidades – Mercado USA")

# =========================================================
# AJUSTES DE VELOCIDAD
# =========================================================
st.sidebar.header("⚙️ Ajustes de rendimiento")
max_tickers = st.sidebar.slider("Máximo de tickers a analizar", 50, 1000, 200, step=50)
usar_sentimiento = st.sidebar.checkbox("Incluir sentimiento (más lento)", value=False)
top_sentimiento = st.sidebar.slider("Calcular sentimiento para Top N", 10, 200, 30, step=10)
top_nombres = st.sidebar.slider("Cargar nombre empresa para Top N", 10, 200, 50, step=10)

universo = st.selectbox(
    "🌍 Universo de mercado",
    ["Tecnología", "S&P 500", "NASDAQ-100", "Russell 1000", "USA (grandes)","Defensa (Aerospace & Defense)" ]
)

# =========================================================
# HELPERS HTTP (ANTI 403)
# =========================================================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def read_html_anti403(url: str):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return pd.read_html(StringIO(r.text))

# =========================================================
# UNIVERSOS
# =========================================================
@st.cache_data(ttl=24 * 60 * 60)
def obtener_tecnologicas():
    tickers = set()

    # NASDAQ-100
    url_nasdaq = "https://en.wikipedia.org/wiki/Nasdaq-100"
    tablas_nasdaq = read_html_anti403(url_nasdaq)
    nasdaq_df = tablas_nasdaq[4]
    tickers.update(nasdaq_df["Ticker"].astype(str).tolist())

    # S&P 500 - Tecnología
    url_sp = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tablas_sp = read_html_anti403(url_sp)
    sp_df = tablas_sp[0]

    sp_tech = sp_df[sp_df["GICS Sector"] == "Information Technology"]["Symbol"].astype(str).tolist()
    tickers.update(sp_tech)

    return sorted(tickers)

@st.cache_data(ttl=24 * 60 * 60)
def obtener_sp500():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tablas = read_html_anti403(url)
    df = tablas[0]
    return sorted(df["Symbol"].astype(str).tolist())

@st.cache_data(ttl=24 * 60 * 60)
def obtener_nasdaq100():
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    tablas = read_html_anti403(url)
    df = tablas[4]
    return sorted(df["Ticker"].astype(str).tolist())

@st.cache_data(ttl=24 * 60 * 60)
def obtener_russell1000():
    url = "https://en.wikipedia.org/wiki/Russell_1000_Index"
    tablas = read_html_anti403(url)
    # OJO: Wikipedia puede cambiar el índice de tabla con el tiempo
    df = tablas[2]
    col = "Ticker" if "Ticker" in df.columns else df.columns[0]
    return sorted(df[col].astype(str).tolist())

@st.cache_data(ttl=24 * 60 * 60)
def obtener_usa_grandes():
    tickers = set()
    tickers.update(obtener_sp500())
    tickers.update(obtener_nasdaq100())
    # Russell 1000 puede variar/romper si cambia Wikipedia; lo mantenemos:
    try:
        tickers.update(obtener_russell1000())
    except Exception:
        pass
    return sorted(tickers)

@st.cache_data(ttl=24 * 60 * 60)
def obtener_defensa_sp500():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tablas = read_html_anti403(url)
    df = tablas[0]

    # Preferimos Sub-Industry si existe (más preciso)
    if "GICS Sub-Industry" in df.columns:
        defensa = df[df["GICS Sub-Industry"].astype(str).str.contains("Aerospace & Defense", na=False)]
    else:
        # Fallback si Wikipedia cambia columnas
        defensa = df[df.astype(str).apply(lambda row: row.str.contains("Aerospace|Defense", case=False, na=False).any(), axis=1)]

    return sorted(defensa["Symbol"].astype(str).tolist())





# =========================================================
# NOMBRE EMPRESA (LENTO) → SOLO TOP N
# =========================================================
@st.cache_data(ttl=7 * 24 * 60 * 60)
def obtener_nombre_empresa(ticker):
    try:
        info = yf.Ticker(ticker).info
        return info.get("shortName") or info.get("longName") or ticker
    except Exception:
        return ticker

# =========================================================
# SENTIMIENTO (LENTO) → SOLO TOP N Y OPCIONAL
# =========================================================
@st.cache_data(ttl=6 * 60 * 60)
def sentimiento_noticias(ticker):
    try:
        noticias = yf.Ticker(ticker).news[:5]
        if not noticias:
            return 0.0
        total = 0.0
        for n in noticias:
            texto = n.get("title", "")
            total += TextBlob(texto).sentiment.polarity
        return total / len(noticias)
    except Exception:
        return 0.0

# =========================================================
# SCORE BASE
# =========================================================
def calcular_score(ema20, ema50, rsi, sentimiento):
    score = 0

    # Tendencia
    if ema20 > ema50:
        score += 40

    # RSI óptimo
    if 40 <= rsi <= 55:
        score += 30
    elif 30 <= rsi < 40:
        score += 20

    # Penalizaciones
    if rsi > 70:
        score -= 20
    if rsi < 25:
        score -= 20

    # Sentimiento suave
    score += int(sentimiento * 10)

    return max(0, min(score, 100))

def explicar_score(ema20, ema50, rsi, sentimiento):
    razones = []
    if ema20 > ema50:
        razones.append("✔ Tendencia alcista (EMA20 > EMA50)")
    else:
        razones.append("❌ Tendencia bajista (EMA20 < EMA50)")

    if 40 <= rsi <= 55:
        razones.append(f"✔ RSI saludable ({rsi:.1f})")
    elif 30 <= rsi < 40:
        razones.append(f"🟡 RSI en corrección ({rsi:.1f})")
    elif rsi > 70:
        razones.append(f"❌ Sobrecompra (RSI {rsi:.1f})")
    else:
        razones.append(f"⚠️ RSI débil ({rsi:.1f})")

    if sentimiento > 0.1:
        razones.append("✔ Sentimiento positivo en noticias")
    elif sentimiento < -0.1:
        razones.append("❌ Sentimiento negativo en noticias")
    else:
        razones.append("➖ Sentimiento neutro")

    return razones

with st.expander("ℹ️ ¿Qué significa el Score?"):
    st.markdown("""
**El Score (0–100)** indica qué tan interesante es una acción **en este momento** según análisis técnico y contexto.

**Cómo interpretarlo:**
- **80–100** → 🔥 Muy buena oportunidad
- **70–79** → 🟢 Buena oportunidad
- **55–69** → 🟡 Para vigilar
- **< 55** → 🔴 No interesante ahora

**Qué tiene en cuenta el Score:**
- 📈 Tendencia (EMA20 vs EMA50)
- 📊 Momento del precio (RSI)
- 🔊 Confirmación (Volumen relativo)
- 📰 Sentimiento (opcional)

👉 El Score **no es recomendación financiera**. Sirve para **priorizar oportunidades**.
""")

# =========================================================
# FASE 2: SCORE CRECIENTE (HISTÓRICO)
# =========================================================
def evaluar_tendencia_score(ticker, score_actual, historico):
    if historico.empty:
        return {"EstadoScore": "Nuevo", "BonusScore": 0}

    datos = historico[historico["Ticker"] == ticker].sort_values("Fecha")
    if len(datos) < 2:
        return {"EstadoScore": "Nuevo", "BonusScore": 0}

    score_ayer = float(datos.iloc[-2]["Score"])

    if score_actual > score_ayer:
        return {"EstadoScore": "Creciendo", "BonusScore": 5}

    if score_actual >= 70 and score_ayer >= 70:
        return {"EstadoScore": "Fuerte", "BonusScore": 3}

    return {"EstadoScore": "Debilitándose", "BonusScore": -5}

def estilo_estado_score(valor):
    if valor == "Creciendo":
        return "background-color: #d4edda; color: #155724; font-weight: bold;"
    elif valor == "Fuerte":
        return "background-color: #cce5ff; color: #004085; font-weight: bold;"
    elif valor == "Debilitándose":
        return "background-color: #f8d7da; color: #721c24; font-weight: bold;"
    elif valor == "Nuevo":
        return "background-color: #e2e3e5; color: #383d41;"
    return ""

def estilo_estado_volumen(valor):
    if valor == "Alto":
        return "background-color: #d4edda; color: #155724; font-weight: bold;"
    elif valor == "Bajo":
        return "background-color: #f8d7da; color: #721c24; font-weight: bold;"
    elif valor == "Normal":
        return "background-color: #e2e3e5; color: #383d41;"
    return ""

# =========================================================
# FASE 3: VOLUMEN RELATIVO
# =========================================================
def evaluar_volumen(volumen_relativo):
    try:
        v = float(volumen_relativo)
    except Exception:
        v = 1.0

    if v >= 1.2:
        return {"EstadoVolumen": "Alto", "BonusVolumen": 5}
    elif v < 0.8:
        return {"EstadoVolumen": "Bajo", "BonusVolumen": -5}
    else:
        return {"EstadoVolumen": "Normal", "BonusVolumen": 0}

# =========================================================
# HISTÓRICO (ROBUSTO)
# =========================================================
def guardar_historico(df):
    archivo = "historico_scores.csv"
    hoy = datetime.now().strftime("%Y-%m-%d")

    historico = df.copy()
    historico["Fecha"] = hoy

    columnas = ["Fecha", "Ticker", "Empresa", "Score", "RSI", "Sentimiento", "Señal", "Momento"]
    historico = historico[columnas]

    if os.path.exists(archivo):
        try:
            existente = pd.read_csv(archivo)
        except Exception:
            existente = pd.DataFrame(columns=columnas)

        combinado = pd.concat([existente, historico], ignore_index=True)
        combinado = combinado.drop_duplicates(subset=["Fecha", "Ticker"], keep="last")
        combinado.to_csv(archivo, index=False)
    else:
        historico.to_csv(archivo, index=False)

def cargar_historico():
    archivo = "historico_scores.csv"
    if not os.path.exists(archivo):
        return pd.DataFrame()
    try:
        return pd.read_csv(archivo)
    except pd.errors.ParserError:
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def detectar_cruces(historico, umbral=70):
    if historico.empty:
        return pd.DataFrame()

    eventos = []
    for ticker in historico["Ticker"].unique():
        datos = historico[historico["Ticker"] == ticker].sort_values("Fecha")
        if len(datos) < 2:
            continue

        datos["Score_prev"] = datos["Score"].shift(1)
        cruces = datos[(datos["Score_prev"] < umbral) & (datos["Score"] >= umbral)]
        for _, fila in cruces.iterrows():
            eventos.append({
                "Fecha": fila["Fecha"],
                "Ticker": fila["Ticker"],
                "Empresa": fila.get("Empresa", fila["Ticker"]),
                "Score": fila["Score"]
            })

    return pd.DataFrame(eventos)

# =========================================================
# ESTADO MERCADO (QQQ)
# =========================================================
@st.cache_data(ttl=60 * 60)
def estado_mercado():
    datos = yf.download("QQQ", period="6mo", interval="1d", progress=False)
    if datos.empty:
        return "DESCONOCIDO"
    if isinstance(datos.columns, pd.MultiIndex):
        datos.columns = datos.columns.get_level_values(0)
    close = datos["Close"].dropna()
    ema20 = EMAIndicator(close, 20).ema_indicator().iloc[-1]
    ema50 = EMAIndicator(close, 50).ema_indicator().iloc[-1]
    return "ALCISTA" if ema20 > ema50 else "DEBIL"

# =========================================================
# DESCARGA EN LOTE (CLAVE DE VELOCIDAD)
# =========================================================
@st.cache_data(ttl=60 * 60)
def descargar_precios_lote(tickers, period="6mo", interval="1d"):
    return yf.download(
        tickers,
        period=period,
        interval=interval,
        group_by="ticker",
        threads=True,
        progress=False
    )

def extraer_df_ticker(datos_all, ticker):
    # datos_all suele venir MultiIndex columns: (ticker, OHLCV)
    if isinstance(datos_all.columns, pd.MultiIndex):
        if ticker not in datos_all.columns.get_level_values(0):
            return None
        df = datos_all[ticker].copy()
    else:
        # caso de 1 solo ticker
        df = datos_all.copy()
    return df

# =========================================================
# ANALIZAR DESDE DATOS YA DESCARGADOS
# =========================================================
def analizar_accion_desde_datos(ticker, datos_all, historico, sentimiento_val=0.0):
    df = extraer_df_ticker(datos_all, ticker)
    if df is None or df.empty:
        return None

    df = df.dropna()
    if len(df) < 60:
        return None

    close = df["Close"].dropna()

    df["EMA20"] = EMAIndicator(close, 20).ema_indicator()
    df["EMA50"] = EMAIndicator(close, 50).ema_indicator()
    df["RSI"] = RSIIndicator(close).rsi()

    df = df.dropna()
    if df.empty:
        return None

    ultimo = df.iloc[-1]

    precio = float(ultimo["Close"])
    ema20 = float(ultimo["EMA20"])
    ema50 = float(ultimo["EMA50"])
    rsi = float(ultimo["RSI"])

    # Volumen relativo robusto
    try:
        vol_media = df["Volume"].rolling(20).mean().iloc[-1]
        vol_rel = float(ultimo.get("Volume", 0)) / float(vol_media) if pd.notna(vol_media) and float(vol_media) > 0 else 1.0
    except Exception:
        vol_rel = 1.0

    score_base = calcular_score(ema20, ema50, rsi, float(sentimiento_val))
    score_final = score_base

    # Fase 2
    ajuste = evaluar_tendencia_score(ticker, score_base, historico)
    score_final = max(0, min(score_final + ajuste["BonusScore"], 100))

    # Fase 3
    ajuste_vol = evaluar_volumen(vol_rel)
    score_final = max(0, min(score_final + ajuste_vol["BonusVolumen"], 100))

    # Señal
    if score_final >= 70:
        senal = "🟢 Comprar"
        momento = "Alta prioridad"
    elif score_final >= 55:
        senal = "🟡 Vigilar"
        momento = "Media prioridad"
    else:
        senal = "🔴 No comprar"
        momento = "Baja prioridad"

    razones = explicar_score(ema20, ema50, rsi, float(sentimiento_val))

    return {
        "Ticker": ticker,
        "Empresa": ticker,  # se completa luego para TOP N
        "Precio": round(precio, 2),
        "RSI": round(rsi, 1),
        "Tendencia": "Alcista" if ema20 > ema50 else "Bajista",
        "Sentimiento": round(float(sentimiento_val), 2),
        "Score": int(score_final),
        "EstadoScore": ajuste["EstadoScore"],
        "VolumenRel": round(float(vol_rel), 2),
        "EstadoVolumen": ajuste_vol["EstadoVolumen"],
        "Señal": senal,
        "Momento": momento,
        "Razones": razones
    }

# =========================================================
# CARGAR UNIVERSO
# =========================================================
with st.spinner("Cargando universo de mercado..."):
    if universo == "Tecnología":
        tickers = obtener_tecnologicas()
    elif universo == "S&P 500":
        tickers = obtener_sp500()
    elif universo == "NASDAQ-100":
        tickers = obtener_nasdaq100()
    elif universo == "Russell 1000":
        tickers = obtener_russell1000()
    elif universo == "Defensa (Aerospace & Defense)":
        tickers = obtener_defensa_sp500()
    else:
        tickers = obtener_usa_grandes()


tickers = [t for t in tickers if isinstance(t, str) and t.strip() != ""]
tickers = tickers[:max_tickers]

st.write(f"📡 Acciones analizadas (máx): **{len(tickers)}**")

# =========================================================
# ESTADO MERCADO + UMBRAL DINÁMICO
# =========================================================
estado = estado_mercado()
if estado == "ALCISTA":
    st.success("📈 Mercado tecnológico alcista (QQQ)")
elif estado == "DEBIL":
    st.warning("📉 Mercado tecnológico débil (QQQ)")
else:
    st.info("ℹ️ Estado del mercado no disponible")

UMBRAL_BASE = 70
umbral_compra = 75 if estado == "DEBIL" else UMBRAL_BASE
st.caption(f"Umbral de compra actual: {umbral_compra}")

# =========================================================
# ESCANEO RÁPIDO (PRECIOS EN LOTE)
# =========================================================
historico = cargar_historico()

with st.spinner("Descargando precios (lote) ..."):
    datos_all = descargar_precios_lote(tickers)

resultados = []
with st.spinner("Analizando mercado (rápido) ..."):
    for ticker in tickers:
        r = analizar_accion_desde_datos(ticker, datos_all, historico, sentimiento_val=0.0)
        if r:
            resultados.append(r)

df = pd.DataFrame(resultados)
if df.empty:
    st.error("No se han podido generar resultados.")
    st.stop()

# =========================================================
# RANKING BASE (SIN SENTIMIENTO NI NOMBRES AÚN)
# =========================================================
ranking = df.sort_values("Score", ascending=False).reset_index(drop=True)

# =========================================================
# SENTIMIENTO SOLO PARA TOP N (OPCIONAL)
# =========================================================
if usar_sentimiento:
    with st.spinner(f"Calculando sentimiento para Top {min(top_sentimiento, len(ranking))} (más lento) ..."):
        for i in range(min(top_sentimiento, len(ranking))):
            t = ranking.loc[i, "Ticker"]
            s = sentimiento_noticias(t)
            ranking.loc[i, "Sentimiento"] = round(float(s), 2)

        # Recalcular SCORE para esos top con nuevo sentimiento (mismo EMA/RSI/volumen ya implícitos, pero aquí no los guardamos)
        # Para mantenerlo simple: dejamos el sentimiento como dato informativo.
        # Si quieres que el sentimiento impacte score en TopN, lo hacemos en la siguiente iteración.

# =========================================================
# NOMBRES SOLO PARA TOP N (LENTO)
# =========================================================
with st.spinner(f"Cargando nombre empresa para Top {min(top_nombres, len(ranking))} ..."):
    for i in range(min(top_nombres, len(ranking))):
        t = ranking.loc[i, "Ticker"]
        ranking.loc[i, "Empresa"] = obtener_nombre_empresa(t)

# =========================================================
# GUARDAR HISTÓRICO
# =========================================================
guardar_historico(ranking)

# =========================================================
# RANKING PRINCIPAL
# =========================================================
st.subheader("🏆 Ranking IA de oportunidades (prioridad)")

ranking_vista = ranking[
    [
        "Ticker",
        "Empresa",
        "Score",
        "EstadoScore",
        "EstadoVolumen",
        "VolumenRel",
        "Precio",
        "RSI",
        "Tendencia",
        "Sentimiento",
        "Señal",
        "Momento",
    ]
]

st.dataframe(
    ranking_vista.style
        .applymap(estilo_estado_score, subset=["EstadoScore"])
        .applymap(estilo_estado_volumen, subset=["EstadoVolumen"]),
    use_container_width=True
)

# =========================================================
# TOP OPORTUNIDADES
# =========================================================
st.subheader("⭐ Mejores oportunidades ahora")
top = ranking[ranking["Score"] >= umbral_compra]
if top.empty:
    st.info("No hay oportunidades claras de alta prioridad ahora mismo.")
else:
    st.dataframe(top, use_container_width=True)

# =========================================================
# PRE-ALERTAS
# =========================================================
st.subheader("🟡 Pre-alertas: acciones cerca de activar señal")

pre_alertas = ranking[
    (ranking["Score"] >= 65) &
    (ranking["Score"] < umbral_compra) &
    (ranking["EstadoScore"].isin(["Creciendo", "Fuerte"])) &
    (ranking["Tendencia"] == "Alcista") &
    (ranking["EstadoVolumen"] != "Bajo")
]

if pre_alertas.empty:
    st.info("No hay acciones cerca de activar señal ahora mismo.")
else:
    st.dataframe(
        pre_alertas[
            ["Ticker", "Empresa", "Score", "EstadoScore", "EstadoVolumen", "VolumenRel", "Precio", "RSI", "Señal"]
        ],
        use_container_width=True
    )

# =========================================================
# EXPLICACIÓN DETALLADA
# =========================================================
st.subheader("🧠 Explicación del score")

accion = st.selectbox(
    "Selecciona una acción para ver el motivo del score",
    options=ranking["Ticker"].tolist()
)

fila = ranking[ranking["Ticker"] == accion].iloc[0]
st.markdown(f"### {fila['Empresa']} ({fila['Ticker']}) — Score {fila['Score']}")

for r in fila["Razones"]:
    st.write(r)

st.caption(f"Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# =========================================================
# HISTÓRICO SCORE
# =========================================================
st.subheader("📈 Evolución histórica del score")
historico2 = cargar_historico()

if historico2.empty:
    st.info("Aún no hay histórico suficiente para mostrar gráficos.")
else:
    historico2["Fecha"] = pd.to_datetime(historico2["Fecha"], errors="coerce")
    historico2 = historico2.dropna(subset=["Fecha"])

    accion_hist = st.selectbox(
        "Selecciona una acción para ver su histórico",
        options=sorted(historico2["Ticker"].unique())
    )

    datos_accion = historico2[historico2["Ticker"] == accion_hist].sort_values("Fecha")
    if not datos_accion.empty:
        st.line_chart(datos_accion.set_index("Fecha")["Score"])
        st.write(
            f"📌 Registros históricos: {len(datos_accion)} | "
            f"Score medio: {datos_accion['Score'].mean():.1f} | "
            f"Score máx: {datos_accion['Score'].max()}"
        )

# =========================================================
# ALERTAS: CRUCES >= 70
# =========================================================
st.subheader("🚨 Alertas: cruces recientes de score ≥ 70")
eventos = detectar_cruces(historico2, umbral=70)

if eventos.empty:
    st.info("No se han detectado cruces recientes del score.")
else:
    eventos = eventos.sort_values("Fecha", ascending=False)
    st.dataframe(eventos, use_container_width=True)
    st.success(f"Se han detectado {len(eventos)} cruces históricos del score ≥ 70")
