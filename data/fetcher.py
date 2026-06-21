"""
数据获取模块
支持 akshare / baostock / 本地 CSV 三种数据源
"""
import os
import time
import csv
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from config import Config


# ──────────────────────────────────────────────
# 工具：自动尝试导入数据源
# ──────────────────────────────────────────────
def _import_akshare():
    try:
        import akshare as ak
        return ak
    except ImportError:
        print("akshare not installed: pip install akshare")
        return None


def _import_baostock():
    try:
        import baostock as bs
        return bs
    except ImportError:
        print("baostock not installed: pip install baostock")
        return None


# ──────────────────────────────────────────────
# 1. 获取 A 股股票列表
# ──────────────────────────────────────────────
def get_stock_list(cfg: Config) -> pd.DataFrame:
    """
    返回 A 股全量股票列表。
    列：code, name, industry, list_date, total_mv, is_st, actual_controller
    """
    df = None

    if cfg.data_source == "akshare":
        ak = _import_akshare()
        if ak:
            df = ak.stock_info_a_code_name()
            # 补充实际控制人信息（国资判断所需）
            try:
                info = ak.stock_info_a_detail()
                df = df.merge(info, on="code", how="left")
            except Exception:
                pass

    elif cfg.data_source == "baostock":
        bs = _import_baostock()
        if bs:
            bs.login()
            rs = bs.query_stock_basic()
            records = []
            while rs.next():
                row = rs.get_row_data()
                records.append({
                    "code": row[0],
                    "name": row[1],
                    "status": row[2],
                    "ipo_date": row[3],
                    "type": row[4],
                })
            bs.logout()
            df = pd.DataFrame(records)

    # fallback：提供模拟数据用于演示
    if df is None or df.empty:
        print("[WARN] 网络数据源不可用，生成模拟股票列表用作演示")
        df = _mock_stock_list()

    return df


# ──────────────────────────────────────────────
# 2. 获取日线行情
# ──────────────────────────────────────────────
def get_daily_data(
    code: str,
    start: str,
    end: str,
    cfg: Config,
) -> Optional[pd.DataFrame]:
    """返回日线行情，列: date, open, high, low, close, volume, amount"""
    df = None

    if cfg.data_source == "akshare":
        ak = _import_akshare()
        if ak:
            try:
                # 适配不同格式代码
                symbol = f"{code}.SH" if code.startswith("6") else f"{code}.SZ"
                if code.startswith("8") or code.startswith("4"):
                    symbol = f"{code}.BJ"
                df = ak.stock_zh_a_hist(symbol=symbol, period="daily",
                                         start_date=start, end_date=end, adjust="qfq")
                rename = {"日期": "date", "开盘": "open", "最高": "high",
                          "最低": "low", "收盘": "close", "成交量": "volume",
                          "成交额": "amount"}
                df = df.rename(columns=rename)
                df["date"] = pd.to_datetime(df["date"])
            except Exception as e:
                print(f"[WARN] 获取 {code} 失败: {e}")

    elif cfg.data_source == "baostock":
        bs = _import_baostock()
        if bs:
            bs.login()
            rs = bs.query_history_k_data_plus(
                code,
                "date,open,high,low,close,volume,amount",
                start_date=start.replace("-", ""),
                end_date=end.replace("-", ""),
                frequency="d", adjustflag="3",
            )
            rows = []
            while rs.next():
                rows.append(rs.get_row_data())
            bs.logout()
            if rows:
                df = pd.DataFrame(rows, columns=["date","open","high","low","close","volume","amount"])
                df["date"] = pd.to_datetime(df["date"])
                for c in ["open","high","low","close","volume","amount"]:
                    df[c] = pd.to_numeric(df[c], errors="coerce")

    if df is None or df.empty:
        print(f"[WARN] 获取 {code} 日线失败，返回模拟数据")
        df = _mock_daily(code, start, end)

    return df


# ──────────────────────────────────────────────
# 3. 获取财务指标（PE、PB、ROE 等）
# ──────────────────────────────────────────────
def get_financials(code: str, cfg: Config) -> dict:
    """返回财务指标字典"""
    if cfg.data_source == "akshare":
        ak = _import_akshare()
        if ak:
            try:
                fin = ak.stock_financial_abstract(code)
                if fin is not None and not fin.empty:
                    latest = fin.iloc[0].to_dict()
                    return {k: _to_float(v) for k, v in latest.items()}
            except Exception as e:
                print(f"[WARN] 获取 {code} 财务数据失败: {e}")
    return {}


