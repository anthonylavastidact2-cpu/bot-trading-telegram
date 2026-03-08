# estrategias.py
# Versión con Twelve Data para obtener datos de mercado

import os
import requests
import pandas as pd
import ta
from ta.volatility import AverageTrueRange
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator

# ------------------------------------------------------------
# FUNCIÓN: Obtener datos desde Twelve Data
# ------------------------------------------------------------
def get_activo_data(simbolo):
    """
    Descarga datos de 1h, 15m y 5m para un símbolo usando la API de Twelve Data.
    Necesita la variable de entorno TWELVE_DATA_API_KEY configurada en Render.
    """
    api_key = os.environ.get("TWELVE_DATA_API_KEY")
    if not api_key:
        print("ERROR: Variable de entorno TWELVE_DATA_API_KEY no encontrada.")
        return None

    # Mapeo de símbolos de Yahoo Finance a símbolos de Twelve Data
    twelve_data_symbols = {
        "GC=F": "XAU/USD",      # Oro
        "CL=F": "WTI/USD",      # Petróleo WTI
        "NQ=F": "US100"         # Nasdaq 100
    }
    symbol_td = twelve_data_symbols.get(simbolo, simbolo)

    base_url = "https://api.twelvedata.com/time_series"
    params = {
        "apikey": api_key,
        "symbol": symbol_td,
        "order": "DESC",
    }

    data = {}

    # --- 1. Datos de 1 hora ---
    params_1h = params.copy()
    params_1h.update({"interval": "1h", "outputsize": 120})
    try:
        response = requests.get(base_url, params=params_1h)
        response.raise_for_status()
        json_data = response.json()
        if "values" in json_data:
            df_1h = pd.DataFrame(json_data["values"])
            df_1h["datetime"] = pd.to_datetime(df_1h["datetime"])
            df_1h = df_1h.sort_values("datetime")
            df_1h[["open", "high", "low", "close"]] = df_1h[["open", "high", "low", "close"]].astype(float)
            data['1h'] = df_1h
        else:
            print(f"Error API Twelve Data (1h) para {simbolo}: {json_data.get('message', 'Respuesta vacía')}")
            return None
    except Exception as e:
        print(f"Excepción al obtener datos 1h: {e}")
        return None

    # --- 2. Datos de 15 minutos ---
    params_15m = params.copy()
    params_15m.update({"interval": "15min", "outputsize": 200})
    try:
        response = requests.get(base_url, params=params_15m)
        response.raise_for_status()
        json_data = response.json()
        if "values" in json_data:
            df_15m = pd.DataFrame(json_data["values"])
            df_15m["datetime"] = pd.to_datetime(df_15m["datetime"])
            df_15m = df_15m.sort_values("datetime")
            df_15m[["open", "high", "low", "close"]] = df_15m[["open", "high", "low", "close"]].astype(float)
            data['15m'] = df_15m
        else:
            print(f"Error API Twelve Data (15m) para {simbolo}: {json_data.get('message', 'Respuesta vacía')}")
            return None
    except Exception as e:
        print(f"Excepción al obtener datos 15m: {e}")
        return None

    # --- 3. Datos de 5 minutos ---
    params_5m = params.copy()
    params_5m.update({"interval": "5min", "outputsize": 200})
    try:
        response = requests.get(base_url, params=params_5m)
        response.raise_for_status()
        json_data = response.json()
        if "values" in json_data:
            df_5m = pd.DataFrame(json_data["values"])
            df_5m["datetime"] = pd.to_datetime(df_5m["datetime"])
            df_5m = df_5m.sort_values("datetime")
            df_5m[["open", "high", "low", "close"]] = df_5m[["open", "high", "low", "close"]].astype(float)
            data['5m'] = df_5m
        else:
            print(f"Error API Twelve Data (5m) para {simbolo}: {json_data.get('message', 'Respuesta vacía')}")
            return None
    except Exception as e:
        print(f"Excepción al obtener datos 5m: {e}")
        return None

    return data


# ------------------------------------------------------------
# FUNCIÓN: Calcular indicadores técnicos (RSI, EMA, ATR)
# ------------------------------------------------------------
def calcular_indicadores(df):
    """Añade RSI, EMA20 y ATR% a un dataframe"""
    df = df.copy()
    df['rsi'] = RSIIndicator(df['Close'], window=14).rsi()
    df['ema_20'] = EMAIndicator(df['Close'], window=20).ema_indicator()
    atr = AverageTrueRange(df['High'], df['Low'], df['Close'], window=14)
    df['atr'] = atr.average_true_range()
    df['atr_pct'] = (df['atr'] / df['Close']) * 100
    return df


