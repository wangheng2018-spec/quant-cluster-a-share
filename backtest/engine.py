"""
回测引擎
模拟时间序列交易，评估策略绩效
支持：条件再平衡、市场波动自适应、多聚类组合
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

from config import Config
from data.fetcher import get_daily_data
from portfolio.manager import PortfolioManager


@dataclass
class BacktestResult:
    summary: dict
    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    positions: list


def run_backtest(
    selected_stocks: pd.DataFrame,
    cfg: Config,
    market_volatility: float = 0.22,
) -> BacktestResult:
    """
    回测主函数
    """
    print("=" * 50)
    print("【回测阶段】")
    print(f"  初始资金: {cfg.initial_capital:,.0f} 元")
    print(f"  再平衡: 条件触发（最大{cfg.rebalance_days}天, 回撤>{cfg.rebalance_max_drawdown*100:.0f}%触发）")
    print(f"  风控: -{cfg.stop_loss*100:.0f}%止损 / +{cfg.take_profit*100:.0f}%分批止盈")
    print(f"  股票池: {len(selected_stocks)} 只")
    print("=" * 50)

    # 1. 获取日线
    print("\n  加载日线数据...")
    price_data = {}
    for _, row in selected_stocks.iterrows():
        code = row["code"]
        daily = get_daily_data(code, cfg.start_date, cfg.end_date, cfg)
        if daily is not None and not daily.empty:
            price_data[code] = daily

    if not price_data:
        print("  ❌ 无法获取行情数据")
        return BacktestResult({}, pd.DataFrame(), pd.DataFrame(), [])

    # 2. 时间轴
    all_dates = sorted(set(
        d.date() for df in price_data.values() for d in df["date"].dt.date
    ))
    print(f"  交易日: {len(all_dates)}")

    # 3. 回测
    portfolio = PortfolioManager(cfg)
    rebalance_count = 0
    hs300_prev = None

    print(f"\n  回测中...")
    for date in all_dates:
        # 当日价格
        prices = {}
        for code, df in price_data.items():
            day = df[df["date"].dt.date == date]
            if not day.empty:
                prices[code] = day.iloc[0]["close"]

        if not prices:
            continue

        # 估算大盘日收益
        closes = [p for p in prices.values() if p > 0]
        avg_close = np.mean(closes) if closes else 0
        market_ret = 0
        if hs300_prev is not None and avg_close > 0:
            market_ret = (avg_close - hs300_prev) / hs300_prev
        hs300_prev = avg_close

        # 条件再平衡
        should_rebal, reason = portfolio.should_rebalance(date, market_ret)
        if should_rebal:
            rebalance_count += 1
            n_pos = min(len(selected_stocks), cfg.max_positions)
            stocks = selected_stocks.head(n_pos)

            # 卖出现有持仓中不在新池子的
            cur = set(portfolio.positions.keys())
            new = set(stocks["code"].iloc[:cfg.max_positions])
            for code in cur - new:
                if code in prices:
                    portfolio.execute_trade({
                        "code": code,
                        "name": portfolio.positions[code].get("name", ""),
                        "action": "sell", "reason": f"再平衡调出: {reason}",
                    }, prices[code], date)

            # 买入
            cluster_scores = None
            signals = portfolio.calculate_positions(
                stocks, cluster_scores, market_volatility
            )
            for sig in signals:
                c = sig["code"]
                if c in prices and c not in portfolio.positions:
                    portfolio.execute_trade(sig, prices[c], date)

            portfolio.last_rebalance_date = date

            if rebalance_count <= 3 or rebalance_count % 10 == 0:
                pos_count = len(portfolio.positions)
                pos_ratio = (portfolio.total_value - portfolio.cash) / portfolio.total_value * 100 if portfolio.total_value > 0 else 0
                print(f"    📊 #{rebalance_count} {date} | {len(portfolio.positions)}只 | "
                      f"仓位{pos_ratio:.0f}% | {reason}")

        # 止损/止盈
        for sig in portfolio.check_stops(prices, date):
            c = sig["code"]
            if c in prices:
                r = portfolio.execute_trade(sig, prices[c], date)
                print(f"    {'⛔' if '止损' in r['reason'] else '💰'} {r['date']} {r['code']} {r['reason']}")

        # 净值
        portfolio.update_nav(prices, date)

    # 4. 报告
    print(f"\n  回测完成！总调仓: {rebalance_count} 次")
    summary = portfolio.get_summary()
    equity_df = pd.DataFrame(portfolio.equity_curve)
    trades_df = pd.DataFrame(portfolio.trades)

    print(f"\n【绩效报告】")
    print(f"  {'指标':<20s} {'数值':<12s}")
    print(f"  {'-'*32}")
    for k, v in summary.items():
        if isinstance(v, float):
            print(f"  {k:<20s} {v:<12.2f}")
        else:
            print(f"  {k:<20s} {v:<12}")

    return BacktestResult(summary, equity_df, trades_df,
                          list(portfolio.positions.keys()))
