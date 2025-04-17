comments[1]={}
comments[2]={}

# 🧠 Настройки
API_KEY = "7u6mrJUC80sCeYMv8zcVXIcGzkuGfF5HsANJUNhnuP8BRZVKgWnZytAqv0plDn4X"
API_SECRET = "rKVkFVGddszfKv9LhBKThOkR6530tmNdaKiD4eRUi1Kbl0J14pV6UrrQXzBbJ9jV"
IS_TESTNET = False
QUANTITY = 0.2
LEVERAGE = 20
ATR_MULT_SL = 0.2
ATR_MULT_TP = 1.2
SYMBOL = SYMBOL

rsi_buy = 40
rsi_sell = 60

BOUNCE_THRESHOLD = 0.001
BOUNCE_CONFIRMATION_RATIO = 0.001

# 📈 Индикаторы
df["rsi"] = ta.rsi(df["close"], length=14)
df["ema"] = ta.ema(df["close"], length=20)
df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)

# 🕯️ Свечные модели
df["bullish_engulfing"] = (df["close"] > df["open"].shift(1)) & (df["open"] < df["close"].shift(1))
df["bearish_engulfing"] = (df["close"] < df["open"].shift(1)) & (df["open"] > df["close"].shift(1))




# 🚪 Условия входа
df["entry_buy"] = (df["rsi"] < rsi_buy) & (df["close"] > df["ema"]) & df["bullish_engulfing"]
df["entry_sell"] = (df["rsi"] > rsi_sell) & (df["close"] < df["ema"]) & df["bearish_engulfing"]

# 🚪 Условия входа простое 
#df["entry_buy"] = (df["rsi"] < rsi_buy) & (df["close"] > df["ema"])
#df["entry_sell"] = (df["rsi"] > rsi_sell) & (df["close"] < df["ema"])


# 🧮 Вероятность входа
df["buy_prob"] = (
    1.0 * (df["rsi"] < rsi_buy).astype(int) +
    1.0 * (df["close"] > df["ema"]).astype(int) +
    1.0 * df["bullish_engulfing"].astype(int)
) / 3 *100

df["sell_prob"] = (
    1.0 * (df["rsi"] > rsi_sell).astype(int) +
    1.0 * (df["close"] < df["ema"]).astype(int) +
    1.0 * df["bearish_engulfing"].astype(int)
) / 3 *100


buy_probability = df["buy_prob"].iloc[-1]
sell_probability = df["sell_prob"].iloc[-1]


if buy_probability > 66:
    comments[2][0]= f"🟢 Сильный бычий сигнал (вероятность входа: {buy_probability:.1f} %)"
elif buy_probability > 33:
    comments[2][0]= f"🟡 Средний бычий сигнал (вероятность входа: {buy_probability:.1f}%)"
elif buy_probability > 0:
    comments[2][0]= f"⚪️ Слабый бычий сигнал (вероятность входа: {buy_probability:.1f}%)"

if sell_probability > 66:
    comments[2][0]= f"🔴 Сильный медвежий сигнал (вероятность входа: {sell_probability:.1f}%)"
elif sell_probability > 33:
    comments[2][0]= f"🟠 Средний медвежий сигнал (вероятность входа: {sell_probability:.1f}%)"
elif sell_probability > 0:
    comments[2][0]= f"⚪️ Слабый медвежий сигнал (вероятность входа: {sell_probability:.1f}%)"

# 🖍️ Метки для графика
df["mark_bullish"] = df["entry_buy"] | df["bullish_engulfing"]
df["mark_bearish"] = df["entry_sell"] | df["bearish_engulfing"]

# Передаём параметры
detector.set_params(order=10, round_to=2)

# Магия уровней
support, resistance, _, _ = detector.detect_levels()

# Создаём колонки если их нет
for col in ["support_levels", "resistance_levels"]:
    if col not in df.columns:
        df[col] = None

# Кладём списки в первую строку
df.at[0, "support_levels"] = support
df.at[0, "resistance_levels"] = resistance

