import pandas as pd
import yfinance as yf

# =========================
# 1. DEFINIR TU CARTERA
# =========================
cartera = pd.DataFrame({
    "Ticker": ["MSFT"],
    "Cantidad": [12],
    "Precio_compra": [437],      # Precio por acción en USD
    "Moneda": ["USD"],
    "Total_compra_USD": [5700],  # Lo que pagaste en USD
    "Total_compra_EUR": [5050]   # 💶 LO QUE PAGASTE REALMENTE EN EUROS
})

# =========================
# 2. DESCARGAR PRECIO ACTUAL DE LA ACCIÓN
# =========================
datos = yf.download(
    cartera["Ticker"].tolist(),
    period="6mo",
    interval="1d",
    group_by="ticker",
    progress=False
)

# Último precio de cierre
cartera["Precio_actual"] = [
    datos[t]["Close"].dropna().iloc[-1] for t in cartera["Ticker"]
]

# =========================
# 3. DESCARGAR CAMBIO USD → EUR
# =========================
fx = yf.download(
    "USDEUR=X",
    period="10d",
    interval="1d",
    progress=False
)

# Forzar a float (CLAVE)
cambio_actual = float(fx["Close"].dropna().iloc[-1].item())

print(f"Cambio USD/EUR actual: {cambio_actual:.4f}")


# =========================
# 4. CÁLCULOS FINANCIEROS
# =========================

# Valor actual total en USD
cartera["Total_actual_USD"] = cartera["Cantidad"] * cartera["Precio_actual"]

# Valor actual total en EUR (al cambio actual)
cartera["Total_actual_EUR"] = cartera["Total_actual_USD"] * cambio_actual

# Beneficio / pérdida real en EUR
cartera["Resultado_EUR"] = (
    cartera["Total_actual_EUR"] - cartera["Total_compra_EUR"]
)

# Rentabilidad porcentual real
cartera["Rentabilidad_%"] = (
    cartera["Resultado_EUR"] / cartera["Total_compra_EUR"]
) * 100

# =========================
# 5. RESULTADO FINAL
# =========================
print("\n📊 RESUMEN DE LA CARTERA\n")

print(cartera[[
    "Ticker",
    "Cantidad",
    "Moneda",
    "Precio_compra",
    "Precio_actual",
    "Total_compra_EUR",
    "Total_actual_EUR",
    "Resultado_EUR",
    "Rentabilidad_%"
]])

# =========================
# 6. DEBUG (POR SI ALGUNA VEZ FALLA)
# =========================
#print("\nDEBUG TIPOS DE DATOS:")
#print(cartera.dtypes)


from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator

# =========================
# INDICADORES TÉCNICOS
# =========================
datos_ind = yf.download(
    cartera["Ticker"].iloc[0],
    period="6mo",
    interval="1d",
    progress=False
)

# Forzar Close a Series 1D
close = datos_ind["Close"].squeeze()

datos_ind["RSI"] = RSIIndicator(close, window=14).rsi()
datos_ind["EMA20"] = EMAIndicator(close, window=20).ema_indicator()
datos_ind["EMA50"] = EMAIndicator(close, window=50).ema_indicator()


ultimo = datos_ind.dropna().iloc[-1]

rsi_actual = float(ultimo["RSI"].iloc[0])
ema20_actual = float(ultimo["EMA20"].iloc[0])
ema50_actual = float(ultimo["EMA50"].iloc[0])

# =========================
# SEÑAL DE DECISIÓN
# =========================
def generar_senal(rentabilidad, rsi, ema20, ema50):
    if rentabilidad > 15 and rsi > 70:
        return "⚠️ Tomar beneficios"
    elif rentabilidad < -10:
        return "🔴 Revisar / stop"
    elif ema20 > ema50:
        return "🟢 Mantener (tendencia alcista)"
    else:
        return "🔵 Mantener / observar"

cartera["Señal"] = generar_senal(
    float(cartera["Rentabilidad_%"].iloc[0]),
    rsi_actual,
    ema20_actual,
    ema50_actual
)

print("\n📊 DECISIÓN AUTOMÁTICA\n")
print(cartera[[
    "Ticker",
    "Rentabilidad_%",
    "Señal"
]])


import os

# =========================
# ALERTAS AUTOMÁTICAS
# =========================

archivo_senal = "ultima_senal.txt"
senal_actual = cartera["Señal"].iloc[0]

# Leer señal anterior (si existe)
if os.path.exists(archivo_senal):
    with open(archivo_senal, "r", encoding="utf-8") as f:
        senal_anterior = f.read().strip()
else:
    senal_anterior = None

# Comparar y alertar
if senal_anterior != senal_actual:
    print("\n🔔 ALERTA DE CAMBIO DE SEÑAL 🔔")
    print(f"Anterior: {senal_anterior}")
    print(f"Actual:    {senal_actual}")
else:
    print("\nℹ️ Sin cambios en la señal.")

# Guardar la señal actual
with open(archivo_senal, "w", encoding="utf-8") as f:
    f.write(senal_actual)

# Alerta por rentabilidad
if cartera["Rentabilidad_%"].iloc[0] > 15:
    print("💰 ALERTA: Rentabilidad superior al 15%")
elif cartera["Rentabilidad_%"].iloc[0] < -10:
    print("🛑 ALERTA: Pérdida superior al -10%")
