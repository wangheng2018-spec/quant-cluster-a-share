"""
回测引擎
模拟时间序列交易，评估策略绩效
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

from config import Config
from data.fetcher import get_daily_data, _mock_daily
from portfolio.manager import PortfolioManager


@dataclass
class BacktestResult:
    """回测结果"""
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
    回测主函数：
    1. 获取所有选中股票的日线数据
    2. 按再平衡周期调仓
    3. 每日检查止损止盈
    4. 输出绩效报告
    """
    print("=" * 50)
    print("【回测阶段】")
    print(f"  初始资金: {cfg.initial_capital:,.0f} 元")
    print(f"  再平衡周期: {cfg.rebalance_days} 天")
    print(f"  股票池: {len(selected_stocks)} 只")
    print("=" * 50)

    # 1. 获取日线数据
    print("\n  加载日线数据...")
    price_data = {}
    for _, row in selected_stocks.iterrows():
        code = row["code"]
        daily = get_daily_data(code, cfg.start_date, cfg.end_date, cfg)
        if daily is not None and not daily.empty:
            price_data[code] = daily

    if not price_data:
        print("  ❌ 无法获取任何股票的行情数据")
        return BacktestResult({}, pd.DataFrame(), pd.DataFrame(), [])

    # 2. 构建统一时间轴
    all_dates = set()
    for code, df in price_data.items():
        all_dates.update(df["date"].dt.date.tolist())
    all_dates = sorted(all_dates)
    print(f"  交易日总数: {len(all_dates)}")

    # 3. 初始化投资组合
    portfolio = PortfolioManager(cfg)
    last_rebalance_date = None
    rebalance_count = 0

    # 4. 开始回测
    print(f"\n  开始回测...")
    for i, date in enumerate(all_dates):
        date_str = date.isoformat() if hasattr(date, 'isoformat') else str(date)

        # 构建当日价格字典
        prices = {}
        for code, df in price_data.items():
            day_data = df[df["date"].dt.date == date]
            if not day_data.empty:
                prices[code] = day_data.iloc[0]["close"]

        if not prices:
            # 跳过无数据交易日
            continue

        # 再平衡检查
        should_rebalance = (
            last_rebalance_date is None
            or (datetime.combine(date, datetime.min.time())
                - datetime.combine(last_rebalance_date, datetime.min.time())).days
                >= cfg.rebalance_days
        )

        if should_rebalance:
            rebalance_count += 1
            # 生成买入信号
            n_positions = min(len(selected_stocks), cfg.max_positions)
            stocks_to_buy = selected_stocks.head(n_positions)

            # 如果已有持仓，先卖出现有持仓中不在新池子里的
            current_codes = set(portfolio.positions.keys())
            new_codes = set(stocks_to_buy["code"].iloc[:cfg.max_positions])
            for code in current_codes - new_codes:
                if code in prices:
                    signal = {
                        "code": code,
                        "name": portfolio.positions[code].get("name", ""),
                        "action": "sell",
                        "reason": "再平衡调出",
                    }
                    portfolio.execute_trade(signal, prices[code], date)

            # 买入新股票
            signals = portfolio.calculate_positions(
                stocks_to_buy,
                market_volatility=market_volatility,
            )
            for sig in signals:
                code = sig["code"]
                if code in prices and code not in portfolio.positions:
                    portfolio.execute_trade(sig, prices[code], date)

            last_rebalance_date = date
            if rebalance_count <= 3 or rebalance_count % 5 == 0:
                print(f"    📊 第{rebalance_count}次再平衡 ({date_str}): "
                      f"持仓 {len(portfolio.positions)} 只, "
                      f"现金 {portfolio.cash:,.0f}")

        # 每日止损止盈检查
        stop_signals = portfolio.check_stops(prices, date)
        for sig in stop_signals:
            code = sig["code"]
            if code in prices:
                portfolio.execute_trade(sig, prices[code], date)

        # 更新净值
        portfolio.update_nav(prices, date)

    # 5. 生成绩效报告
    print(f"\n  回测完成！")
    print(f"  总调仓次数: {rebalance_count}")
    summary = portfolio.get_summary()

    # 转为 DataFrame
    equity_df = pd.DataFrame(portfolio.equity_curve)
    trades_df = pd.DataFrame(portfolio.trades)

    # 打印收益率曲线摘要
    if equity_df is not None and len(equity_df) > 0:
        print(f"\n【绩效报告】")
        print(f"  {'指标':<20s} {'数值':<12s}")
        print(f"  {'-'*32}")
        for k, v in summary.items():
            if isinstance(v, float):
                print(f"  {k:<20s} {v:<12.2f}")
            else:
                print(f"  {k:<20s} {v:<12}")

    return BacktestResult(
        summary=summary,
        equity_curve=equity_df,
        trades=trades_df,
        positions=list(portfolio.positions.keys()),
    )
