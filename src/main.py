import flet as ft
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from binance.client import Client
import tempfile
import threading
import time
import requests

client = Client()
bot_thread = None
bot_running = False


def load_klines(symbol="BTCUSDT", interval="1h", limit=200):
    klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(klines, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "number_of_trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
    return df


def build_plot(df, plot_columns, mark_condition=None):
    fig = go.Figure()

    for col in plot_columns:
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=df["timestamp"],
                y=df[col],
                mode="lines",
                name=col
            ))

    if mark_condition is not None:
        marked = df[mark_condition]
        fig.add_trace(go.Scatter(
            x=marked["timestamp"],
            y=marked["close"],
            mode="markers",
            name="Signal",
            marker=dict(color="green", size=10, symbol="arrow-up")
        ))

    fig.update_layout(title="График с пользовательской стратегией", xaxis_rangeslider_visible=False)
    return fig


def main(page: ft.Page):
    page.title = "Торговый бот (браузер + фон)"
    page.scroll = ft.ScrollMode.ALWAYS

    # UI
    symbol_input = ft.TextField(label="Монета", value="BTCUSDT", width=150)
    interval_input = ft.TextField(label="Таймфрейм", value="1h", width=100)
    limit_input = ft.TextField(label="Свечей", value="200", width=100)
    status_text = ft.Text(value="Бот остановлен")

    code_input = ft.TextField(
        label="Python код стратегии",
        multiline=True,
        min_lines=12,
        max_lines=30,
        expand=True,
        value="""# Пример стратегии:
df["rsi"] = ta.rsi(df["close"], length=14)
df["ema"] = ta.ema(df["close"], length=20)
df["entry"] = (df["rsi"] < 30) & (df["close"] > df["ema"])

plot_columns = ["close", "rsi", "ema"]
mark_condition = df["entry"]

# Пример сигнала:
if df['entry'].iloc[-1]:
    requests.post("https://webhook.site/your-url", json={
        "symbol": "BTCUSDT",
        "signal": "BUY",
        "price": float(df['close'].iloc[-1])
    })
"""
    )

    graph_img = ft.Image()
    log_output = ft.Text()

    def run_bot():
        global bot_running
        while bot_running:
            try:
                df = load_klines(
                    symbol_input.value,
                    interval_input.value,
                    int(limit_input.value)
                )

                local_vars = {
                    "df": df.copy(),
                    "ta": ta,
                    "pd": pd,
                    "requests": requests,
                    "plot_columns": [],
                    "mark_condition": None
                }

                exec(code_input.value, {}, local_vars)

                df_result = local_vars["df"]
                plot_columns = local_vars.get("plot_columns", [])
                mark_condition = local_vars.get("mark_condition", None)

                fig = build_plot(df_result, plot_columns, mark_condition)

                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
                    fig.write_image(tmpfile.name, format="png", width=1000, height=600)
                    graph_img.src = tmpfile.name
                    page.update()

                log_output.value = f"Выполнено успешно: {time.strftime('%H:%M:%S')}"
                page.update()

            except Exception as ex:
                log_output.value = f"Ошибка: {str(ex)}"
                page.update()

            time.sleep(60)

    def start_bot(e):
        global bot_thread, bot_running
        if not bot_running:
            bot_running = True
            bot_thread = threading.Thread(target=run_bot)
            bot_thread.start()
            status_text.value = "Бот запущен!"
            page.update()

    def stop_bot(e):
        global bot_running
        bot_running = False
        status_text.value = "Бот остановлен"
        page.update()

    page.add(
        ft.Row([
            symbol_input, interval_input, limit_input,
            ft.ElevatedButton("Старт", on_click=start_bot),
            ft.ElevatedButton("Стоп", on_click=stop_bot),
            status_text
        ]),
        code_input,
        graph_img,
        log_output
    )

ft.app(target=main)
