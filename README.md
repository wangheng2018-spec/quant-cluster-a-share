# 量化聚类选股系统

**A 股国资低价股 · 聚类量化选股 + 动态仓位管理 + 回测**

> 基于 KMeans / DBSCAN / GMM 聚类算法，从 A 股全市场筛选**国资背景 + 股价低于 10 元**的股票，通过聚类找出"低估值、高股息、低波动"的最优投资组合，配合动态仓位管理和定期再平衡，实现长期稳定盈利。

---

## 核心策略

### 📊 选股逻辑

```
全市场 A 股
  ├─ 国资背景（国资委 / 国企 / 地方政府控制）
  ├─ 股价 ≤ 10 元
  ├─ 非 ST / 退市
  └─ 市值 ≥ 2 亿
        ↓
  特征矩阵（PE / PB / ROE / 股息率 / 波动率 / 增长率…）
        ↓
  KMeans / DBSCAN / GMM 聚类
        ↓
  选择"低估值 + 高股息 + 低波动"的最优聚类
        ↓
  等权重建仓（最大 20 只）
```

### 📈 仓位管理

- **动态总仓位**: 根据市场波动率自动调整（高波动减仓，低波动加仓）
- **等权重分配**: 每只股票等权重，分散风险
- -8% 止损 / +25% 分批止盈
- **定期再平衡**: 每 20 个交易日重新评估
- **最大单只权重**: ≤ 15%

### 🧠 聚类算法支持

| 算法 | 特点 | 适用场景 |
|------|------|----------|
| **KMeans** | 指定 K 值，快速稳定 | 默认推荐 |
| **DBSCAN** | 自动发现聚类数，识别噪声 | 数据分布不均匀 |
| **GMM** | 软聚类，概率输出 | 需要置信度评分 |
| **Agglomerative** | 层次聚类，树状可视化 | 探索性分析 |

---

## 安装

```bash
# 1. 克隆
git clone https://github.com/wangheng2018-spec/quant-cluster-a-share.git
cd quant-cluster-a-share

# 2. 创建虚拟环境（推荐）
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 安装 A 股数据源（可选，离线模式自动用模拟数据）
pip install akshare baostock
```

---

## 快速运行

```bash
# 默认模式：离线模拟 + 聚类选股 + 回测
python main.py

# 仅分析选股（不回测）
python main.py --mode analyze

# 完整回测
python main.py --mode backtest

# Windows
run_quant.bat
```

### 参数调优

```bash
# 使用 DBSCAN 聚类
python main.py --cluster dbscan

# 使用 GMM 并指定 6 个聚类
python main.py --cluster gmm --k 6

# 筛选更低价股票（≤ 8 元）
python main.py --price 8

# 调整再平衡周期（每 10 天）
python main.py --rebalance 10

# 更多持仓（最大 30 只）
python main.py --top 30

# 设置初始资金
python main.py --capital 500000

# 自定义回测区间
python main.py --start 2023-01-01 --end 2024-12-31

# 完整示例
python main.py --cluster kmeans --k 5 --price 10 --top 20 --capital 100000 --rebalance 20
```

---

## 项目结构

```
quant_cluster/
├── main.py                    # 主入口
├── config.py                  # 配置模块
├── requirements.txt           # Python 依赖
├── run_quant.bat              # Windows 一键运行
│
├── data/
│   └── fetcher.py             # 数据获取（akshare/baostock/离线模拟）
│
├── screening/
│   └── screener.py            # 国资 + 低价股筛选器
│
├── features/
│   └── engineering.py         # 特征工程（标准化/异常值处理）
│
├── clustering/
│   └── cluster.py             # 聚类算法 + 最优聚类选择
│
├── portfolio/
│   └── manager.py             # 仓位管理 + 风控 + 交易执行
│
├── backtest/
│   └── engine.py              # 回测引擎
│
└── examples/                  # 示例数据
```

---

## 回测报告解读

```
【绩效报告】
  初始资本     100,000.00 元
  最终资产     115,432.50 元
  总收益率        15.43 %
  年化收益         8.12 %
  最大回撤         6.34 %
  夏普比率         1.23
  交易次数        42 笔
  最终持仓        18 只
```

| 指标 | 说明 | 优秀标准 |
|------|------|----------|
| **总收益率** | 回测期内总收益 | > 10% |
| **年化收益** | 年化收益率 | > 6% |
| **最大回撤** | 从峰值到谷底最大跌幅 | < 20% |
| **夏普比率** | 风险调整后收益 | > 1.0 |

---

## 部署到 Ubuntu 服务器

```bash
# 1. 更新系统
sudo apt update && sudo apt upgrade -y

# 2. 安装 Python
sudo apt install python3 python3-pip python3-venv -y

# 3. 克隆项目
git clone https://github.com/wangheng2018-spec/quant-cluster-a-share.git
cd quant-cluster-a-share

# 4. 设置定时任务（每周运行一次）
crontab -e
# 添加：每周一 9:00 运行
0 9 * * 1 cd /path/to/quant-cluster-a-share && python3 main.py --mode analyze >> report.log 2>&1
```

---

## 策略优化建议

1. **聚类数调优**: 尝试 K=3~8，用 Silhouette Score 评估
2. **特征工程**: 可加入动量因子、资金流等
3. **再平衡频率**: 10~40 天之间测试最佳值
4. **市场波动阈值**: 根据 A 股历史波动率调整
5. **多聚类组合**: 不只选最优聚类，可组合 2~3 个聚类
6. **实盘对接**: 对接 QMT / PTrade 等券商 API 实现自动化交易
