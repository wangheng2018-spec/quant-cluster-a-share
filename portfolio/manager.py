"""
仓位管理与风险控制
核心：条件触发再平衡 + 市场波动自适应仓位 + 多聚类组合资金分配
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta

from config import Config


class PortfolioManager:
    """投资组合管理器"""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.positions: Dict[str, dict] = {}
        self.cash: float = cfg.initial_capital
        self.total_value: float = cfg.initial_capital
        self.trades: List[dict] = []
        self.equity_curve: List[dict] = []
        self.last_rebalance_date = None
        self.peak_value = cfg.initial_capital

    # ──────────────────────────────────────────
    # 条件再平衡检查
    # ──────────────────────────────────────────
    def should_rebalance(self, current_date,
                         market_return_today: float = 0.0) -> Tuple[bool, str]:
        """
        检查是否满足再平衡触发条件（按优先级）
        返回 (是否触发, 原因)
        """
        if self.last_rebalance_date is None:
            return True, "首次建仓"

        days_since = (current_date - self.last_rebalance_date).days
        if days_since < self.cfg.rebalance_min_days:
            return False, f"未到最小间隔（{days_since}/{self.cfg.rebalance_min_days}天）"

        # 条件1：最大间隔天数
        if days_since >= self.cfg.rebalance_days:
            return True, f"最大间隔触发（{days_since}天）"

        # 条件2：组合回撤
        if self.peak_value > 0:
            current_dd = (self.peak_value - self.total_value) / self.peak_value
            if current_dd >= self.cfg.rebalance_max_drawdown:
                return True, f"回撤{current_dd*100:.1f}%触发再平衡"

        # 条件3：市场冲击
        if market_return_today <= -self.cfg.rebalance_market_shock:
            return True, f"市场单日跌幅{market_return_today*100:.1f}%触发再平衡"

        return False, "无触发条件"

    # ──────────────────────────────────────────
    # 仓位分配
    # ──────────────────────────────────────────
    def calculate_positions(
        self, selected_stocks: pd.DataFrame,
        cluster_scores: dict = None,
        market_volatility: float = 0.25,
    ) -> List[dict]:
        """
        计算目标仓位分配
        多聚类组合按评分加权，单聚类等权重
        """
        n = min(len(selected_stocks), self.cfg.max_positions)
        if n == 0:
            return []

        # 1. 市场波动 -> 总仓位系数
        vol_factor = self._volatility_adjust(market_volatility)
        target_position_weight = np.clip(
            self.cfg.max_position_weight * vol_factor,
            self.cfg.min_position_weight,
            self.cfg.max_position_weight,
        )
        target_value = self.total_value * target_position_weight

        # 2. 分配权重
        if self.cfg.equal_weight or "alloc_weight" not in selected_stocks.columns:
            # 等权重
            per_stock = target_value / n
            per_stock = min(per_stock, self.total_value * self.cfg.max_single_weight)
            signals = []
            for _, row in selected_stocks.head(n).iterrows():
                w = per_stock / self.total_value
                signals.append(self._make_buy_signal(row, per_stock, w))
        else:
            # 评分加权（多聚类）
            total_weight = selected_stocks["alloc_weight"].sum()
            signals = []
            per_stock_base = target_value / total_weight
            for _, row in selected_stocks.head(n).iterrows():
                w = row.get("alloc_weight", 1.0 / n)
                amount = min(per_stock_base * w,
                             self.total_value * self.cfg.max_single_weight)
                signals.append(self._make_buy_signal(row, amount, amount / self.total_value))

        return signals

    def _make_buy_signal(self, row, amount, weight):
        return {
            "code": row["code"],
            "name": row["name"],
            "target_amount": amount,
            "target_weight": round(weight, 4),
            "action": "buy",
            "cluster": row.get("cluster", "?"),
            "reason": (f"聚类#{row.get('cluster','?')} 选入 | "
                       f"PE={row.get('pe_ttm','?'):.1f} "
                       f"PB={row.get('pb','?'):.2f}"),
        }

    # ──────────────────────────────────────────
    # 市场波动 -> 仓位系数
    # ──────────────────────────────────────────
    def _volatility_adjust(self, vol: float) -> float:
        if vol <= self.cfg.vol_low:
            return 1.0
        elif vol <= self.cfg.vol_normal:
            return 0.85
        elif vol <= self.cfg.vol_high:
            return 0.70
        elif vol <= self.cfg.vol_extreme:
            return 0.50
        else:
            return 0.30

    def get_market_state(self, vol: float) -> str:
        if vol <= self.cfg.vol_low:
            return "🟢 低波动·满仓"
        elif vol <= self.cfg.vol_normal:
            return "🟡 正常·8.5成仓"
        elif vol <= self.cfg.vol_high:
            return "🟠 高波动·7成仓"
        elif vol <= self.cfg.vol_extreme:
            return "🔴 极高波动·5成仓"
        else:
            return "⛔ 极端行情·3成仓"

    # ──────────────────────────────────────────
    # 止损/止盈
    # ──────────────────────────────────────────
    def check_stops(self, prices: Dict[str, float], date) -> List[dict]:
        signals = []
        for code, pos in list(self.positions.items()):
            price = prices.get(code)
            if price is None:
                continue
            cost = pos["avg_cost"]
            change = (price - cost) / cost

            if change <= -self.cfg.stop_loss:
                signals.append({
                    "code": code, "name": pos["name"],
                    "action": "sell",
                    "reason": f"止损: {change*100:.1f}% ≤ -{self.cfg.stop_loss*100:.0f}%",
                    "amount": pos["shares"] * price,
                })
            elif change >= self.cfg.take_profit:
                sell_s = pos["shares"] // 2
                if sell_s > 0:
                    signals.append({
                        "code": code, "name": pos["name"],
                        "action": "sell_partial",
                        "reason": f"止盈: {change*100:.1f}% ≥ {self.cfg.take_profit*100:.0f}%",
                        "amount": sell_s * price,
                        "shares": sell_s,
                    })
        return signals

    # ──────────────────────────────────────────
    # 执行交易
    # ──────────────────────────────────────────
    def execute_trade(self, signal: dict, price: float, date) -> dict:
        code = signal["code"]
        action = signal["action"]
        trade = {
            "date": date, "code": code,
            "name": signal.get("name", ""),
            "action": action, "price": round(price, 3),
            "reason": signal.get("reason", ""),
        }

        if action == "buy":
            amt = signal.get("target_amount", 0)
            shares = int(amt / price) if price > 0 else 0
            cost = shares * price
            comm = cost * self.cfg.commission
            total = cost + comm
            if total <= self.cash and shares > 0:
                self.cash -= total
                if code in self.positions:
                    p = self.positions[code]
                    total_s = p["shares"] + shares
                    total_basis = p["cost_basis"] + cost
                    p.update(shares=total_s, cost_basis=total_basis,
                             avg_cost=total_basis / total_s)
                else:
                    self.positions[code] = {
                        "shares": shares, "cost_basis": cost,
                        "avg_cost": price, "name": signal.get("name", code),
                    }
                trade.update(shares=shares, amount=round(total, 2),
                             commission=round(comm, 2))
            else:
                trade["status"] = "skipped"

        elif action in ("sell",):
            pos = self.positions.get(code)
            if pos:
                s = pos["shares"]
                proceeds = s * price
                stamp = proceeds * self.cfg.stamp_tax
                comm = proceeds * self.cfg.commission
                net = proceeds - stamp - comm
                self.cash += net
                del self.positions[code]
                trade.update(shares=s, amount=round(proceeds, 2),
                             commission=round(comm, 2),
                             stamp_tax=round(stamp, 2), net=round(net, 2))

        elif action == "sell_partial":
            pos = self.positions.get(code)
            sell_s = signal.get("shares", pos["shares"] // 2 if pos else 0)
            if pos and sell_s > 0:
                proceeds = sell_s * price
                stamp = proceeds * self.cfg.stamp_tax
                comm = proceeds * self.cfg.commission
                net = proceeds - stamp - comm
                self.cash += net
                pos["shares"] -= sell_s
                pos["cost_basis"] *= pos["shares"] / (pos["shares"] + sell_s)
                if pos["shares"] <= 0:
                    del self.positions[code]
                trade.update(shares=sell_s, amount=round(proceeds, 2),
                             commission=round(comm, 2),
                             stamp_tax=round(stamp, 2), net=round(net, 2))

        self.trades.append(trade)
        return trade

    # ──────────────────────────────────────────
    # 每日净值
    # ──────────────────────────────────────────
    def update_nav(self, prices: Dict[str, float], date) -> dict:
        pos_value = sum(
            prices.get(c, 0) * p["shares"]
            for c, p in self.positions.items()
        )
        self.total_value = self.cash + pos_value
        if self.total_value > self.peak_value:
            self.peak_value = self.total_value

        dd = (self.peak_value - self.total_value) / self.peak_value if self.peak_value > 0 else 0
        entry = {
            "date": date, "cash": round(self.cash, 2),
            "position_value": round(pos_value, 2),
            "total_value": round(self.total_value, 2),
            "position_ratio": round(pos_value / self.total_value, 4) if self.total_value > 0 else 0,
            "drawdown": round(dd * 100, 2),
            "positions": len(self.positions),
        }
        self.equity_curve.append(entry)
        return entry

    # ──────────────────────────────────────────
    # 绩效统计
    # ──────────────────────────────────────────
    def get_summary(self) -> dict:
        if not self.equity_curve:
            return {}

        init = self.cfg.initial_capital
        final = self.equity_curve[-1]["total_value"]
        total_ret = (final - init) / init
        n_days = len(self.equity_curve)
        annual_ret = (1 + total_ret) ** (250 / max(n_days, 1)) - 1 if n_days > 0 else 0

        # 最大回撤
        max_dd = max(e.get("drawdown", 0) for e in self.equity_curve)

        # 夏普
        daily_rets = []
        for i in range(1, len(self.equity_curve)):
            r = (self.equity_curve[i]["total_value"]
                 - self.equity_curve[i-1]["total_value"])
            daily_rets.append(r)
        sharpe = 0
        if len(daily_rets) > 1:
            m = np.mean(daily_rets)
            s = np.std(daily_rets)
            if s > 0:
                sharpe = round((m / s) * np.sqrt(250), 2)

        # 胜率
        wins = sum(1 for t in self.trades
                   if t.get("action") in ("sell", "sell_partial")
                   and t.get("net", 0) > t.get("amount", 0))
        total_closed = sum(1 for t in self.trades
                           if t.get("action") in ("sell", "sell_partial"))

        return {
            "initial_capital": init,
            "final_value": round(final, 2),
            "total_return": round(total_ret * 100, 2),
            "annual_return": round(annual_ret * 100, 2),
            "max_drawdown": round(max_dd, 2),
            "sharpe_ratio": sharpe,
            "total_trades": len(self.trades),
            "win_rate": round(wins / max(total_closed, 1) * 100, 1),
            "final_positions": len(self.positions),
            "cash_remaining": round(self.cash, 2),
        }
