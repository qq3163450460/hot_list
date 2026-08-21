# hot-list

Hot List 聚合抖音、微博、哔哩哔哩、知乎、今日头条等主流平台热榜，支持按小时、按天查询历史数据，快速追踪热点的出现、升温与变化趋势。内置 AI 分析能力，可对热门事件进行智能总结、趋势解读与舆情洞察。无论是内容创作、热点研究，还是运营选题，都能更快发现值得关注的信号。
## 主要功能

- 定时采集并持久化多平台热榜，默认按 `Asia/Shanghai` 时区每小时整点执行。
- 按日期、实际存在的小时和平台查询历史快照。
- 提供首页筛选、分页展示、状态信息和热榜条目查看。
- 提供独立的 AI 分析页面，可选择历史快照和一个或多个平台，将数据发送到用户自行配置的兼容接口，分析跨平台热度、共振话题和趋势信号。
- AI 接口地址、模型配置和 API Key 仅保存在浏览器本地，不写入服务端数据库。使用者仍应只连接自己信任且有权使用的接口。
- 提供只读历史 API、健康检查、图片代理和命令行采集、写入与查询入口。
- 支持 SQLite 单实例轻量部署，以及使用 `mysql+asyncmy` 的 MySQL 8 部署。
- 支持 Docker Compose、Linux、Windows、反向代理与 HTTPS 部署方式。

## 支持的平台

当前代码配置和适配器覆盖微博、哔哩哔哩、今日头条、百度热榜、知乎和抖音。小红书与虎扑仍属于受限适配器，在取得经过授权且可复现的官方请求链之前，不提供端点、签名、令牌或响应字段配置。平台实际可用性可能受登录状态、Cookie、地区限制、频率控制、风控策略和上游接口变化影响。

## 使用场景

- 聚合查看多个内容平台的当前热点。
- 保存小时级快照并回看指定日期和时段的热榜。
- 对比同一话题在不同平台的传播与热度共振。
- 使用自定义 AI 接口生成热点摘要、趋势信号和跨平台分析。
- 为研究、内容选题、舆情观察和内部数据看板提供基础数据。使用时应遵守目标平台条款、适用法律和授权范围。

## 快速开始

### Docker Compose 部署（推荐）

最快上手方式，一条命令启动完整服务：

```bash
# 1. 复制环境变量配置
cp .env.example .env

# 2. 如需自定义 Cookie，编辑 .env 文件
#    不要将 .env 提交到版本库

# 3. 验证配置并启动
docker compose config
docker compose up --build -d

# 4. 查看运行状态
docker compose ps
docker compose logs -f app
```

服务启动后访问：

| 地址 | 说明 |
|------|------|
| `http://localhost:8765/` | 热榜主页 |
| `http://localhost:8765/ai-analysis` | AI 分析页面 |
| `http://localhost:8765/health` | 健康检查 |
| `http://localhost:8765/docs` | OpenAPI 接口文档 |

停止并清理：

```bash
# 停止容器（保留数据卷）
docker compose down

# 停止并删除数据卷（⚠️ 会清除所有历史数据）
docker compose down -v
```

### Python 源码部署

适合需要自定义修改或不想使用 Docker 的场景：

```bash
# 1. 获取源码
git clone <仓库地址>
cd hot_list

# 2. 创建并激活虚拟环境
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# Windows PowerShell:
# .\.venv\Scripts\Activate.ps1
# Windows CMD:
# .\.venv\Scripts\activate.bat

# 3. 安装项目
python -m pip install -e ".[dev]"

# 4. 配置环境变量
cp .env.example .env
# 注意：源码部署默认数据库路径应改为相对路径
# HOT_LIST_DATABASE_URL=sqlite+aiosqlite:///./data/hot_list.db
mkdir -p data

# 5. 启动服务
python main.py serve
# 或安装后使用全局命令：
# hot-list serve
```

开发调试模式（自动重载 + debug 日志）：

```bash
python main.py dev
# 等价命令：
# python -m uvicorn web.app:app --host 127.0.0.1 --port 8765 --reload --log-level debug
```

停止服务按 `Ctrl+C`，退出虚拟环境执行 `deactivate`。

### 启动与关闭速查

| 部署方式 | 启动 | 停止 | 查看日志 |
|---------|------|------|---------|
| Docker | `docker compose up --build -d` | `docker compose down` | `docker compose logs -f app` |
| Python 源码 | `python main.py serve` | `Ctrl+C` | 终端直接输出 |
| Python 开发模式 | `python main.py dev` | `Ctrl+C` | 终端直接输出 |

## 项目截图

### 热榜主页

![热榜主页](images/主页.png)

首页展示各平台最新热榜快照，支持按日期、小时、平台筛选，显示状态徽章和条目数量。

### 分页浏览

![分页浏览](images/分页.png)

分页控件支持浏览历史快照，每条热榜条目展示标题、排名、链接和热度信息。

### AI 热榜分析

![AI 热榜分析](images/ai分析.png)

AI 分析页面可选择历史快照日期，勾选一个或多个平台，配置 AI 接口后发起跨平台热度分析。

### AI 分析结果

![AI 分析结果](images/分析结果.png)

AI 返回的跨平台趋势摘要、共振话题和热度信号，帮助用户快速捕捉热点脉络。
