import flet as ft
from import_p import *
from build import *

comments = defaultdict(dict)

tr = BinanceTrader()
notifier = TelegramNotifier()
detector = SupportResistanceDetector()

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
    return ""

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

def main(page: ft.Page):
    page.title = "Trading Strategy Viewer"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window_width = 610
    page.window_height = 460

    client = Client()
    all_spot = sorted([s["symbol"] for s in client.get_exchange_info()["symbols"] if s["status"] == "TRADING"])
    all_futures = sorted([s["symbol"] for s in client.futures_exchange_info()["symbols"] if s["contractType"] == "PERPETUAL"])

    bot_running = False
    bot_thread = None
    orders_enabled = False
    settings = load_settings()

    

    font_style = ft.TextStyle(size=10)

    symbol = ft.Dropdown(
        label="Пара", width=120, value=settings["symbol"], options=[],
        text_style=font_style
    )

    search_input = ft.TextField(
        label="🔍 Поиск", width=120,
        text_style=font_style
    )

    interval = ft.Dropdown(
        label="TF", width=90, value=settings["interval"],
        options=[ft.dropdown.Option(i) for i in [
            "1s", "1m", "3m", "5m", "15m", "30m",
            "1h", "2h", "4h", "6h", "8h", "12h",
            "1d", "3d", "1w", "1M"
        ]],
        text_style=font_style
    )

    market = ft.Dropdown(
        label="Тип", width=100, value=settings["market_type"],
        options=[ft.dropdown.Option("spot"), ft.dropdown.Option("futures")],
        text_style=font_style
    )

    limit = ft.TextField(
        label="Свечей", value=str(settings["limit"]),
        width=90, text_style=font_style
    )

    refresh = ft.TextField(
        label="⏱ (сек)", value=str(settings["refresh_interval"]),
        width=80, text_style=font_style
    )

    status_text = ft.Text(value="", size=12, color=ft.colors.BLUE_GREY_600)
    status_text.value = "⛔ Ордера выключены"
    
    def toggle_orders(e):
        nonlocal orders_enabled
        orders_enabled = not orders_enabled
        tr.set_orders_enabled(orders_enabled)
        btn_toggle_orders.text = "Стоп ордера" if orders_enabled else "Старт ордера"
        status_text.value = "🟢 Ордера активны" if orders_enabled else "⛔ Ордера выключены"
        page.update()

    btn_toggle_orders = ft.ElevatedButton("Старт ордера", on_click=toggle_orders)

    def refresh_pairs(e=None):
        current_list = all_futures if market.value == "futures" else all_spot
        query = search_input.value.upper()
        filtered = [s for s in current_list if query in s]
        symbol.options = [ft.dropdown.Option(s) for s in filtered]
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

    code = ft.TextField(multiline=True, min_lines=30, expand=True, width=400,
                        text_style=ft.TextStyle(font_family="Courier New", size=12),
                        value=load_strategy())
    code.on_change = lambda e: save_strategy(code.value)

    chart = PlotlyChart(original_size=400,expand=True)
    log = ft.Text()

    loading_bar = ft.ProgressBar(width=400)
    loading_text = ft.Text("📊 Идёт загрузка графика...", size=14)
    output_column = ft.Column(
        [loading_bar, loading_text],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        scroll=ft.ScrollMode.AUTO,
        expand=True
    )
    chart_container = ft.Container(output_column, expand=2, padding=10)


    def run_bot():
        nonlocal bot_running
        while bot_running:
            try:
                df = load_klines(symbol.value, interval.value, int(limit.value), market.value)
                fig = make_subplots(
                    rows=2, cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.05,
                    row_heights=[0.7, 0.3]
                )
                detector.set_data(df)

                local_vars = {
                        "df": df.copy(),
                        "ta": ta,
                        "pd": pd,
                        "go": go,
                        "make_subplots": make_subplots,
                        "log":log,
                        "extra_traces": [],
                        "fig": fig,
                        "detector": detector,
                        "requests": requests,
                        "plot_columns": [],
                        "mark_condition": None,
                        "comments": {},
                        "tr": tr,
                        "notifier": notifier,
                        "SYMBOL": symbol.value
                    }
                try:
                    exec(code.value, {}, local_vars)

                    fig = build_plot_advanced(local_vars["df"], local_vars["plot_columns"], local_vars["mark_condition"], local_vars["comments"], local_vars["fig"])
                    for item in local_vars["extra_traces"]:
                        fig.add_trace(item["trace"], row=item["row"], col=item["col"])

                    chart.figure = fig
                    output_column.controls.clear()
                    output_column.controls.append(chart)
                    output_column.controls.append(log)

                    log.value = f"Обновлено: {time.strftime('%H:%M:%S')}"
                    page.update()

                    time.sleep(int(refresh.value))

                except Exception as e:
                    error_text = traceback.format_exc()
                    log.value = f"🚨 Ошибка в стратегии:\n{error_text}"
                    print(log.value)
                    page.update()
            except Exception as ex:
                log.value = f"Ошибка: {str(ex)}"
                page.update()
            time.sleep(1)

    def start_bot(e=None):
        nonlocal bot_running, bot_thread
        if not bot_running:
            bot_running = True
            bot_thread = threading.Thread(target=run_bot)
            bot_thread.start()
            page.update()

    def stop_bot(e):
        nonlocal bot_running
        bot_running = False
        page.update()

    page.add(
        ft.Row([
            search_input, symbol, interval, market, limit, refresh,
            btn_toggle_orders,
            status_text
        ])
    )

    page.add(
        ft.Row([
            ft.Container(ft.Column([code], scroll=ft.ScrollMode.AUTO), expand=True, padding=10),
            chart_container
        ], expand=True)
    )

    start_bot()

ft.app(target=main)
