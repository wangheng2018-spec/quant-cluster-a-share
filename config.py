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
    cluster_method: str = "kmeans"        # kmeans / dbscan / gmm / hdbscan / agglomerative
    n_clusters: int = 5                   # KMeans 聚类数（auto_k=True 时自动寻优）
    auto_k: bool = True                   # 自动用 Silhouette Score 寻优（K=3~8）
    dbscan_eps: float = 0.5
    dbscan_min_samples: int = 5
    random_state: int = 42

    # === 多聚类组合 ===
    top_n_clusters: int = 2               # 选取评分最高的 N 个聚类组合（>1 启用多聚类）
    cluster_alloc_method: str = "score_weighted"  # equal / score_weighted

    # === 选仓策略 ===
    target_cluster_count: int = 10        # 每个聚类选多少只
    max_positions: int = 20               # 最大持仓数
    equal_weight: bool = True             # 等权重

    # === 风控参数 ===
    stop_loss: float = 0.08               # -8% 止损
    take_profit: float = 0.25             # +25% 止盈
    max_single_weight: float = 0.15       # 单只上限 15%
    max_position_weight: float = 0.95     # 总仓位上限 95%
    min_position_weight: float = 0.20     # 最低仓位 20%

    # === 再平衡（条件触发，按优先级） ===
    rebalance_days: int = 20              # 最大间隔天数
    rebalance_min_days: int = 10          # 最小间隔天数
    rebalance_max_drawdown: float = 0.05  # 组合回撤超 5% 触发
    rebalance_market_shock: float = 0.03  # 单日大盘跌超 3% 触发
    rebalance_on_cluster_change: bool = True  # 聚类结果变化时触发

    # === 市场波动阈值 ===
    vol_low: float = 0.15                 # 低波动阈值
    vol_normal: float = 0.25              # 正常波动阈值
    vol_high: float = 0.35                # 高波动阈值
    vol_extreme: float = 0.50             # 极端波动阈值

    # === 特征工程（基础+动量） ===
    feature_list: List[str] = field(default_factory=lambda: [
        # 估值
        "pe_ttm", "pb",
        # 质量
        "roe", "gross_margin", "debt_ratio",
        # 收益
        "dividend_yield", "revenue_growth", "profit_growth",
        # 技术/动量
        "volatility_20d", "turnover_rate", "volume_ratio",
        "market_cap",
        # 新增动量因子（离线模拟时默认有值）
        "momentum_60d", "rsi_14", "bias_5",
    ])

    # === 回测配置 ===
    initial_capital: float = 100000.0
    commission: float = 0.0003             # 万三佣金
    stamp_tax: float = 0.001               # 千一印花税（卖出）
    slippage: float = 0.002                # 滑点 0.2%
