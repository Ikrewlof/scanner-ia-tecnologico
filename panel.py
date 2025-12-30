import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import os

from io import StringIO
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from textblob import TextBlob
from datetime import datetime


# =========================================================
# CONFIGURACIÓN STREAMLIT
# =========================================================
st.set_page_config(page_title="Scanner IA Tecnológico", layout="wide")
st.title("🤖 Scanner IA de oportunidades – Acciones Tecnológicas")

# =========================================================
# OBTENER LISTADO TECNOLÓGICO (ANTI 403)
# =========================================================
@st.cache_data(ttl=24 * 60 * 60)
def obtener_tecnologicas():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    tickers = set()

    # NASDAQ-100
    url_nasdaq = "https://en.wikipedia.org/wiki/Nasdaq-100"
    r = requests.get(url_nasdaq, headers=headers, timeout=15)
    r.raise_for_status()
    tablas_nasdaq = pd.read_html(StringIO(r.text))
    nasdaq_df = tablas_nasdaq[4]
    tickers.update(nasdaq_df["Ticker"].tolist())

    # S&P 500 - Tecnología
    url_sp = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    r = requests.get(url_sp, headers=headers, timeout=15)
    r.raise_for_status()
    tablas_sp = pd.read_html(StringIO(r.text))
    sp_df = tablas_sp[0]

    sp_tech = sp_df[
        sp_df["GICS Sector"] == "Information Technology"
    ]["Symbol"].tolist()

    tickers.update(sp_tech)

    return sorted(tickers)

# =========================================================
# OBTENER NOMBRE DE EMPRESA
# =========================================================
@st.cache_data(ttl=7 * 24 * 60 * 60)
def obtener_nombre_empresa(ticker):
    try:
        info = yf.Ticker(ticker).info
        return info.get("shortName") or info.get("longName") or ticker
    except Exception:
        return ticker

# =========================================================
# SENTIMIENTO DE NOTICIAS
# =========================================================
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
# FUNCIÓN DE SCORE
# =========================================================
def calcular_score(ema20, ema50, rsi, sentimiento):
    score = 0

    if ema20 > ema50:
        score += 40

    if 40 <= rsi <= 55:
        score += 30
    elif 30 <= rsi < 40:
        score += 20

    if rsi > 70:
        score -= 20
    if rsi < 25:
        score -= 20

    score += int(sentimiento * 10)

    return max(0, min(score, 100))


#analizar mercado

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

    if ema20 > ema50:
        return "ALCISTA"
    else:
        return "DEBIL"


# =========================================================
# EXPLICACIÓN DEL SCORE (NUEVO, NO TOCA NADA)
# =========================================================




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
- 📰 Sentimiento de noticias recientes

