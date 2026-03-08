# estrategias.py
# Versión robusta con yfinance + reintentos + validación de datos

import time
import random
import pandas as pd
import yfinance as yf
import ta
from ta.volatility import AverageTrueRange
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator

# ------------------------------------------------------------
# FUNCIÓN: Obtener datos desde yfinance con reintentos
# ------------------------------------------------------------
def get_activo_data(simbolo, max_reintentos=3):
    """
    Descarga datos de 1h, 15m y 5m para un símbolo usando yfinance.
    Implementa reintentos automáticos y validación de datos mínimos.
    """
    for intento in range(1, max_reintentos + 1):
        try:
            ticker = yf.Ticker(simbolo)

            # Descargar datos con timeouts explícitos
            df_1h = ticker.history(period="5d", interval="1h", timeout=10)
            df_15m = ticker.history(period="2d", interval="15m", timeout=10)
            df_5m = ticker.history(period="1d", interval="5m", timeout=10)

            # Verificar que no estén vacíos y tengan suficientes filas
            if df_1h.empty or len(df_1h) < 20:
                raise ValueError(f"Datos insuficientes para 1h: {len(df_1h)} filas")
            if df_15m.empty or len(df_15m) < 30:
                raise ValueError(f"Datos insuficientes para 15m: {len(df_15m)} filas")
            if df_5m.empty or len(df_5m) < 30:
                raise ValueError(f"Datos insuficientes para 5m: {len(df_5m)} filas")

            # Renombrar columnas a minúsculas para consistencia (opcional)
            df_1h.columns = [c.lower() for c in df_1h.columns]
            df_15m.columns = [c.lower() for c in df_15m.columns]
            df_5m.columns = [c.lower() for c in df_5m.columns]

            return {'1h': df_1h, '15m': df_15m, '5m': df_5m}

        except Exception as e:
            print(f"Intento {intento}/{max_reintentos} falló para {simbolo}: {e}")
            if intento < max_reintentos:
                # Esperar un tiempo aleatorio antes de reintentar (backoff)
                time.sleep(random.uniform(2, 5))
            else:
                print(f"Todos los intentos fallaron para {simbolo}")
                return None
    return None


# ------------------------------------------------------------
# FUNCIÓN: Calcular indicadores técnicos (con validación)
# ------------------------------------------------------------
def calcular_indicadores(df):
    """Añade RSI, EMA20 y ATR% a un dataframe, verificando que haya suficientes datos."""
    if df is None or len(df) < 20:
        print(f"DataFrame con muy pocos datos ({len(df) if df is not None else 0}) para calcular indicadores")
        return None
    df = df.copy()
    try:
        # Asegurar que las columnas existen
        required_cols = ['close', 'high', 'low']
        if not all(col in df.columns for col in required_cols):
            print(f"Columnas requeridas no encontradas: {df.columns.tolist()}")
            return None

        df['rsi'] = RSIIndicator(df['close'], window=14).rsi()
        df['ema_20'] = EMAIndicator(df['close'], window=20).ema_indicator()
        atr = AverageTrueRange(df['high'], df['low'], df['close'], window=14)
        df['atr'] = atr.average_true_range()
        df['atr_pct'] = (df['atr'] / df['close']) * 100
        return df
    except Exception as e:
        print(f"Error calculando indicadores: {e}")
        return None


