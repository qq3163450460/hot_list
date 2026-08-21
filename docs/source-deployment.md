# 源码与虚拟环境部署

本文说明如何直接从源码创建 Python 虚拟环境、安装 hot-list、配置 SQLite 或外部数据库，并使用项目实际提供的命令行入口运行服务。

## 环境要求

- Python 3.10 或更高版本
- pip
- 可选：Git
- 默认使用 SQLite，无需单独安装数据库服务

确认 Python 版本：

```bash
python --version
```

如果系统同时安装了多个 Python 版本，请明确使用满足要求的解释器，例如 `python3.12` 或 Windows 上的 `py -3.12`。

## 获取源码

如果仓库尚未下载，可使用 Git 获取源码，然后进入项目根目录：

```bash
git clone <请替换为实际仓库地址>
cd hot_list
```

如果源码已经存在，直接进入包含 `pyproject.toml` 和 `main.py` 的项目根目录。

## 创建虚拟环境

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

激活后升级基础安装工具：

```bash
python -m pip install --upgrade pip
```

## 安装项目

仅安装运行依赖：

```bash
python -m pip install .
```

开发、测试或修改源码时，建议以可编辑模式安装开发依赖：

```bash
python -m pip install -e ".[dev]"
```

安装后会提供 `hot-list` 控制台命令。也可以始终使用 `python main.py`，两种入口调用的是同一套命令行实现。

验证安装：

```bash
python main.py --help
hot-list --help
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

源码部署默认数据库地址应使用项目目录下的 SQLite 文件：

```dotenv
HOT_LIST_DATABASE_URL=sqlite+aiosqlite:///./data/hot_list.db
```

注意，仓库中的 `.env.example` 默认展示的是 Docker 容器路径 `/app/data/hot_list.db`。源码部署时应将其改为上面的相对路径，否则会尝试访问主机根目录下的 `/app/data`。

创建本地数据目录：

Linux 或 macOS：

```bash
mkdir -p data
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force data
```

建议检查以下生产配置：

```dotenv
HOT_LIST_DEBUG=false
HOT_LIST_LOG_LEVEL=INFO
HOT_LIST_APP_TIMEZONE=Asia/Shanghai
HOT_LIST_SCHEDULER_ENABLED=true
HOT_LIST_COLLECT_ON_STARTUP=true
HOT_LIST_COLLECT_CRON_MINUTE=0
```

不要将真实 Cookie、数据库密码或其他凭据提交到版本库。敏感信息只能写入本地 `.env`、系统环境变量或部署平台的密钥管理系统。

## 启动 Web 服务

生产模式：

```bash
python main.py serve
```

安装项目后也可以使用：

```bash
hot-list serve
```

项目的 `serve` 命令会在 `127.0.0.1:8765` 启动 Uvicorn，默认不启用自动重载。可访问：

- Web 页面：`http://127.0.0.1:8765/`
- AI 分析页面：`http://127.0.0.1:8765/ai-analysis`
- 健康检查：`http://127.0.0.1:8765/health`
- OpenAPI 文档：`http://127.0.0.1:8765/docs`

健康检查：

```bash
curl --fail http://127.0.0.1:8765/health
```

预期响应：

```json
{"status":"ok"}
```

## 开发调试模式

启用自动重载和 debug 日志：

```bash
python main.py dev
```

`debug` 是 `dev` 的别名：

```bash
python main.py debug
```

安装项目后也可使用：

```bash
hot-list dev
```

开发模式会设置 `HOT_LIST_DEBUG=true`，并以 Uvicorn reload 模式启动。生产环境不应使用该模式。

## 命令行用法

### 实时采集但不写入数据库

采集所有已启用平台：

```bash
python main.py live
```

采集单个平台：

```bash
python main.py live weibo
```

### 采集并保存当前小时数据

采集所有已启用平台：

```bash
python main.py collect
```

采集单个平台：

```bash
python main.py collect weibo
```

### 查询最新快照

查询全部平台：

```bash
python main.py latest
```

查询指定平台：

```bash
python main.py latest --platform weibo
```

### 查询历史快照

查询指定日期：

```bash
python main.py history 2026-08-21
```

指定小时：

```bash
python main.py history 2026-08-21 --hour 12
```

指定小时和平台：

```bash
python main.py history 2026-08-21 --hour 12 --platform weibo
```

日期必须使用 `YYYY-MM-DD` 格式，小时范围为 0 至 23。

### 调整 JSON 缩进

全局 `--indent` 参数必须放在子命令之前：

```bash
python main.py --indent 4 latest
```

## 当前平台标识

当前应用实际注册以下平台：

- `weibo`
- `bilibili`
- `toutiao`
- `baidu`
- `zhihu`
- `douyin`

运行中的服务可通过以下接口返回平台启用状态：

```bash
curl http://127.0.0.1:8765/api/platforms
```

平台接口可能受网络环境、访问频率、Cookie、上游接口调整和平台访问规则影响。单个平台采集失败时，聚合采集会在该平台结果中保留错误，不会阻止其他平台完成。

## 调度器运行约束

服务启动时会初始化数据库。启用 `HOT_LIST_COLLECT_ON_STARTUP=true` 后，应用会补采当前小时缺失的平台数据。启用 `HOT_LIST_SCHEDULER_ENABLED=true` 后，APScheduler 会按照 `HOT_LIST_APP_TIMEZONE` 指定的时区，每小时在 `HOT_LIST_COLLECT_CRON_MINUTE` 指定的分钟执行采集。

只要调度器或启动补采仍然启用，就应保持单进程、单副本运行。不要同时启动多个 `serve` 进程，也不要使用多个 Uvicorn worker，否则每个进程都可能独立执行采集任务。

如需运行多个纯 Web 副本，应先将调度任务拆分为独立单实例服务，并在 Web 副本中配置：

```dotenv
HOT_LIST_SCHEDULER_ENABLED=false
HOT_LIST_COLLECT_ON_STARTUP=false
```

## 运行测试与静态检查

安装开发依赖后，在项目根目录执行：

```bash
python -m pytest
python -m ruff check .
python -m mypy database services spider tools web
```

这些命令分别对应项目 `pyproject.toml` 中配置的 pytest、Ruff 和 mypy 检查。

## 停止与退出虚拟环境

前台运行服务时，按 `Ctrl+C` 停止应用。退出虚拟环境：

```bash
deactivate
```

Linux 生产进程管理请继续阅读 `linux-deployment.md`，Windows 部署请阅读 `windows-deployment.md`，升级及数据备份请阅读 `maintenance.md`。