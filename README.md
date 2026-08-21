# hot-list

hot-list 是基于 FastAPI、SQLAlchemy 2.x 异步 ORM、APScheduler 和原生 Web 前端构建的多平台热榜采集、小时快照存储、历史查询与 AI 热点分析服务。项目支持 SQLite 和 MySQL，可通过 Python 源码或 Docker Compose 部署。

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

## 配置

复制 `.env.example` 为 `.env`。环境变量使用 `HOT_LIST_` 前缀。

核心配置：

- `HOT_LIST_DATABASE_URL` — 数据库连接地址
- `HOT_LIST_APP_TIMEZONE=Asia/Shanghai` — 时区设置
- `HOT_LIST_SCHEDULER_ENABLED=true` — 是否启用定时采集调度器
- `HOT_LIST_COLLECT_ON_STARTUP=true` — 启动时补采当前小时缺失数据
- `HOT_LIST_COLLECT_CRON_MINUTE=0` — 每小时第几分钟执行采集
- `HOT_LIST_WEIBO_COOKIE` / `HOT_LIST_BILIBILI_COOKIE` 等 — 各平台 Cookie

Cookie 等敏感信息不得提交到版本库、测试 fixtures 或日志。

## 部署方式详解

### Docker Compose 部署

#### SQLite 默认部署

复制示例环境变量文件，并按需填写 Cookie 等敏感配置。不要将 `.env` 提交到版本库：

```bash
cp .env.example .env
docker compose config
docker compose up --build -d
```

服务通过 `http://localhost:8765` 提供访问，健康检查端点为 `http://localhost:8765/health`。容器内 Uvicorn 绑定到 `0.0.0.0:8765`，固定使用一个 worker。

SQLite 数据库存放在容器的 `/app/data/hot_list.db`，并通过 `hot_list_data` 命名卷持久化。停止并重新创建容器不会删除数据；只有显式执行 `docker compose down -v` 才会删除该命名卷及其中的数据。

常用管理命令：

```bash
docker compose ps                # 查看容器状态
docker compose logs -f app       # 跟踪应用日志
docker compose exec app python main.py latest   # 查询最新快照
docker compose exec app python main.py collect  # 手动采集
docker compose restart app       # 重启服务
docker compose down              # 停止（保留数据卷）
docker compose down -v           # 停止并删除数据卷（⚠️ 数据丢失）
```

#### APScheduler 与副本数量

应用进程内运行 APScheduler，并可在启动时执行缺失数据补采。启用 `HOT_LIST_SCHEDULER_ENABLED=true` 或 `HOT_LIST_COLLECT_ON_STARTUP=true` 时，**必须保持应用为单副本**，并维持 Uvicorn `--workers 1`。

```bash
# ❌ 错误：多副本会导致重复采集
docker compose up --scale app=2

# ✅ 正确：保持单副本运行
docker compose up --build -d
```

如需横向扩展 Web 服务，应先将调度任务拆分为独立的单实例服务，并在 Web 副本中设置：

```dotenv
HOT_LIST_SCHEDULER_ENABLED=false
HOT_LIST_COLLECT_ON_STARTUP=false
```

#### 可选 MySQL 部署

MySQL 配置位于 `docker-compose.mysql.yml`。先在本地 `.env` 中设置真实凭据：

```dotenv
MYSQL_DATABASE=hot_list
MYSQL_USER=hot_list
MYSQL_PASSWORD=replace-with-a-strong-password
MYSQL_ROOT_PASSWORD=replace-with-a-different-strong-password
HOT_LIST_DATABASE_URL=mysql+asyncmy://hot_list:replace-with-a-strong-password@mysql:3306/hot_list?charset=utf8mb4
```

启动组合配置：

```bash
docker compose -f docker-compose.yml -f docker-compose.mysql.yml config
docker compose -f docker-compose.yml -f docker-compose.mysql.yml up --build -d
```

MySQL 数据通过 `hot_list_mysql_data` 命名卷持久化。应用会等待 MySQL 健康检查通过后再启动。详细步骤参见 [docs/mysql-deployment.md](docs/mysql-deployment.md)。

#### Docker 验证

```bash
docker compose config          # 验证配置语法
docker compose build           # 构建镜像
docker compose up -d           # 后台启动
docker compose ps              # 检查运行状态
curl --fail http://localhost:8765/health   # 健康检查
docker compose exec app python main.py latest   # 验证数据
```

### Python 源码部署

