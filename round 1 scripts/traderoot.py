import json
from typing import Any, Optional

from prosperity4bt.datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState

class Logger:
    """Collects compact logs and prints a single compressed payload per tick."""

    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(
            self.to_json(
                [
                    self.compress_state(state, ""),
                    self.compress_orders(orders),
                    conversions,
                    "",
                    "",
                ]
            )
        )

        max_item_length = (self.max_log_length - base_length) // 3

        print(
            self.to_json(
                [
                    self.compress_state(state, self.truncate(state.traderData, max_item_length)),
                    self.compress_orders(orders),
                    conversions,
                    self.truncate(trader_data, max_item_length),
                    self.truncate(self.logs, max_item_length),
                ]
            )
        )

        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp,
            trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]
    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        compressed = []
        for listing in listings.values():
            compressed.append([listing.symbol, listing.product, listing.denomination])
        return compressed
    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        compressed = {}
        for symbol, order_depth in order_depths.items():
            compressed[symbol] = [order_depth.buy_orders, order_depth.sell_orders]
        return compressed
    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        compressed = []
        for arr in trades.values():
            for trade in arr:
                compressed.append(
                    [trade.symbol, trade.price, trade.quantity, trade.buyer, trade.seller, trade.timestamp]
                )
        return compressed
    def compress_observations(self, observations: Observation) -> list[Any]:
        conversion_observations = {}
        for product, observation in observations.conversionObservations.items():
            conversion_observations[product] = [
                observation.bidPrice,
                observation.askPrice,
                observation.transportFees,
                observation.exportTariff,
                observation.importTariff,
                observation.sugarPrice,
                observation.sunlightIndex,
            ]
        return [observations.plainValueObservations, conversion_observations]
    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        compressed = []
        for arr in orders.values():
            for order in arr:
                compressed.append([order.symbol, order.price, order.quantity])
        return compressed
    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))
    def truncate(self, value: str, max_length: int) -> str:
        lo, hi = 0, min(len(value), max_length)
        out = ""

        while lo <= hi:
            mid = (lo + hi) // 2
            candidate = value[:mid]
            if len(candidate) < len(value):
                candidate += "..."
            encoded_candidate = json.dumps(candidate)
            if len(encoded_candidate) <= max_length:
                out = candidate
                lo = mid + 1
            else:
                hi = mid - 1

        return out
logger = Logger()