# ------------------------------------------------------------
# ESTRATEGIA DE APALANCAMIENTO
# ------------------------------------------------------------
def detectar_senales_apalancamiento(data):
    if not data:
        return None

    df_1h = calcular_indicadores(data['1h'])
    df_15m = calcular_indicadores(data['15m'])
    df_5m = calcular_indicadores(data['5m'])

    if df_1h is None or df_15m is None or df_5m is None:
        print("Datos insuficientes para calcular señales de apalancamiento")
        return None

    # Últimos valores
    ultimo_1h = df_1h.iloc[-1]
    ultimo_15m = df_15m.iloc[-1]
    ultimo_5m = df_5m.iloc[-1]

    # Volumen medio en 5m (si existe columna volume)
    if 'volume' in df_5m.columns:
        volumen_medio_5m = df_5m['volume'].tail(20).mean()
    else:
        volumen_medio_5m = 1  # Valor por defecto para no bloquear

    senal = None

    # --- COMPRA (CALL) ---
    tendencia_alcista_1h = (
        ultimo_1h['close'] > ultimo_1h['ema_20'] and
        df_1h['ema_20'].iloc[-1] > df_1h['ema_20'].iloc[-5]
    )
    soporte_15m = df_15m['low'].tail(10).min()
    cerca_soporte = abs(ultimo_15m['close'] - soporte_15m) / soporte_15m < 0.01
    spring_5m = (
        df_5m['low'].iloc[-2] < soporte_15m and
        ultimo_5m['close'] > soporte_15m
    )
    rsi_ok = 30 <= ultimo_5m['rsi'] <= 45
    ema_ok = ultimo_5m['close'] > ultimo_5m['ema_20']
    volumen_ok = df_5m['volume'].iloc[-1] > volumen_medio_5m * 1.2 if 'volume' in df_5m else True
    atr_ok = ultimo_5m['atr_pct'] > 0.5

    if (tendencia_alcista_1h and (cerca_soporte or spring_5m) and
        rsi_ok and ema_ok and volumen_ok and atr_ok):
        precio = round(ultimo_5m['close'], 2)
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
        ultimo_1h['close'] < ultimo_1h['ema_20'] and
        df_1h['ema_20'].iloc[-1] < df_1h['ema_20'].iloc[-5]
    )
    resistencia_15m = df_15m['high'].tail(10).max()
    cerca_resistencia = abs(resistencia_15m - ultimo_15m['close']) / resistencia_15m < 0.01
    upthrust_5m = (
        df_5m['high'].iloc[-2] > resistencia_15m and
        ultimo_5m['close'] < resistencia_15m
    )
    rsi_put_ok = 55 <= ultimo_5m['rsi'] <= 70
    ema_put_ok = ultimo_5m['close'] < ultimo_5m['ema_20']

    if (tendencia_bajista_1h and (cerca_resistencia or upthrust_5m) and
        rsi_put_ok and ema_put_ok and volumen_ok and atr_ok):
        precio = round(ultimo_5m['close'], 2)
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
    if not data:
        return None

    df_15m = calcular_indicadores(data['15m'])
    df_5m = calcular_indicadores(data['5m'])

    if df_15m is None or df_5m is None:
        print("Datos insuficientes para calcular señales de binarias")
        return None

    ultimo_15m = df_15m.iloc[-1]
    ultimo_5m = df_5m.iloc[-1]

    if 'volume' in df_5m.columns:
        volumen_medio_5m = df_5m['volume'].tail(20).mean()
    else:
        volumen_medio_5m = 1

    senal = None

    # --- COMPRA (CALL) ---
    call_15m = (
        ultimo_15m['close'] > ultimo_15m['ema_20'] and
        40 <= ultimo_15m['rsi'] <= 60 and
        ultimo_15m['close'] > df_15m['close'].rolling(10).min().iloc[-1]
    )
    call_5m = (
        ultimo_5m['close'] > ultimo_5m['ema_20'] and
        (df_5m['volume'].iloc[-1] > volumen_medio_5m if 'volume' in df_5m else True) and
        df_5m['close'].iloc[-1] > df_5m['close'].iloc[-2]
    )

    if call_15m and call_5m:
        senal = {
            'tipo': 'COMPRA (CALL)',
            'precio': round(ultimo_5m['close'], 2),
            'duracion': '5-15 min',
            'confianza': 'ALTA'
        }

    # --- VENTA (PUT) ---
    put_15m = (
        ultimo_15m['close'] < ultimo_15m['ema_20'] and
        40 <= ultimo_15m['rsi'] <= 60 and
        ultimo_15m['close'] < df_15m['close'].rolling(10).max().iloc[-1]
    )
    put_5m = (
        ultimo_5m['close'] < ultimo_5m['ema_20'] and
        (df_5m['volume'].iloc[-1] > volumen_medio_5m if 'volume' in df_5m else True) and
        df_5m['close'].iloc[-1] < df_5m['close'].iloc[-2]
    )

    if put_15m and put_5m:
        senal = {
            'tipo': 'VENTA (PUT)',
            'precio': round(ultimo_5m['close'], 2),
            'duracion': '5-15 min',
            'confianza': 'ALTA'
        }

    return senal


# ------------------------------------------------------------
# BACKTESTING (función simplificada)
# ------------------------------------------------------------
def backtest_estrategia(simbolo, periodo_dias=180):
    """Ejecuta backtesting de la estrategia de apalancamiento en un período."""
    from datetime import datetime, timedelta

    end_date = datetime.now()
    start_date = end_date - timedelta(days=periodo_dias)

    try:
        ticker = yf.Ticker(simbolo)
        df = ticker.history(start=start_date, end=end_date, interval="1h", timeout=15)
    except Exception as e:
        return {"mensaje": f"No se pudieron obtener datos históricos: {e}"}

    if df.empty or len(df) < 20:
        return {"mensaje": "No se generaron operaciones en el período."}

    # Renombrar columnas
    df.columns = [c.lower() for c in df.columns]
    df = calcular_indicadores(df)
    if df is None:
        return {"mensaje": "Error calculando indicadores para backtest."}

    operaciones = []
    capital = 1000
    riesgo_por_operacion = 0.02 * capital

    for i in range(20, len(df)-1):
        fila = df.iloc[i]
        fila_sig = df.iloc[i+1]

        if (30 <= fila['rsi'] <= 45 and
            fila['close'] > fila['ema_20'] and
            fila['atr_pct'] > 0.5):

            entrada = fila['close']
            stop = entrada * 0.99
            tp = entrada * 1.02

            resultado = 1 if fila_sig['high'] >= tp else (-1 if fila_sig['low'] <= stop else 0)
            if resultado == 1:
                ganancia = tp - entrada
            elif resultado == -1:
                ganancia = stop - entrada
            else:
                ganancia = fila_sig['close'] - entrada

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
