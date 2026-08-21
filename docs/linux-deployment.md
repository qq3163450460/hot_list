# Linux 服务器部署

本文说明如何在 Linux 服务器上通过 Python 虚拟环境、systemd 和 SQLite 部署 hot-list。若希望使用容器部署，请改为阅读 `docker-deployment.md`。

## 前置要求

- Python 3.10 或更高版本
- pip 和 venv
- Git，可选
- 具备 sudo 权限
- 反向代理场景下已安装 Nginx 或其他代理服务器

以下示例使用部署目录 `/opt/hot-list`、运行用户 `hotlist`，服务监听项目实际固定的 `127.0.0.1:8765`。请根据服务器环境调整路径、域名和用户。

## 创建运行用户和部署目录

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin hotlist
sudo mkdir -p /opt/hot-list
sudo chown -R hotlist:hotlist /opt/hot-list
```

将项目源码复制或克隆到 `/opt/hot-list`。仓库地址需要替换为实际地址：

```bash
sudo -u hotlist git clone <请替换为实际仓库地址> /opt/hot-list
```

如果源码由其他方式上传，请确保运行用户拥有读取项目文件以及写入 `data` 目录的权限：

```bash
sudo mkdir -p /opt/hot-list/data
sudo chown -R hotlist:hotlist /opt/hot-list
```

## 安装 Python 环境

以 Debian 或 Ubuntu 为例：

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```

创建虚拟环境并安装项目：

```bash
sudo -u hotlist python3 -m venv /opt/hot-list/.venv
sudo -u hotlist /opt/hot-list/.venv/bin/python -m pip install --upgrade pip
sudo -u hotlist /opt/hot-list/.venv/bin/python -m pip install /opt/hot-list
```

需要在服务器上运行测试或修改源码时，可安装开发依赖：

```bash
sudo -u hotlist /opt/hot-list/.venv/bin/python -m pip install -e "/opt/hot-list[dev]"
```

## 创建生产配置

从示例文件创建本地配置：

```bash
sudo -u hotlist cp /opt/hot-list/.env.example /opt/hot-list/.env
sudo chmod 600 /opt/hot-list/.env
```

源码部署必须将 SQLite 地址改为服务器上的实际路径。建议在 `.env` 中使用绝对路径：

```dotenv
HOT_LIST_DATABASE_URL=sqlite+aiosqlite:////opt/hot-list/data/hot_list.db
HOT_LIST_DEBUG=false
HOT_LIST_LOG_LEVEL=INFO
HOT_LIST_APP_TIMEZONE=Asia/Shanghai
HOT_LIST_SCHEDULER_ENABLED=true
HOT_LIST_COLLECT_ON_STARTUP=true
HOT_LIST_COLLECT_CRON_MINUTE=0
```

SQLite 绝对路径在 URL 中需要四个斜杠。不要直接沿用 `.env.example` 中面向 Docker 的 `/app/data/hot_list.db`，除非服务器确实存在该目录。

平台 Cookie、数据库密码和其他敏感内容只能保存在权限受限的 `.env` 或服务器密钥管理系统中。不要将真实凭据写入 systemd 单元、部署文档或版本库。

## 首次手动验证

先以运行用户执行命令行帮助：

```bash
cd /opt/hot-list
sudo -u hotlist /opt/hot-list/.venv/bin/python main.py --help
```

查询数据库。首次执行时应用会初始化数据库：

```bash
cd /opt/hot-list
sudo -u hotlist /opt/hot-list/.venv/bin/python main.py latest
```

为了避免手动验证 Web 服务时立即访问外部平台，可以临时关闭调度器和启动补采：

```bash
cd /opt/hot-list
sudo -u hotlist env HOT_LIST_SCHEDULER_ENABLED=false HOT_LIST_COLLECT_ON_STARTUP=false /opt/hot-list/.venv/bin/python main.py serve
```

另开终端检查健康接口：

```bash
curl --fail http://127.0.0.1:8765/health
```

预期响应：

```json
{"status":"ok"}
```

