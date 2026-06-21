"""
聚类算法模块
核心：将股票按多维特征聚类，选出最优聚类作为投资池
"""
import numpy as np
import pandas as pd
from typing import Tuple, List, Optional, Dict

from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering
from sklearn.mixture import GaussianMixture
from sklearn.metrics import silhouette_score, calinski_harabasz_score
from sklearn.decomposition import PCA

from config import Config


def run_clustering(
    X_scaled: np.ndarray,
    df_original: pd.DataFrame,
    cfg: Config,
) -> Tuple[np.ndarray, dict]:
    """
    执行聚类，返回 (labels, 聚类报告)
    支持方法: kmeans, dbscan, gmm, agglomerative
    """
    print("=" * 50)
    print("【聚类分析阶段】")
    print(f"  方法: {cfg.cluster_method}")
    print(f"  数据: {X_scaled.shape[0]} 个样本, {X_scaled.shape[1]} 个特征")
    print("=" * 50)

    labels = None
    report = {}

    if cfg.cluster_method == "kmeans":
        labels, report = _kmeans_cluster(X_scaled, df_original, cfg)
    elif cfg.cluster_method == "dbscan":
        labels, report = _dbscan_cluster(X_scaled, df_original, cfg)
    elif cfg.cluster_method == "gmm":
        labels, report = _gmm_cluster(X_scaled, df_original, cfg)
    elif cfg.cluster_method == "agglomerative":
        labels, report = _agglo_cluster(X_scaled, df_original, cfg)
    else:
        print(f"  ❌ 未知聚类方法: {cfg.cluster_method}，使用 KMeans")
        labels, report = _kmeans_cluster(X_scaled, df_original, cfg)

    # 添加聚类质量评估
    unique_labels = set(labels) - {-1}
    if len(unique_labels) > 1:
        mask = labels != -1
        if mask.sum() > 1:
            try:
                report["silhouette"] = round(
                    silhouette_score(X_scaled[mask], labels[mask]), 4
                )
                report["calinski_harabasz"] = round(
                    calinski_harabasz_score(X_scaled[mask], labels[mask]), 2
                )
                print(f"  Silhouette Score: {report['silhouette']}")
                print(f"  Calinski-Harabasz Score: {report['calinski_harabasz']}")
            except Exception:
                pass

    # PCA 可视化降维数据
    if X_scaled.shape[1] > 2:
        pca = PCA(n_components=2, random_state=cfg.random_state)
        coords = pca.fit_transform(X_scaled)
        report["pca_coords"] = coords
        report["pca_var_ratio"] = pca.explained_variance_ratio_.tolist()
        print(f"  PCA 前2维方差解释比: {report['pca_var_ratio']}")
    else:
        report["pca_coords"] = X_scaled

    return labels, report


def _kmeans_cluster(
    X: np.ndarray, df: pd.DataFrame, cfg: Config
) -> Tuple[np.ndarray, dict]:
    """KMeans 聚类 + 自动调优"""
    # 用肘部法则评估最佳 K
    inertia_values = []
    best_k = cfg.n_clusters

    if cfg.n_clusters <= 1:
        # 自动选择 K（3~10 范围内）
        K_range = range(3, min(11, len(X)))
        for k in K_range:
            km = KMeans(n_clusters=k, n_init=10,
                        random_state=cfg.random_state)
            km.fit(X)
            inertia_values.append(km.inertia_)

        # 用二阶差分找拐点
        if len(inertia_values) >= 4:
            diffs = np.diff(inertia_values)
            diffs2 = np.diff(diffs)
            best_k = K_range[np.argmin(diffs2) + 1] \
                if np.min(diffs2) < 0 else K_range[0]
        else:
            best_k = 5

    print(f"  聚类数 K = {best_k}")

    model = KMeans(n_clusters=best_k, n_init=10,
                   random_state=cfg.random_state)
    labels = model.fit_predict(X)

    # 聚类分析
    report = {
        "model": "KMeans",
        "n_clusters": best_k,
        "inertia": round(model.inertia_, 2),
        "cluster_sizes": _cluster_sizes(labels),
        "cluster_centers": model.cluster_centers_,
    }

    df["cluster"] = labels
    _print_cluster_profiles(df, labels)

    return labels, report


def _dbscan_cluster(
    X: np.ndarray, df: pd.DataFrame, cfg: Config
) -> Tuple[np.ndarray, dict]:
    """DBSCAN 聚类"""
    model = DBSCAN(eps=cfg.dbscan_eps, min_samples=cfg.dbscan_min_samples)
    labels = model.fit_predict(X)

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = list(labels).count(-1)

    report = {
        "model": "DBSCAN",
        "n_clusters": n_clusters,
        "noise_points": n_noise,
        "cluster_sizes": _cluster_sizes(labels),
    }

    df["cluster"] = labels
    print(f"  聚类数: {n_clusters}, 噪声点: {n_noise}")
    _print_cluster_profiles(df, labels)

    return labels, report