class Trader:
    """Rule-based trader for osmium and buy-and-hold accumulation for roots."""

    POSITION_LIMITS = {"ASH_COATED_OSMIUM": 80, "INTARIAN_PEPPER_ROOT": 80}
    OSMIUM_FAIR_WINDOW = 5000
    ROOT_FAIR_BOOTSTRAP_TICKS = 10000
    ROOT_FAIR_STEP_TICKS = 1000
    ROOT_FAIR_INITIAL_OFFSET = 5.0

    def _load_trader_data(self, trader_data: str) -> dict[str, Any]:
        if not trader_data:
            return {}
        try:
            parsed = json.loads(trader_data)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _dump_trader_data(self, data: dict[str, Any]) -> str:
        return json.dumps(data, separators=(",", ":"))

    def _update_osmium_fair(self, data: dict[str, Any], fair_price: float) -> float:
        """Store the current osmium fair price in traderData."""

        data["osmium_fair"] = {"value": fair_price}
        return fair_price

    def _load_osmium_fair(self, data: dict[str, Any]) -> float:
        """Load the current osmium fair price from traderData."""

        fair_state = data.get("osmium_fair", {}) if isinstance(data.get("osmium_fair", {}), dict) else {}
        return float(fair_state.get("value", 10_000.0))

    def _update_root_fair(self, data: dict[str, Any], mid_price: float) -> float:
        """Build root fair until timestamp 10000, then add +1 every 1000 timestamp ticks."""

        fair_state = data.get("root_fair", {}) if isinstance(data.get("root_fair", {}), dict) else {}
        count = int(fair_state.get("count", 0))
        avg_mid = float(fair_state.get("avg_mid", 11_000.0))

        new_count = count + 1
        avg_mid = ((avg_mid * count) + mid_price) / new_count

        fair_value = avg_mid + (avg_mid % 1000)

        data["root_fair"] = {
            "count": new_count,
            "avg_mid": avg_mid,
            "value": fair_value,
        }
        return fair_value

    def _load_root_fair(self, data: dict[str, Any]) -> float:
        """Load current root fair from traderData."""

        fair_state = data.get("root_fair", {}) if isinstance(data.get("root_fair", {}), dict) else {}
        return float(fair_state.get("value", 11_005.0))

    def _update_stage_2_flag(self, data: dict[str, Any]) -> None:
        """Mark that we've entered stage 2 (position >= 80) permanently."""

        if "stage_2_entered" not in data:
            data["stage_2_entered"] = True

    def _is_stage_2(self, data: dict[str, Any]) -> bool:
        """Check if stage 2 has been entered (permanent flag)."""

        return data.get("stage_2_entered", False)

    def _update_max_root_buy_price(self, data: dict[str, Any], own_root_trades: list[Trade]) -> None:
        """Track highest executed buy price for roots from own trades."""

        current_max = data.get("max_root_buy_price", 0)
        for trade in own_root_trades:
            if trade.buyer == "SUBMISSION" and trade.price > current_max:
                current_max = trade.price
        data["max_root_buy_price"] = current_max

    def _get_max_root_buy_price(self, data: dict[str, Any]) -> int:
        """Get the highest executed buy price for roots."""

        return data.get("max_root_buy_price", 0)

    def _update_osmium_dip_counts(
        self,
        data: dict[str, Any],
        best_bid: int,
        best_ask: int,
        fair_price: float,
    ) -> tuple[dict[str, int], bool]:
        """Track osmium dip hits for fair+1, fair, and fair-1 within the rolling window."""

        threshold_state = (
            data.get("osmium_dip_counts", {})
            if isinstance(data.get("osmium_dip_counts", {}), dict)
            else {}
        )
        history = threshold_state.get("history", []) if isinstance(threshold_state.get("history", []), list) else []

        current = {
            "ask_below_fair_plus_1": int(best_ask < fair_price + 1),
            "ask_below_fair": int(best_ask < fair_price),
            "ask_below_fair_minus_1": int(best_ask < fair_price - 1),
            "bid_above_fair_plus_1": int(best_bid > fair_price + 1),
            "bid_above_fair": int(best_bid > fair_price),
            "bid_above_fair_minus_1": int(best_bid > fair_price - 1),
        }
        history.append(current)
        window_complete = len(history) >= self.OSMIUM_FAIR_WINDOW

        counts = {
            "ask_below_fair_plus_1": sum(item["ask_below_fair_plus_1"] for item in history),
            "ask_below_fair": sum(item["ask_below_fair"] for item in history),
            "ask_below_fair_minus_1": sum(item["ask_below_fair_minus_1"] for item in history),
            "bid_above_fair_plus_1": sum(item["bid_above_fair_plus_1"] for item in history),
            "bid_above_fair": sum(item["bid_above_fair"] for item in history),
            "bid_above_fair_minus_1": sum(item["bid_above_fair_minus_1"] for item in history),
            "combined_fair_plus_1": sum(
                item["ask_below_fair_plus_1"] + item["bid_above_fair_plus_1"] for item in history
            ),
            "combined_fair": sum(item["ask_below_fair"] + item["bid_above_fair"] for item in history),
            "combined_fair_minus_1": sum(
                item["ask_below_fair_minus_1"] + item["bid_above_fair_minus_1"] for item in history
            ),
        }

        data["osmium_dip_counts"] = {
            "history": [] if window_complete else history,
            "counts": counts,
        }
        return counts, window_complete

    def _best_bid_ask(self, order_depth: OrderDepth) -> tuple[Optional[int], Optional[int]]:
        """Return the best bid and best ask from the current order book, if available."""

        best_bid = max(order_depth.buy_orders) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders) if order_depth.sell_orders else None
        return best_bid, best_ask

    def _mid_price(self, order_depth: OrderDepth) -> Optional[float]:
        """Compute a mid price from the current best bid and ask."""

        best_bid, best_ask = self._best_bid_ask(order_depth)
        if best_bid is None and best_ask is None:
            return None
        if best_bid is None:
            assert best_ask is not None
            return float(best_ask)
        if best_ask is None:
            assert best_bid is not None
            return float(best_bid)
        return (best_bid + best_ask) / 2.0

    def _allowable_buy(self, product: Symbol, position: int) -> int:
        """Return how many more units we can buy without breaching the long limit."""

        return max(0, self.POSITION_LIMITS[product] - position)

    def _allowable_sell(self, product: Symbol, position: int) -> int:
        """Return how many more units we can sell without breaching the short limit."""

        return max(0, self.POSITION_LIMITS[product] + position)

    def _update_root_buy_weighted_avg(self, data: dict[str, Any], own_root_trades: list[Trade]) -> None:
        """Track weighted-average executed buy price for roots from own trades."""

        state = data.get("root_buy_wavg", {}) if isinstance(data.get("root_buy_wavg", {}), dict) else {}
        total_px_qty = float(state.get("total_px_qty", 0.0))
        total_qty = int(state.get("total_qty", 0))

        for trade in own_root_trades:
            if trade.buyer != "SUBMISSION":
                continue
            qty = abs(int(trade.quantity))
            if qty <= 0:
                continue
            total_px_qty += float(trade.price) * qty
            total_qty += qty

        weighted_avg = total_px_qty / total_qty if total_qty > 0 else 0.0
        data["root_buy_wavg"] = {
            "total_px_qty": total_px_qty,
            "total_qty": total_qty,
            "value": weighted_avg,
        }

    def _get_root_buy_weighted_avg(self, data: dict[str, Any]) -> float:
        """Get weighted-average executed buy price for roots (0.0 when uninitialized)."""

        state = data.get("root_buy_wavg", {}) if isinstance(data.get("root_buy_wavg", {}), dict) else {}
        return float(state.get("value", 0.0))

    def _run_root_fair_strategy(
        self,
        trader_state: dict[str, Any],
        order_depth: OrderDepth,
        position: int,
    ) -> tuple[list[Order], int, float, float, float]:
        """Run the current root fair-value strategy."""

        orders: list[Order] = []
        temp_position = position

        root_mid = self._mid_price(order_depth)
        root_fair = self._load_root_fair(trader_state)
        if root_mid is not None:
            root_fair = self._update_root_fair(trader_state, root_mid)

        buy_trigger = root_fair + 2
        sell_trigger = root_fair + 3 if position < 80 else root_fair + 1
        max_buy_price = self._get_max_root_buy_price(trader_state)

        buy_remaining = self._allowable_buy("INTARIAN_PEPPER_ROOT", temp_position)
        for ask_price in sorted(order_depth.sell_orders):
            if ask_price >= buy_trigger or buy_remaining <= 0:
                break
            available = -order_depth.sell_orders[ask_price]
            qty = min(available, buy_remaining)
            if qty > 0:
                orders.append(Order("INTARIAN_PEPPER_ROOT", ask_price, qty))
                temp_position += qty
                buy_remaining -= qty

        sell_remaining = self._allowable_sell("INTARIAN_PEPPER_ROOT", temp_position)
        for bid_price in sorted(order_depth.buy_orders, reverse=True):
            if bid_price <= sell_trigger or bid_price <= max_buy_price or sell_remaining <= 0:
                break
            available = order_depth.buy_orders[bid_price]
            qty = min(available, sell_remaining, 4)
            if qty > 0:
                orders.append(Order("INTARIAN_PEPPER_ROOT", bid_price, -qty))
                temp_position -= qty
                sell_remaining -= qty

        return orders, temp_position, root_fair, buy_trigger, sell_trigger

    def _run_root_l1_accumulation_strategy(
        self,
        order_depth: OrderDepth,
        position: int,
        root_buy_weighted_avg: float,
    ) -> tuple[list[Order], int]:
        """Buy only from L1 (best ask) until position reaches 80."""

        orders: list[Order] = []
        temp_position = position

        if not order_depth.sell_orders:
            return orders, temp_position

        best_ask = min(order_depth.sell_orders)
        buy_remaining = self._allowable_buy("INTARIAN_PEPPER_ROOT", temp_position)
        available = -order_depth.sell_orders[best_ask]
        qty = min(available, buy_remaining)

        # If uninitialized average (0) or this buy is above weighted-average, buy 1.
        if float(best_ask) > root_buy_weighted_avg + 1.5:
            qty = 1

        if qty > 0:
            orders.append(Order("INTARIAN_PEPPER_ROOT", best_ask, qty))
            temp_position += qty

        return orders, temp_position

    def run(self, state: TradingState):
        """Main entry point called by the simulator each tick."""

        result: dict[Symbol, list[Order]] = {}
        trader_state = self._load_trader_data(state.traderData)

        for product in self.POSITION_LIMITS:
            if product not in state.order_depths:
                continue

            order_depth = state.order_depths[product]
            position = state.position.get(product, 0)

            if product == "INTARIAN_PEPPER_ROOT":
                orders = []
                temp_position = position
                root_fair = self._load_root_fair(trader_state)

                # Track highest executed buy price for sell constraint
                own_root_trades = state.own_trades.get(product, [])
                self._update_max_root_buy_price(trader_state, own_root_trades)
                self._update_root_buy_weighted_avg(trader_state, own_root_trades)
                root_buy_weighted_avg = self._get_root_buy_weighted_avg(trader_state)

                if position < self.POSITION_LIMITS["INTARIAN_PEPPER_ROOT"] and not self._is_stage_2(trader_state):
                    # Stage 1: L1 accumulation only
                    orders, temp_position = self._run_root_l1_accumulation_strategy(
                        order_depth, position, root_buy_weighted_avg
                    )
                    logger.print(
                        f"{product} STAGE_1_ACCUMULATION pos={position} root_buy_wavg={root_buy_weighted_avg:.2f} orders={len(orders)}"
                    )
                else:
                    # Stage 2: Fair-value trading (permanent)
                    if not self._is_stage_2(trader_state):
                        self._update_stage_2_flag(trader_state)

                    fair_orders, temp_position, root_fair, buy_trigger, sell_trigger = self._run_root_fair_strategy(
                        trader_state, order_depth, position
                    )
                    orders = fair_orders
                    logger.print(
                        f"{product} STAGE_2_FAIR_VALUE pos={position} fair={root_fair:.2f} "
                        f"buy_below={buy_trigger:.2f} sell_above={sell_trigger:.2f} orders={len(orders)}"
                    )

                result[product] = orders
                continue

            stop_trade = False
            if product == "ASH_COATED_OSMIUM" and stop_trade:
                orders: list[Order] = []
                temp_position = position
                osmium_fair = self._load_osmium_fair(trader_state)

                best_bid, best_ask = self._best_bid_ask(order_depth)
                dip_counts = {
                    "ask_below_fair_plus_1": 0,
                    "ask_below_fair": 0,
                    "ask_below_fair_minus_1": 0,
                    "bid_above_fair_plus_1": 0,
                    "bid_above_fair": 0,
                    "bid_above_fair_minus_1": 0,
                    "combined_fair_plus_1": 0,
                    "combined_fair": 0,
                    "combined_fair_minus_1": 0,
                }
                window_complete = False
                if best_bid is not None and best_ask is not None:
                    dip_counts, window_complete = self._update_osmium_dip_counts(
                        trader_state, best_bid, best_ask, osmium_fair
                    )

                if window_complete:
                    c_minus_1 = dip_counts["combined_fair_minus_1"]
                    c_0 = dip_counts["combined_fair"]
                    c_plus_1 = dip_counts["combined_fair_plus_1"]

                    if c_minus_1 > c_0 and c_minus_1 > c_plus_1:
                        osmium_fair -= 1
                    elif c_plus_1 > c_0 and c_plus_1 > c_minus_1:
                        osmium_fair += 1
                    elif c_minus_1 == c_0 and c_plus_1 < c_0:
                        osmium_fair -= 1
                    elif c_0 == c_plus_1 and c_minus_1 < c_0:
                        osmium_fair += 1
                    self._update_osmium_fair(trader_state, osmium_fair)

                buy_trigger = osmium_fair - 2
                sell_trigger = osmium_fair + 2

                buy_remaining = self._allowable_buy(product, temp_position)
                for ask_price in sorted(order_depth.sell_orders):
                    if ask_price >= buy_trigger or buy_remaining <= 0:
                        break
                    available = -order_depth.sell_orders[ask_price]
                    qty = min(available, buy_remaining)
                    if qty > 0:
                        orders.append(Order(product, ask_price, qty))
                        temp_position += qty
                        buy_remaining -= qty

                sell_remaining = self._allowable_sell(product, temp_position)
                for bid_price in sorted(order_depth.buy_orders, reverse=True):
                    if bid_price <= sell_trigger or sell_remaining <= 0:
                        break
                    available = order_depth.buy_orders[bid_price]
                    qty = min(available, sell_remaining)
                    if qty > 0:
                        orders.append(Order(product, bid_price, -qty))
                        temp_position -= qty
                        sell_remaining -= qty

                result[product] = orders
                logger.print(
                    f"{product} pos={position} fair={osmium_fair:.2f} "
                    f"buy_below={buy_trigger:.2f} sell_above={sell_trigger:.2f} orders={len(orders)}"
                )
                logger.print(
                    f"{product} dip_counts win={self.OSMIUM_FAIR_WINDOW} "
                    f"ask<fair+1={dip_counts['ask_below_fair_plus_1']} "
                    f"ask<fair={dip_counts['ask_below_fair']} "
                    f"ask<fair-1={dip_counts['ask_below_fair_minus_1']} "
                    f"bid>fair+1={dip_counts['bid_above_fair_plus_1']} "
                    f"bid>fair={dip_counts['bid_above_fair']} "
                    f"bid>fair-1={dip_counts['bid_above_fair_minus_1']} "
                    f"combined+1={dip_counts['combined_fair_plus_1']} "
                    f"combined={dip_counts['combined_fair']} "
                    f"combined-1={dip_counts['combined_fair_minus_1']} "
                    f"window_complete={int(window_complete)}"
                )

        trader_data = self._dump_trader_data(trader_state)
        conversions = 0

        logger.flush(state, result, conversions, trader_data)
        return result, conversions, trader_data
