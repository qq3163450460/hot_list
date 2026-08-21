# Windows 部署

本文说明如何在 Windows 上通过 Python 虚拟环境部署和运行 hot-list。若希望使用容器部署，请改为阅读 `docker-deployment.md`。

## 前置要求

- Windows 10、Windows 11 或 Windows Server
- Python 3.10 或更高版本
- pip 和 venv
- 可选：Git
- 项目目录及 `data` 目录的读写权限

以下命令默认在项目根目录执行，也就是包含 `pyproject.toml` 和 `main.py` 的目录。

## 确认 Python 环境

在 PowerShell 中运行：

```powershell
py --version
py -0p
```

如果未安装 Python，请从可信的软件源安装 Python 3.10 或更高版本，并确保 Python Launcher 或 `python` 命令可用。

## 创建虚拟环境

在项目根目录运行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

如果系统没有 Python 3.12，但已安装其他满足要求的版本，可以改用相应版本，例如：

```powershell
py -3.10 -m venv .venv
```

如果 PowerShell 阻止执行激活脚本，可仅对当前用户设置适当的执行策略：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

如果组织策略不允许修改执行策略，可以不激活虚拟环境，后续命令直接使用：

```powershell
.\.venv\Scripts\python.exe
```

在命令提示符中激活虚拟环境：

```bat
.venv\Scripts\activate.bat
```

## 安装项目

升级 pip：

```powershell
python -m pip install --upgrade pip
```

仅安装运行依赖：

```powershell
python -m pip install .
```

开发、测试或修改源码时，建议以可编辑模式安装开发依赖：

```powershell
python -m pip install -e ".[dev]"
```

验证命令行入口：

```powershell
python main.py --help
hot-list --help
```

## 配置环境变量

复制示例配置：

```powershell
Copy-Item .env.example .env
```

源码部署应将 `.env` 中的数据库地址设置为项目目录下的 SQLite 文件：

```dotenv
HOT_LIST_DATABASE_URL=sqlite+aiosqlite:///./data/hot_list.db
HOT_LIST_DEBUG=false
HOT_LIST_LOG_LEVEL=INFO
HOT_LIST_APP_TIMEZONE=Asia/Shanghai
HOT_LIST_SCHEDULER_ENABLED=true
HOT_LIST_COLLECT_ON_STARTUP=true
HOT_LIST_COLLECT_CRON_MINUTE=0
```

仓库的 `.env.example` 默认展示 Docker 容器使用的 `/app/data/hot_list.db`。Windows 源码部署时不要直接沿用该容器路径。

创建数据目录：

```powershell
New-Item -ItemType Directory -Force data
```

平台 Cookie、MySQL 密码和其他敏感配置只能保存在本地 `.env`、Windows 凭据管理方案或部署平台的密钥管理系统中。不要将真实凭据写入 Markdown、脚本、日志或提交到版本库。

## 启动 Web 服务

生产模式：

```powershell
python main.py serve
```

安装项目后也可以使用：

```powershell
hot-list serve
```

服务默认监听 `127.0.0.1:8765`。可访问：

- Web 页面：`http://127.0.0.1:8765/`
- AI 分析页面：`http://127.0.0.1:8765/ai-analysis`
- 健康检查：`http://127.0.0.1:8765/health`
- OpenAPI 文档：`http://127.0.0.1:8765/docs`

使用 PowerShell 检查健康状态：

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
```

预期结果中的 `status` 为 `ok`。

停止前台服务时按 `Ctrl+C`。

## 开发调试模式

启用自动重载和 debug 日志：

```powershell
python main.py dev
```

`debug` 是 `dev` 的别名：

```powershell
python main.py debug
```

仓库还提供 `start_debug.bat`。该脚本会优先查找 `.venv`、`venv` 或 `env` 目录中的 Python，然后执行 `python main.py debug`：

```powershell
.\start_debug.bat
```

开发模式不应作为生产部署方式。

## 命令行操作

实时采集但不写入数据库：

```powershell
python main.py live
python main.py live weibo
```

采集并保存当前小时数据：

```powershell
python main.py collect
python main.py collect weibo
```

查询最新持久化快照：

```powershell
python main.py latest
python main.py latest --platform weibo
```

查询历史快照：

```powershell
python main.py history 2026-08-21
python main.py history 2026-08-21 --hour 12
python main.py history 2026-08-21 --hour 12 --platform weibo
```

日期必须使用 `YYYY-MM-DD` 格式，小时范围为 0 至 23。

全局 JSON 缩进参数必须放在子命令之前：

```powershell
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

