"""
量化聚类选股系统 - 主入口
A股国资低价股 · 聚类量化选股 + 多聚类组合 + 条件再平衡 + 回测

使用方法:
    python main.py                                  # 默认运行
    python main.py --mode backtest                  # 回测模式
    python main.py --mode analyze                   # 仅分析选股
    python main.py --auto-k                         # 自动寻优 K
    python main.py --cluster gmm --auto-k           # GMM + 自动寻优
    python main.py --top-n 2                        # 多聚类组合
    python main.py --price 8 --rebalance 10         # 低价 + 高频再平衡
    python main.py --capital 500000                 # 50万初始资金
"""
import argparse
import sys
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

from config import Config
from data.fetcher import fetch_all_data
from screening.screener import screen_stocks, get_screener_summary
from features.engineering import build_feature_matrix, get_feature_importance
from clustering.cluster import run_clustering, select_best_cluster
from backtest.engine import run_backtest


def main():
    parser = argparse.ArgumentParser(
        description="A股国资低价股 · 聚类量化选股系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  python main.py                          # 离线模拟回测
  python main.py --auto-k                 # 自动寻优 K 值
  python main.py --cluster gmm --auto-k   # GMM + 自动寻优
  python main.py --top-n 2                # 多聚类组合
  python main.py --price 8                # 筛选股价<8元
        """,
    )
    parser.add_argument("--mode", default="backtest", choices=["backtest", "analyze", "live"])
    parser.add_argument("--cluster", default="kmeans", choices=["kmeans", "dbscan", "gmm", "agglomerative"])
    parser.add_argument("--auto-k", action="store_true", default=True,
                        help="自动用 Silhouette Score 寻优 K=3~8（默认开启）")
    parser.add_argument("--no-auto-k", action="store_true", help="禁用自动 K 寻优")
    parser.add_argument("--k", type=int, default=5, help="聚类数（auto-k=False 时生效）")
    parser.add_argument("--top-n", type=int, default=1, help="多聚类组合数量（>1 启用）")
    parser.add_argument("--price", type=float, default=10.0, help="股价上限")
    parser.add_argument("--start", default="2024-01-01", help="回测开始日期")
    parser.add_argument("--end", default="", help="回测结束日期（默认今天）")
    parser.add_argument("--capital", type=float, default=100000, help="初始资金（元）")
    parser.add_argument("--top", type=int, default=20, help="最大持仓数")
    parser.add_argument("--rebalance", type=int, default=20, help="再平衡最大间隔（天）")
    parser.add_argument("--vol", type=float, default=0.22, help="市场波动率（默认0.22）")

    args = parser.parse_args()
    auto_k = args.auto_k and not args.no_auto_k

    cfg = Config(
        cluster_method=args.cluster,
        auto_k=auto_k,
        n_clusters=args.k,
        top_n_clusters=args.top_n,
        max_price=args.price,
        start_date=args.start,
        end_date=args.end if args.end else datetime.now().strftime("%Y-%m-%d"),
        initial_capital=args.capital,
        max_positions=args.top,
        rebalance_days=args.rebalance,
    )

    end_display = cfg.end_date

    # 市场状态
    from portfolio.manager import PortfolioManager
    pm = PortfolioManager(cfg)
    market_state = pm.get_market_state(args.vol)

    print(f"""

╔══════════════════════════════════════════════════════════╗
║          A股 国资低价股 · 聚类量化选股系统                ║
║       KMeans/DBSCAN/GMM · 多聚类组合 · 条件再平衡         ║
╚══════════════════════════════════════════════════════════╝

    时间区间:     {cfg.start_date} ~ {end_display}
    选股条件:     国资背景 + 股价≤{cfg.max_price}元
    聚类方法:     {cfg.cluster_method.upper()}
    自动寻优:     {'✅ 开启 (K=3~8)' if cfg.auto_k else '❌ 关闭 (K={})'.format(cfg.n_clusters)}
    多聚类组合:   {'✅ Top-{}'.format(cfg.top_n_clusters) if cfg.top_n_clusters > 1 else '❌ 单聚类'}
    初始资金:     {cfg.initial_capital:,.0f} 元
    最大持仓:     {cfg.max_positions} 只
    再平衡:       条件触发（最{cfg.rebalance_days}天 / 回撤>{cfg.rebalance_max_drawdown*100:.0f}%）
    市场状态:     {market_state} (波动率={args.vol})
    风控:         -{cfg.stop_loss*100:.0f}%止损 / +{cfg.take_profit*100:.0f}%止盈
    ─────────────────────────────────────────
    """)

    # Step 1 - 数据
    print()
    raw_data = fetch_all_data(cfg)

    # Step 2 - 筛选
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
    for ind, cnt in sorted(summary['industries'].items(), key=lambda x: -x[1])[:5]:
        print(f"    - {ind}: {cnt} 只")

    # Step 3 - 特征
    print()
    X_df, X_scaled, scaler = build_feature_matrix(screened, cfg)

    # Step 4 - 聚类
    print()
    labels, cluster_report = run_clustering(X_scaled, screened, cfg)

    # Step 5 - 选股
    print()
    selected, reason = select_best_cluster(screened, labels, cfg)
    if selected.empty:
        print("\n⚠️  未选出股票，退出。")
        return

    # 打印选中股票
    print(f"\n【选中股票 - Top {min(10, len(selected))}】")
    print(f"  {'代码':>8s} {'名称':>10s} {'价格':>6s} {'PE':>6s} {'PB':>6s} "
          f"{'股息':>6s} {'波动':>6s} {'RSI':>6s} {'聚类':>4s}")
    print(f"  {'-'*60}")
    for _, row in selected.head(10).iterrows():
        print(f"  {row['code']:>8s} {row['name']:>10s} "
              f"{row.get('current_price',0):>6.2f} "
              f"{row.get('pe_ttm',0):>6.1f} "
              f"{row.get('pb',0):>6.2f} "
              f"{row.get('dividend_yield',0)*100:>6.2f} "
              f"{row.get('volatility_20d',0):>6.3f} "
              f"{row.get('rsi_14',50):>6.1f} "
              f"{row.get('cluster','?'):>4s}")

    # 特征重要性
    print(f"\n【特征重要性分析】")
    try:
        importance = get_feature_importance(X_df, labels)
        ranked = sorted(importance.items(), key=lambda x: -x[1]["f_score"])
        for feat, info in ranked[:8]:
            icon = "⭐" if info["importance"] == "high" else "📊" if info["importance"] == "medium" else "📉"
            print(f"  {icon} {feat:20s} F={info['f_score']:>8.2f}  p={info['p_value']:.4f}  [{info['importance']}]")
    except Exception as e:
        print(f"  (特征重要性计算跳过: {e})")

    if args.mode == "analyze":
        print(f"\n✅ 分析完成。共选中 {len(selected)} 只国资低价股。")
        print(f"  选股逻辑: {reason}")
        print(f"  可用聚类参数调优: --cluster dbscan/gmm --k 6 --auto-k")
        return

    # Step 6 - 回测
    print()
    result = run_backtest(selected, cfg, market_volatility=args.vol)

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
        print(f"  {'胜率':>12s}: {s.get('win_rate',0):>9.1f}%")
        print(f"  {'交易次数':>12s}: {s.get('total_trades',0):>10} 笔")
        print(f"  {'最终持仓':>12s}: {s.get('final_positions',0):>10} 只")

    total_ret = result.summary.get("total_return", 0)
    if total_ret > 0:
        print(f"\n✅ 策略盈利！年化 {result.summary.get('annual_return',0):.1f}% | "
              f"夏普 {result.summary.get('sharpe_ratio',0):.2f}")
    else:
        print(f"\n⚠️  策略亏损 ({total_ret:.1f}%)，建议:")
        print(f"   • 调整聚类方法: --cluster gmm / dbscan")
        print(f"   • 开启多聚类组合: --top-n 2")
        print(f"   • 调整再平衡: --rebalance 10 / 40")
        print(f"   • 放宽筛选: --price 12")


if __name__ == "__main__":
    main()
