
def calculate_strategy_profit(df, initial_balance=1000, qty_fraction=0.5, leverage=10, start_date=None, end_date=None, visualize=False):
    """
    Подсчёт прибыли стратегии на выбранном отрезке времени.

    :param df: DataFrame с колонками ['timestamp', 'close', 'signal']
    :param initial_balance: Начальный депозит
    :param qty_fraction: Процент от баланса на одну сделку
    :param leverage: Плечо
    :param start_date: Начало периода (datetime или строка)
    :param end_date: Конец периода (datetime или строка)
    :param visualize: Показать график с входами/выходами
    :return: словарь с результатами
    """
    import pandas as pd
    import plotly.graph_objects as go

    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")

    if start_date:
        df = df[df["timestamp"] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df["timestamp"] <= pd.to_datetime(end_date)]

    balance = initial_balance
    position = None
    entry_price = 0
    trade_log = []
    trade_points = []

    for i, row in df.iterrows():
        signal = row.get("signal")
        price = row["close"]
        timestamp = row["timestamp"]

        if signal == "BUY" and not position:
            qty = (balance * qty_fraction * leverage) / price
            entry_price = price
            position = ("LONG", qty)
            trade_points.append(("BUY", timestamp, price))

        elif signal == "SELL" and not position:
            qty = (balance * qty_fraction * leverage) / price
            entry_price = price
            position = ("SHORT", qty)
            trade_points.append(("SELL", timestamp, price))

        elif position:
            direction, qty = position
            if signal == "SELL" and direction == "LONG":
                profit = (price - entry_price) * qty
                balance += profit
                trade_log.append(profit)
                position = None
                trade_points.append(("CLOSE_LONG", timestamp, price))
            elif signal == "BUY" and direction == "SHORT":
                profit = (entry_price - price) * qty
                balance += profit
                trade_log.append(profit)
                position = None
                trade_points.append(("CLOSE_SHORT", timestamp, price))

    results = {
        "Начальный баланс": initial_balance,
        "Финальный баланс": balance,
        "Сделок": len(trade_log),
        "Прибыль": balance - initial_balance,
        "Прибыль %": (balance - initial_balance) / initial_balance * 100
    }

    if visualize:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df["close"], mode="lines", name="Цена"))

        for tp in trade_points:
            action, time, price = tp
            color = "green" if "BUY" in action else "red"
            symbol = "triangle-up" if "BUY" in action else "triangle-down"
            fig.add_trace(go.Scatter(
                x=[time], y=[price],
                mode="markers+text",
                marker=dict(color=color, size=10, symbol=symbol),
                name=action,
                text=[action],
                textposition="top center"
            ))

        fig.update_layout(title="Backtest сделки", height=600)
        fig.show()

    return results
