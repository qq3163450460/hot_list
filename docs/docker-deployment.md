# Docker 与 Docker Compose 部署

本文说明如何使用仓库现有的 `Dockerfile`、`docker-compose.yml` 和可选的 `docker-compose.mysql.yml` 部署 hot-list。默认方案使用 SQLite，并通过 Docker 命名卷持久化数据。

## 前置要求

- Docker Engine 或 Docker Desktop
- Docker Compose V2，可使用 `docker compose` 命令
- 已取得项目源码
- 主机的 8765 端口未被其他程序占用

在项目根目录执行以下命令确认环境：

```bash
docker --version
docker compose version
```

## 配置环境变量

复制示例配置：

Linux 或 macOS：

```bash
cp .env.example .env
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

默认 Compose 配置会将数据库地址覆盖为容器内的 SQLite 文件：

```dotenv
HOT_LIST_DATABASE_URL=sqlite+aiosqlite:////app/data/hot_list.db
```

平台 Cookie、数据库密码等敏感信息只能写入本地 `.env` 或密钥管理系统。不要在文档、Compose 文件或 Git 提交中写入真实凭据。

生产环境建议至少检查以下配置：

```dotenv
HOT_LIST_DEBUG=false
HOT_LIST_LOG_LEVEL=INFO
HOT_LIST_APP_TIMEZONE=Asia/Shanghai
HOT_LIST_SCHEDULER_ENABLED=true
HOT_LIST_COLLECT_ON_STARTUP=true
HOT_LIST_COLLECT_CRON_MINUTE=0
```

## 启动默认 SQLite 部署

先验证 Compose 配置：

```bash
docker compose config
```

构建并后台启动：

```bash
docker compose up --build -d
```

查看容器状态：

```bash
docker compose ps
```

跟踪应用日志：

```bash
docker compose logs -f app
```

服务默认映射到主机的 8765 端口：

- Web 页面：`http://localhost:8765/`
- AI 分析页面：`http://localhost:8765/ai-analysis`
- 健康检查：`http://localhost:8765/health`
- OpenAPI 文档：`http://localhost:8765/docs`

可使用以下命令检查健康状态：

```bash
curl --fail http://localhost:8765/health
```

预期响应：

```json
{"status":"ok"}
```

## 数据持久化

默认 Compose 配置将 `/app/data` 挂载到 `hot_list_data` 命名卷，SQLite 数据库位于：

```text
/app/data/hot_list.db
```

查看命名卷：

```bash
docker volume ls
```

重新创建应用容器不会删除该命名卷：

```bash
docker compose up -d --force-recreate app
```

停止并删除容器及网络，但保留数据卷：

```bash
docker compose down
```

以下命令会删除命名卷及其中的 SQLite 数据，除非已经完成备份，否则不要执行：

```bash
docker compose down -v
```

## 容器内命令行用法

查询最新持久化快照：

```bash
docker compose exec app python main.py latest
```

查询指定平台：

```bash
docker compose exec app python main.py latest --platform weibo
```

采集并保存所有已启用平台的当前小时数据：

```bash
docker compose exec app python main.py collect
```

只采集并保存一个平台：

```bash
docker compose exec app python main.py collect weibo
```

查询指定日期的历史数据：

```bash
docker compose exec app python main.py history 2026-08-21
```

查询指定日期、小时和平台：

```bash
docker compose exec app python main.py history 2026-08-21 --hour 12 --platform weibo
```

`live` 命令会实时采集，但不会写入数据库：

```bash
docker compose exec app python main.py live
docker compose exec app python main.py live weibo
```

支持的平台标识以 `/api/platforms` 的实际响应为准。当前代码注册了 `weibo`、`bilibili`、`toutiao`、`baidu`、`zhihu` 和 `douyin`。

## 更新镜像并重建

拉取或替换新版本源码后执行：

```bash
docker compose build --pull
docker compose up -d
```

验证更新结果：

```bash
docker compose ps
docker compose logs --tail 100 app
curl --fail http://localhost:8765/health
```

升级前应备份 SQLite 数据卷。完整操作流程参见 `maintenance.md`。

## APScheduler 与副本数量

应用进程内运行 APScheduler，并可在启动时补采当前小时缺失的数据。只要以下任一配置为 `true`，就应保持单进程、单副本运行：

```dotenv
HOT_LIST_SCHEDULER_ENABLED=true
HOT_LIST_COLLECT_ON_STARTUP=true
```

仓库的 Dockerfile 已使用一个 Uvicorn worker：

```text
--workers 1
```

不要在保留内置调度器的情况下使用以下类型的横向扩展：

```bash
docker compose up --scale app=2
```

多个应用进程会分别启动调度器，可能造成重复采集和并发写入。如果需要扩展 Web 服务，应先将调度工作拆分为独立的单实例服务，并在纯 Web 副本中关闭调度和启动补采：

```dotenv
HOT_LIST_SCHEDULER_ENABLED=false
HOT_LIST_COLLECT_ON_STARTUP=false
```

## 使用可选 MySQL 组合配置

MySQL 部署通过基础 Compose 文件和覆盖文件共同启动：

```bash
docker compose -f docker-compose.yml -f docker-compose.mysql.yml config
docker compose -f docker-compose.yml -f docker-compose.mysql.yml up --build -d
```

必须先在本地 `.env` 中设置 `MYSQL_USER`、`MYSQL_PASSWORD` 和 `MYSQL_ROOT_PASSWORD`。详细配置、备份和恢复方法参见 `mysql-deployment.md`。

## 常用管理命令

```bash
docker compose ps
docker compose logs -f app
docker compose restart app
docker compose stop
docker compose start
docker compose down
```

查看最近 100 行日志：

```bash
docker compose logs --tail 100 app
```

查看容器内有效环境变量时，应避免将输出复制到公开问题或日志中，因为其中可能含有 Cookie 或数据库凭据：

```bash
docker compose exec app env
```

## 基础验证流程

Docker 配置或应用代码变更后，建议依次运行：

```bash
docker compose config
docker compose build
docker compose up -d
docker compose ps
curl --fail http://localhost:8765/health
docker compose exec app python main.py latest
```

如果容器无法启动、健康检查失败或采集结果异常，请继续阅读 `troubleshooting.md`。公网提供服务前，请阅读 `reverse-proxy.md` 并配置 HTTPS。