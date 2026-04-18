import json
from typing import Any, Optional

from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState

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
    OSMIUM_EKF_INIT_PHI = 0.997229
    OSMIUM_EKF_Q_X = 0.4927061830400836
    OSMIUM_EKF_Q_PHI = 1e-8
    OSMIUM_EKF_R = 5.349606**2
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

    def _initialize_osmium_ekf_state(self, data: dict[str, Any]) -> dict[str, float]:
        """Create EKF state once and keep it in traderData for subsequent ticks."""

        existing = data.get("osmium_ekf", {}) if isinstance(data.get("osmium_ekf", {}), dict) else {}
        if all(k in existing for k in ("x", "phi", "p00", "p01", "p10", "p11")):
            return {
                "x": float(existing["x"]),
                "phi": float(existing["phi"]),
                "p00": float(existing["p00"]),
                "p01": float(existing["p01"]),
                "p10": float(existing["p10"]),
                "p11": float(existing["p11"]),
            }

        init_state = {
            "x": 0.0,
            "phi": self.OSMIUM_EKF_INIT_PHI,
            "p00": 1.0,
            "p01": 0.0,
            "p10": 0.0,
            "p11": 0.01,
        }
        data["osmium_ekf"] = init_state
        return init_state

    def _update_osmium_ekf_fair(self, data: dict[str, Any], measurement: float) -> tuple[float, float]:
        """Update EKF-OU state using volumetric fair-value measurement and return filtered fair, phi."""

        ekf_state = self._initialize_osmium_ekf_state(data)
        x = ekf_state["x"]
        phi = ekf_state["phi"]
        p00 = ekf_state["p00"]
        p01 = ekf_state["p01"]
        p10 = ekf_state["p10"]
        p11 = ekf_state["p11"]

        z = measurement - 10_000.0

        x_pred = phi * x
        phi_pred = phi

        f00 = phi
        f01 = x
        f10 = 0.0
        f11 = 1.0

        fp00 = f00 * p00 + f01 * p10
        fp01 = f00 * p01 + f01 * p11
        fp10 = p10
        fp11 = p11

        p_pred00 = fp00 * f00 + fp01 * f01 + self.OSMIUM_EKF_Q_X
        p_pred01 = fp00 * f10 + fp01 * f11
        p_pred10 = fp10 * f00 + fp11 * f01
        p_pred11 = fp10 * f10 + fp11 * f11 + self.OSMIUM_EKF_Q_PHI

        innovation = z - x_pred
        s = p_pred00 + self.OSMIUM_EKF_R
        if s <= 0:
            s = 1e-9

        k0 = p_pred00 / s
        k1 = p_pred10 / s

        x = x_pred + k0 * innovation
        phi = phi_pred + k1 * innovation

        p00 = (1 - k0) * p_pred00
        p01 = (1 - k0) * p_pred01
        p10 = -k1 * p_pred00 + p_pred10
        p11 = -k1 * p_pred01 + p_pred11

        data["osmium_ekf"] = {
            "x": x,
            "phi": phi,
            "p00": p00,
            "p01": p01,
            "p10": p10,
            "p11": p11,
        }

        fair_value = x + 10_000.0
        data["osmium_fair"] = {"value": fair_value}
        return fair_value, phi

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

    def _calculate_osmium_book_fair_value(self, order_depth: OrderDepth) -> Optional[float]:
        """Calculate volumetric fair value from top 3 bid/ask levels in order book.

        FV_book = (sum of bid_price_i * bid_volume_i + sum of ask_price_i * ask_volume_i) /
                  (sum of bid_volumes + sum of ask_volumes)
        for i in [1, 2, 3]
        """

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return None

        # Get top 3 bid levels (sorted descending by price)
        bid_prices = sorted(order_depth.buy_orders.keys(), reverse=True)[:3]
        bid_numerator = sum(price * order_depth.buy_orders[price] for price in bid_prices)
        bid_volume = sum(order_depth.buy_orders[price] for price in bid_prices)

        # Get top 3 ask levels (sorted ascending by price)
        ask_prices = sorted(order_depth.sell_orders.keys())[:3]
        ask_numerator = sum(price * (-order_depth.sell_orders[price]) for price in ask_prices)
        ask_volume = sum(-order_depth.sell_orders[price] for price in ask_prices)

        total_volume = bid_volume + ask_volume
        if total_volume <= 0:
            return None

        fair_value = (bid_numerator + ask_numerator) / total_volume
        return fair_value

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

        buy_trigger = root_fair + 1 if position < 60 else root_fair
        sell_trigger = root_fair + 2
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

                if position < self.POSITION_LIMITS["INTARIAN_PEPPER_ROOT"] and not self._is_stage_2(trader_state) and state.timestamp < 999999:
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

            stop_trade = True
            if product == "ASH_COATED_OSMIUM" and stop_trade:
                orders: list[Order] = []
                temp_position = position

                # Use top-3 volumetric fair value as EKF measurement; filtered output is trade fair value.
                osmium_fair_book = self._calculate_osmium_book_fair_value(order_depth)
                osmium_phi: Optional[float] = None
                if osmium_fair_book is not None:
                    osmium_fair, osmium_phi = self._update_osmium_ekf_fair(trader_state, osmium_fair_book)
                else:
                    osmium_fair = self._load_osmium_fair(trader_state)

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
                if osmium_phi is None:
                    logger.print(
                        f"{product} pos={position} fair={osmium_fair:.2f} "
                        f"buy_below={buy_trigger:.2f} sell_above={sell_trigger:.2f} orders={len(orders)}"
                    )
                else:
                    logger.print(
                        f"{product} pos={position} fair={osmium_fair:.2f} phi={osmium_phi:.6f} "
                        f"buy_below={buy_trigger:.2f} sell_above={sell_trigger:.2f} orders={len(orders)}"
                    )

        trader_data = self._dump_trader_data(trader_state)
        conversions = 0

        logger.flush(state, result, conversions, trader_data)
        return result, conversions, trader_data