#### 环境要求

- Python 3.10 或更高版本
- pip
- 默认使用 SQLite，无需单独安装数据库服务

#### 创建虚拟环境

Linux 或 macOS：

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Windows 命令提示符：

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
```

#### 安装项目

```bash
# 生产部署（仅运行依赖）
python -m pip install .

# 开发/调试部署（含测试工具）
python -m pip install -e ".[dev]"
```

#### 环境变量配置

```bash
cp .env.example .env
# 修改数据库路径为本地相对路径
# HOT_LIST_DATABASE_URL=sqlite+aiosqlite:///./data/hot_list.db
mkdir -p data
```

#### 启动与停止

```bash
# 生产模式
python main.py serve
# 或：hot-list serve

# 开发调试模式（自动重载）
python main.py dev

# 停止：按 Ctrl+C
# 退出虚拟环境：deactivate
```

#### 常用 CLI 命令

```bash
# 实时采集（不写入数据库）
python main.py live
python main.py live weibo

# 采集并保存当前小时数据
python main.py collect
python main.py collect weibo

# 查询最新快照
python main.py latest
python main.py latest --platform weibo

# 查询历史数据
python main.py history 2026-08-21
python main.py history 2026-08-21 --hour 12 --platform weibo
```

### Linux systemd 部署

将 hot-list 注册为 systemd 服务，实现开机自启和进程守护。详细步骤参见 [docs/linux-deployment.md](docs/linux-deployment.md)。

### Windows 部署

Windows 环境下可使用批处理脚本或 `start_debug.bat` 启动服务。详细步骤参见 [docs/windows-deployment.md](docs/windows-deployment.md)。

### 反向代理与 HTTPS

公网部署前需配置反向代理和 HTTPS 证书。支持 Nginx、Caddy 等常见代理方案。详细步骤参见 [docs/reverse-proxy.md](docs/reverse-proxy.md)。

## API

只读数据库接口：

- `GET /api/hot`：各平台最新快照
- `GET /api/hot/{platform}`：指定平台最新快照
- `GET /api/history/latest`：所有平台最新快照
- `GET /api/history/dates`：数据库实际存在的日期
- `GET /api/history/hours?date=YYYY-MM-DD`：指定日期实际存在的小时
- `GET /api/history/hot?date=YYYY-MM-DD&hour=HH&platform=weibo`：历史热榜查询

仅传日期时，历史接口返回当天最新可用小时；无数据时返回结构化空结果。以上页面和热榜请求不会触发 Spider。

其他接口：

- `GET /health`
- `GET /api/platforms`
- `GET /api/image-proxy`

## CLI

实时采集但不入库：

```bash
python main.py live
python main.py live weibo
```

手动采集并写入当前小时：

```bash
python main.py collect
python main.py collect weibo
```

查询最新数据：

```bash
python main.py latest
python main.py latest --platform weibo
```

查询指定日期、小时和平台：

```bash
python main.py history 2026-08-19
python main.py history 2026-08-19 --hour 10 --platform weibo
```

安装后也可使用 `hot-list` 命令执行相同子命令。

## 前端

首页提供日期、实际存在小时、平台和最新数据筛选，展示快照时间、采集时间、状态和条目数。微博分类标签使用高对比度配色，热度标签使用独立中性色；标题保持单行省略并通过悬浮标题显示完整内容。

## 检查

```bash
python -m compileall -q database services spider tools web main.py
python -m ruff check database services spider tools web tests main.py
python -m mypy database services spider tools web main.py
python -m pytest -q
```

## 文档导航

- [docs/README.md](docs/README.md) — 文档中心索引
- [docs/docker-deployment.md](docs/docker-deployment.md) — Docker 部署详细指南
- [docs/source-deployment.md](docs/source-deployment.md) — 源码部署详细指南
- [docs/linux-deployment.md](docs/linux-deployment.md) — Linux systemd 部署
- [docs/windows-deployment.md](docs/windows-deployment.md) — Windows 部署
- [docs/mysql-deployment.md](docs/mysql-deployment.md) — MySQL 数据库部署
- [docs/reverse-proxy.md](docs/reverse-proxy.md) — 反向代理与 HTTPS 配置
- [docs/maintenance.md](docs/maintenance.md) — 日常运维与数据备份
- [docs/troubleshooting.md](docs/troubleshooting.md) — 常见问题排查
- [docs/release-checklist.md](docs/release-checklist.md) — 发布检查清单
