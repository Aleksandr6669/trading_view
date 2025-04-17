comments = {1: {}, 2: {}}

# Настройки
API_KEY = "7u6mrJUC80sCeYMv8zcVXIcGzkuGfF5HsANJUNhnuP8BRZVKgWnZytAqv0plDn4X"
API_SECRET = "rKVkFVGddszfKv9LhBKThOkR6530tmNdaKiD4eRUi1Kbl0J14pV6UrrQXzBbJ9jV"
TOKIN = "7979456533:AAGneMP9LlIASbHeFKeOoNruMMBd-nmQRnQ"

ID = "353095791"
IS_TESTNET = False

QUANTITY = 0.2
LEVERAGE = 20
ATR_MULT_SL = 0.2
ATR_MULT_TP = 1.2
SYMBOL = "BTCUSDT"

rsi_buy = 30
rsi_sell = 70
BOUNCE_THRESHOLD = 0.001
BOUNCE_CONFIRMATION_RATIO = 0.001

# Индикаторы
df["rsi"] = ta.rsi(df["close"], length=14)
df["ema"] = ta.ema(df["close"], length=20)
df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)

# Свечные модели
df["bullish_engulfing"] = (df["close"] > df["open"].shift(1)) & (df["open"] < df["close"].shift(1))
df["bearish_engulfing"] = (df["close"] < df["open"].shift(1)) & (df["open"] > df["close"].shift(1))

# Уровни
detector.set_params(order=10, round_to=2)
support, resistance, _, _ = detector.detect_levels()
df.at[0, "support_levels"] = support
df.at[0, "resistance_levels"] = resistance

# 💥 Отскоки (с гибким подтверждением в 3 свечах)
bounce_support_flags = []
bounce_resistance_flags = []

for i in range(len(df)):
    price = df["close"].iloc[i]
    confirmed_support = False
    confirmed_resistance = False

    # Проверка поддержки
    for lvl in support:
        if abs(price - lvl) / lvl < BOUNCE_THRESHOLD:
            for j in range(1, 4):  # до 3 свечей вперёд
                if i + j >= len(df):
                    break
                future_price = df["close"].iloc[i + j]
                if (future_price - lvl) / lvl > BOUNCE_CONFIRMATION_RATIO:
                    confirmed_support = True
                    break
            if confirmed_support:
                break

    # Проверка сопротивления
    for lvl in resistance:
        if abs(price - lvl) / lvl < BOUNCE_THRESHOLD:
            for j in range(1, 4):  # до 3 свечей вперёд
                if i + j >= len(df):
                    break
                future_price = df["close"].iloc[i + j]
                if (lvl - future_price) / lvl > BOUNCE_CONFIRMATION_RATIO:
                    confirmed_resistance = True
                    break
            if confirmed_resistance:
                break

    bounce_support_flags.append(confirmed_support)
    bounce_resistance_flags.append(confirmed_resistance)

df["bounce_support"] = bounce_support_flags
df["bounce_resistance"] = bounce_resistance_flags


# Условия входа
df["entry_buy"] = df["bounce_support"] & (df["rsi"] > rsi_buy) & (df["close"] > df["ema"])
df["entry_sell"] = df["bounce_resistance"] & (df["rsi"] < rsi_sell) & (df["close"] < df["ema"])
df["signal"] = None
df.loc[df["entry_buy"], "signal"] = "BUY"
df.loc[df["entry_sell"], "signal"] = "SELL"

# Вероятности
df["buy_prob"] = (
    df["bounce_support"].astype(int) +
    (df["rsi"] > rsi_buy).astype(int) +
    (df["close"] > df["ema"]).astype(int)
) / 3 * 100

df["sell_prob"] = (
    df["bounce_resistance"].astype(int) +
    (df["rsi"] < rsi_sell).astype(int) +
    (df["close"] < df["ema"]).astype(int)
) / 3 * 100

buy_probability = df["buy_prob"].iloc[-1]
sell_probability = df["sell_prob"].iloc[-1]

if buy_probability > 66:
    comments[1][2.75] = f"🟢 Сильный отскок вверх ({buy_probability:.1f}%)"
elif buy_probability > 33:
    comments[1][2.75] = f"🟡 Средний отскок вверх ({buy_probability:.1f}%)"
elif buy_probability > 0:
    comments[1][2.75] = f"⚪️ Слабый отскок вверх ({buy_probability:.1f}%)"

if sell_probability > 66:
    comments[1][2.75] = f"🔴 Сильный отскок вниз ({sell_probability:.1f}%)"
elif sell_probability > 33:
    comments[1][2.75] = f"🟠 Средний отскок вниз ({sell_probability:.1f}%)"
elif sell_probability > 0:
    comments[1][2.75] = f"⚪️ Слабый отскок вниз ({sell_probability:.1f}%)"

# Авторизация
tr.set_credentials(API_KEY, API_SECRET, IS_TESTNET)
notifier.set_credentials("TOKIN", "ID")

balance = tr.check_futures_balance()
comments[1][0] = f"💰 Баланс: {balance}"

# Позиция
position_info = tr.get_open_position(SYMBOL)
has_open = tr.has_open_position(SYMBOL)

if position_info:
    amt = position_info["amount"]
    direction = "LONG" if amt > 0 else "SHORT"
    comments[1][1.55] = f"{'🟢' if amt > 0 else '🔴'} Позиция: {direction} | 📍 Вход: {position_info['entry_price']} | 📈 Текущая: {position_info['mark_price']} | 💵 PnL: {position_info['pnl']}"
else:
    comments[1][1.57] = "📭 Позиция не найдена"

# SL и TP
atr = df["atr"].iloc[-1]
price = df["close"].iloc[-1]
SL_PCT = (ATR_MULT_SL * atr) / price
TP_PCT = (ATR_MULT_TP * atr) / price
sl_price = price - price * SL_PCT
tp_price = price + price * TP_PCT
comments[1][2.2] = f"🔻 : {sl_price:.4f} | 🔺 : {tp_price:.4f}"

# Торговля
if df["entry_buy"].iloc[-1]:
    if tr.last_signal == "SELL":
        close_msg = tr.close_position(SYMBOL, "SELL", QUANTITY)
        notifier.send(close_msg)
        comments[2][3] = close_msg
    if not has_open:
        open_msg = tr.open_position(SYMBOL, "BUY", QUANTITY, SL_PCT, TP_PCT, LEVERAGE)
        notifier.send(open_msg)
        comments[2][3] = open_msg

elif df["entry_sell"].iloc[-1]:
    if tr.last_signal == "BUY":
        close_msg = tr.close_position(SYMBOL, "BUY", QUANTITY)
        notifier.send(close_msg)
        comments[2][3] = close_msg
    if not has_open:
        open_msg = tr.open_position(SYMBOL, "SELL", QUANTITY, SL_PCT, TP_PCT, LEVERAGE)
        notifier.send(open_msg)
        comments[2][3] = open_msg
else:
    comments[1][2.5] = "⏳ Пока нет сигнала — наблюдаем рынок..."

# Очистка
tr.cleanup_after_trailing_stop(SYMBOL)

# График
plot_columns = ["close", "rsi:2", "ema", "buy_prob:2", "sell_prob:2"]
mark_condition = df["entry_buy"] | df["entry_sell"]