def _gmm_cluster(
    X: np.ndarray, df: pd.DataFrame, cfg: Config
) -> Tuple[np.ndarray, dict]:
    """高斯混合模型聚类（软聚类）"""
    n = cfg.n_clusters if cfg.n_clusters > 1 else 5
    model = GaussianMixture(n_components=n, random_state=cfg.random_state)
    labels = model.fit_predict(X)
    probs = model.predict_proba(X)

    report = {
        "model": "GMM",
        "n_components": n,
        "aic": round(model.aic(X), 2),
        "bic": round(model.bic(X), 2),
        "cluster_sizes": _cluster_sizes(labels),
    }

    df["cluster"] = labels
    df["cluster_prob"] = probs.max(axis=1)
    _print_cluster_profiles(df, labels)

    return labels, report


def _agglo_cluster(
    X: np.ndarray, df: pd.DataFrame, cfg: Config
) -> Tuple[np.ndarray, dict]:
    """层次聚类"""
    n = cfg.n_clusters if cfg.n_clusters > 1 else 5
    model = AgglomerativeClustering(n_clusters=n)
    labels = model.fit_predict(X)

    report = {
        "model": "Agglomerative",
        "n_clusters": n,
        "cluster_sizes": _cluster_sizes(labels),
    }

    df["cluster"] = labels
    _print_cluster_profiles(df, labels)

    return labels, report


# ──────────────────────────────────────────────
# 选股策略：从聚类结果中选出"最优聚类"
# ──────────────────────────────────────────────
def select_best_cluster(
    df: pd.DataFrame,
    labels: np.ndarray,
    cfg: Config,
) -> Tuple[pd.DataFrame, str]:
    """
    从聚类结果中选出最佳投资组合：
    策略：选择 "低估值 + 高股息 + 低波动" 特征的聚类
    返回 (选中的股票 DataFrame, 选择理由)
    """
    if "cluster" not in df.columns:
        df["cluster"] = labels

    # 计算每个聚类的综合评分
    cluster_scores = {}
    for c in sorted(df["cluster"].unique()):
        if c == -1:
            continue  # 跳过 DBSCAN 噪声点
        sub = df[df["cluster"] == c]
        if len(sub) < 2:
            continue

        # 评分维度（越小越好）
        avg_pe = sub["pe_ttm"].median()
        avg_pb = sub["pb"].median()
        avg_vol = sub["volatility_20d"].median()
        avg_div = sub["dividend_yield"].median()  # 越大越好

        # 综合评分（加权）
        # 低 PE + 低 PB + 低波动 + 高股息
        score = (
            0.30 * _norm_score(avg_pe, higher_better=False)
            + 0.20 * _norm_score(avg_pb, higher_better=False)
            + 0.20 * _norm_score(avg_vol, higher_better=False)
            + 0.30 * _norm_score(avg_div, higher_better=True)
        )
        cluster_scores[c] = {
            "score": round(score, 4),
            "count": len(sub),
            "avg_pe": round(avg_pe, 2),
            "avg_pb": round(avg_pb, 2),
            "avg_vol": round(avg_vol, 3),
            "avg_div": round(avg_div, 4),
        }

    if not cluster_scores:
        print("  ❌ 无有效聚类可评分")
        return pd.DataFrame(), ""

    # 选评分最高的聚类
    best_cluster = max(cluster_scores, key=lambda k: cluster_scores[k]["score"])
    best_info = cluster_scores[best_cluster]
    selected = df[df["cluster"] == best_cluster].copy()

    print(f"\n【最佳聚类选择】")
    print(f"  选中的聚类: #{best_cluster}")
    print(f"  评分: {best_info['score']}")
    print(f"  股票数: {best_info['count']}")
    print(f"  中位数 PE: {best_info['avg_pe']}")
    print(f"  中位数 PB: {best_info['avg_pb']}")
    print(f"  中位数波动率: {best_info['avg_vol']}")
    print(f"  中位数股息率: {best_info['avg_div']}%")

    reason = (
        f"选中聚类 #{best_cluster}（评分 {best_info['score']}）: "
        f"PE={best_info['avg_pe']}, PB={best_info['avg_pb']}, "
        f"波动={best_info['avg_vol']}, 股息={best_info['avg_div']}%"
    )

    return selected, reason


def _norm_score(value: float, higher_better: bool = True) -> float:
    """将值归一化为 0~1 评分"""
    # 越界截断
    value = max(0.01, min(value, 100))
    if higher_better:
        return min(1.0, value / 10.0)
    else:
        return max(0.0, 1.0 - value / 50.0)


def _cluster_sizes(labels: np.ndarray) -> Dict:
    return {int(k): int(v) for k, v in zip(*np.unique(labels, return_counts=True))}


def _print_cluster_profiles(df: pd.DataFrame, labels: np.ndarray):
    """打印每个聚类的特征画像"""
    print(f"\n  聚类画像:")
    print(f"  {'聚 类':>8s} {'数量':>6s} {'中位PE':>8s} {'中位PB':>8s} {'中位股息':>8s} {'中位波动':>8s} {'中位ROE':>8s}")
    print(f"  {'-'*54}")
    for c in sorted(set(labels)):
        sub = df[labels == c]
        if c == -1:
            label = "噪声"
        else:
            label = f"#{c}"
        print(f"  {label:>8s} {len(sub):>6d} "
              f"{sub['pe_ttm'].median():>8.1f} "
              f"{sub['pb'].median():>8.2f} "
              f"{sub['dividend_yield'].median()*100:>8.2f} "
              f"{sub['volatility_20d'].median():>8.3f} "
              f"{sub['roe'].median():>8.1f}")
