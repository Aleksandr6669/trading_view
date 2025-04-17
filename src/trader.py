from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException, BinanceOrderException
import pandas_ta as ta
from decimal import Decimal, ROUND_DOWN
from math import floor

class BinanceTrader:
    def __init__(self, api_key=None, api_secret=None, is_testnet=True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.is_testnet = is_testnet
        self.client = None
        self.last_signal = None  # ⏳ Последний сигнал
        self.last_entry_price = None  # 💵 Цена входа
        self.symbol_precisions = {}
        self.orders_enabled = False
        self.default_leverage = None  # 💾 Сохраняем переданное плечо
        if api_key and api_secret:
            self.init_client()

    def set_credentials(self, api_key, api_secret, is_testnet=False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.is_testnet = is_testnet
        self.init_client()

    def init_client(self):
        self.client = Client(self.api_key, self.api_secret, testnet=self.is_testnet)
        self.fetch_precisions()

    def set_orders_enabled(self, enabled: bool):
        self.orders_enabled = enabled


    def fetch_precisions(self):
        info = self.client.futures_exchange_info()
        for symbol_info in info["symbols"]:
            symbol = symbol_info["symbol"]
            price_step = float(next(f["tickSize"] for f in symbol_info["filters"] if f["filterType"] == "PRICE_FILTER"))
            qty_step = float(next(f["stepSize"] for f in symbol_info["filters"] if f["filterType"] == "LOT_SIZE"))
            self.symbol_precisions[symbol] = {
                "price_step": price_step,
                "qty_step": qty_step
            }

    def round_to_step(self, value, step):
        step_dec = Decimal(str(step))
        value_dec = Decimal(str(value))
        return float(value_dec.quantize(step_dec, rounding=ROUND_DOWN))

    def round_price(self, symbol, value):
        if symbol not in self.symbol_precisions:
            raise ValueError(f"❌ Тикер {symbol} не найден в symbol_precisions")
        step = self.symbol_precisions[symbol]["price_step"]
        return self.round_to_step(value, step)

    def round_qty(self, symbol, value):
        if symbol not in self.symbol_precisions:
            raise ValueError(f"❌ Тикер {symbol} не найден в symbol_precisions")
        step = self.symbol_precisions[symbol]["qty_step"]
        return self.round_to_step(value, step)

    def check_futures_balance(self):
        try:
            account_info = self.client.futures_account()
            for asset in account_info["assets"]:
                if asset["asset"] == "USDT":
                    balance = asset['walletBalance']
                    return float(balance)
            msg = "⚠️ USDT не найден в фьючерсном аккаунте."
            print(msg)
            return 0
        except Exception as e:
            msg = f"[⚠️ Ошибка при получении баланса]: {str(e)}"
            print(msg)
            return 0

    def set_leverage(self, symbol, leverage):
        try:
            result = self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
            msg = f"📐 Плечо установлено: {result['leverage']}x для {symbol}"
            print(msg)
            return msg
        except Exception as e:
            msg = f"[⚠️ Ошибка установки плеча]: {str(e)}"
            print(msg)
            return msg

    def has_open_position(self, symbol):
        try:
            positions = self.client.futures_position_information(symbol=symbol)
            for pos in positions:
                if pos['positionSide'] == 'BOTH':
                    amt = float(pos['positionAmt'])
                    if amt != 0:
                        return True
            self.last_signal = None
            self.last_entry_price = None
            return False
        except Exception as e:
            print(f"[⚠️ Ошибка проверки позиции]: {str(e)}")
            return False

    def get_open_position(self, symbol):
        try:
            positions = self.client.futures_position_information(symbol=symbol)
            open_orders = self.client.futures_get_open_orders(symbol=symbol)

            sl_order = None
            tp_order = None

            for order in open_orders:
                if order.get("reduceOnly") and order["type"] in ["STOP", "STOP_MARKET"]:
                    sl_order = order
                elif order.get("reduceOnly") and order["type"] in ["TAKE_PROFIT", "TAKE_PROFIT_MARKET"]:
                    tp_order = order

            for pos in positions:
                if pos['positionSide'] == 'BOTH':
                    amt = float(pos.get('positionAmt', 0))
                    if amt != 0:
                        entry_price = float(pos.get('entryPrice', 0))
                        leverage = float(pos.get('leverage', 0))
                        if leverage == 0.0:
                            leverage = self.default_leverage

                        unrealized_pnl = float(pos.get('unRealizedProfit', 0))
                        margin = float(pos.get('positionMargin', 0))
                        mark_price = float(pos.get('markPrice', 0))

                        # 🛡 Защита: если ордера нет, не упадём
                        sl_price = float(sl_order.get("stopPrice", 0)) if sl_order else None
                        tp_price = float(tp_order.get("stopPrice", 0)) if tp_order else None

                        return {
                            "amount": amt,
                            "entry_price": entry_price,
                            "leverage": leverage,
                            "pnl": unrealized_pnl,
                            "margin": margin,
                            "mark_price": mark_price,
                            "sl": sl_price,
                            "tp": tp_price
                        }
            return None
        except Exception as e:
            return None


    def open_position(self, symbol, side, quantity, sl_pct, tp_pct, leverage):
        if not self.orders_enabled:
            print("🛑 Ордера отключены — открытие отменено.")
            return "🛑 Ордера отключены — открытие отменено."
        self.cleanup_after_trailing_stop(symbol)
        try:
            if self.last_signal == side:
                msg = f"⏳ Сигнал {side} уже был обработан. Ждём нового."
                print(msg)
                return msg

            self.last_signal = side
            self.set_leverage(symbol, leverage)

            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            current_price = float(ticker["price"])
            print(f"📍 Текущая цена: {current_price}")

            # Расчёт SL и TP до округления
            sl_raw = current_price * (1 - sl_pct) if side == "BUY" else current_price * (1 + sl_pct)
            tp_raw = current_price * (1 + tp_pct) if side == "BUY" else current_price * (1 - tp_pct)

            # Округление всех значений
            sl = self.round_price(symbol, sl_raw)
            tp = self.round_price(symbol, tp_raw)
            quantity = self.round_qty(symbol, quantity)

            notional = current_price * quantity
            if quantity <= 0:
                msg = f"[❌ Ошибка]: Расчётное количество меньше или равно нулю. QTY={quantity}"
                print(msg)
                return msg
            if notional < 5:
                msg = f"[❌ Ошибка]: Notional ({notional:.4f}) меньше 5 USDT. QTY={quantity}, Цена={current_price}"
                print(msg)
                return msg

            print(f"🔄 SL: {sl:.4f} | TP: {tp:.4f} | Qty: {quantity} | Notional: {notional:.4f}")

            

            # Противоположная сторона
            opposite_side = SIDE_SELL if side == "BUY" else SIDE_BUY

            # Округлённые значения лимит-цен
            sl_limit_price = self.round_price(symbol, sl * 0.998 if side == "BUY" else sl * 1.002)
            tp_limit_price = self.round_price(symbol, tp * 1.002 if side == "BUY" else tp * 0.998)

            # Ещё раз строго округляем stopPrice
            stop_price_sl = self.round_price(symbol, sl)
            stop_price_tp = self.round_price(symbol, tp)

            # Stop Loss
            self.client.futures_create_order(
                symbol=symbol,
                side=opposite_side,
                type=FUTURE_ORDER_TYPE_STOP,
                stopPrice=stop_price_sl,
                price=sl_limit_price,
                quantity=quantity,
                reduceOnly=True,
                timeInForce=TIME_IN_FORCE_GTC,
                workingType="CONTRACT_PRICE",
                priceProtect=True
            )
            print(f"🛑 Stop Loss LIMIT: стоп={stop_price_sl} → лимит={sl_limit_price}")

            # Take Profit
            self.client.futures_create_order(
                symbol=symbol,
                side=opposite_side,
                type=FUTURE_ORDER_TYPE_TAKE_PROFIT,
                stopPrice=stop_price_tp,
                price=tp_limit_price,
                quantity=quantity,
                reduceOnly=True,
                timeInForce=TIME_IN_FORCE_GTC,
                workingType="CONTRACT_PRICE",
                priceProtect=True
            )
            print(f"🎯 Take Profit LIMIT: стоп={stop_price_tp} → лимит={tp_limit_price}")

            # Открытие рыночной позиции
            order = self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_BUY if side == "BUY" else SIDE_SELL,
                type=FUTURE_ORDER_TYPE_MARKET,
                quantity=quantity,
            )
            print(f"✅ Позиция открыта: {order['orderId']}")


            # Получаем цену входа
            position_info = self.client.futures_position_information(symbol=symbol)
            entry_price = float(next(p for p in position_info if p["positionSide"] == "BOTH")['entryPrice'])
            self.last_entry_price = entry_price
            self.default_leverage = leverage
            print(f"📊 Цена входа: {entry_price}")

            return f"✅ Открыта позиция на {side} по {symbol}, SL={stop_price_sl}, TP={stop_price_tp}"

        except BinanceAPIException as e:
            msg = f"[❌ Binance API ошибка]: {e.message}"
            print(msg)
            self.cleanup_after_trailing_stop(symbol)
            return msg
        except BinanceOrderException as e:
            msg = f"[❌ Ошибка ордера]: {e.message}"
            print(msg)
            self.cleanup_after_trailing_stop(symbol)
            return msg
        except Exception as e:
            msg = f"[⚠️ Неизвестная ошибка]: {str(e)}"
            print(msg)
            return msg


    def close_position(self, symbol, side, quantity):
        if not self.orders_enabled:
            print("🛑 Ордера отключены — открытие отменено.")
            return "🛑 Ордера отключены — открытие отменено."
        try:
            quantity = self.round_qty(symbol, quantity)
            if quantity <= 0:
                return f"[❌ Ошибка]: Некорректное количество для закрытия: {quantity}"

            open_orders = self.client.futures_get_open_orders(symbol=symbol)
            for order in open_orders:
                self.client.futures_cancel_order(symbol=symbol, orderId=order["orderId"])
            print("🚫 Все отложенные ордера отменены.")

            close_side = SIDE_SELL if side == "BUY" else SIDE_BUY

            order = self.client.futures_create_order(
                symbol=symbol,
                side=close_side,
                type=FUTURE_ORDER_TYPE_MARKET,
                quantity=quantity,
                reduceOnly=True
            )

            pnl = None
            if self.last_entry_price:
                fills = order.get("fills", [])
                if fills:
                    exit_price = float(fills[0]["price"])
                else:
                    exit_price = float(order.get("avgFillPrice", 0))
                entry_price = self.last_entry_price
                if side == "BUY":
                    pnl = (exit_price - entry_price) * quantity
                else:
                    pnl = (entry_price - exit_price) * quantity

            self.last_signal = None
            self.last_entry_price = None

            msg = f"❎ Позиция закрыта: {quantity} {symbol} ({close_side})"
            self.cleanup_after_trailing_stop(symbol)
            if pnl is not None:
                msg += f" | 💸 Прибыль: {pnl:.2f} USDT"
            print(msg)
            return msg

        except BinanceAPIException as e:
            msg = f"[❌ Binance API ошибка при закрытии]: {e.message}"
            print(msg)
            return msg
        except BinanceOrderException as e:
            msg = f"[❌ Ошибка ордера при закрытии]: {e.message}"
            print(msg)
            return msg
        except Exception as e:
            msg = f"[⚠️ Неизвестная ошибка при закрытии позиции]: {str(e)}"
            print(msg)
            return msg

    def cleanup_after_trailing_stop(self, symbol):
        try:
            if not self.has_open_position(symbol):
                open_orders = self.client.futures_get_open_orders(symbol=symbol)
                if open_orders:
                    for order in open_orders:
                        self.client.futures_cancel_order(symbol=symbol, orderId=order["orderId"])
                    print("🧹 Удалены оставшиеся отложенные ордера.")
                self.last_signal = None
                self.last_entry_price = None
                return "🧼 Чистка завершена после выхода."
        except Exception as e:
            return f"[⚠️ Ошибка при авто-чистке]: {str(e)}"
        return "🧼 Чистка не требуется, позиция ещё открыта."
