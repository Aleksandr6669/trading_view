# Индикаторы
df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)
df["ema50"] = ta.ema(df["close"], length=50)
df["slope"] = df["ema50"].diff()

# Диапазон колебаний
df["range_high"] = df["close"].rolling(30).max()
df["range_low"] = df["close"].rolling(30).min()

# Определяем тренд по наклону
slope = df["slope"].iloc[-1]
if slope > 0.1:
    trend = "Восходящий"
elif slope < -0.1:
    trend = "Нисходящий"
else:
    trend = "Флэт"

# Волатильность по ATR
atr = df["atr"].iloc[-1]
atr_ratio = atr / df["close"].mean()

if atr_ratio > 0.02:
    volatility = "Высокая"
elif atr_ratio > 0.01:
    volatility = "Средняя"
else:
    volatility = "Низкая"

comments = {}

# Комментарии для отображения под панелью 1
comments[1]="Основной график"

# Комментарии для отображения под панелью 2
comments[2] = f"Тренд:{trend}| Волатильность:{volatility}| Диапазон: {df['range_low'].iloc[-1]:.2f} - {df['range_high'].iloc[-1]:.2f}"

# Стандартный вывод для графика
plot_columns = ["ema50", "range_high:2", "range_low:2", "atr:3"]
mark_condition = None