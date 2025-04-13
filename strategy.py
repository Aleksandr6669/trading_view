# RSI + EMA + MACD стратегия
df["rsi"] = ta.rsi(df["close"], length=14)
df["ema"] = ta.ema(df["close"], length=21)
df["macd"] = ta.macd(df["close"]).iloc[:, 0]

df["entry"] = (df["rsi"] < 35) & (df["close"] > df["ema"]) & (df["macd"] > 0)

df["signal"] = None
df.loc[(df["rsi"] < 30) & (df["macd"] > 0), "signal"] = "BUY"
df.loc[(df["rsi"] > 60) & (df["macd"] < 0), "signal"] = "SELL"


plot_columns = ["ema", "rsi:2", "macd:3"]
mark_condition = df["entry"]