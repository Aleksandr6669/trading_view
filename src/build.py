from import_p import *

def build_plot_advanced(df, plot_columns, mark_condition=None, comments=None, fig=None,):
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

    
    

    if "resistance_levels" in df.columns and "support_levels" in df.columns:
        support_levels = df["support_levels"].iloc[0]
        resistance_levels = df["resistance_levels"].iloc[0]

        # Проверяем, что они не пустые
        if isinstance(support_levels, list) and isinstance(resistance_levels, list):

            for level in support_levels:
                fig.add_trace(go.Scatter(
                    x=[df["timestamp"].iloc[0], df["timestamp"].iloc[-1]],
                    y=[level, level],
                    mode="lines",
                    name=f"Support {level}",
                    line=dict(color="green", dash="dot")
                ), row=1, col=1)

            for level in resistance_levels:
                fig.add_trace(go.Scatter(
                    x=[df["timestamp"].iloc[0], df["timestamp"].iloc[-1]],
                    y=[level, level],
                    mode="lines",
                    name=f"Resistance {level}",
                    line=dict(color="red", dash="dot")
                ), row=1, col=1)
        else:
            print("❗ Уровни поддержки или сопротивления ещё не заданы.")


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
    
    if comments:
        for panel, comment in comments.items():

            
            y_base = 0.98  # Начальная Y-позиция в панели
            if isinstance(comment, dict):  # если это вложенный словарь
                for subpanel, subtext in comment.items():
                    line_height = panel*subpanel*0.05  # расстояние между строками
                    fig.add_annotation(
                        text=subtext,
                        xref="paper",
                        yref=f"y{panel if panel > 1 else ''} domain",
                        x=0.01,
                        y=y_base - subpanel * line_height,
                        showarrow=False,
                        yanchor="top",
                        align="left",
                        font=dict(size=12),
                        bgcolor="rgba(255,255,255,0.85)",
                        bordercolor="black",
                        borderwidth=1,
                       
                    )
            else:
                fig.add_annotation(
                    text=comment,
                    xref="paper",
                    yref=f"y{panel if panel > 1 else ''} domain",
                    x=0.01,
                    y=y_base,
                    showarrow=False,
                    yanchor="top",
                    align="left",
                    font=dict(size=12),
                    bgcolor="rgba(255,255,255,0.85)",
                    bordercolor="black",
                    borderwidth=1,
                )
    timestamps = df["timestamp"]
    if len(timestamps) > 3:
        step = timestamps.iloc[-1] - timestamps.iloc[-2]
        offset = step * 3
    else:
        offset = pd.Timedelta(minutes=15)

    fig.update_layout(
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