"""
股票筛选器：从全市场筛选国资背景 + 低价股
"""
import pandas as pd
import numpy as np
from typing import Tuple

from data.fetcher import is_state_owned
from config import Config


def screen_stocks(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """
    筛选流程：
    1. 国资背景（actual_controller 包含国资关键词）
    2. 股价 < max_price
    3. 非 ST / *ST
    4. 市值 > min_market_cap
    5. 剔除金融行业（可选）
    """
    print("=" * 50)
    print("【筛选阶段】")
    print(f"  条件: 国资 + 股价<{cfg.max_price}元 + 非ST")
    print(f"  初始股票数: {len(df)}")
    print("=" * 50)

    filtered = df.copy()

    # 1. 国资背景筛选
    if cfg.soe_only:
        filtered["is_soe"] = filtered["actual_controller"].apply(
            lambda x: is_state_owned(str(x)) if pd.notna(x) else False
        )
        filtered = filtered[filtered["is_soe"]].copy()
        print(f"  国资背景: {len(filtered)} 只")

    # 2. 股价筛选
    if "current_price" in filtered.columns:
        filtered = filtered[filtered["current_price"] <= cfg.max_price].copy()
        print(f"  股价≤{cfg.max_price}元: {len(filtered)} 只")

    # 3. 排除 ST（根据名称判断）
    if "name" in filtered.columns:
        filtered = filtered[
            ~filtered["name"].str.contains("ST|*ST|退|SST", na=False)
        ].copy()
        print(f"  排除 ST/退市: {len(filtered)} 只")

    # 4. 市值筛选
    if "market_cap" in filtered.columns:
        filtered = filtered[filtered["market_cap"] >= cfg.min_market_cap].copy()
        print(f"  市值≥{cfg.min_market_cap/1e8:.0f}亿: {len(filtered)} 只")

    # 5. 排除金融行业（可选）
    if "industry" in filtered.columns:
        fin_keywords = ["银行", "保险", "证券", "信托", "金融"]
        before = len(filtered)
        filtered = filtered[
            ~filtered["industry"].isin(fin_keywords)
        ].copy()
        excluded = before - len(filtered)
        if excluded > 0:
            print(f"  排除金融行业: {excluded} 只")

    print(f"  ✅ 最终入选: {len(filtered)} 只")

    if filtered.empty:
        print("  ⚠️ 没有股票通过筛选，请放宽条件")

    return filtered


def get_screener_summary(df: pd.DataFrame) -> dict:
    """返回筛选统计摘要"""
    if df.empty:
        return {"count": 0}
    return {
        "count": len(df),
        "avg_price": round(df["current_price"].mean(), 2),
        "avg_market_cap": round(df["market_cap"].mean() / 1e8, 2),
        "industries": df["industry"].value_counts().to_dict(),
        "avg_pe": round(df["pe_ttm"].mean(), 2),
        "avg_pb": round(df["pb"].mean(), 2),
        "avg_dividend": round(df["dividend_yield"].mean() * 100, 2),
    }
