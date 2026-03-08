# estrategias.py

import pandas as pd
import yfinance as yf
import ta
from ta.volatility import AverageTrueRange
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator

def get_activo_data(simbolo):
    """
    Descarga datos de 1h, 15m y 5m para un símbolo.
    Devuelve un diccionario con los dataframes.
    """
    try:
        ticker = yf.Ticker(simbolo)
        # Descargar múltiples timeframes
        df_1h = ticker.history(period="5d", interval="1h")
        df_15m = ticker.history(period="2d", interval="15m")
        df_5m = ticker.history(period="1d", interval="5m")
        
        # Verificar que no estén vacíos
        if df_1h.empty or df_15m.empty or df_5m.empty:
            return None
            
        return {
            '1h': df_1h,
            '15m': df_15m,
            '5m': df_5m
        }
    except Exception as e:
        print(f"Error descargando datos: {e}")
        return None

def calcular_indicadores(df):
    """Añade RSI, EMA20 y ATR% a un dataframe"""
    df = df.copy()
    df['rsi'] = RSIIndicator(df['Close'], window=14).rsi()
    df['ema_20'] = EMAIndicator(df['Close'], window=20).ema_indicator()
    atr = AverageTrueRange(df['High'], df['Low'], df['Close'], window=14)
    df['atr'] = atr.average_true_range()
    df['atr_pct'] = (df['atr'] / df['Close']) * 100
    return df

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
    
    # Calcular volumen medio (últimas 20 velas en 5m)
    volumen_medio_5m = df_5m['Volume'].tail(20).mean()
    
    # Inicializar señal
    senal = None
    
    # --- Lógica para COMPRA (CALL) ---
    # 1. Tendencia principal alcista en 1h
    tendencia_alcista_1h = (
        ultimo_1h['Close'] > ultimo_1h['ema_20'] and
        df_1h['ema_20'].iloc[-1] > df_1h['ema_20'].iloc[-5]  # pendiente positiva
    )
    
    # 2. Precio en zona de soporte en 15m (aproximación)
    soporte_15m = df_15m['Low'].tail(10).min()
    cerca_soporte = abs(ultimo_15m['Close'] - soporte_15m) / soporte_15m < 0.01
    
    # 3. Patrón Spring en 5m (falso quiebre)
    spring_5m = (
        df_5m['Low'].iloc[-2] < soporte_15m and
        ultimo_5m['Close'] > soporte_15m
    )
    
    # 4. Condiciones RSI y EMA en 5m
    rsi_ok = 30 <= ultimo_5m['rsi'] <= 45
    ema_ok = ultimo_5m['Close'] > ultimo_5m['ema_20']
    
    # 5. Volumen
    volumen_ok = df_5m['Volume'].iloc[-1] > volumen_medio_5m * 1.2  # 20% más que la media
    
    # 6. ATR suficiente
    atr_ok = ultimo_5m['atr_pct'] > 0.5  # >0.5% del precio
    
    if (tendencia_alcista_1h and (cerca_soporte or spring_5m) and 
        rsi_ok and ema_ok and volumen_ok and atr_ok):
        precio = round(ultimo_5m['Close'], 2)
        senal = {
            'tipo': 'COMPRA (CALL)',
            'precio': precio,
            'tp1': round(precio * 1.02, 2),  # +2%
            'tp2': round(precio * 1.04, 2),  # +4%
            'timeframe': '5m',
            'confianza': 'ALTA' if spring_5m else 'MEDIA'
        }
    
    # --- Lógica para VENTA (PUT) ---
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
            'tp1': round(precio * 0.98, 2),  # -2%
            'tp2': round(precio * 0.96, 2),  # -4%
            'timeframe': '5m',
            'confianza': 'ALTA' if upthrust_5m else 'MEDIA'
        }
    
    return senal

def detectar_senales_binarias(data):
    """
    Estrategia de Binarias (Triple Confirmación + Fractal)
    Versión optimizada con timeframes 15m, 5m, 1m.
    """
    if not data:
        return None
        
    df_15m = calcular_indicadores(data['15m'])
    df_5m = calcular_indicadores(data['5m'])
    df_1h = data['1h']  # Para contexto
    
    # Últimos valores
    ultimo_15m = df_15m.iloc[-1]
    ultimo_5m = df_5m.iloc[-1]
    
    # Calcular volumen medio en 5m
    volumen_medio_5m = df_5m['Volume'].tail(20).mean()
    
    senal = None
    
    # --- COMPRA (CALL) para binarias ---
    # Condiciones en 15m
    call_15m = (
        ultimo_15m['Close'] > ultimo_15m['ema_20'] and
        40 <= ultimo_15m['rsi'] <= 60 and
        ultimo_15m['Close'] > df_15m['Close'].rolling(10).min().iloc[-1]  # soporte dinámico
    )
    
    # Condiciones en 5m
    call_5m = (
        ultimo_5m['Close'] > ultimo_5m['ema_20'] and
        df_5m['Volume'].iloc[-1] > volumen_medio_5m and
        df_5m['Close'].iloc[-1] > df_5m['Close'].iloc[-2]  # vela alcista
    )
    
    if call_15m and call_5m:
        senal = {
            'tipo': 'COMPRA (CALL)',
            'precio': round(ultimo_5m['Close'], 2),
            'duracion': '5-15 min',
            'confianza': 'ALTA'
        }
    
    # --- VENTA (PUT) para binarias ---
    put_15m = (
        ultimo_15m['Close'] < ultimo_15m['ema_20'] and
        40 <= ultimo_15m['rsi'] <= 60 and
        ultimo_15m['Close'] < df_15m['Close'].rolling(10).max().iloc[-1]  # resistencia dinámica
    )
    
    put_5m = (
        ultimo_5m['Close'] < ultimo_5m['ema_20'] and
        df_5m['Volume'].iloc[-1] > volumen_medio_5m and
        df_5m['Close'].iloc[-1] < df_5m['Close'].iloc[-2]  # vela bajista
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
    """
    Ejecuta backtesting de la estrategia de apalancamiento en un período.
    Devuelve estadísticas.
    """
    import yfinance as yf
    from datetime import datetime, timedelta
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=periodo_dias)
    
    ticker = yf.Ticker(simbolo)
    df = ticker.history(start=start_date, end=end_date, interval="1h")
    
    if df.empty:
        return None
    
    # Simulación simple: cada vez que se cumple la condición de compra/venta,
    # se abre una operación con stop y tp fijos.
    # Esta es una versión simplificada; puedes complicarla cuanto quieras.
    
    df = calcular_indicadores(df)
    
    operaciones = []
    capital = 1000  # capital inicial ficticio
    riesgo_por_operacion = 0.02 * capital  # 2%
    
    for i in range(20, len(df)-1):
        fila = df.iloc[i]
        fila_sig = df.iloc[i+1]
        
        # Lógica de compra simplificada (puedes usar la misma que en la estrategia)
        if (30 <= fila['rsi'] <= 45 and 
            fila['Close'] > fila['ema_20'] and
            fila['atr_pct'] > 0.5):
            
            entrada = fila['Close']
            stop = entrada * 0.99  # stop 1%
            tp = entrada * 1.02    # tp 2%
            
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