"""
量化聚类选股系统 - 配置模块
"""
from dataclasses import dataclass, field
from typing import List

@dataclass
class Config:
    # === 数据配置 ===
    data_source: str = "akshare"          # akshare / baostock / local
    start_date: str = "2024-01-01"
    end_date: str = "2025-12-31"

    # === 筛选条件 ===
    max_price: float = 10.0               # 股价上限
    min_market_cap: float = 2e9           # 最低市值（2亿，过滤壳）
    soe_only: bool = True                 # 仅国资背景

    # === 聚类参数 ===
    cluster_method: str = "kmeans"        # kmeans / dbscan / hdbscan / gmm
    n_clusters: int = 5                   # KMeans 聚类数
    dbscan_eps: float = 0.5
    dbscan_min_samples: int = 5
    random_state: int = 42

    # === 选仓策略 ===
    selected_clusters: List[int] = field(default_factory=lambda: [0, 1])
    target_cluster_count: int = 10        # 每个聚类选多少只
    max_positions: int = 20               # 最大持仓数
    equal_weight: bool = True             # 等权重

    # === 风控参数 ===
    stop_loss: float = 0.08               # -8% 止损
    take_profit: float = 0.25             # +25% 止盈
    max_single_weight: float = 0.15       # 单只上限 15%
    max_position_weight: float = 0.95     # 总仓位上限 95%
    min_position_weight: float = 0.20     # 最低仓位 20%
    rebalance_days: int = 20              # 每 20 交易日再平衡

    # === 特征工程 ===
    feature_list: List[str] = field(default_factory=lambda: [
        "pe_ttm", "pb", "roe", "dividend_yield",
        "revenue_growth", "profit_growth",
        "volatility_20d", "turnover_rate",
        "market_cap", "volume_ratio",
        "gross_margin", "debt_ratio",
    ])

    # === 回测配置 ===
    initial_capital: float = 100000.0
    commission: float = 0.0003             # 万三佣金
    stamp_tax: float = 0.001               # 千一印花税（卖出）
    slippage: float = 0.002                # 滑点 0.2%
