# 量化聚类选股系统

**A股国资低价股 · 聚类量化选股 + 条件再平衡 + 多聚类组合 + 回测**

> 基于 KMeans / DBSCAN / GMM 聚类算法，从 A 股全市场筛选**国资背景 + 股价低于 10 元**的股票，通过**多维度评分**选出最佳聚类组合，配合**条件触发再平衡**和**市场波动自适应仓位**，实现长期稳定盈利。

---

## 核心策略

### 📊 选股流程

```
全市场 A 股
  ├─ 国资背景（国资委 / 国企 / 地方政府控制）
  ├─ 股价 ≤ 10 元
  ├─ 非 ST / 退市
  └─ 市值 ≥ 2 亿
        ↓
  特征矩阵（12+ 维度）
  ├─ 估值: PE / PB
  ├─ 质量: ROE / 毛利率 / 负债率
  ├─ 收益: 股息率 / 营收增长 / 利润增长
  └─ 动量: RSI / MACD / 乖离率 / 60日动量
        ↓
  聚类算法 (KMeans/DBSCAN/GMM)
  ├─ 自动 K 寻优（Silhouette Score 评估 K=3~8）
  └─ 聚类评分（低PE + 低PB + 高股息 + 高ROE + 低波动）
        ↓
  多聚类组合 (Top-N)
  ├─ 单聚类: 选评分最高的
  └─ 多聚类: 选 2~3 个，按评分加权分配资金
        ↓
  等权重 / 评分加权建仓
  └─ 市场波动自适应仓位
```

### 📈 仓位与风控

- **条件触发再平衡**: 满足任一条件即再平衡
  - 每 20 天（最长间隔）
  - 组合回撤超 5%
  - 单日大盘跌超 3%
- **市场波动自适应**: 根据波动率动态调整总仓位
- **多聚类资金分配**: 按聚类评分加权分配
- -8% 止损 / +25% 分批止盈（卖一半）

### 🧠 聚类算法

| 算法 | 特点 | 使用方式 |
|------|------|----------|
| **KMeans** | 快速稳定，自动寻优 | 默认 |
| **DBSCAN** | 自动发现聚类数，识别异常 | `--cluster dbscan` |
| **GMM** | 软聚类，概率输出 | `--cluster gmm` |
| **Agglomerative** | 层次聚类 | `--cluster agglomerative` |

### 🆕 新增优化功能

| 功能 | 说明 | 参数 |
|------|------|------|
| **自动 K 寻优** | Silhouette Score 评估 K=3~8 | `--auto-k`（默认开启） |
| **多聚类组合** | Top-N 聚类评分加权组合 | `--top-n 2` |
| **条件再平衡** | 回撤/市场冲击触发 | 默认启用 |
| **动量因子** | RSI、MACD、乖离率、60日动量 | 自动计算 |
| **特征重要性** | ANOVA F 值评估各特征区分度 | 自动输出 |
| **市场状态显示** | 根据波动率显示当前市场状态 | `--vol 0.22` |

---

## 安装

```bash
git clone https://github.com/wangheng2018-spec/quant-cluster-a-share.git
cd quant-cluster-a-share
pip install -r requirements.txt
```

## 快速使用

> 📖 **完整实操指南请见 [GUIDE.md](./GUIDE.md)**
> 包含：证券开户 → 环境搭建 → QMT/PTrade 实盘对接 → 免坑指南 → 检查清单

```bash
# 默认运行（KMeans + 自动 K 寻优 + 单聚类）
python main.py

# 仅分析选股（不回测）
python main.py --mode analyze

# GMM + 自动寻优 + 多聚类组合
python main.py --cluster gmm --top-n 2

# DBSCAN
python main.py --cluster dbscan

# 自定义参数
python main.py --price 8 --capital 500000 --top 30 --rebalance 10
```

### 参数详解

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--cluster` | kmeans | 聚类方法 |
| `--auto-k` | True | 自动寻优 K=3~8 |
| `--no-auto-k` | - | 禁用自动寻优 |
| `--k` | 5 | 聚类数（auto-k 关闭时使用） |
| `--top-n` | 1 | 多聚类组合（>1 启用） |
| `--price` | 10.0 | 股价上限 |
| `--capital` | 100000 | 初始资金 |
| `--top` | 20 | 最大持仓数 |
| `--rebalance` | 20 | 再平衡最大间隔 |
| `--vol` | 0.22 | 市场波动率 |
| `--mode` | backtest | backtest / analyze |
| `--start` | 2024-01-01 | 回测开始 |
| `--end` | 今天 | 回测结束 |

### 完整示例

```bash
# 生产级配置：GMM + 自动寻优 + 多聚类 + 10天再平衡
python main.py \
  --cluster gmm \
  --auto-k \
  --top-n 2 \
  --price 10 \
  --capital 500000 \
  --top 25 \
  --rebalance 10 \
  --vol 0.20 \
  --mode backtest
```

---

## 项目结构

```
quant_cluster/
├── main.py                    # 主入口（CLI 参数解析）
├── config.py                  # 配置中心
├── requirements.txt           # 依赖
├── run_quant.bat              # Windows 一键运行
│
├── data/
│   └── fetcher.py             # 数据获取
├── screening/
│   └── screener.py            # 国资低价筛选
├── features/
│   └── engineering.py         # 特征工程 + 动量因子
├── clustering/
│   └── cluster.py             # 聚类 + 自动寻优 + 多聚类组合
├── portfolio/
│   └── manager.py             # 仓位管理 + 条件再平衡
├── backtest/
│   └── engine.py              # 回测引擎
└── examples/
```

---

## 回测报告解读

```
【绩效报告】
  指标                    数值
  --------------------------------
  初始资本          100,000.00 元
  最终资产          115,432.50 元
  总收益率              15.43 %
  年化收益               8.12 %
  最大回撤               6.34 %
  夏普比率               1.23
  胜率                  62.5 %
  交易次数              42 笔
  最终持仓              18 只
```

| 指标 | 说明 | 优秀标准 |
|------|------|----------|
| **总收益率** | 回测期内总收益 | > 10% |
| **年化收益** | 年化收益率 | > 8% |
| **最大回撤** | 从峰值到谷底 | < 15% |
| **夏普比率** | 风险调整收益 | > 1.0 |
| **胜率** | 盈利交易占比 | > 55% |

## 实盘对接

| 券商 | 方案 | 费用 |
|------|------|------|
| 国金 QMT | Python API | 一般免费 |
| 华泰 PTrade | 支持 Python 策略 | 资产达标免费 |
| 迅投 QMT | 网格/算法交易 | 开户免费 |
