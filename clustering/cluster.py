"""
聚类算法模块
核心：将股票按多维特征聚类，选出最优聚类作为投资池
支持自动 K 寻优（Silhouette Score）、多聚类组合
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
    auto_k=True 时自动用 Silhouette Score 寻优（仅 KMeans/GMM）
    """
    print("=" * 50)
    print("【聚类分析阶段】")
    print(f"  方法: {cfg.cluster_method.upper()}")
    print(f"  数据: {X_scaled.shape[0]} 个样本, {X_scaled.shape[1]} 个特征")
    if cfg.auto_k and cfg.cluster_method in ("kmeans", "gmm"):
        print(f"  自动寻优: K=3~8 按 Silhouette Score")
    print("=" * 50)

    df = df_original.copy()
    labels = None
    report = {}

    if cfg.cluster_method == "kmeans":
        labels, report = _kmeans_cluster(X_scaled, df, cfg)
    elif cfg.cluster_method == "dbscan":
        labels, report = _dbscan_cluster(X_scaled, df, cfg)
    elif cfg.cluster_method == "gmm":
        labels, report = _gmm_cluster(X_scaled, df, cfg)
    elif cfg.cluster_method == "agglomerative":
        labels, report = _agglo_cluster(X_scaled, df, cfg)
    else:
        print(f"  ⚠️ 未知方法 {cfg.cluster_method}，使用 KMeans")
        labels, report = _kmeans_cluster(X_scaled, df, cfg)

    # 聚类质量评估
    unique_labels = set(labels) - {-1}
    if len(unique_labels) >= 2:
        mask = labels != -1
        if mask.sum() > 1:
            try:
                sil = silhouette_score(X_scaled[mask], labels[mask])
                ch = calinski_harabasz_score(X_scaled[mask], labels[mask])
                report["silhouette"] = round(sil, 4)
                report["calinski_harabasz"] = round(ch, 2)
                print(f"  Silhouette Score:      {report['silhouette']}")
                print(f"  Calinski-Harabasz:     {report['calinski_harabasz']}")
            except Exception:
                pass

    # PCA 降维（用于可视化）
    if X_scaled.shape[1] > 2:
        pca = PCA(n_components=2, random_state=cfg.random_state)
        coords = pca.fit_transform(X_scaled)
        report["pca_coords"] = coords
        report["pca_var_ratio"] = [round(v, 4) for v in pca.explained_variance_ratio_]
        print(f"  PCA 前2维方差解释比:  {report['pca_var_ratio']}")
    else:
        report["pca_coords"] = X_scaled

    # 聚类画像
    _print_cluster_profiles(df.assign(cluster=labels), labels)

    return labels, report


# ──────────────────────────────────────────────
# 自动 K 寻优
# ──────────────────────────────────────────────
def _find_best_k(X: np.ndarray, k_range: range, method: str = "kmeans",
                 random_state: int = 42) -> Tuple[int, List[dict]]:
    """用 Silhouette Score 寻找最佳 K"""
    scores = []
    best_k, best_score = k_range[0], -1.0

    for k in k_range:
        if k >= len(X):
            continue
        if method == "kmeans":
            model = KMeans(n_clusters=k, n_init=10, random_state=random_state)
        elif method == "gmm":
            model = GaussianMixture(n_components=k, random_state=random_state)
        else:
            break

        labels = model.fit_predict(X)
        score = silhouette_score(X, labels)
        scores.append({"k": k, "silhouette": round(score, 4)})

        if score > best_score:
            best_k, best_score = k, score

    return best_k, scores


def _kmeans_cluster(
    X: np.ndarray, df: pd.DataFrame, cfg: Config
) -> Tuple[np.ndarray, dict]:
    """KMeans 聚类 + 自动调优"""
    best_k = cfg.n_clusters

    if cfg.auto_k:
        best_k, k_scores = _find_best_k(X, range(3, min(9, len(X))),
                                        "kmeans", cfg.random_state)
        print(f"\n  Silhouette Score 寻优结果:")
        print(f"  {'K':>4s} {'Silhouette':>12s}")
        for s in k_scores:
            marker = " ← best" if s["k"] == best_k else ""
            print(f"  {s['k']:>4d} {s['silhouette']:>12.4f}{marker}")

    print(f"\n  选定 K = {best_k}")

    model = KMeans(n_clusters=best_k, n_init=10, random_state=cfg.random_state)
    labels = model.fit_predict(X)

    df["cluster"] = labels
    report = {
        "model": "KMeans",
        "n_clusters": best_k,
        "inertia": round(model.inertia_, 2),
        "cluster_sizes": _cluster_sizes(labels),
        "cluster_centers": model.cluster_centers_,
    }

    return labels, report


