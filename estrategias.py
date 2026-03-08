# estrategias.py
import os
import requests
import pandas as pd
import ta
from ta.volatility import AverageTrueRange
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator

def get_activo_data(simbolo):
    api_key = os.environ.get("TWELVE_DATA_API_KEY")
    if not api_key:
        print("ERROR: Variable de entorno TWELVE_DATA_API_KEY no encontrada.")
        return None

    twelve_data_symbols = {
        "GC=F": "XAU/USD",
        "CL=F": "WTI/USD",
        "NQ=F": "US100"
    }
    symbol_td = twelve_data_symbols.get(simbolo, simbolo)

    base_url = "https://api.twelvedata.com/time_series"
    params = {
        "apikey": api_key,
        "symbol": symbol_td,
        "order": "DESC",
    }

    data = {}
    timeouts = (5, 10)
    min_required = 30  # mínimo de filas para poder calcular indicadores

    # 1h
    try:
        params_1h = params.copy()
        params_1h.update({"interval": "1h", "outputsize": min_required})
        response = requests.get(base_url, params=params_1h, timeout=timeouts)
        response.raise_for_status()
        json_data = response.json()
        if "values" not in json_data or len(json_data["values"]) < min_required:
            print(f"Error: Pocos datos 1h para {simbolo}")
            return None
        df_1h = pd.DataFrame(json_data["values"])
        df_1h["datetime"] = pd.to_datetime(df_1h["datetime"])
        df_1h = df_1h.sort_values("datetime")
        df_1h[["open", "high", "low", "close"]] = df_1h[["open", "high", "low", "close"]].astype(float)
        data['1h'] = df_1h
    except Exception as e:
        print(f"Error 1h: {e}")
        return None

    # 15m
    try:
        params_15m = params.copy()
        params_15m.update({"interval": "15min", "outputsize": min_required})
        response = requests.get(base_url, params=params_15m, timeout=timeouts)
        response.raise_for_status()
        json_data = response.json()
        if "values" not in json_data or len(json_data["values"]) < min_required:
            print(f"Error: Pocos datos 15m para {simbolo}")
            return None
        df_15m = pd.DataFrame(json_data["values"])
        df_15m["datetime"] = pd.to_datetime(df_15m["datetime"])
        df_15m = df_15m.sort_values("datetime")
        df_15m[["open", "high", "low", "close"]] = df_15m[["open", "high", "low", "close"]].astype(float)
        data['15m'] = df_15m
    except Exception as e:
        print(f"Error 15m: {e}")
        return None

    # 5m
    try:
        params_5m = params.copy()
        params_5m.update({"interval": "5min", "outputsize": min_required})
        response = requests.get(base_url, params=params_5m, timeout=timeouts)
        response.raise_for_status()
        json_data = response.json()
        if "values" not in json_data or len(json_data["values"]) < min_required:
            print(f"Error: Pocos datos 5m para {simbolo}")
            return None
        df_5m = pd.DataFrame(json_data["values"])
        df_5m["datetime"] = pd.to_datetime(df_5m["datetime"])
        df_5m = df_5m.sort_values("datetime")
        df_5m[["open", "high", "low", "close"]] = df_5m[["open", "high", "low", "close"]].astype(float)
        data['5m'] = df_5m
    except Exception as e:
        print(f"Error 5m: {e}")
        return None

    return data

def calcular_indicadores(df):
    """Añade RSI, EMA20 y ATR% a un dataframe, con manejo de datos insuficientes"""
    if len(df) < 20:
        return None
    df = df.copy()
    df['rsi'] = RSIIndicator(df['Close'], window=14).rsi()
    df['ema_20'] = EMAIndicator(df['Close'], window=20).ema_indicator()
    atr = AverageTrueRange(df['High'], df['Low'], df['Close'], window=14)
    df['atr'] = atr.average_true_range()
    df['atr_pct'] = (df['atr'] / df['Close']) * 100
    return df

def detectar_senales_apalancamiento(data):
    if not data:
        return None

    df_1h = calcular_indicadores(data['1h'])
    df_15m = calcular_indicadores(data['15m'])
    df_5m = calcular_indicadores(data['5m'])

    if df_1h is None or df_15m is None or df_5m is None:
        return None

    # ... resto igual que antes ...
    ultimo_1h = df_1h.iloc[-1]
    ultimo_15m = df_15m.iloc[-1]
    ultimo_5m = df_5m.iloc[-1]

    volumen_medio_5m = df_5m['Volume'].tail(20).mean() if 'Volume' in df_5m else 1000000

    senal = None

    # COMPRA
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

    # VENTA
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

def detectar_senales_binarias(data):
    if not data:
        return None

    df_15m = calcular_indicadores(data['15m'])
    df_5m = calcular_indicadores(data['5m'])

    if df_15m is None or df_5m is None:
        return None

    ultimo_15m = df_15m.iloc[-1]
    ultimo_5m = df_5m.iloc[-1]

    volumen_medio_5m = df_5m['Volume'].tail(20).mean() if 'Volume' in df_5m else 1000000

    senal = None

    # CALL
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

    # PUT
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

def backtest_estrategia(simbolo, periodo_dias=180):
    # ... (igual que antes, pero no es crítico ahora)
    import yfinance as yf
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
    if df is None:
        return {"mensaje": "Datos insuficientes para backtest."}
    # ... resto del código de backtest (lo dejamos igual) ...
    # Nota: no es necesario modificarlo ahora, pero asegúrate de que esté completo.
    # Por brevedad, omito el resto, pero en tu archivo debe estar completo.
