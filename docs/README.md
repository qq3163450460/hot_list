# hot-list 文档中心

本文档目录集中说明 hot-list 的部署、配置、运维、故障排查和 GitHub 发布准备。项目概览、核心功能与最短快速开始流程请先阅读仓库根目录的 ../README.md。

## 部署指南

- docker-deployment.md
- source-deployment.md
- linux-deployment.md
- windows-deployment.md
- mysql-deployment.md
- reverse-proxy.md

## 运维与发布

- maintenance.md
- troubleshooting.md
- release-checklist.md

## 阅读建议

1. 本地试用优先阅读根目录 README 的快速开始章节。
2. 希望快速部署时选择 Docker Compose；默认使用持久化 SQLite 命名卷。
3. 需要直接管理 Python 进程时，选择源码部署，并根据操作系统继续阅读 Linux 或 Windows 指南。
4. 只有在确实需要独立数据库服务时才启用 MySQL 组合配置。
5. 公网部署前必须配置反向代理、HTTPS、访问控制和可靠的备份策略。

## 重要运行约束

应用内置 APScheduler，并且可在启动时补采当前小时缺失的数据。当 `HOT_LIST_SCHEDULER_ENABLED=true` 或 `HOT_LIST_COLLECT_ON_STARTUP=true` 时，应保持应用为单进程、单副本运行。Dockerfile 已固定使用一个 Uvicorn worker。不要在未拆分调度任务的情况下启用多个 worker 或横向扩展多个应用副本，否则可能重复采集并产生并发写入。

所有平台 Cookie、MySQL 密码及其他敏感配置都只能写入本地 `.env` 或部署平台的密钥管理系统。不要将真实凭据写入 Markdown、Compose 文件或提交到版本库。