👉 El Score **no es una recomendación financiera**, es una herramienta para **priorizar oportunidades**.
""")



#GUARDA HISTORICO

def guardar_historico(df):
    archivo = "historico_scores.csv"
    hoy = datetime.now().strftime("%Y-%m-%d")

    historico = df.copy()
    historico["Fecha"] = hoy

    columnas = [
        "Fecha",
        "Ticker",
        "Empresa",
        "Score",
        "RSI",
        "Sentimiento",
        "Señal",
        "Momento"
    ]

    historico = historico[columnas]

    if os.path.exists(archivo):
        existente = pd.read_csv(archivo)

        combinado = pd.concat([existente, historico])
        combinado = combinado.drop_duplicates(
            subset=["Fecha", "Ticker"],
            keep="last"
        )
        combinado.to_csv(archivo, index=False)
    else:
        historico.to_csv(archivo, index=False)


def cargar_historico():
    archivo = "historico_scores.csv"
    if not os.path.exists(archivo):
        return pd.DataFrame()
    return pd.read_csv(archivo)


def detectar_cruces(historico, umbral=70):
    eventos = []

    for ticker in historico["Ticker"].unique():
        datos = historico[historico["Ticker"] == ticker] \
            .sort_values("Fecha")

        if len(datos) < 2:
            continue

        datos["Score_prev"] = datos["Score"].shift(1)

        cruces = datos[
            (datos["Score_prev"] < umbral) &
            (datos["Score"] >= umbral)
        ]

        for _, fila in cruces.iterrows():
            eventos.append({
                "Fecha": fila["Fecha"],
                "Ticker": fila["Ticker"],
                "Empresa": fila["Empresa"],
                "Score": fila["Score"]
            })

    return pd.DataFrame(eventos)

    # ANALIZAR TENDENCIA DEL Score
def evaluar_tendencia_score(ticker, score_actual, historico):
    datos = historico[historico["Ticker"] == ticker] \
        .sort_values("Fecha")

    if len(datos) < 2:
        return {
            "EstadoScore": "Nuevo",
            "BonusScore": 0
        }

    score_ayer = datos.iloc[-2]["Score"]

    # Score creciente
    if score_actual > score_ayer:
        return {
            "EstadoScore": "Creciendo",
            "BonusScore": 5
        }

    # Score estable alto
    if score_actual >= 70 and score_ayer >= 70:
        return {
            "EstadoScore": "Fuerte",
            "BonusScore": 3
        }

    # Score perdiendo fuerza
    return {
        "EstadoScore": "Debilitándose",
        "BonusScore": -5
    }


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


    #funcion evaluar volumen_actual
def evaluar_volumen(volumen_relativo):
    if volumen_relativo >= 1.2:
        return {
            "EstadoVolumen": "Alto",
            "BonusVolumen": 5
        }
    elif volumen_relativo < 0.8:
        return {
            "EstadoVolumen": "Bajo",
            "BonusVolumen": -5
        }
    else:
        return {
            "EstadoVolumen": "Normal",
            "BonusVolumen": 0
        }



# =========================================================
# ANÁLISIS COMPLETO DE UNA ACCIÓN
# =========================================================


def analizar_accion(ticker):
    datos = yf.download(ticker, period="6mo", interval="1d", progress=False)

    if datos.empty:
        return None

    if isinstance(datos.columns, pd.MultiIndex):
        datos.columns = datos.columns.get_level_values(0)

    close = datos["Close"].dropna()

    datos["EMA20"] = EMAIndicator(close, 20).ema_indicator()
    datos["EMA50"] = EMAIndicator(close, 50).ema_indicator()
    datos["RSI"] = RSIIndicator(close).rsi()

    datos_limpios = datos.dropna()

    if len(datos_limpios) < 50:
        return None

    ultimo = datos_limpios.iloc[-1]


    precio = float(ultimo["Close"])
    ema20 = float(ultimo["EMA20"])
    ema50 = float(ultimo["EMA50"])
    rsi = float(ultimo["RSI"])

    # ===== FASE 3: VOLUMEN (SEGURO) =====
    # ===== FASE 3: VOLUMEN (ROBUSTO) =====
    try:
        volumen_actual = float(ultimo.get("Volume", 0))

        vol_series = datos["Volume"].rolling(20).mean().dropna()

        if vol_series.empty:
            volumen_relativo = 1
        else:
            volumen_media = float(vol_series.iloc[-1])
            volumen_relativo = (
                volumen_actual / volumen_media
                if volumen_media > 0
                else 1
            )
    except Exception:
        volumen_relativo = 1




    sentimiento = sentimiento_noticias(ticker)
    score_base = calcular_score(ema20, ema50, rsi, sentimiento)
    score_final = score_base


    # ===== FASE 2: SCORE CRECIENTE =====
    historico = cargar_historico()
    ajuste = evaluar_tendencia_score(ticker, score_base, historico)
    #score_final = max(0, min(score_base + ajuste["BonusScore"], 100))

    ajuste_vol = evaluar_volumen(volumen_relativo)

    score_final = max(
        0,
        min(score_final + ajuste_vol["BonusVolumen"], 100)
    )


    razones = explicar_score(ema20, ema50, rsi, sentimiento)





    if score_final >= 70:
        senal = "🟢 Comprar"
        momento = "Alta prioridad"
    elif score_final >= 55:
        senal = "🟡 Vigilar"
        momento = "Media prioridad"
    else:
        senal = "🔴 No comprar"
        momento = "Baja prioridad"

    resultado = {
        "Ticker": ticker,
        "Empresa": obtener_nombre_empresa(ticker),
        "Precio": round(precio, 2),
        "RSI": round(rsi, 1),
        "Tendencia": "Alcista" if ema20 > ema50 else "Bajista",
        "Sentimiento": round(sentimiento, 2),
        "Score": score_final,
        "EstadoScore": ajuste["EstadoScore"],
        "VolumenRel": round(volumen_relativo, 2),
        "EstadoVolumen": ajuste_vol["EstadoVolumen"],
        "Señal": senal,
        "Momento": momento,
        "Razones": razones
    }



    return resultado

   


# =========================================================
# CARGAR UNIVERSO
# =========================================================
with st.spinner("Cargando universo tecnológico..."):
    tickers = obtener_tecnologicas()

st.write(f"📡 Acciones tecnológicas analizadas: **{len(tickers)}**")



#OBTENER ESTADO DEL MERCADO


estado = estado_mercado()

if estado == "ALCISTA":
    st.success("📈 Mercado tecnológico alcista (QQQ)")
elif estado == "DEBIL":
    st.warning("📉 Mercado tecnológico débil (QQQ)")
else:
    st.info("ℹ️ Estado del mercado no disponible")


# =========================================================
# ESCANEAR MERCADO
# =========================================================
resultados = []

with st.spinner("Analizando mercado con IA..."):
    for ticker in tickers:
        try:
            r = analizar_accion(ticker)
            if r:
                resultados.append(r)
        except Exception as e:
            st.warning(f"Error en {ticker}: {e}")


df = pd.DataFrame(resultados)

# 🔧 Limpieza defensiva del EstadoScore
if "EstadoScore" in df.columns:
    df["EstadoScore"] = df["EstadoScore"].astype(str)


if df.empty:
    st.error("No se han podido generar resultados.")
    st.stop()



#AJUSTAR EL UMBRAL

UMBRAL_BASE = 70

if estado == "DEBIL":
    umbral_compra = 75
else:
    umbral_compra = UMBRAL_BASE


# =========================================================
# RANKING PRINCIPAL (NO TOCADO)
# =========================================================
st.subheader("🏆 Ranking IA de oportunidades (prioridad)")

ranking = df.sort_values("Score", ascending=False)

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
        "Señal",
        "Momento",
    ]
]

st.dataframe(
    ranking_vista.style.applymap(
        estilo_estado_score, subset=["EstadoScore"]
    ),
    use_container_width=True
)



guardar_historico(ranking)

# =========================================================
# FILTRO TOP OPORTUNIDADES (NO TOCADO)
# =========================================================
st.subheader("⭐ Mejores oportunidades ahora")

top = ranking[ranking["Score"] >= umbral_compra]

st.caption(f"Umbral de compra actual: {umbral_compra}")



if top.empty:
    st.info("No hay oportunidades claras de alta prioridad ahora mismo.")
else:
    st.dataframe(top, use_container_width=True)

# =========================================================
# EXPLICACIÓN DEL SCORE (VISTA DETALLADA)
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

st.caption(
    f"Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)


# =========================================================
# HISTÓRICO DE SCORE (GRÁFICA)
# =========================================================
st.subheader("📈 Evolución histórica del score")

historico = cargar_historico()

if historico.empty:
    st.info("Aún no hay histórico suficiente para mostrar gráficos.")
else:
    historico["Fecha"] = pd.to_datetime(historico["Fecha"])

    accion_hist = st.selectbox(
        "Selecciona una acción para ver su histórico",
        options=sorted(historico["Ticker"].unique())
    )

    datos_accion = historico[historico["Ticker"] == accion_hist] \
        .sort_values("Fecha")

    st.line_chart(
        datos_accion.set_index("Fecha")["Score"]
    )

    st.write(
        f"📌 Registros históricos: {len(datos_accion)} | "
        f"Score medio: {datos_accion['Score'].mean():.1f} | "
        f"Score máx: {datos_accion['Score'].max()}"
    )


# =========================================================
# ALERTAS: CRUCE DE SCORE >= 70
# =========================================================
st.subheader("🚨 Alertas: cruces recientes de score ≥ 70")

eventos = detectar_cruces(historico, umbral=70)

if eventos.empty:
    st.info("No se han detectado cruces recientes del score.")
else:
    eventos = eventos.sort_values("Fecha", ascending=False)

    st.dataframe(
        eventos,
        use_container_width=True
    )

    st.success(
        f"Se han detectado {len(eventos)} cruces históricos del score ≥ 70"
    )






