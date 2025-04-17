
# 📘 Как создать стратегию с входом в сделку, уведомлением и визуализацией

Этот шаблон поможет тебе — или любому другому разработчику — создать полноценную торговую стратегию в твоей системе. Всё описано пошагово, с пояснениями.

---

## 🔧 1. Базовые настройки

```python
comments = {1: {}, 2: {}}

API_KEY = "твой_api_key"
API_SECRET = "твой_api_secret"
TOKIN = "токен_твоего_бота"
ID = "твой_telegram_id"
IS_TESTNET = False

QUANTITY = 0.2
LEVERAGE = 20
ATR_MULT_SL = 0.2
ATR_MULT_TP = 1.2
SYMBOL = "BTCUSDT"
```

---

## 📈 2. Индикаторы

```python
df["rsi"] = ta.rsi(df["close"], length=14)
df["ema"] = ta.ema(df["close"], length=20)
df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)
```

---

## 🕯️ 3. Свечные модели

```python
df["bullish_engulfing"] = (df["close"] > df["open"].shift(1)) & (df["open"] < df["close"].shift(1))
df["bearish_engulfing"] = (df["close"] < df["open"].shift(1)) & (df["open"] > df["close"].shift(1))
```

---

## 🏛️ 4. Уровни и отскок

```python
detector.set_params(order=10, round_to=2)
support, resistance, _, _ = detector.detect_levels()

# Отскоки (по 3 свечи на подтверждение)
bounce_support_flags = []
bounce_resistance_flags = []

for i in range(len(df)):
    price = df["close"].iloc[i]
    confirmed_support = False
    confirmed_resistance = False

    for lvl in support:
        if abs(price - lvl) / lvl < 0.001:
            for j in range(1, 4):
                if i + j >= len(df):
                    break
                if (df["close"].iloc[i + j] - lvl) / lvl > 0.001:
                    confirmed_support = True
                    break
    for lvl in resistance:
        if abs(price - lvl) / lvl < 0.001:
            for j in range(1, 4):
                if i + j >= len(df):
                    break
                if (lvl - df["close"].iloc[i + j]) / lvl > 0.001:
                    confirmed_resistance = True
                    break

    bounce_support_flags.append(confirmed_support)
    bounce_resistance_flags.append(confirmed_resistance)

df["bounce_support"] = bounce_support_flags
df["bounce_resistance"] = bounce_resistance_flags
```

---

## 🚪 5. Условия входа в сделку

```python
rsi_buy = 30
rsi_sell = 70

df["entry_buy"] = df["bounce_support"] & (df["rsi"] > rsi_buy) & (df["close"] > df["ema"])
df["entry_sell"] = df["bounce_resistance"] & (df["rsi"] < rsi_sell) & (df["close"] < df["ema"])

df["signal"] = None
df.loc[df["entry_buy"], "signal"] = "BUY"
df.loc[df["entry_sell"], "signal"] = "SELL"
```

---

## 🎯 6. Расчёт SL/TP

```python
atr = df["atr"].iloc[-1]
price = df["close"].iloc[-1]

SL_PCT = (ATR_MULT_SL * atr) / price
TP_PCT = (ATR_MULT_TP * atr) / price

sl_price = price - price * SL_PCT
tp_price = price + price * TP_PCT
```

---

## 📬 7. Telegram и трейдинг

```python
tr.set_credentials(API_KEY, API_SECRET, IS_TESTNET)
notifier.set_credentials(TOKIN, ID)

balance = tr.check_futures_balance()
comments[1][0] = f"Баланс: {balance}"

position_info = tr.get_open_position(SYMBOL)
has_open = tr.has_open_position(SYMBOL)

# Визуализация позиции
if position_info:
    amt = position_info["amount"]
    direction = "LONG" if amt > 0 else "SHORT"
    comments[1][1.55] = f"Позиция: {direction} | Вход: {position_info['entry_price']} | Текущая: {position_info['mark_price']} | PnL: {position_info['pnl']}"
else:
    comments[1][1.57] = "Позиция не найдена"
```

---

## 🟢 8. Торговая логика + уведомления

```python
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
    comments[1][2.5] = "Пока нет сигнала — наблюдаем рынок..."
```

---

## 📉 9. График

```python
plot_columns = ["close", "rsi:2", "ema", "buy_prob:2", "sell_prob:2"]
mark_condition = df["entry_buy"] | df["entry_sell"]
```

---

## 🧼 10. Очистка

```python
tr.cleanup_after_trailing_stop(SYMBOL)
```