运行中的服务可通过以下命令查看平台启用状态：

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/platforms
```

真实平台采集可能受 Cookie、登录状态、访问频率、网络环境、地区限制和上游接口变化影响。

## 单实例运行约束

应用进程内运行 APScheduler，并可在启动时补采当前小时缺失的平台数据。当以下任一配置为 `true` 时，应保持应用为单进程、单副本运行：

```dotenv
HOT_LIST_SCHEDULER_ENABLED=true
HOT_LIST_COLLECT_ON_STARTUP=true
```

不要同时运行多个 `python main.py serve` 实例，也不要在未拆分调度任务的情况下增加多个 Uvicorn worker。每个进程都可能独立执行采集任务，造成重复采集和并发写入。

如需运行多个纯 Web 副本，应先将调度任务拆分为独立的单实例服务，并在 Web 副本中设置：

```dotenv
HOT_LIST_SCHEDULER_ENABLED=false
HOT_LIST_COLLECT_ON_STARTUP=false
```

## 作为后台任务运行

对于长期运行的生产实例，建议使用具备自动重启、日志收集和受控权限的 Windows 服务管理方案，而不是让 PowerShell 窗口长期保持打开。

无论使用哪种服务管理器，启动程序都应满足以下条件：

- 工作目录指向项目根目录，以便应用读取 `.env`
- 使用虚拟环境中的 Python
- 执行 `main.py serve`
- 仅启动一个应用实例
- 服务账户能够读取项目文件和 `.env`
- 服务账户能够写入 `data` 目录
- 不在命令行参数或服务定义中写入真实密钥

对应的程序和参数示例：

```text
程序：D:\myproject\hot_list\.venv\Scripts\python.exe
参数：D:\myproject\hot_list\main.py serve
工作目录：D:\myproject\hot_list
```

实际路径应根据部署位置调整。服务账户不应拥有超过运行应用所需的权限。

## Windows 防火墙与反向代理

项目的 `serve` 命令绑定到 `127.0.0.1:8765`，默认只能从本机访问，适合由同一台机器上的反向代理转发。

不建议直接将开发服务器端口暴露到公网。公网部署前应配置 HTTPS、访问控制、请求大小限制和安全响应头。相关建议参见 `reverse-proxy.md`。

## 运行测试和静态检查

安装开发依赖后执行：

```powershell
python -m compileall -q database services spider tools web main.py
python -m ruff check database services spider tools web tests main.py
python -m mypy database services spider tools web main.py
python -m pytest -q
```

如果某个工具未安装，应先确认已执行：

```powershell
python -m pip install -e ".[dev]"
```

## 更新部署

升级前先停止应用，并备份本地 `.env` 与 `data\hot_list.db`。

更新源码后重新安装：

```powershell
python -m pip install .
```

如果使用可编辑安装，通常不需要重复安装本地代码，但依赖或 `pyproject.toml` 发生变化后仍应执行：

```powershell
python -m pip install -e ".[dev]"
```

启动应用后验证：

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
python main.py latest
```

完整备份、恢复、升级和回滚流程参见 `maintenance.md`。

## 常见检查

确认虚拟环境中的 Python 可运行：

```powershell
.\.venv\Scripts\python.exe --version
```

确认 8765 端口占用情况：

```powershell
Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue
```

检查数据库文件：

```powershell
Get-Item .\data\hot_list.db -ErrorAction SilentlyContinue
```

检查 `.env` 是否存在，但不要将其内容复制到公开日志或问题中：

```powershell
Test-Path .\.env
```

如果应用无法启动、端口被占用、数据库不可写、环境变量未加载或采集失败，请继续阅读 `troubleshooting.md`。