# ------------------------------------------------------------
# ESTRATEGIA DE APALANCAMIENTO
# ------------------------------------------------------------
def detectar_senales_apalancamiento(data):
    """
    Estrategia de Apalancamiento (Tendencia + Pirámide + Gestión Absoluta)
    Versión optimizada con todos los filtros.
    """
    if not data:
        return None

    df_1h = calcular_indicadores(data['1h'])
    df_15m = calcular_indicadores(data['15m'])
    df_5m = calcular_indicadores(data['5m'])

    # Últimos valores
    ultimo_1h = df_1h.iloc[-1]
    ultimo_15m = df_15m.iloc[-1]
    ultimo_5m = df_5m.iloc[-1]

    # Volumen medio en 5m
    volumen_medio_5m = df_5m['Volume'].tail(20).mean() if 'Volume' in df_5m else 1000000  # Si no hay volumen, asumimos un valor alto

    senal = None

    # --- COMPRA (CALL) ---
    tendencia_alcista_1h = (
        ultimo_1h['Close'] > ultimo_1h['ema_20'] and
        df_1h['ema_20'].iloc[-1] > df_1h['ema_20'].iloc[-5]
    )
    soporte_15m = df_15m['Low'].tail(10).min()
    cerca_soporte = abs(ultimo_15m['Close'] - soporte_15m) / soporte_15m < 0.01
    spring_5m = (
        df_5m['Low'].iloc[-2] < soporte_15m and
        ultimo_5m['Close'] > soporte_15m
    )
    rsi_ok = 30 <= ultimo_5m['rsi'] <= 45
    ema_ok = ultimo_5m['Close'] > ultimo_5m['ema_20']
    volumen_ok = df_5m['Volume'].iloc[-1] > volumen_medio_5m * 1.2 if 'Volume' in df_5m else True
    atr_ok = ultimo_5m['atr_pct'] > 0.5

    if (tendencia_alcista_1h and (cerca_soporte or spring_5m) and
        rsi_ok and ema_ok and volumen_ok and atr_ok):
        precio = round(ultimo_5m['Close'], 2)
        senal = {
            'tipo': 'COMPRA (CALL)',
            'precio': precio,
            'tp1': round(precio * 1.02, 2),
            'tp2': round(precio * 1.04, 2),
            'timeframe': '5m',
            'confianza': 'ALTA' if spring_5m else 'MEDIA'
        }

    # --- VENTA (PUT) ---
    tendencia_bajista_1h = (
        ultimo_1h['Close'] < ultimo_1h['ema_20'] and
        df_1h['ema_20'].iloc[-1] < df_1h['ema_20'].iloc[-5]
    )
    resistencia_15m = df_15m['High'].tail(10).max()
    cerca_resistencia = abs(resistencia_15m - ultimo_15m['Close']) / resistencia_15m < 0.01
    upthrust_5m = (
        df_5m['High'].iloc[-2] > resistencia_15m and
        ultimo_5m['Close'] < resistencia_15m
    )
    rsi_put_ok = 55 <= ultimo_5m['rsi'] <= 70
    ema_put_ok = ultimo_5m['Close'] < ultimo_5m['ema_20']

    if (tendencia_bajista_1h and (cerca_resistencia or upthrust_5m) and
        rsi_put_ok and ema_put_ok and volumen_ok and atr_ok):
        precio = round(ultimo_5m['Close'], 2)
        senal = {
            'tipo': 'VENTA (PUT)',
            'precio': precio,
            'tp1': round(precio * 0.98, 2),
            'tp2': round(precio * 0.96, 2),
            'timeframe': '5m',
            'confianza': 'ALTA' if upthrust_5m else 'MEDIA'
        }

    return senal


