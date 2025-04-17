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
from trader import BinanceTrader
from teleg_tr import TelegramNotifier
from matem import SupportResistanceDetector
from collections import defaultdict
from scipy.signal import argrelextrema
import numpy as np
from itertools import chain
import traceback
from strategy_profit_calculator import calculate_strategy_profit