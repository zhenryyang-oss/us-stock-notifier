# 美股每日推送 Agent

零成本、零服务器，基于 GitHub Actions 的微信推送。

## 部署（5分钟）

### 1. 创建 GitHub 仓库

在 GitHub 上创建一个**私有**仓库（Private），比如叫 `us-stock-notifier`。

### 2. 上传代码

把这个目录下的所有文件 push 上去：

```bash
cd /Users/henry/Desktop/DolphinDB_ARM64_V3/server/auto_research/github_notifier
git init
git add .
git commit -m "init: us stock notifier"
git remote add origin git@github.com:你的用户名/us-stock-notifier.git
git push -u origin main
```

### 3. 设置 Secret

在仓库页面：**Settings → Secrets and variables → Actions → New repository secret**

| 名称 | 值 |
|------|-----|
| `SCT_KEY` | `SCT361063TVWXMa4hGeehHy6dmj40Dutlb`（你的ServerChan Key） |

### 4. 等它自动跑

GitHub Actions 会在每天自动触发：

| 北京时间 | 内容 |
|---------|------|
| **08:00** | 每日盘前简报（持仓行情 + 宏观事件 + 新闻） |
| **18:00** | 午间更新 |
| **22:00** | 收盘总结（持仓表现 + 异动提醒） |

也可以手动触发：仓库页面 → Actions → Run workflow → 选择模式 → 运行

## 费用

- GitHub Actions：每月免费 **2000分钟**（每天用不到3分钟）
- ServerChan：免费
- **总计：¥0**

## 文件结构

```
├── .github/workflows/notifier.yml  # GitHub Actions 调度配置
├── us_stock_daily.py               # 主脚本（纯Python，无第三方依赖）
└── README.md                       # 说明
```
