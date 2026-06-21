"""
量化聚类选股系统 - 主入口
A股国资低价股聚类选股 + 动态仓位管理 + 回测

使用方法：
    python main.py                          # 默认配置运行
    python main.py --mode backtest          # 运行回测
    python main.py --mode analyze           # 仅分析当前市场
    python main.py --cluster dbscan         # 使用 DBSCAN
"""
import argparse
import sys
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

from config import Config
from data.fetcher import fetch_all_data
from screening.screener import screen_stocks, get_screener_summary
from features.engineering import build_feature_matrix
from clustering.cluster import run_clustering, select_best_cluster
from backtest.engine import run_backtest


def main():
    parser = argparse.ArgumentParser(
        description="A股国资低价股 · 聚类量化选股系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                          # 离线模拟回测
  python main.py --mode backtest          # 完整回测
  python main.py --mode analyze           # 仅分析选股
  python main.py --cluster dbscan         # DBSCAN 聚类
  python main.py --cluster gmm            # 高斯混合模型
  python main.py --k 6                    # K=6 聚类
  python main.py --price 8                # 筛选股价<8元
        """,
    )
    parser.add_argument("--mode", default="backtest",
                        choices=["backtest", "analyze", "live"])
    parser.add_argument("--cluster", default="kmeans",
                        choices=["kmeans", "dbscan", "gmm", "agglomerative"])
    parser.add_argument("--k", type=int, default=5, help="聚类数（KMeans/GMM）")
    parser.add_argument("--price", type=float, default=10.0, help="股价上限")
    parser.add_argument("--start", default="2024-01-01", help="回测开始日期")
    parser.add_argument("--end", default="", help="回测结束日期（默认今天）")
    parser.add_argument("--capital", type=float, default=100000,
                        help="初始资金（元）")
    parser.add_argument("--top", type=int, default=20, help="最大持仓数")
    parser.add_argument("--rebalance", type=int, default=20,
                        help="再平衡周期（交易日）")

    args = parser.parse_args()

    # 配置
    cfg = Config(
        cluster_method=args.cluster,
        n_clusters=args.k,
        max_price=args.price,
        start_date=args.start,
        end_date=args.end if args.end else datetime.now().strftime("%Y-%m-%d"),
        initial_capital=args.capital,
        max_positions=args.top,
        rebalance_days=args.rebalance,
    )

    end_display = cfg.end_date
    print(f"""

╔══════════════════════════════════════════════════════╗
║      A股 国资低价股 · 聚类量化选股系统              ║
║      基于 KMeans/DBSCAN/GMM 的智能选股策略           ║
╚══════════════════════════════════════════════════════╝

    时间区间: {cfg.start_date} ~ {end_display}
    选股条件: 国资背景 + 股价<={cfg.max_price}元
    聚类方法: {cfg.cluster_method.upper()} (K={cfg.n_clusters})
    初始资金: {cfg.initial_capital:,.0f} 元
    最大持仓: {cfg.max_positions} 只
    再平衡: 每 {cfg.rebalance_days} 个交易日
    ─────────────────────────────────────────
    """)

    # Step 1 - 数据获取
    print()
    raw_data = fetch_all_data(cfg)

    # Step 2 - 股票筛选
    print()
    screened = screen_stocks(raw_data, cfg)
    if screened.empty:
        print("\n⚠️  无股票通过筛选，退出。")
        return

    summary = get_screener_summary(screened)
    print(f"\n【筛选结果摘要】")
    print(f"  入选: {summary['count']} 只")
    print(f"  均价: {summary['avg_price']} 元")
    print(f"  平均市值: {summary['avg_market_cap']} 亿")
    print(f"  行业分布 Top5:")
    for ind, cnt in sorted(summary['industries'].items(),
                            key=lambda x: -x[1])[:5]:
        print(f"    - {ind}: {cnt} 只")

    # Step 3 - 特征工程
    print()
    X_df, X_scaled, scaler = build_feature_matrix(screened, cfg)

    # Step 4 - 聚类分析
    print()
    labels, cluster_report = run_clustering(X_scaled, screened, cfg)

    # Step 5 - 最优聚类选股
    print()
    selected, reason = select_best_cluster(screened, labels, cfg)
    if selected.empty:
        print("\n⚠️  未选出最佳聚类，退出。")
        return

    # 打印选中的股票列表
    print(f"\n【选中股票 - Top {min(10, len(selected))}】")
    print(f"  {'代码':>8s} {'名称':>10s} {'价格':>6s} {'PE':>6s} {'PB':>6s} {'股息率':>6s} {'波动率':>6s}")
    print(f"  {'-'*52}")
    for _, row in selected.head(10).iterrows():
        print(f"  {row['code']:>8s} {row['name']:>10s} "
              f"{row.get('current_price',0):>6.2f} "
              f"{row.get('pe_ttm',0):>6.1f} "
              f"{row.get('pb',0):>6.2f} "
              f"{row.get('dividend_yield',0)*100:>6.2f} "
              f"{row.get('volatility_20d',0):>6.3f}")

    if args.mode == "analyze":
        print(f"\n✅ 分析完成。共选中 {len(selected)} 只国资低价股。")
        print(f"  选股逻辑: {reason}")
        return

    # Step 6 - 回测
    print()
    result = run_backtest(selected, cfg)

    # 最终总结
    print(f"\n{'='*50}")
    print(f"【最终总结】")
    print(f"{'='*50}")
    if result.summary:
        s = result.summary
        print(f"  {'初始资金':>12s}: {s.get('initial_capital',0):>10,.0f} 元")
        print(f"  {'最终资产':>12s}: {s.get('final_value',0):>10,.0f} 元")
        print(f"  {'总收益率':>12s}: {s.get('total_return',0):>9.2f}%")
        print(f"  {'年化收益':>12s}: {s.get('annual_return',0):>9.2f}%")
        print(f"  {'最大回撤':>12s}: {s.get('max_drawdown',0):>9.2f}%")
        print(f"  {'夏普比率':>12s}: {s.get('sharpe_ratio',0):>9.2f}")
        print(f"  {'交易次数':>12s}: {s.get('total_trades',0):>10} 笔")
        print(f"  {'最终持仓':>12s}: {s.get('final_positions',0):>10} 只")

    if result.summary.get("total_return", 0) > 0:
        print(f"\n✅ 策略盈利！年化 {result.summary.get('annual_return',0):.1f}%")
    else:
        print(f"\n⚠️  策略亏损，建议调整参数或更换聚类方法")

    print(f"\n💡 建议:")
    print(f"   1. 尝试不同聚类方法: --cluster dbscan / gmm / agglomerative")
    print(f"   2. 调整聚类数: --k 3~8")
    print(f"   3. 调整筛选条件: --price 8  (选更低价的)")
    print(f"   4. 调整再平衡周期: --rebalance 10 / 40")
    print(f"📊 详细交易记录已保存在 trades 变量中")


if __name__ == "__main__":
    main()
