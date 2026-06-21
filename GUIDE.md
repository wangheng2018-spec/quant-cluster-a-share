# A股量化实盘部署 · 实操指南

> 从零开始：证券开户 → 环境搭建 → 策略配置 → 实盘运行 · 免坑手册

---

## 目录

1. [证券账号申请（量化专用）](#1-证券账号申请量化专用)
2. [量化交易平台对比](#2-量化交易平台对比)
3. [环境搭建（Windows 版）](#3-环境搭建windows-版)
4. [环境搭建（Ubuntu 服务器版）](#4-环境搭建ubuntu-服务器版)
5. [策略配置与实盘对接](#5-策略配置与实盘对接)
6. [YongQuant / QMT 接入示例](#6-yongquant--qmt-接入示例)
7. [免坑指南（常见问题）](#7-免坑指南常见问题)
8. [安全须知](#8-安全须知)
9. [检查清单](#9-检查清单)

---

## 1. 证券账号申请（量化专用）

### 1.1 推荐券商（支持 Python API 实盘交易）

| 券商 | 量化平台 | Python API | 资金门槛 | 费率 | 评级 |
|------|----------|-----------|----------|------|------|
| **国金证券** | QMT | ✅ 支持 | 无（免费） | 万1.5 | ⭐⭐⭐⭐⭐ |
| **华泰证券** | PTrade | ✅ 支持 | 1 万以上 | 万1.3 | ⭐⭐⭐⭐⭐ |
| **中信建投** | QMT | ✅ 支持 | 1 万以上 | 万1.5 | ⭐⭐⭐⭐ |
| **国泰君安** | 迅投 QMT | ✅ 支持 | 50 万 | 万1.8 | ⭐⭐⭐⭐ |
| **广发证券** | 自有平台 | ❌ 仅 Java | 无 | 万1.5 | ⭐⭐⭐ |
| **东方财富** | Choice | ❌ 仅客户端 | 无 | 万2.5 | ⭐⭐⭐ |

### 1.2 开户流程（以国金 QMT 为例）

```
第1步：下载「国金证券」APP → 开户
第2步：准备材料：身份证 + 本人银行卡 + 手机号（需本人实名）
第3步：开户流程
  ├─ 身份认证：上传身份证正反面，人脸识别
  ├─ 风险测评：选「积极型」或「进取型」
  ├─ 三方存管：绑定银行卡（工农中建招等）
  └─ 视频见证：工作日 9:00-16:00 人工视频
第4步：开户成功后（T+1 交易日生效）：
  ├─ 下载「国金证券 QMT」客户端
  └─ 联系客户经理开通「量化接口权限」
```

### 1.3 ⚠️ 开户注意事项

- **必须主动联系客户经理开通量化权限**，默认不开通
- 开户时风险测评必须选 **「进取型」或「积极型」**，保守型无法开通
- **一人三户**：每人最多开 3 个沪A 账户，已有 3 个需要销户或转户
- QMT 权限开通后，需 **去营业部或视频认证** 签署《量化交易协议》
- **创业板/科创板** 需单独开通（分别要求 2 年/2 年交易经验 + 10万/50万资产）

---

## 2. 量化交易平台对比

### 2.1 QMT（迅投）— 推荐

**特点**：独立客户端，提供 Python 3.8 环境，支持本地策略运行

```
├─ 优点：策略本地运行（安全）、回测速度快、数据全
├─ 缺点：GUI 不够现代、学习曲线略陡
└─ 适用：中高频交易、复杂策略
```

Python API 接口签名：
```python
# QMT 内置 API（无需 pip install）
from xtquant import xtdata       # 行情接口
from xtquant import xttrader      # 交易接口
from xtquant import xtconstant    # 常量定义
```

### 2.2 PTrade（华泰）— 备选

**特点**：Web 端策略管理，支持在线回测

```
├─ 优点：Web 界面友好、一键部署、有模拟盘
├─ 缺点：策略必须上传到服务器（代码安全风险）
└─ 适用：中低频策略、新手入门
```

Python API 接口签名：
```python
# PTrade 内置 API
from ptrade import get_price       # 获取行情
from ptrade import order           # 下单
from ptrade import get_positions   # 查询持仓
```

### 2.3 对接本系统的方式

| 方式 | 难度 | 说明 |
|------|------|------|
| **本系统分析 + 手动跟单** | ⭐ | 每次选股结果出来手动下单 |
| **本系统生成信号 + QMT 自动执行** | ⭐⭐ | 信号文件对接 QMT 调度 |
| **本系统代码嵌入 QMT** | ⭐⭐⭐ | 把策略代码放到 QMT 的 Python 环境下运行 |
| **通过 YongQuant 接入** | ⭐⭐ | 开源量化框架，支持多券商 |

---

## 3. 环境搭建（Windows 版）

### 3.1 一键部署

```bat
@echo off
chcp 65001
echo ================================================
echo   量化环境搭建 - Windows 一键脚本
echo ================================================

:: 1. 安装 Python（如果还没装）
winget install Python.Python.3.12

:: 2. 创建虚拟环境
cd /d %~dp0
python -m venv venv
call venv\Scripts\activate.bat

:: 3. 升级 pip
python -m pip install --upgrade pip -q

:: 4. 安装依赖
pip install -r requirements.txt -q

:: 5. 测试安装
python -c "import pandas, numpy, sklearn; print('✅ 量化环境就绪')"
pause
```

### 3.2 分步详解

**第1步：安装 Python 3.10~3.12**

```
推荐版本：Python 3.12.4（QMT 使用 3.8，兼容性最好用 3.10）

下载地址：https://www.python.org/downloads/
安装时务必勾选：
  ✅ Add Python to PATH
  ✅ Install pip

验证：
  C:\> python --version
  Python 3.12.4
  C:\> pip --version
  pip 24.1
```

**第2步：克隆项目并创建虚拟环境**

```bash
# 克隆策略代码
git clone https://github.com/wangheng2018-spec/quant-cluster-a-share.git
cd quant-cluster-a-share

# 创建虚拟环境（隔离依赖）
python -m venv venv

# 激活虚拟环境
# PowerShell:
venv\Scripts\Activate.ps1
# CMD:
venv\Scripts\activate.bat
# Git Bash:
source venv/Scripts/activate

# 看到提示符前面有 (venv) 表示成功
(venv) C:\quant-cluster-a-share>
```

**第3步：安装依赖**

```bash
# 基础依赖（必须）
pip install --upgrade pip
pip install pandas numpy scikit-learn

# 离线选股/模拟回测用
pip install akshare baostock tushare

# 可视化（可选）
pip install matplotlib seaborn

# 验证安装
python -c "import pandas,numpy,sklearn; print('OK')"
```

**第4步：配置 QMT 环境**

```bash
# QMT 的 Python 路径默认在：
C:\迅投QMT\bin\python.exe
C:\国金QMT\python\python.exe

# 在本项目的虚拟环境安装 QMT SDK
pip install xtquant --index-url https://pypi.org/simple/

# 或者直接将策略复制到 QMT 的 strategy 目录
C:\国金QMT\userdata\strategy\
```

### 3.3 ⚠️ Windows 环境避坑

```
❌ 坑1：路径有中文
   解决方案：项目路径不要有中文/空格（如 C:\量化交易\ → C:\quant\）

❌ 坑2：Python 版本冲突
   解决方案：必须用虚拟环境，系统 Python 和 QMT 内置 Python 不冲突

❌ 坑3：PowerShell 执行策略
   解决方案：以管理员运行 → Set-ExecutionPolicy Unrestricted -Scope CurrentUser

❌ 坑4：pip 安装慢
   解决方案：pip install -i https://pypi.tuna.tsinghua.edu.cn/simple 包名

❌ 坑5：akshare 版本问题
   解决方案：pip install akshare==1.14.0（特定版本兼容性更好）
```

---

## 4. 环境搭建（Ubuntu 服务器版）

### 4.1 一键部署

```bash
#!/bin/bash
set -e

echo "=== 量化环境搭建 - Ubuntu ==="

# 1. 更新系统
sudo apt update && sudo apt upgrade -y

# 2. 安装 Python
sudo apt install -y python3 python3-pip python3-venv git

# 3. 安装系统依赖
sudo apt install -y build-essential libssl-dev libffi-dev \
    libxml2-dev libxslt1-dev zlib1g-dev

# 4. 克隆项目
git clone https://github.com/wangheng2018-spec/quant-cluster-a-share.git
cd quant-cluster-a-share

# 5. 虚拟环境
python3 -m venv venv
source venv/bin/activate

# 6. 安装依赖
pip install --upgrade pip
pip install -r requirements.txt

# 7. 创建数据缓存目录
mkdir -p data_cache logs

# 8. 设置定时任务（每天早上 8:55 运行选股）
crontab -l 2>/dev/null | { cat; echo "55 8 * * 1-5 cd $(pwd) && source venv/bin/activate && python main.py --mode analyze >> logs/daily_$(date +\%Y\%m\%d).log 2>&1"; } | crontab -

echo "✅ 安装完成！"
echo "查看今日选股结果: cat logs/daily_*.log"
```

### 4.2 分步详解

**第1步：购买云服务器（国内推荐）**

| 厂商 | 最低配置 | 价格 | 量化够用？ |
|------|---------|------|-----------|
| **阿里云** | 2C4G | ~68元/月 | ✅ 足够 |
| **腾讯云** | 2C4G | ~65元/月 | ✅ 足够 |
| **华为云** | 2C4G | ~60元/月 | ✅ 足够 |
| **UCloud** | 2C4G | ~50元/月 | ✅ 够用 |
| **AWS 海外** | 2C4G | ~$15/月 | ✅ 但延迟高 |

**推荐配置**：2核4G + 40G SSD + Ubuntu 22.04 LTS

**第2~7步**：参考一键部署脚本

### 4.3 ⚠️ Ubuntu 环境避坑

```
❌ 坑1：系统时区
   解决方案：timedatectl set-timezone Asia/Shanghai

❌ 坑2：防火墙
   解决方案：sudo ufw allow 22/tcp（SSH），其他端口按需开放

❌ 坑3：内存不足
   解决方案：2G 内存可能不够 sklearn 跑聚类，创建 swap
   sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile
   sudo mkswap /swapfile && sudo swapon /swapfile

❌ 坑4：中文乱码
   解决方案：sudo apt install -y fonts-wqy-microhei

❌ 坑5：定时任务不执行
   解决方案：crontab 里使用绝对路径
```

---

## 5. 策略配置与实盘对接

### 5.1 策略参数调优建议

```bash
# 第一步：离线模拟回测，找到最佳参数
python main.py --cluster kmeans --auto-k --top-n 2 --rebalance 10 --capital 100000

# 第二步：调整参数对比
python main.py --cluster gmm --auto-k --top-n 2 --rebalance 10
python main.py --cluster kmeans --auto-k --top-n 3 --rebalance 15
python main.py --cluster dbscan --rebalance 20

# 第三步：确定最佳参数后，用于实盘
# 建议记录每次回测结果到 excel 对比
```

### 5.2 实盘模式配置

编辑 `config.py` 中的实盘参数：

```python
# 实盘推荐配置
cfg = Config(
    # 数据
    start_date="2025-01-01",
    end_date="2025-12-31",
    
    # 筛选
    max_price=10.0,
    soe_only=True,
    
    # 聚类
    cluster_method="kmeans",
    auto_k=True,
    top_n_clusters=2,        # 多聚类组合
    
    # 风控（实盘更严格）
    stop_loss=0.07,          # -7% 止损（比默认8%更保守）
    take_profit=0.20,        # +20% 止盈
    max_position_weight=0.85, # 不超过 85% 仓位
    max_single_weight=0.10,  # 单只不超过 10%
    
    # 再平衡
    rebalance_days=10,       # 10天
    rebalance_max_drawdown=0.03,  # 回撤 3% 即触发
    
    # 初始资金
    initial_capital=100000,
    max_positions=20,
)
```

### 5.3 选股结果输出到文件

添加一个简单的输出脚本，把选股结果保存到 CSV，方便手动跟单：

```bash
# 运行分析模式，输出结果到文件
python main.py --mode analyze 2>&1 | tee -a signal_$(date +%Y%m%d).log
```

或者在 `main.py` 末尾添加：

```python
# 导出选股结果
if args.mode == "analyze":
    csv_path = f"signals/signal_{datetime.now().strftime('%Y%m%d')}.csv"
    os.makedirs("signals", exist_ok=True)
    selected[["code", "name", "current_price", "pe_ttm", "pb",
              "dividend_yield", "volatility_20d", "cluster"]].to_csv(
        csv_path, index=False, encoding="utf-8-sig")
    print(f"\n📄 选股信号已导出: {csv_path}")
```

---

## 6. YongQuant / QMT 接入示例

### 6.1 QMT 极简下单脚本

将策略选出的股票列表导入 QMT，自动下单：

```python
"""
文件保存为：C:\国金QMT\userdata\strategy\auto_buy.py
在 QMT 客户端中创建此策略并启动
"""
import time
import pandas as pd
from xtquant import xtdata, xttrader, xtconstant

# === 配置 ===
ACCOUNT_ID = "你的资金账号"          # 6位数字
SIGNAL_FILE = r"C:\quant-cluster-a-share\signals\latest.csv"

# === 连接交易接口 ===
def main():
    # 1. 读入选股信号
    try:
        signals = pd.read_csv(SIGNAL_FILE, encoding="utf-8-sig")
    except FileNotFoundError:
        print(f"⚠️ 信号文件不存在: {SIGNAL_FILE}")
        return
    
    stocks = signals["code"].tolist()
    print(f"今日选股: {len(stocks)} 只: {stocks}")
    
    # 2. 连接交易
    trader = xttrader.XtQuantTrader()
    trader.connect()
    trader.login(ACCOUNT_ID)
    
    # 3. 获取持仓
    positions = trader.get_positions(ACCOUNT_ID)
    hold_codes = {p["stock_code"] for p in positions}
    
    # 4. 卖出不在选股池中的持仓
    for pos in positions:
        if pos["stock_code"] not in stocks and pos["can_use_volume"] > 0:
            order = trader.order_target_volume(
                ACCOUNT_ID, pos["stock_code"], 
                xtconstant.STOCK_SELL, 0
            )
            print(f"  卖出: {pos['stock_code']} {order}")
    
    # 5. 买入新选出的股票（等权重）
    total_cash = trader.get_asset(ACCOUNT_ID)["cash"]
    per_stock = total_cash / max(len(stocks), 1) * 0.95
    
    for code in stocks:
        if code not in hold_codes:
            order = trader.order_value(
                ACCOUNT_ID, code,
                xtconstant.STOCK_BUY, per_stock
            )
            print(f"  买入: {code} {per_stock:.0f}元 {order}")
    
    # 6. 断开连接
    trader.disconnect()
    print("✅ 交易完成")

if __name__ == "__main__":
    main()
```

### 6.2 通过 YongQuant 接入多券商

```bash
# 安装 YongQuant
pip install yongquant

# 支持券商：国金QMT、华泰PTrade、中信、华宝等
```

```python
from yongquant import Broker

# 对接券商
broker = Broker("国金QMT", account="资金账号", password="密码")
broker.connect()

# 获取账户信息
account = broker.get_account()
print(f"可用资金: {account.cash}")

# 下单
broker.buy("600519.SH", amount=10000)   # 金额下单
broker.buy("000001.SZ", shares=100)     # 股数下单

# 查询持仓
positions = broker.get_positions()
broker.disconnect()
```

---

## 7. 免坑指南（常见问题）

### 🕳️ 开户阶段

| 坑 | 后果 | 解决方案 |
|----|------|----------|
| 线上开户默认不开量化权限 | 买不了 QMT/PTrade | 开户后主动联系客户经理 |
| 风险测评选保守型 | 无法开通量化 | 重做测评选进取型 |
| 已有 3 个沪市账户 | 新开户失败 | 先销户/转户一个 |
| 身份证过期 | 开户驳回 | 先更新身份证 |
| 银行卡非一类卡 | 银证转账失败 | 必须用一类银行卡 |

### 🕳️ 环境搭建

| 坑 | 后果 | 解决方案 |
|----|------|----------|
| Python 没加到 PATH | cmd 找不到 python | 重装时勾选 Add to PATH |
| pip 版本过低 | 安装失败 | python -m pip install --upgrade pip |
| 没用虚拟环境 | 依赖冲突 | 必须用 python -m venv venv |
| sklearn 版本不对 | 聚类报错 | pip install scikit-learn==1.3.0 |
| Windows 中文路径 | 库读取失败 | 路径不要有中文和空格 |

### 🕳️ 策略运行

| 坑 | 后果 | 解决方案 |
|----|------|----------|
| akshare 数据延迟 | 选股结果滞后 | 交易日 9:25 后再运行 |
| 停牌股买入 | 废单 | 选股时过滤停牌股 |
| 跌停买/涨停卖 | 无法成交 | 加入涨跌停过滤条件 |
| 除权除息未复权 | 价格跳跃 | 使用前复权数据 |
| 回测过拟合 | 实盘亏损 | 增加样本外测试，KISS 原则 |

### 🕳️ 实盘交易

| 坑 | 后果 | 解决方案 |
|----|------|----------|
| QMT 未登录 | 不下单 | 设置开机自启+自动登录 |
| 交易时间外下单 | 废单 | 仅在 9:30-15:00 下单 |
| 资金不足买入 | 部分成交 | 下单前检查可用资金 |
| T+1 卖出限制 | 当天买不能卖 | 选股时考虑已持仓 |
| 最小交易单位 | 下单失败 | 沪市 100股，科创板 200股 |
| 滑点过大 | 成交价偏离 | 用限价单，留 2~3 档价差 |

---

## 8. 安全须知

### 🔐 账号安全

```
✅ 必须做的：
  ├─ 使用独立的交易密码（不和登录密码相同）
  ├─ 交易密码定期更换（每 3 个月）
  ├─ 设置 QMT 的 IP 白名单（仅限自己的服务器 IP）
  ├─ 策略代码不要上传到公开仓库（本系统是分析工具，安全）
  └─ 定期检查委托记录，发现异常立即冻结账号

❌ 绝对不能做的：
  ├─ 把账号密码写在代码里提交到 GitHub
  ├─ 使用来源不明的第三方交易脚本
  ├─ 开启 QMT 的免密登录
  └─ 在公共电脑上登录交易账号
```

### 🔒 资金安全

```
初始建议：先用 1 万元测试策略 → 稳定后再加仓
单策略最大资金：不超过总资产的 30%
每个交易品种：不超过总资产的 10%
总仓位上限：任何时候不超过 85%
```

---

## 9. 检查清单

### ✅ 开户阶段

- [ ] 选定券商（推荐国金 QMT 或华泰 PTrade）
- [ ] 完成线上开户（工作日 9:00-16:00）
- [ ] 联系客户经理开通量化权限
- [ ] 签署《量化交易协议》
- [ ] 下载对应客户端并登录验证
- [ ] 转入资金（建议先转 1 万测试）

### ✅ 环境搭建

- [ ] 安装 Python 3.10~3.12
- [ ] 克隆项目到本地（路径无中文）
- [ ] 创建并激活虚拟环境
- [ ] 安装 requirements.txt
- [ ] 运行 python main.py --mode analyze 验证
- [ ] 确认离线模拟回测正常

### ✅ 实盘前测试

- [ ] 离线回测 1 年以上数据
- [ ] 不同市场环境测试（牛/熊/震荡）
- [ ] 参数敏感性测试（小范围修改看结果稳定性）
- [ ] 模拟盘运行 1 个月（QMT 支持模拟交易）
- [ ] 设置止损/止盈参数
- [ ] 准备好应急预案（断网/崩溃/异常）

### ✅ 实盘运行

- [ ] 每日开盘前检查信号
- [ ] 检查 QMT 是否正常运行
- [ ] 检查可用资金是否充足
- [ ] 检查是否持有停牌股
- [ ] 收盘后复盘，记录成交情况
- [ ] 每周统计绩效，与回测预期对比

---

> **最后忠告**：量化交易不是印钞机。本系统是选股辅助工具，实盘前请充分测试。
> 任何量化策略都有失效的可能，建议多策略组合、动态调整。
> 入门从 1 万元开始，跑顺了再加仓。

---

*文档版本: v2.0 | 最后更新: 2025-06*