# ------------------------------------------------------------
# ESTRATEGIA DE BINARIAS
# ------------------------------------------------------------
def detectar_senales_binarias(data):
    """
    Estrategia de Binarias (Triple Confirmación + Fractal)
    Versión optimizada con timeframes 15m, 5m.
    """
    if not data:
        return None

    df_15m = calcular_indicadores(data['15m'])
    df_5m = calcular_indicadores(data['5m'])

    ultimo_15m = df_15m.iloc[-1]
    ultimo_5m = df_5m.iloc[-1]

    volumen_medio_5m = df_5m['Volume'].tail(20).mean() if 'Volume' in df_5m else 1000000

    senal = None

    # --- COMPRA (CALL) ---
    call_15m = (
        ultimo_15m['Close'] > ultimo_15m['ema_20'] and
        40 <= ultimo_15m['rsi'] <= 60 and
        ultimo_15m['Close'] > df_15m['Close'].rolling(10).min().iloc[-1]
    )
    call_5m = (
        ultimo_5m['Close'] > ultimo_5m['ema_20'] and
        (df_5m['Volume'].iloc[-1] > volumen_medio_5m if 'Volume' in df_5m else True) and
        df_5m['Close'].iloc[-1] > df_5m['Close'].iloc[-2]
    )

    if call_15m and call_5m:
        senal = {
            'tipo': 'COMPRA (CALL)',
            'precio': round(ultimo_5m['Close'], 2),
            'duracion': '5-15 min',
            'confianza': 'ALTA'
        }

    # --- VENTA (PUT) ---
    put_15m = (
        ultimo_15m['Close'] < ultimo_15m['ema_20'] and
        40 <= ultimo_15m['rsi'] <= 60 and
        ultimo_15m['Close'] < df_15m['Close'].rolling(10).max().iloc[-1]
    )
    put_5m = (
        ultimo_5m['Close'] < ultimo_5m['ema_20'] and
        (df_5m['Volume'].iloc[-1] > volumen_medio_5m if 'Volume' in df_5m else True) and
        df_5m['Close'].iloc[-1] < df_5m['Close'].iloc[-2]
    )

    if put_15m and put_5m:
        senal = {
            'tipo': 'VENTA (PUT)',
            'precio': round(ultimo_5m['Close'], 2),
            'duracion': '5-15 min',
            'confianza': 'ALTA'
        }

    return senal


# ------------------------------------------------------------
# BACKTESTING (función simplificada)
# ------------------------------------------------------------
def backtest_estrategia(simbolo, periodo_dias=180):
    """
    Ejecuta backtesting de la estrategia de apalancamiento en un período.
    Versión simplificada para Twelve Data.
    """
    import yfinance as yf  # Para backtesting usamos yfinance (opcional)
    from datetime import datetime, timedelta

    end_date = datetime.now()
    start_date = end_date - timedelta(days=periodo_dias)

    try:
        ticker = yf.Ticker(simbolo)
        df = ticker.history(start=start_date, end=end_date, interval="1h")
    except:
        return {"mensaje": "No se pudieron obtener datos históricos para backtest."}

    if df.empty:
        return {"mensaje": "No se generaron operaciones en el período."}

    df = calcular_indicadores(df)

    operaciones = []
    capital = 1000
    riesgo_por_operacion = 0.02 * capital

    for i in range(20, len(df)-1):
        fila = df.iloc[i]
        fila_sig = df.iloc[i+1]

        # Condición de compra simplificada
        if (30 <= fila['rsi'] <= 45 and
            fila['Close'] > fila['ema_20'] and
            fila['atr_pct'] > 0.5):

            entrada = fila['Close']
            stop = entrada * 0.99
            tp = entrada * 1.02

            resultado = 1 if fila_sig['High'] >= tp else (-1 if fila_sig['Low'] <= stop else 0)
            if resultado == 1:
                ganancia = tp - entrada
            elif resultado == -1:
                ganancia = stop - entrada
            else:
                ganancia = fila_sig['Close'] - entrada

            operaciones.append(ganancia)

    if not operaciones:
        return {"mensaje": "No se generaron operaciones en el período."}

    ganancias = [op for op in operaciones if op > 0]
    perdidas = [op for op in operaciones if op < 0]

    return {
        "total_operaciones": len(operaciones),
        "operaciones_ganadoras": len(ganancias),
        "operaciones_perdedoras": len(perdidas),
        "win_rate": round(len(ganancias)/len(operaciones)*100, 2),
        "ganancia_total": round(sum(operaciones), 2),
        "ganancia_promedio": round(sum(ganancias)/len(ganancias), 2) if ganancias else 0,
        "perdida_promedio": round(sum(perdidas)/len(perdidas), 2) if perdidas else 0
    }
