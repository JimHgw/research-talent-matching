# 开发与 Docker 使用说明

本项目后端使用 **Flask + SQLAlchemy + SQLite**，容器内由 **Gunicorn** 启动 Flask 应用。现在可以运行一键脚本，自动构建后端镜像并启动容器。SQLite 由后端直接读写，不需要 PostgreSQL、MySQL 或第二个数据库容器。

Sprint 需求、数据模型与接口规格见 [README_DEVELOPER_EN.md](README_DEVELOPER_EN.md)；不使用 Docker 的本机开发方式见 [backend/README.md](backend/README.md)。

## 1. 运行前准备

- Windows / macOS：安装并启动 [Docker Desktop](https://docs.docker.com/desktop/)。Windows 使用 **Linux containers** 模式。
- Linux：安装并启动 Docker Engine，安装 Docker Compose 插件，并确保当前用户有权限访问 Docker。
- 使用支持 `docker compose up --wait --wait-timeout` 的新版 Compose。
- 首次构建需要联网下载 Python 基础镜像和后端依赖。
- 默认使用本机 `8000` 端口；如果之前启动过本机 Flask，请先停止它，或按第 5 节更换端口。

只运行 Docker 后端时，无需先运行 `setup.ps1` / `setup.sh`，也无需在宿主机安装 Python、Node.js 或 Python 依赖。前端开发仍使用原有安装流程。

## 2. 一键封装并启动

在项目根目录执行以下命令。

**Windows PowerShell：**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\docker-backend.ps1
```

**macOS / Linux：**

```sh
sh docker-backend.sh
```

也可以从其他目录使用脚本的绝对路径。脚本按自身位置定位项目，支持路径中包含空格。

默认操作为 `up`，程序会依次完成：

1. 检查 Docker、Compose 和 Linux 容器环境。
2. 从 `backend/Dockerfile` 构建镜像 `banana-backend:local`。
3. 创建或复用 SQLite 命名数据卷，启动一个 `backend` 容器。
4. 在容器启动时通过 Flask CLI 执行 `init-db` 和 `seed-tags`，然后使用 Gunicorn 启动 Flask 应用。
5. 最多等待 120 秒，直到健康检查通过。镜像构建时间不包含在这个等待时间内。

成功后会显示容器映射地址。默认健康检查地址为：

```text
http://127.0.0.1:8000/healthz
```

正常响应是 `{"status":"ok"}`。该接口只检查服务和数据库连接，不创建账号或会话；数据库访问失败时返回 HTTP 503。访问 `/` 返回 404 是正常的，本镜像仅提供后端 API，不包含前端页面。

构建、初始化或健康检查失败时，脚本返回非零状态，不会报告启动成功。健康检查失败后容器可能仍在运行或重启，使用 `logs` 查看原因，必要时执行 `stop`。

默认端口只绑定宿主机 `127.0.0.1`。容器内 Gunicorn 监听 `0.0.0.0:8000`，加载 `backend.app:create_app()`，不启用开发调试器或自动重载。默认 HTTP 和端口设置适合**本地开发与演示**；正式部署还应配置 HTTPS 和可信反向代理。

Gunicorn 不替换 Flask：Flask 负责路由、业务逻辑和数据库访问，Gunicorn 负责接收 HTTP 请求、运行应用和管理工作进程。Docker 构建时会从 `backend/requirements-docker.txt` 自动安装固定版本的 Gunicorn，无需手工安装。它仅运行在 Linux 容器内，不加入 Windows 本机开发依赖；本机开发仍可使用 `flask run`。参见 [Flask 的 Gunicorn 部署说明](https://flask.palletsprojects.com/en/stable/deploying/gunicorn/)。

初始配置为 **1 个 worker、4 个线程**，保持单容器并控制资源占用。SQLite 写事务仍使用现有的串行写锁；增加线程不会使 SQLite 支持多个同时写事务。Gunicorn 将访问日志和错误日志输出到容器日志；停止容器时 Compose 留出 35 秒供默认的优雅关闭流程完成。

## 3. 创建登录账号

初始化会创建缺失的数据表和受控标签，**不会创建默认账号或密码**。新容器使用新的数据库，不会自动导入本机 `data/h18abanana.db` 中的账号。

启动成功后，在项目根目录分别执行以下命令。这些命令在 PowerShell 和 macOS / Linux 终端中相同：

```sh
docker compose exec backend python -m flask --app backend.app provision-user --email talent@example.test --display-name "Demo Talent" --role TALENT
docker compose exec backend python -m flask --app backend.app provision-user --email team@example.test --display-name "Demo Team" --role RESEARCH_TEAM
```

每条命令会要求输入两次密码，输入不显示在终端中。相同邮箱不能重复创建。停止或重建容器后账号仍然存在，无需重新创建。

## 4. 连接现有前端

前端不包含在后端镜像中。首次本机开发先按原有说明运行 `setup.ps1`（Windows）或 `sh setup.sh`（macOS / Linux），然后在另一终端启动前端：

**Windows：**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\frontend\run.ps1 dev
```

**macOS / Linux：**

```sh
sh frontend/run.sh dev
```

打开 `http://127.0.0.1:5173`，使用第 3 节创建的账号登录。Vite 默认将 `/api` 转发至 `http://127.0.0.1:8000`，与 Docker 后端兼容。浏览器访问期间保持同一主机名，不要来回切换 `localhost` 和 `127.0.0.1`。

## 5. 自定义端口与环境变量

默认无需创建任何环境文件。需要修改配置时，复制根目录的 `.env.example` 为根目录 `.env`：

```powershell
# Windows
Copy-Item .env.example .env
```

```sh
# macOS / Linux
cp .env.example .env
```

| 配置 | 默认值 | 说明 |
| --- | --- | --- |
| `BACKEND_PORT` | `8000` | 宿主机端口，容器内部仍为 8000 |
| `COOKIE_SECURE` | `false` | 本地 HTTP 使用 false；HTTPS 部署使用 true |
| `ALLOWED_ORIGINS` | `http://127.0.0.1:5173,http://localhost:5173` | 允许的前端 Origin，逗号分隔且不带结尾 `/` |

修改后重新运行一键脚本。例如 `BACKEND_PORT=8001` 时，健康地址变为 `http://127.0.0.1:8001/healthz`；同时在 `frontend/.env.local` 中设置 `API_PROXY_TARGET=http://127.0.0.1:8001` 并重启前端。

脚本显式读取**仓库根目录**的 `.env`（存在时）或 `.env.example`，不会读取启动脚本所在终端目录中的其他 `.env`。终端已导出的同名变量优先级更高。`backend/.env.example` 仍是本机启动的配置参考，不会被此脚本自动读取。

`DATABASE_URL` 在 Compose 中固定为 `sqlite:////app/data/h18abanana.db`，确保数据库写入数据卷。不要将本机 Windows 数据库路径填入容器配置。`ALLOWED_ORIGINS` 用于 CSRF 校验，不代表启用了跨域 CORS；前端继续通过 Vite 同域代理访问 API。

## 6. 构建、停止、查看日志

| 操作 | Windows：`docker-backend.ps1` 参数 | macOS / Linux：`docker-backend.sh` 参数 |
| --- | --- | --- |
| 构建并启动 / 更新 | 无参数，或 `-Action up` | 无参数，或 `up` |
| 只构建镜像，不启动容器 | `-Action build` | `build` |
| 查看状态 | `-Action status` | `status` |
| 持续查看最近日志 | `-Action logs` | `logs` |
| 停止容器 | `-Action stop` | `stop` |
| 删除容器及网络，保留数据卷 | `-Action down` | `down` |

例如只封装镜像：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\docker-backend.ps1 -Action build
```

```sh
sh docker-backend.sh build
```

需要将镜像交给其他人时，可在构建后导出：

```sh
docker image save --output banana-backend.tar banana-backend:local
```

接收方导入镜像后，使用同一版本项目的 Compose 配置启动，不重新构建：

```sh
docker image load --input banana-backend.tar
docker compose up --no-build --detach --wait --wait-timeout 120 backend
```

导出的镜像包含后端代码和 Python 依赖，不包含数据库记录、账号或本机环境文件。数据备份需要单独处理。

## 7. 数据保存与更新行为

- 只有一个后端服务，SQLite 没有独立进程或数据库容器。
- Compose 项目名默认是 `banana-backend`，数据卷默认是 `banana-backend_backend_data`，挂载至 `/app/data`。保持同一个项目名即可复用数据；多份仓库默认也会操作同一个项目。
- 重复运行启动脚本会复用数据卷；`init-db` 只创建缺失的表，重复载入相同标签不会覆盖数据。
- 现有表结构变化仍需显式迁移；现有标签与种子定义冲突时，启动会失败，需要先核对差异，不能靠重建容器解决。
- `stop`、脚本的 `down` 和镜像重建保留数据。**不要使用 `docker compose down -v` 或删除该数据卷，除非明确要清空数据库。**
- 数据卷与容器生命周期分离，但不是备份。备份 SQLite 时先停止后端再备份数据卷，或使用 SQLite backup API，避免直接复制正在写入的数据库。
- 本机 `data/`、虚拟环境、前端依赖和环境文件均不进入镜像。现有本机数据不会自动复制或覆盖。
- 源代码复制进镜像，不是实时挂载。后端代码更新后重新运行启动脚本即可重建镜像；默认保持一个后端实例。

如果通过 `COMPOSE_PROJECT_NAME` 自定义项目名，启动、账号管理、日志与停止操作都要使用同一个值；新项目名会创建另一套数据卷。

## 8. 排错与验证

| 现象 | 处理方式 |
| --- | --- |
| 找不到 Docker | 安装 Docker Desktop / Engine，确认 `docker` 在 PATH 上，重新打开终端 |
| 无法连接 Docker | 启动 Docker Desktop / Engine；Linux 检查当前用户访问 Docker 的权限 |
| 提示需要 Linux containers | 在 Docker Desktop 中切换至 Linux 容器模式 |
| Compose 不支持 `--wait` | 更新 Docker Desktop 或 Compose 插件 |
| 8000 端口已被占用 | 停止原有本机后端，或按第 5 节修改端口 |
| 镜像或依赖下载失败 | 检查 Docker 网络、代理及镜像仓库访问，然后重试 |
| 健康检查超时 / 初始化失败 | 执行 `logs` 检查日志；不要删除数据卷作为默认修复方法 |
| 前端登录失败 | 确认已创建账号、前端代理端口匹配、Origin 在白名单内，本地 HTTP 使用 `COOKIE_SECURE=false` |

代码层回归测试仍使用隔离的临时 SQLite 文件，不修改本机或容器数据：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

```sh
.venv/bin/python -m pytest -q
```

`backend/tests/test_docker_backend.py` 检查启动脚本的失败处理、路径解析、初始化幂等性与健康接口；其中 Docker 命令使用替身，不代表真实镜像已构建成功。实际 Docker 验收应执行一键启动、创建账号并登录、执行 `down` 后重新启动，确认原账号和资料仍存在。
