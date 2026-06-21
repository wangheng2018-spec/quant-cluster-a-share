"""
特征工程模块
对筛选后的股票计算统一特征矩阵 + 动量因子（RSI, MACD, BIAS等）
"""
import pandas as pd
import numpy as np
from typing import List, Tuple, Optional

from sklearn.preprocessing import StandardScaler, RobustScaler

from config import Config


# ──────────────────────────────────────────────
# 动量因子计算
# ──────────────────────────────────────────────

def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """计算 RSI 指标"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(period, min_periods=period).mean()
    avg_loss = loss.rolling(period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def compute_macd(series: pd.Series) -> pd.Series:
    """计算 MACD 柱状图值"""
    ema12 = series.ewm(span=12).mean()
    ema26 = series.ewm(span=26).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9).mean()
    return macd_line - signal  # MACD 柱


def compute_bias(series: pd.Series, period: int = 5) -> pd.Series:
    """计算乖离率 (price - ma) / ma"""
    ma = series.rolling(period).mean()
    return (series - ma) / ma.replace(0, np.nan) * 100


def add_momentum_features(
    df: pd.DataFrame,
    price_col: str = "close",
    volume_col: str = "volume",
) -> pd.DataFrame:
    """
    给日线 DataFrame 添加动量特征列。
    返回最后一行（最新交易日）的特征 Series。
    """
    if df is None or len(df) < 60:
        return None

    df = df.copy().sort_values("date")
    close = df[price_col]

    # 基础动量
    df["momentum_60d"] = close.pct_change(60)
    df["momentum_20d"] = close.pct_change(20)
    df["volume_ma_ratio"] = df[volume_col] / df[volume_col].rolling(20).mean()

    # RSI
    df["rsi_14"] = compute_rsi(close, 14)

    # MACD 柱
    df["macd_hist"] = compute_macd(close)

    # 乖离率
    df["bias_5"] = compute_bias(close, 5)
    df["bias_10"] = compute_bias(close, 10)

    return df.iloc[-1:].to_dict("records")[0] if len(df) > 0 else {}


# ──────────────────────────────────────────────
# 主特征矩阵构建
# ──────────────────────────────────────────────

def build_feature_matrix(
    df: pd.DataFrame,
    cfg: Config,
    scaler_type: str = "standard",
) -> Tuple[pd.DataFrame, np.ndarray, Optional[object]]:
    """
    构建特征矩阵 X，返回 (DataFrame, numpy_array, scaler)
    特征包括：估值、成长性、质量、波动率、动量因子
    """
    print("=" * 50)
    print("【特征工程阶段】")
    print("=" * 50)

    df = df.copy()
    features = cfg.feature_list
    available = [f for f in features if f in df.columns]
    missing = [f for f in features if f not in df.columns]

    if missing:
        print(f"  ⚠️ 缺失特征（将填充默认值）")
        for m in missing:
            val = _default_feature_value(m)
            df[m] = val
            print(f"    + {m:20s} = {val}")

    X_df = df[available].copy()

    # 处理无穷值和缺失值
    X_df = X_df.replace([np.inf, -np.inf], np.nan)
    nan_counts = X_df.isna().sum()
    if nan_counts.sum() > 0:
        print(f"  缺失值填充:")
        for col, cnt in nan_counts[nan_counts > 0].items():
            print(f"    - {col}: {cnt} 行 → 中位数填充")
        X_df = X_df.fillna(X_df.median())

    # 异常值截断（MAD 方法，更鲁棒）
    for col in X_df.columns:
        med = X_df[col].median()
        mad = (X_df[col] - med).abs().median() * 1.4826
        if mad > 0:
            lower = med - 5 * mad
            upper = med + 5 * mad
            X_df[col] = X_df[col].clip(lower, upper)

    # 标准化
    scaler = RobustScaler() if scaler_type == "robust" else StandardScaler()
    X_scaled = scaler.fit_transform(X_df)
    X_scaled = np.nan_to_num(X_scaled, nan=0.0)

    print(f"  ✅ 特征矩阵: {X_scaled.shape[0]} 行 × {X_scaled.shape[1]} 列")
    print(f"  特征列表:")
    for f in available:
        med = X_df[f].median()
        print(f"    - {f:20s} (中位数={med:.4f})")

    return X_df, X_scaled, scaler


def _default_feature_value(feature: str) -> float:
    """缺失特征的合理默认值（模拟数据用）"""
    defaults = {
        "pe_ttm": 30.0, "pb": 2.0,
        "roe": 5.0, "dividend_yield": 0.01,
        "revenue_growth": 0.0, "profit_growth": 0.0,
        "volatility_20d": 0.3, "turnover_rate": 2.0,
        "market_cap": 5e9, "volume_ratio": 1.0,
        "gross_margin": 30.0, "debt_ratio": 50.0,
        # 动量因子默认值
        "momentum_60d": 0.05, "rsi_14": 50.0,
        "bias_5": 0.0, "macd_hist": 0.0,
        "momentum_20d": 0.02, "bias_10": 0.0,
    }
    return defaults.get(feature, 0.0)


def get_feature_importance(X_df: pd.DataFrame, labels: np.ndarray) -> dict:
    """
    通过 ANOVA F 值评估每个特征对聚类结果的区分度
    """
    from sklearn.feature_selection import f_classif
    f_scores, p_values = f_classif(X_df, labels)
    importance = {}
    for i, col in enumerate(X_df.columns):
        importance[col] = {
            "f_score": round(f_scores[i], 2),
            "p_value": round(p_values[i], 4),
            "importance": "high" if p_values[i] < 0.01
            else "medium" if p_values[i] < 0.05
            else "low",
        }
    return importance
