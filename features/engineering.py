"""
特征工程模块
对筛选后的股票计算统一特征矩阵，供聚类算法使用
"""
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, RobustScaler
from typing import List, Tuple, Optional

from config import Config


def build_feature_matrix(
    df: pd.DataFrame,
    cfg: Config,
    scaler_type: str = "standard",
) -> Tuple[pd.DataFrame, np.ndarray, Optional[object]]:
    """
    构建特征矩阵 X，返回 (DataFrame, numpy_array, scaler)
    特征包括：估值、成长性、质量、波动率等
    """
    print("=" * 50)
    print("【特征工程阶段】")
    print("=" * 50)

    features = cfg.feature_list
    available = [f for f in features if f in df.columns]
    missing = [f for f in features if f not in df.columns]
    if missing:
        print(f"  ⚠️ 缺失特征（将填充默认值）: {missing}")
        for m in missing:
            df[m] = _default_value(m)

    X_df = df[available].copy()

    # 处理无穷值和缺失值
    X_df = X_df.replace([np.inf, -np.inf], np.nan)
    nan_counts = X_df.isna().sum()
    if nan_counts.sum() > 0:
        print(f"  缺失值填充:")
        for col, cnt in nan_counts[nan_counts > 0].items():
            print(f"    - {col}: {cnt} 行")
        X_df = X_df.fillna(X_df.median())

    # 异常值截断（MAD 方法，更鲁棒）
    for col in X_df.columns:
        med = X_df[col].median()
        mad = (X_df[col] - med).abs().median() * 1.4826  # 正态修正
        if mad > 0:
            lower = med - 5 * mad
            upper = med + 5 * mad
            X_df[col] = X_df[col].clip(lower, upper)

    # 标准化
    if scaler_type == "standard":
        scaler = StandardScaler()
    elif scaler_type == "robust":
        scaler = RobustScaler()
    else:
        scaler = StandardScaler()

    X_scaled = scaler.fit_transform(X_df)
    X_scaled = np.nan_to_num(X_scaled, nan=0.0)

    print(f"  ✅ 特征矩阵: {X_scaled.shape[0]} 行 × {X_scaled.shape[1]} 列")
    print(f"  特征列表: {available}")

    return X_df, X_scaled, scaler


def _default_value(feature: str) -> float:
    """缺失特征填充默认值"""
    defaults = {
        "pe_ttm": 30.0,
        "pb": 2.0,
        "roe": 5.0,
        "dividend_yield": 0.01,
        "revenue_growth": 0.0,
        "profit_growth": 0.0,
        "volatility_20d": 0.3,
        "turnover_rate": 2.0,
        "market_cap": 5e9,
        "volume_ratio": 1.0,
        "gross_margin": 30.0,
        "debt_ratio": 50.0,
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
        }
    return importance