def _to_float(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return np.nan


# ──────────────────────────────────────────────
# 4. 判断是否国资背景（实际控制人含关键词）
# ──────────────────────────────────────────────
def is_state_owned(controller: str) -> bool:
    if not controller or not isinstance(controller, str):
        return False
    keywords = [
        "国务院", "国资委", "国资", "地方", "国有", "国营",
        "中央", "国家", "财政部", "发改委", "省", "市",
        "人民政府", "控股集团", "国投", "国控",
        "State-owned", "SOE",
    ]
    return any(k in controller for k in keywords)


# ──────────────────────────────────────────────
# 5. 模拟数据（离线演示用）
# ──────────────────────────────────────────────
def _mock_stock_list() -> pd.DataFrame:
    np.random.seed(42)
    stocks = []
    soe_controllers = [
        "国务院国资委", "省国有资产监督管理委员会",
        "市国有资产监督管理委员会", "财政部", "中央企业",
        "中国国投控股", "国控集团",
    ]
    private_controllers = [
        "张三", "个人", "投资有限公司", "科技集团",
    ]
    for i in range(200):
        code = f"{np.random.choice(['600','000','002','300','301','688','8'])}{np.random.randint(10000,99999)}"
        price = round(np.random.uniform(3, 25), 2)
        is_soe = np.random.random() < 0.45
        controller = np.random.choice(soe_controllers) if is_soe else np.random.choice(private_controllers)
        stocks.append({
            "code": code,
            "name": f"股票{chr(65+i%26)}{i}",
            "industry": np.random.choice(["银行","地产","医药","科技","消费","制造","能源","公用事业","交通"]),
            "current_price": price,
            "market_cap": round(np.random.uniform(1e9, 1e11), 0),
            "actual_controller": controller,
            "pe_ttm": round(np.random.uniform(5, 60), 2),
            "pb": round(np.random.uniform(0.3, 5), 2),
            "roe": round(np.random.uniform(-10, 30), 2),
            "dividend_yield": round(np.random.uniform(0, 0.06), 4),
            "revenue_growth": round(np.random.uniform(-20, 40), 2),
            "profit_growth": round(np.random.uniform(-30, 60), 2),
            "volatility_20d": round(np.random.uniform(0.1, 0.5), 3),
            "turnover_rate": round(np.random.uniform(0.1, 10), 2),
            "volume_ratio": round(np.random.uniform(0.3, 3), 2),
            "gross_margin": round(np.random.uniform(10, 90), 2),
            "debt_ratio": round(np.random.uniform(10, 80), 2),
        })
    return pd.DataFrame(stocks)


def _mock_daily(code: str, start: str, end: str) -> pd.DataFrame:
    np.random.seed(abs(hash(code)) % 2**31)
    dates = pd.date_range(start, end, freq="B")  # 仅交易日
    n = len(dates)
    base = np.random.uniform(5, 15)
    changes = np.random.randn(n) * 0.02 + 0.0003
    prices = base * (1 + np.cumsum(changes))
    prices = np.maximum(prices, 1.0)
    df = pd.DataFrame({
        "date": dates[:n],
        "open": prices * (1 + np.random.randn(n) * 0.003),
        "high": prices * (1 + abs(np.random.randn(n)) * 0.008),
        "low": prices * (1 - abs(np.random.randn(n)) * 0.008),
        "close": prices,
        "volume": np.random.randint(100000, 10000000, n),
        "amount": prices * np.random.randint(100000, 10000000, n),
    })
    for c in ["open","high","low"]:
        df[c] = df[c].clip(lower=0.5)
    return df


# ──────────────────────────────────────────────
# 统一数据获取接口
# ──────────────────────────────────────────────
def fetch_all_data(cfg: Config) -> pd.DataFrame:
    """
    主入口：获取全部股票列表 + 行情 + 财务数据，返回整合 DataFrame。
    离线模式使用模拟数据。
    """
    print("=" * 50)
    print("【数据获取阶段】")
    print(f"  数据源: {cfg.data_source}")
    print(f"  时间: {cfg.start_date} ~ {cfg.end_date}")
    print("=" * 50)

    stocks = get_stock_list(cfg)
    print(f"  获取股票列表: {len(stocks)} 只")

    # 模拟模式下财务指标已经包含，直接返回
    if cfg.data_source != "local" and cfg.data_source != "akshare":
        pass  # 模拟数据已有指标

    # 确保每只股票有日线数据用于回测
    stocks["daily_data"] = None
    sample_codes = stocks["code"].iloc[:5].tolist()
    print(f"  抽样获取日线行情（前 5 只）...")
    for code in sample_codes:
        daily = get_daily_data(code, cfg.start_date, cfg.end_date, cfg)
        stocks.loc[stocks["code"] == code, "daily_data"] = [daily]
    print(f"  数据准备完成")

    return stocks