# 💥 Отскоки


bounce_support_flags = []
bounce_resistance_flags = []

for i in range(len(df)):
    price = df["close"].iloc[i]
    confirmed_support = False
    confirmed_resistance = False

    for lvl in support:
        if abs(price - lvl) / lvl < BOUNCE_THRESHOLD:
            # Проверим отскок через 1-2 свечи
            if i + 2 < len(df):
                future_price = df["close"].iloc[i + 2]
                if (future_price - lvl) / lvl > BOUNCE_CONFIRMATION_RATIO:
                    confirmed_support = True
                    break

    for lvl in resistance:
        if abs(price - lvl) / lvl < BOUNCE_THRESHOLD:
            if i + 2 < len(df):
                future_price = df["close"].iloc[i + 2]
                if (lvl - future_price) / lvl > BOUNCE_CONFIRMATION_RATIO:
                    confirmed_resistance = True
                    break

    bounce_support_flags.append(confirmed_support)
    bounce_resistance_flags.append(confirmed_resistance)

df["bounce_support"] = bounce_support_flags
df["bounce_resistance"] = bounce_resistance_flags


# 🚪 Условия входа
df["entry_buy"] = df["bounce_support"] & (df["rsi"] > rsi_buy) & (df["close"] > df["ema"])
df["entry_sell"] = df["bounce_resistance"] & (df["rsi"] < rsi_sell) & (df["close"] < df["ema"])

df["signal"] = None  # по умолчанию пусто
df.loc[df["entry_buy"], "signal"] = "BUY"
df.loc[df["entry_sell"], "signal"] = "SELL"

if not df["entry_buy"].iloc[-1] and df["bounce_support"].iloc[-1]:
    comments[1][3.2] = "⚪️ Есть касание уровня поддержки, но отскок слабый или без подтверждения."

if not df["entry_sell"].iloc[-1] and df["bounce_resistance"].iloc[-1]:
    comments[1][3.2] = "⚪️ Есть касание уровня сопротивления, но отскок слабый или без подтверждения."



# 🧮 Вероятности
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

# 💬 Комментарии
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

# 📊 График
plot_columns = ["close", "rsi:2", "ema", "buy_prob:2", "sell_prob:2",]
mark_condition = df["mark_bullish"] | df["mark_bearish"]




# 🔐 Авторизация
tr.set_credentials(API_KEY, API_SECRET, IS_TESTNET)
notifier.set_credentials("7979456533:AAGneMP9LlIASbHeFKeOoNruMMBd-nmQRnQ", "353095791")

balance = tr.check_futures_balance()
comments[1][0] = f"💰 Баланс USDT: {balance}"

# 📊 Информация по открытой позиции
position_info = tr.get_open_position(SYMBOL)

if position_info:
    # 🧭 Направление позиции
    amt = position_info['amount']
    if amt > 0:
        comments[1][1.55] = "🟢 Позиция: LONG"
    elif amt < 0:
        comments[1][1.55] = "🔴 Позиция: SHORT"
    else:
        comments[1][1.55] = "⚪️ Позиция открыта, но объём 0"

    # 💬 Детали позиции
    comments[1][1.55] += (
        f"📍 Вход: {position_info['entry_price']:.2f} | "
        f"📈 Текущая: {position_info['mark_price']:.2f} | "
        f"💵 PnL: {position_info['pnl']:.2f} USDT"
    )

    # 🎯 SL и TP
    sl = position_info['sl']
    tp = position_info['tp']
    sl_text = f"{sl:.4f}" if sl else "❌"
    tp_text = f"{tp:.4f}" if tp else "❌"
    comments[1][1.9] = f"📊 SL: {sl_text} | TP: {tp_text}"

else:
    comments[1][1.57] = "📭 Позиция не найдена"


# 🔍 Проверка позиции
has_open = tr.has_open_position(SYMBOL)
if has_open:
    comments[1][1.1] = f"📌Позиция открыта"
else:
    comments[1][1.1] = "📌Нет позиции"

