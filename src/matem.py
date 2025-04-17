import numpy as np
from scipy.signal import argrelextrema

class SupportResistanceDetector:
    def __init__(self):
        self.df = None
        self.order = None
        self.round_to = None
        self.support_levels = []
        self.resistance_levels = []
        self.min_idx = []
        self.max_idx = []

    def set_data(self, df):
        self.df = df

        for col in ["support_levels", "resistance_levels"]:
            if col not in df.columns:
                df[col] = None

    def set_params(self, order, round_to):
        self.order = order
        self.round_to = round_to

    def detect_levels(self):
        if self.df is None:
            raise ValueError("❌ Данные не установлены. Используй set_data(df)")
        if self.order is None or self.round_to is None:
            raise ValueError("❌ Параметры не заданы. Используй set_params(order, round_to)")

        close_values = self.df["close"].values

        self.min_idx = argrelextrema(close_values, np.less_equal, order=self.order)[0]
        self.max_idx = argrelextrema(close_values, np.greater_equal, order=self.order)[0]

        self.support_levels = (
            self.df["close"].iloc[self.min_idx].round(self.round_to).unique().tolist()
        )
        self.resistance_levels = (
            self.df["close"].iloc[self.max_idx].round(self.round_to).unique().tolist()
        )


        return self.support_levels, self.resistance_levels, self.min_idx, self.max_idx