def _dbscan_cluster(
    X: np.ndarray, df: pd.DataFrame, cfg: Config
) -> Tuple[np.ndarray, dict]:
    """DBSCAN 聚类"""
    model = DBSCAN(eps=cfg.dbscan_eps, min_samples=cfg.dbscan_min_samples)
    labels = model.fit_predict(X)

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = list(labels).count(-1)

    df["cluster"] = labels
    report = {
        "model": "DBSCAN",
        "n_clusters": n_clusters,
        "noise_points": n_noise,
        "cluster_sizes": _cluster_sizes(labels),
    }
    print(f"  聚类数: {n_clusters}, 噪声点: {n_noise}")

    return labels, report


def _gmm_cluster(
    X: np.ndarray, df: pd.DataFrame, cfg: Config
) -> Tuple[np.ndarray, dict]:
    """高斯混合模型聚类（软聚类）"""
    best_k = cfg.n_clusters

    if cfg.auto_k:
        best_k, k_scores = _find_best_k(X, range(3, min(9, len(X))),
                                        "gmm", cfg.random_state)
        print(f"\n  Silhouette Score 寻优结果:")
        print(f"  {'K':>4s} {'Silhouette':>12s}")
        for s in k_scores:
            marker = " ← best" if s["k"] == best_k else ""
            print(f"  {s['k']:>4d} {s['silhouette']:>12.4f}{marker}")

    print(f"\n  选定 K = {best_k}")
    model = GaussianMixture(n_components=best_k, random_state=cfg.random_state)
    labels = model.fit_predict(X)
    probs = model.predict_proba(X)

    df["cluster"] = labels
    df["cluster_prob"] = probs.max(axis=1)

    report = {
        "model": "GMM",
        "n_components": best_k,
        "aic": round(model.aic(X), 2),
        "bic": round(model.bic(X), 2),
        "cluster_sizes": _cluster_sizes(labels),
    }

    return labels, report


def _agglo_cluster(
    X: np.ndarray, df: pd.DataFrame, cfg: Config
) -> Tuple[np.ndarray, dict]:
    """层次聚类"""
    n = cfg.n_clusters if cfg.n_clusters > 1 else 5
    model = AgglomerativeClustering(n_clusters=n)
    labels = model.fit_predict(X)

    df["cluster"] = labels
    report = {
        "model": "Agglomerative",
        "n_clusters": n,
        "cluster_sizes": _cluster_sizes(labels),
    }

    return labels, report


# ──────────────────────────────────────────────
# 聚类评分 & 多聚类组合选股
# ──────────────────────────────────────────────

def score_clusters(df: pd.DataFrame) -> Dict[int, dict]:
    """
    对每个聚类计算综合评分。
    评分维度：低PE + 低PB + 低波动 + 高股息 + 高ROE + 正向动量
    """
    scores = {}
    for c in sorted(df["cluster"].unique()):
        if c == -1:
            continue
        sub = df[df["cluster"] == c]
        if len(sub) < 2:
            continue

        score = (
            + 0.20 * _norm_better_lower(sub["pe_ttm"].median(), 5, 40)
            + 0.15 * _norm_better_lower(sub["pb"].median(), 0.5, 5)
            + 0.15 * _norm_better_lower(sub["volatility_20d"].median(), 0.1, 0.5)
            + 0.15 * _norm_better_higher(sub["dividend_yield"].median(), 0, 0.05)
            + 0.15 * _norm_better_higher(sub["roe"].median(), -5, 30)
            + 0.10 * _norm_better_higher(sub.get("momentum_60d", sub.get("revenue_growth", 0)).median(), -0.2, 0.3)
            + 0.05 * _norm_better_lower(sub.get("debt_ratio", sub.get("pe_ttm", 50)).median(), 10, 80)
            + 0.05 * _norm_better_higher(sub.get("rsi_14", 50).median(), 20, 80)
        )

        scores[int(c)] = {
            "score": round(score, 4),
            "count": len(sub),
            "avg_pe": round(sub["pe_ttm"].median(), 2),
            "avg_pb": round(sub["pb"].median(), 2),
            "avg_vol": round(sub["volatility_20d"].median(), 3),
            "avg_div": round(sub["dividend_yield"].median(), 4),
            "avg_roe": round(sub["roe"].median(), 2),
        }

    return scores