# 📉 Расчёт SL и TP с учётом уровней

# 💰 Текущая цена и ATR
atr = df["atr"].iloc[-1]
current_price = df["close"].iloc[-1]

# 🔍 Минимальная дистанция — пусть будет равна atr (или можно умножить, если хочешь)
min_distance = atr

# 🔽 Поиск ближайшей поддержки: ниже цены, не слишком близко, минимальная разница
nearest_support = None
min_support_diff = float("inf")

for lvl in support:
    diff = abs(current_price - lvl)
    if lvl < current_price and diff >= min_distance and diff < min_support_diff:
        nearest_support = lvl
        min_support_diff = diff

# 🔼 Поиск ближайшего сопротивления: выше цены, не слишком близко, минимальная разница
nearest_resistance = None
min_resistance_diff = float("inf")

for lvl in resistance:
    diff = abs(current_price - lvl)
    if lvl > current_price and diff >= min_distance and diff < min_resistance_diff:
        nearest_resistance = lvl
        min_resistance_diff = diff



use_support = len(support) > 1
use_resistance = len(resistance) > 1

# 🧮 Расчёт SL и TP
if df["entry_buy"].iloc[-1] and nearest_support and use_support:
    SL_PCT = (current_price - nearest_support) / current_price
    TP_PCT = (nearest_resistance - current_price) / current_price if nearest_resistance else (ATR_MULT_TP * atr) / current_price

elif df["entry_sell"].iloc[-1] and nearest_resistance and use_resistance:
    SL_PCT = (nearest_resistance - current_price) / current_price
    TP_PCT = (current_price - nearest_support) / current_price if nearest_support else (ATR_MULT_TP * atr) / current_price

else:
    SL_PCT = (ATR_MULT_SL * atr) / current_price
    TP_PCT = (ATR_MULT_TP * atr) / current_price

SL_PCT = (ATR_MULT_SL * atr) / current_price
TP_PCT = (ATR_MULT_TP * atr) / current_price

# 💰 Точные цены стопа и профита
sl_price = current_price - (current_price * SL_PCT)
tp_price = current_price + (current_price * TP_PCT)

comments[1][2.2] = f"🔻 : {sl_price:.4f} | 🔺 : {tp_price:.4f}"

# ✅ Торговая логика — осознанная и честная
if df["entry_buy"].iloc[-1]:
    comments[1][2.5] = "🟢 Сигнал на покупку — бычья возможность!"
elif df["entry_sell"].iloc[-1]:
    comments[1][2.5] = "🔴 Сигнал на продажу — медвежий шанс!"
else:
    comments[1][2.5] = "⏳ Пока нет сигнала — наблюдаем рынок..."



# ✅ Торговая логика
if df["entry_buy"].iloc[-1]:
    if tr.last_signal == "SELL":
        close_msg = tr.close_position(SYMBOL, "SELL", QUANTITY)
        comments[2][3] = close_msg
        notifier.send(close_msg)

    if not has_open:
        open_msg = tr.open_position(SYMBOL, "BUY", QUANTITY, SL_PCT, TP_PCT, LEVERAGE)
        comments[2][3] = open_msg
        notifier.send(open_msg)
      

elif df["entry_sell"].iloc[-1]:
    if tr.last_signal == "BUY":
        close_msg = tr.close_position(SYMBOL, "BUY", QUANTITY)
        comments[2][3] = close_msg
        notifier.send(close_msg)

    if not has_open:
        open_msg = tr.open_position(SYMBOL, "SELL", QUANTITY, SL_PCT, TP_PCT, LEVERAGE)
        comments[2][3] = open_msg
        notifier.send(open_msg)

# 🧹 Очистка после TP/SL
tr.cleanup_after_trailing_stop(SYMBOL)

comments[1][3] = f"💬 Инфо: - RSI: {df['rsi'].iloc[-1]:.4f} - Цена: {df['close'].iloc[-1]:.4f} - EMA: {df['ema'].iloc[-1]:.4f}"