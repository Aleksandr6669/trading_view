import flet as ft
from flet.plotly_chart import PlotlyChart
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from binance.client import Client
import threading
import time
import requests
import re
import os
import json

STRATEGY_PATH = "strategy.py"
SETTINGS_PATH = "settings.json"

default_settings = {
    "symbol": "BTCUSDT",
    "interval": "15m",
    "market_type": "spot",
    "limit": 200,
    "refresh_interval": 10
}

def save_settings(settings):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f)

def load_settings():
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return default_settings.copy()

def save_strategy(code):
    with open(STRATEGY_PATH, "w", encoding="utf-8") as f:
        f.write(code)

def load_strategy():
    if os.path.exists(STRATEGY_PATH):
        with open(STRATEGY_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return '''# Пример стратегии:
df["rsi"] = ta.rsi(df["close"], length=14)
df["ema"] = ta.ema(df["close"], length=20)
df["entry"] = (df["rsi"] < 30) & (df["close"] > df["ema"])
df["signal"] = None
df.loc[df["rsi"] < 30, "signal"] = "BUY"
df.loc[df["rsi"] > 70, "signal"] = "SELL"
plot_columns = ["close", "rsi:2", "ema"]
mark_condition = df["entry"]
'''

def load_klines(symbol, interval, limit, market_type):
    client = Client()
    if market_type == "futures":
        klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
    else:
        klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(klines, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "number_of_trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
    return df

def build_plot_advanced(df, plot_columns, mark_condition=None):
    panel_map = {}
    for col in plot_columns:
        match = re.match(r"@?([\w_]+)(?::(\d+))?", col.strip())
        if match:
            name = match.group(1)
            panel = int(match.group(2)) if match.group(2) else 1
            if name in df.columns:
                panel_map.setdefault(panel, []).append(name)

    panel_ids = sorted(panel_map.keys())
    n_panels = max(2, max(panel_ids)) if panel_ids else 2

    fig = make_subplots(
        rows=n_panels, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.6] + [0.4 / (n_panels - 1)] * (n_panels - 1),
        specs=[[{"type": "xy"}] for _ in range(n_panels)]
    )

    fig.add_trace(go.Candlestick(
        x=df["timestamp"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        name="Свечи"
    ), row=1, col=1)

    for panel, columns in panel_map.items():
        for col in columns:
            fig.add_trace(go.Scatter(
                x=df["timestamp"],
                y=df[col],
                mode="lines",
                name=col.upper()
            ), row=panel, col=1)

    # Текущая цена
    last_price = df["close"].iloc[-1]
    fig.add_trace(go.Scatter(
        x=[df["timestamp"].iloc[-1]],
        y=[last_price],
        mode="lines+text",
        name="Цена",
        text=[f"{last_price:.6f}"],
        textposition="top left",
        line=dict(color="red", dash="dot"),
        showlegend=False
    ), row=1, col=1)

    # Точки входа
    if mark_condition is not None and isinstance(mark_condition, pd.Series):
        marked = df[mark_condition]
        fig.add_trace(go.Scatter(
            x=marked["timestamp"],
            y=marked["close"],
            mode="markers",
            name="Entry",
            marker=dict(color="blue", symbol="circle", size=10)
        ), row=1, col=1)

    # Сигналы BUY / SELL
    if "signal" in df.columns:
        buy = df[df["signal"] == "BUY"]
        sell = df[df["signal"] == "SELL"]

        fig.add_trace(go.Scatter(
            x=buy["timestamp"],
            y=buy["close"],
            mode="markers",
            name="BUY",
            marker=dict(color="green", symbol="triangle-up", size=12)
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=sell["timestamp"],
            y=sell["close"],
            mode="markers",
            name="SELL",
            marker=dict(color="red", symbol="triangle-down", size=12)
        ), row=1, col=1)

    timestamps = df["timestamp"]
    if len(timestamps) > 3:
        step = timestamps.iloc[-1] - timestamps.iloc[-2]
        offset = step * 3
    else:
        offset = pd.Timedelta(minutes=15)

    fig.update_layout(
        title="График стратегии",
        height=400 + 250 * n_panels,
        xaxis_rangeslider_visible=False,
        xaxis=dict(
            range=[
                timestamps.iloc[0],
                timestamps.iloc[-1] + offset
            ]
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(tickformat=".6f")
    )

    return fig

def main(page: ft.Page):
    page.title = "Trading Strategy Viewer"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window_width = 1400
    page.window_height = 900

    client = Client()
    all_spot = sorted([s["symbol"] for s in client.get_exchange_info()["symbols"] if s["status"] == "TRADING"])
    all_futures = sorted([s["symbol"] for s in client.futures_exchange_info()["symbols"] if s["contractType"] == "PERPETUAL"])

    bot_running = False
    bot_thread = None
    settings = load_settings()

    symbol = ft.Dropdown(label="Пара", width=180, value=settings["symbol"], options=[])
    search_input = ft.TextField(label="Поиск пары", width=150)

    interval = ft.Dropdown(label="Таймфрейм", width=100, value=settings["interval"],
                           options=[ft.dropdown.Option(i) for i in ["1m", "5m", "15m", "1h"]])
    market = ft.Dropdown(label="Тип", width=100, value=settings["market_type"],
                         options=[ft.dropdown.Option("spot"), ft.dropdown.Option("futures")])
    limit = ft.TextField(label="Свечей", value=str(settings["limit"]), width=100)
    refresh = ft.TextField(label="Обновление (сек)", value=str(settings["refresh_interval"]), width=150)
    status_text = ft.Text(value="")

    def refresh_pairs(e=None):
        current_list = all_futures if market.value == "futures" else all_spot
        query = search_input.value.upper()
        filtered = [s for s in current_list if query in s]
        symbol.options = [ft.dropdown.Option(s) for s in filtered]
        # Не обновляем symbol.value автоматически
        page.update()
        save_ui()

    def save_ui(e=None):
        save_settings({
            "symbol": symbol.value,
            "interval": interval.value,
            "market_type": market.value,
            "limit": int(limit.value),
            "refresh_interval": int(refresh.value)
        })

    for field in [symbol, interval, market, limit, refresh]:
        field.on_change = save_ui

    search_input.on_change = refresh_pairs
    market.on_change = refresh_pairs
    refresh_pairs()

    code = ft.TextField(label="Код стратегии", multiline=True, min_lines=30, expand=True, width=500,
                        text_style=ft.TextStyle(font_family="Courier New", size=12),
                        value=load_strategy())
    code.on_change = lambda e: save_strategy(code.value)

    chart = PlotlyChart(expand=True)
    log = ft.Text()

    def run_bot():
        nonlocal bot_running
        while bot_running:
            try:
                df = load_klines(symbol.value, interval.value, int(limit.value), market.value)
                local_vars = {"df": df.copy(), "ta": ta, "pd": pd, "requests": requests,
                              "plot_columns": [], "mark_condition": None}
                exec(code.value, {}, local_vars)
                fig = build_plot_advanced(local_vars["df"], local_vars["plot_columns"], local_vars["mark_condition"])
                chart.figure = fig
                log.value = f"Обновлено: {time.strftime('%H:%M:%S')}"
                page.update()
            except Exception as ex:
                log.value = f"Ошибка: {str(ex)}"
                page.update()
            time.sleep(int(refresh.value))

    def start_bot(e=None):
        nonlocal bot_running, bot_thread
        if not bot_running:
            bot_running = True
            bot_thread = threading.Thread(target=run_bot)
            bot_thread.start()
            status_text.value = "Бот запущен"
            page.update()

    def stop_bot(e):
        nonlocal bot_running
        bot_running = False
        status_text.value = "Бот остановлен"
        page.update()

    page.add(
        ft.Row([
            search_input, symbol, interval, market, limit, refresh,
            ft.ElevatedButton("Старт", on_click=start_bot),
            ft.ElevatedButton("Стоп", on_click=stop_bot),
            status_text
        ])
    )

    page.add(
        ft.Row([
            ft.Container(ft.Column([code], scroll=ft.ScrollMode.AUTO), expand=1, height=650, padding=10),
            ft.Container(ft.Column([chart, log], scroll=ft.ScrollMode.AUTO), expand=2, height=650, padding=10)
        ], expand=True)
    )

    start_bot()

ft.app(target=main)