def _norm_better_lower(value, good, bad):
    """值越小越好，归一化到 0~1"""
    return max(0.0, min(1.0, (bad - value) / (bad - good))) if bad != good else 0.5


def _norm_better_higher(value, bad, good):
    """值越大越好，归一化到 0~1"""
    return max(0.0, min(1.0, (value - bad) / (good - bad))) if good != bad else 0.5


def select_best_cluster(
    df: pd.DataFrame,
    labels: np.ndarray,
    cfg: Config,
) -> Tuple[pd.DataFrame, str]:
    """
    从聚类结果中选出最佳投资组合：
    - top_n_clusters=1: 选评分最高的单聚类
    - top_n_clusters>1: 选多个聚类组合，按评分加权分配
    """
    if "cluster" not in df.columns:
        df = df.copy()
        df["cluster"] = labels

    cluster_scores = score_clusters(df)
    if not cluster_scores:
        print("  ❌ 无有效聚类可评分")
        return pd.DataFrame(), ""

    # 按评分排序
    ranked = sorted(cluster_scores.items(), key=lambda x: -x[1]["score"])
    n_select = min(cfg.top_n_clusters, len(ranked))

    print(f"\n【聚类评分排名】")
    print(f"  {'排名':>4s} {'聚类':>6s} {'评分':>8s} {'数量':>6s} {'中位PE':>8s} {'中位PB':>8s}")
    print(f"  {'-'*44}")
    for i, (cid, info) in enumerate(ranked):
        marker = " ←" if i < n_select else ""
        print(f"  {i+1:>4d} #{cid:<5d} {info['score']:>8.4f} {info['count']:>6d}"
              f" {info['avg_pe']:>8.1f} {info['avg_pb']:>8.2f}{marker}")

    if n_select == 1:
        # 单聚类
        best_cid = ranked[0][0]
        selected = df[df["cluster"] == best_cid].copy()
        reason = (f"单聚类 #{best_cid}（评分 {cluster_scores[best_cid]['score']}）: "
                  f"PE={cluster_scores[best_cid]['avg_pe']}, "
                  f"PB={cluster_scores[best_cid]['avg_pb']}")
        print(f"\n【单聚类选择】选中聚类 #{best_cid}, 股票数 {len(selected)}")
    else:
        # 多聚类组合
        selected_clusters = [ranked[i][0] for i in range(n_select)]
        scores_sum = sum(cluster_scores[cid]["score"] for cid in selected_clusters)

        parts = []
        selected_dfs = []
        for cid in selected_clusters:
            sub = df[df["cluster"] == cid].copy()
            weight = cluster_scores[cid]["score"] / scores_sum
            n_stocks = max(2, int(cfg.max_positions * weight))
            picked = sub.head(n_stocks)
            picked["alloc_weight"] = weight / n_stocks
            selected_dfs.append(picked)
            parts.append(f"#{cid}({weight*100:.0f}%)")

        selected = pd.concat(selected_dfs, ignore_index=True).head(cfg.max_positions)
        reason = f"多聚类组合: {', '.join(parts)}"
        print(f"\n【多聚类组合】{n_select} 个聚类组合, 总股票数 {len(selected)}")

    return selected, reason


def _cluster_sizes(labels: np.ndarray) -> Dict:
    return {int(k): int(v) for k, v in zip(*np.unique(labels, return_counts=True))}


def _print_cluster_profiles(df: pd.DataFrame, labels: np.ndarray):
    """打印每个聚类的特征画像"""
    print(f"\n  聚类画像:")
    print(f"  {'聚 类':>8s} {'数量':>6s} {'中位PE':>8s} {'中位PB':>8s} {'中位股息':>8s} "
          f"{'中位波动':>8s} {'中位ROE':>8s} {'RSI':>8s}")
    print(f"  {'-'*62}")
    for c in sorted(set(labels)):
        sub = df[labels == c]
        label = "噪声" if c == -1 else f"#{c}"
        rsi_med = sub.get("rsi_14", pd.Series([50] * len(sub))).median()
        print(f"  {label:>8s} {len(sub):>6d} "
              f"{sub['pe_ttm'].median():>8.1f} "
              f"{sub['pb'].median():>8.2f} "
              f"{sub['dividend_yield'].median()*100:>8.2f} "
              f"{sub['volatility_20d'].median():>8.3f} "
              f"{sub['roe'].median():>8.1f} "
              f"{rsi_med:>8.1f}")
