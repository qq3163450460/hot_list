# hot-list

基于 FastAPI、SQLAlchemy 2.x 异步 ORM、aiosqlite 和 APScheduler 的多平台历史热榜服务，目前包含微博、哔哩哔哩、今日头条、百度热榜和知乎采集器。

## 环境要求

- Python 3.10.3 或更高版本
- 默认使用 SQLite
- 可通过 `DATABASE_URL` 风格配置迁移到 `mysql+asyncmy`

## 安装

```bash
python -m pip install -e ".[dev]"
```

## 启动服务

生产模式默认不启用自动重载：

```bash
python main.py serve
# 安装项目后也可使用：hot-list serve
```

开发调试模式会设置 `HOT_LIST_DEBUG=true`，并统一使用 Uvicorn 的 reload 和 debug 日志参数：

```bash
python main.py dev
# debug 是 dev 的别名：python main.py debug
# 等效底层命令：
# python -m uvicorn web.app:app --host 127.0.0.1 --port 8765 --reload --log-level debug
```

也可以在 `.env` 中设置 `HOT_LIST_DEBUG=true`，让 FastAPI 启用 debug 状态。生产环境应保持 `HOT_LIST_DEBUG=false`，且不应强制启用 reload。

服务启动时会初始化数据库；启用启动补采后，会检查当前小时缺失的平台并立即采集。调度器默认在 Asia/Shanghai 时区每小时整点采集并保存，关闭服务时会停止调度器、关闭 HTTP 客户端并释放数据库连接。

## 数据库

默认数据库地址：

```text
sqlite+aiosqlite:///./data/hot_list.db
```

主要表：

- `hot_snapshots`：平台小时快照，包含平台、快照小时、采集时间、状态、错误及条目数
- `hot_items`：快照条目，包含原始排名、保存顺序、标题、链接、图片、热度、分类、描述及元数据

`hot_snapshots` 对 `(platform, snapshot_hour)` 设置唯一约束，保证同一平台同一小时幂等保存。Repository 使用 SQLAlchemy ORM 查询，不依赖 SQLite 专属业务 SQL。

未来迁移 MySQL 时可配置：

```text
HOT_LIST_DATABASE_URL=mysql+asyncmy://user:password@127.0.0.1:3306/hot_list?charset=utf8mb4
```

## 配置

复制 `.env.example` 为 `.env`。环境变量使用 `HOT_LIST_` 前缀。

核心配置：

- `HOT_LIST_DATABASE_URL`
- `HOT_LIST_APP_TIMEZONE=Asia/Shanghai`
- `HOT_LIST_SCHEDULER_ENABLED=true`
- `HOT_LIST_COLLECT_ON_STARTUP=true`
- `HOT_LIST_COLLECT_CRON_MINUTE=0`

Cookie 等敏感信息不得提交到版本库、测试 fixtures 或日志。

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

真实平台采集仍可能受 Cookie、登录状态、风控、地区限制和上游接口变化影响。测试 fixtures 应来自已授权且已脱敏的响应。

## Docker 部署

### SQLite 默认部署

复制示例环境变量文件，并按需填写 Cookie 等敏感配置。不要将 `.env` 提交到版本库：

```bash
cp .env.example .env
docker compose config
docker compose up --build -d
```

服务通过 `http://localhost:8765` 提供访问，健康检查端点为 `http://localhost:8765/health`。容器内 Uvicorn 绑定到 `0.0.0.0:8765`，固定使用一个 worker。

SQLite 数据库存放在容器的 `/app/data/hot_list.db`，并通过 `hot_list_data` 命名卷持久化。停止并重新创建容器不会删除数据；只有显式执行 `docker compose down -v` 才会删除该命名卷及其中的数据。

常用命令：

```bash
docker compose ps
docker compose logs -f app
docker compose exec app python main.py latest
docker compose down
```

### APScheduler 与副本数量

应用进程内运行 APScheduler，并可在启动时执行缺失数据补采。启用 `HOT_LIST_SCHEDULER_ENABLED=true` 或 `HOT_LIST_COLLECT_ON_STARTUP=true` 时，必须保持应用为单副本，并维持 Uvicorn `--workers 1`。不要通过 `docker compose up --scale app=N`、多 worker 或多个相同部署实例横向扩展，否则每个进程都会启动独立调度器，可能造成重复采集和并发写入。

如需横向扩展 Web 服务，应先将调度任务拆分为独立的单实例服务，并在 Web 副本中设置：

```dotenv
HOT_LIST_SCHEDULER_ENABLED=false
HOT_LIST_COLLECT_ON_STARTUP=false
```

### 可选 MySQL 部署

MySQL 配置位于 `docker-compose.mysql.yml`。先在本地 `.env` 中设置真实凭据，不要把密码写入 Compose 文件或提交到版本库：

```dotenv
MYSQL_DATABASE=hot_list
MYSQL_USER=hot_list
MYSQL_PASSWORD=replace-with-a-strong-password
MYSQL_ROOT_PASSWORD=replace-with-a-different-strong-password
```

启动并验证组合配置：

```bash
docker compose -f docker-compose.yml -f docker-compose.mysql.yml config
docker compose -f docker-compose.yml -f docker-compose.mysql.yml up --build -d
```

MySQL 数据通过 `hot_list_mysql_data` 命名卷持久化。应用会等待 MySQL 健康检查通过后再启动。

### Docker 验证

配置或镜像发生变更后，建议依次运行：

```bash
docker compose config
docker compose build
docker compose up -d
docker compose ps
curl --fail http://localhost:8765/health
```

持久化检查可通过记录数据库文件状态、重新创建应用容器并再次检查来完成：

```bash
docker compose exec app python -c "from pathlib import Path; p=Path('/app/data/hot_list.db'); print(p.exists(), p.stat().st_size if p.exists() else 0)"
docker compose up -d --force-recreate app
docker compose exec app python -c "from pathlib import Path; p=Path('/app/data/hot_list.db'); print(p.exists(), p.stat().st_size if p.exists() else 0)"
```

不要在持久化验证期间运行 `docker compose down -v`，因为该命令会主动删除数据卷。