验证完成后按 `Ctrl+C` 停止临时服务。

## 创建 systemd 服务

创建 `/etc/systemd/system/hot-list.service`：

```ini
[Unit]
Description=hot-list FastAPI service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=hotlist
Group=hotlist
WorkingDirectory=/opt/hot-list
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/hot-list/.venv/bin/python /opt/hot-list/main.py serve
Restart=on-failure
RestartSec=5
TimeoutStopSec=30
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

项目会从工作目录中的 `.env` 自动加载配置，因此 `WorkingDirectory=/opt/hot-list` 不应省略。

重新加载 systemd 并启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now hot-list
```

检查状态：

```bash
sudo systemctl status hot-list --no-pager
```

查看日志：

```bash
sudo journalctl -u hot-list -f
```

查看最近 100 行日志：

```bash
sudo journalctl -u hot-list -n 100 --no-pager
```

重启或停止服务：

```bash
sudo systemctl restart hot-list
sudo systemctl stop hot-list
sudo systemctl start hot-list
```

## 单实例约束

应用进程内运行 APScheduler，并可在启动时补采当前小时缺失的平台数据。当以下任一选项为 `true` 时，只能运行一个应用实例：

```dotenv
HOT_LIST_SCHEDULER_ENABLED=true
HOT_LIST_COLLECT_ON_STARTUP=true
```

不要同时启动多个 systemd 服务副本，也不要为 Uvicorn配置多个 worker，否则不同进程会分别执行采集任务，可能造成重复采集和并发写入。

如果未来需要运行多个纯 Web 副本，应先将调度任务拆分为独立的单实例服务，并在所有 Web 副本中关闭内置调度和启动补采：

```dotenv
HOT_LIST_SCHEDULER_ENABLED=false
HOT_LIST_COLLECT_ON_STARTUP=false
```

## 防火墙与监听地址

项目的 `python main.py serve` 实际监听 `127.0.0.1:8765`，适合由同一台服务器上的 Nginx 或其他反向代理转发，无需把 8765 端口暴露到公网。

如果启用了主机防火墙，只需开放反向代理使用的 HTTP 和 HTTPS 端口。例如使用 UFW：

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

不要为了公网访问而直接修改文档示例去暴露开发服务器。推荐按照 `reverse-proxy.md` 配置反向代理和 HTTPS。

## 日常健康检查

```bash
sudo systemctl is-active hot-list
curl --fail http://127.0.0.1:8765/health
sudo journalctl -u hot-list -n 50 --no-pager
```

检查最新持久化快照：

```bash
cd /opt/hot-list
sudo -u hotlist /opt/hot-list/.venv/bin/python main.py latest
```

检查指定平台：

```bash
cd /opt/hot-list
sudo -u hotlist /opt/hot-list/.venv/bin/python main.py latest --platform weibo
```

## 更新部署

升级前应先备份 `/opt/hot-list/data/hot_list.db` 和本地 `.env`。停止服务后更新源码并重新安装：

```bash
sudo systemctl stop hot-list
cd /opt/hot-list
sudo -u hotlist git pull --ff-only
sudo -u hotlist /opt/hot-list/.venv/bin/python -m pip install /opt/hot-list
sudo systemctl start hot-list
```

验证升级结果：

```bash
sudo systemctl status hot-list --no-pager
curl --fail http://127.0.0.1:8765/health
sudo journalctl -u hot-list -n 100 --no-pager
```

完整的升级、SQLite 备份、恢复和回滚流程参见 `maintenance.md`。

## 常见权限检查

确认运行用户可以读取配置并写入数据目录：

```bash
sudo -u hotlist test -r /opt/hot-list/.env
sudo -u hotlist test -w /opt/hot-list/data
```

修复项目目录所有权：

```bash
sudo chown -R hotlist:hotlist /opt/hot-list
sudo chmod 600 /opt/hot-list/.env
```

如果服务无法启动、数据库不可写、端口被占用或平台采集失败，请查看 `troubleshooting.md`。