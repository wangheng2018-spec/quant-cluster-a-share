"""
仓位管理与风险控制
核心：根据聚类评分、市场状态动态分配资金 + 止损止盈
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional

from config import Config


class PortfolioManager:
    """投资组合管理器"""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.positions: Dict[str, dict] = {}   # code -> 持仓信息
        self.cash: float = cfg.initial_capital
        self.total_value: float = cfg.initial_capital
        self.trades: List[dict] = []            # 交易记录
        self.equity_curve: List[dict] = []      # 净值曲线

    # ──────────────────────────────────────────
    # 核心：仓位分配
    # ──────────────────────────────────────────
    def calculate_positions(
        self, selected_stocks: pd.DataFrame,
        cluster_scores: dict = None,
        market_volatility: float = 0.25,
    ) -> List[dict]:
        """
        计算目标仓位分配
        策略: 等权重 + 动态总仓位控制
        """
        n = min(len(selected_stocks), self.cfg.max_positions)
        if n == 0:
            return []

        # 1. 根据市场波动率调整总仓位
        vol_factor = self._volatility_adjust(market_volatility)
        target_position_weight = np.clip(
            self.cfg.max_position_weight * vol_factor,
            self.cfg.min_position_weight,
            self.cfg.max_position_weight,
        )

        # 2. 计算目标总仓位
        target_position_value = self.total_value * target_position_weight

        # 3. 等权重分配
        if self.cfg.equal_weight:
            per_stock = target_position_value / n
            per_stock = min(per_stock, self.total_value * self.cfg.max_single_weight)
        else:
            # 按评分加权分配
            total_score = sum(
                cluster_scores.get(s.get("cluster", 0), {}).get("score", 1.0)
                for _, s in selected_stocks.head(n).iterrows()
            ) if cluster_scores else n
            per_stock = target_position_value / total_score

        # 4. 生成交易信号
        signals = []
        for idx, row in selected_stocks.head(n).iterrows():
            code = row["code"]
            weight = per_stock / self.total_value
            signals.append({
                "code": code,
                "name": row["name"],
                "target_amount": per_stock,
                "target_weight": round(weight, 4),
                "action": "buy",
                "reason": (
                    f"聚类标的中选入 | "
                    f"PE={row.get('pe_ttm','?'):.1f} "
                    f"PB={row.get('pb','?'):.2f} "
                    f"股息={row.get('dividend_yield',0)*100:.2f}%"
                ),
            })

        return signals

    def _volatility_adjust(self, market_vol: float) -> float:
        """
        市场波动率调整系数
        波动高 -> 降低仓位，波动低 -> 满仓
        """
        if market_vol <= 0.15:
            return 1.0                     # 低波动，满仓
        elif market_vol <= 0.25:
            return 0.85                    # 正常波动
        elif market_vol <= 0.35:
            return 0.70                    # 偏高波动
        elif market_vol <= 0.50:
            return 0.50                    # 高波动，半仓
        else:
            return 0.30                    # 极高波动，轻仓

    # ──────────────────────────────────────────
    # 止损/止盈检查
    # ──────────────────────────────────────────
    def check_stops(self, prices: Dict[str, float], date) -> List[dict]:
        """
        检查所有持仓的止损止盈
        返回需要卖出的信号列表
        """
        signals = []
        for code, pos in list(self.positions.items()):
            current_price = prices.get(code)
            if current_price is None:
                continue

            cost = pos["avg_cost"]
            change = (current_price - cost) / cost

            # 止损
            if change <= -self.cfg.stop_loss:
                signals.append({
                    "code": code,
                    "name": pos["name"],
                    "action": "sell",
                    "reason": f"止损触发: {change*100:.1f}% ≤ -{self.cfg.stop_loss*100:.0f}%",
                    "amount": pos["shares"] * current_price,
                })

            # 止盈
            elif change >= self.cfg.take_profit:
                # 分批止盈：卖出一半
                sell_shares = pos["shares"] // 2
                if sell_shares > 0:
                    signals.append({
                        "code": code,
                        "name": pos["name"],
                        "action": "sell_partial",
                        "reason": f"止盈触发: {change*100:.1f}% ≥ {self.cfg.take_profit*100:.0f}%",
                        "amount": sell_shares * current_price,
                        "shares": sell_shares,
                    })

        return signals

    # ──────────────────────────────────────────
    # 执行交易
    # ──────────────────────────────────────────
    def execute_trade(self, signal: dict, price: float, date) -> dict:
        """执行单笔交易"""
        code = signal["code"]
        action = signal["action"]
        trade = {
            "date": date,
            "code": code,
            "name": signal.get("name", ""),
            "action": action,
            "price": round(price, 3),
            "reason": signal.get("reason", ""),
        }

        if action in ("buy",):
            shares = int(signal["target_amount"] / price)
            cost = shares * price
            commission = cost * self.cfg.commission
            total_cost = cost + commission

            if total_cost <= self.cash:
                self.cash -= total_cost
                # 更新持仓
                if code in self.positions:
                    pos = self.positions[code]
                    total_shares = pos["shares"] + shares
                    total_cost_basis = pos["cost_basis"] + cost
                    pos["shares"] = total_shares
                    pos["cost_basis"] = total_cost_basis
                    pos["avg_cost"] = total_cost_basis / total_shares
                else:
                    self.positions[code] = {
                        "shares": shares,
                        "cost_basis": cost,
                        "avg_cost": price,
                        "name": signal.get("name", code),
                    }
                trade.update({
                    "shares": shares,
                    "amount": round(total_cost, 2),
                    "commission": round(commission, 2),
                })
            else:
                trade["status"] = "skipped (insufficient cash)"

        elif action in ("sell",):
            pos = self.positions.get(code)
            if pos:
                shares = pos["shares"]
                proceeds = shares * price
                stamp = proceeds * self.cfg.stamp_tax
                commission = proceeds * self.cfg.commission
                net_proceeds = proceeds - stamp - commission

                self.cash += net_proceeds
                del self.positions[code]
                trade.update({
                    "shares": shares,
                    "amount": round(proceeds, 2),
                    "commission": round(commission, 2),
                    "stamp_tax": round(stamp, 2),
                    "net_proceeds": round(net_proceeds, 2),
                })

        elif action in ("sell_partial",):
            pos = self.positions.get(code)
            sell_shares = signal.get("shares", pos["shares"] // 2 if pos else 0)
            if pos and sell_shares > 0:
                proceeds = sell_shares * price
                stamp = proceeds * self.cfg.stamp_tax
                commission = proceeds * self.cfg.commission
                net_proceeds = proceeds - stamp - commission

                self.cash += net_proceeds
                pos["shares"] -= sell_shares
                pos["cost_basis"] *= (pos["shares"]
                                      / (pos["shares"] + sell_shares))
                if pos["shares"] <= 0:
                    del self.positions[code]
                trade.update({
                    "shares": sell_shares,
                    "amount": round(proceeds, 2),
                    "commission": round(commission, 2),
                    "stamp_tax": round(stamp, 2),
                    "net_proceeds": round(net_proceeds, 2),
                })

        self.trades.append(trade)
        return trade

    # ──────────────────────────────────────────
    # 每日净值更新
    # ──────────────────────────────────────────
    def update_nav(self, prices: Dict[str, float], date) -> dict:
        """更新每日净值"""
        position_value = 0.0
        for code, pos in list(self.positions.items()):
            price = prices.get(code)
            if price:
                position_value += price * pos["shares"]

        self.total_value = self.cash + position_value
        entry = {
            "date": date,
            "cash": round(self.cash, 2),
            "position_value": round(position_value, 2),
            "total_value": round(self.total_value, 2),
            "position_ratio": round(position_value / self.total_value, 4)
            if self.total_value > 0 else 0,
            "positions": len(self.positions),
        }
        self.equity_curve.append(entry)
        return entry

    # ──────────────────────────────────────────
    # 组合统计
    # ──────────────────────────────────────────
    def get_summary(self) -> dict:
        """返回投资组合绩效统计"""
        if not self.equity_curve:
            return {}

        initial = self.cfg.initial_capital
        final = self.equity_curve[-1]["total_value"]
        total_return = (final - initial) / initial

        # 年化收益率（按 250 交易日）
        n_days = len(self.equity_curve)
        annual_return = (1 + total_return) ** (250 / max(n_days, 1)) - 1

        # 最大回撤
        peak = initial
        max_dd = 0
        for e in self.equity_curve:
            v = e["total_value"]
            if v > peak:
                peak = v
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd

        # 夏普比
        daily_returns = []
        for i in range(1, len(self.equity_curve)):
            r = (self.equity_curve[i]["total_value"]
                 - self.equity_curve[i - 1]["total_value"])
            daily_returns.append(r)

        sharpe = 0
        if len(daily_returns) > 1:
            mean_ret = np.mean(daily_returns)
            std_ret = np.std(daily_returns)
            if std_ret > 0:
                sharpe = (mean_ret / std_ret) * np.sqrt(250)

        # 胜率
        wins = 0
        total_trades = len(self.trades)
        for i in range(1, len(self.trades)):
            if self.trades[i].get("net_proceeds", 0) > 0 \
               and self.trades[i].get("amount", 0) > 0:
                ratio = (self.trades[i]["net_proceeds"]
                         - self.trades[i]["amount"]) / self.trades[i]["amount"]
                if ratio > 0:
                    wins += 1

        return {
            "initial_capital": initial,
            "final_value": final,
            "total_return": round(total_return * 100, 2),
            "annual_return": round(annual_return * 100, 2),
            "max_drawdown": round(max_dd * 100, 2),
            "sharpe_ratio": round(sharpe, 2),
            "total_trades": total_trades,
            "final_positions": len(self.positions),
            "cash_remaining": round(self.cash, 2),
        }
