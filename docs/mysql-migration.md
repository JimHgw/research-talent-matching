# SQLite 转 MySQL

项目默认使用 **MySQL 8.4 + PyMySQL + SQLAlchemy**。前端和 HTTP API 不需要更改。
SQLite 连接仍可显式配置，供旧数据迁移、回退和快速回归测试使用。

## 不保留旧数据：直接启动空的 MySQL

新环境，或明确不需要旧 SQLite 账号、资料及其他记录时，直接使用本节即可。
**跳过后面的迁移命令，无需删除旧 SQLite 文件或数据卷。**
确认进程环境及根目录 `.env` 中没有仍指向 SQLite 的 `DATABASE_URL`；如有，移除该覆盖，
使用下面的 `MYSQL_*` 设置。此方式在首次创建 `mysql_data` 时得到空的业务数据库；
若已有 MySQL 数据卷，普通启动会继续使用其中的数据，不会自动清空。

在项目根目录检查 `.env.example`。已有 `.env` 时，将新增的 `MYSQL_*` 配置合并进去，
保留原来的 SMTP、端口和其他设置。示例密码仅用于本地开发，部署时须设置自己的密码。
MySQL 镜像仅在数据卷第一次初始化时创建库和账号；已有 MySQL 卷时，修改 `.env`
不会自动更改库内密码，应先在 MySQL 中更新账号，再同步 API/worker 配置。

```sh
docker compose up --build --detach --wait --wait-timeout 180
```

Compose 先等待 MySQL 可连接，再初始化后端和词表，最后启动前端和文档 worker。
MySQL 默认不向宿主机公开端口；后端通过内部地址 `mysql:3306` 连接。
`mysql_data` 存放数据库，原 `backend_data` 保留上传文件及旧 SQLite 文件。
新 MySQL 库不会自动导入旧账号，也不会创建默认账号。
启动时会自动创建表并初始化标签词表；账号需要重新注册或通过 `provision-user` 创建。
旧上传文件即使仍在 `backend_data` 中，也不会自动出现在新的数据库或用户界面里。

## 迁移现有 Docker 环境

**需要保留旧 SQLite 数据时，先完成本节，再启动新版本 API。** 普通启动会初始化词表，
迁移命令会拒绝向任何已有业务数据的 MySQL 库导入。使用原来的 Compose 项目名，
以便挂载原 `backend_data`，不要更换项目名或删除数据卷。

1. 停止 API 和文档 worker，暂停业务写入，并保存当前版本与数据库配置。

   ```sh
   docker compose stop backend document-worker
   docker compose build backend
   ```

2. 在仍挂载旧数据卷的临时容器中创建 SQLite 一致性备份。备份保存在原数据卷，
   文件名带时间戳。上传文件继续保留在 `/app/data/documents`；应另外备份整个文档目录。

   ```sh
   docker compose run --rm --no-deps --entrypoint python backend -c "import sqlite3; from datetime import datetime, timezone; source = sqlite3.connect('file:/app/data/h18abanana.db?mode=ro', uri=True); name = '/app/data/h18abanana-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.backup.db'; target = sqlite3.connect(name); source.backup(target); target.close(); source.close(); print(name)"
   ```

3. 启动 MySQL，然后直接运行迁移命令。这里覆盖容器入口，避免预先运行 `seed-tags`。

   ```sh
   docker compose up --detach --wait --wait-timeout 180 mysql
   docker compose run --rm --no-deps --entrypoint python backend -m flask --app backend.app migrate-sqlite --source sqlite:////app/data/h18abanana.db
   ```

   迁移按外键顺序复制所有已知业务表，包括账号和密码哈希、会话、资料、隐私、
   机会、收藏、短名单、文档元数据、提取结果和 worker 租约。保留 ID、JSON、空值和 UTC 微秒时间。
   每张表按主键计算行数和内容校验值，全部一致后才提交。任何失败都会回滚已复制数据；
   MySQL 建表操作可能保留空表。原 SQLite 文件不被修改。

   目标库非空、源字段不匹配或出现未知表时会停止。不要通过清空有数据的目标库来重试；
   应先核对配置，或由数据库管理员准备独立的空库。旧版本缺少后续新增的整张表时，
   迁移会将其作为空表处理。请确认这些表确实尚未使用。

4. 看到 `Migration committed` 后再启动全部服务。

   ```sh
   docker compose up --build --detach --wait --wait-timeout 180
   docker compose ps
   ```

   使用原账号登录，检查资料、隐私、机会、收藏和短名单；上传文档并等待提取，
   同时确认旧文件可下载。重启后再次检查持久化。

回退：停止 API/worker，将根 `.env` 的 `DATABASE_URL` 显式设为
`sqlite:////app/data/h18abanana.db`，再启动服务。旧 SQLite 仅包含切换前的数据；
MySQL 切换后的新增/修改不会自动同步回 SQLite，已有新写入时应先制定反向迁移方案。
不要删除两个数据卷。`docker compose down` 保留数据，`down -v` 会删除数据。

## 本机 Flask 开发或迁移本机 SQLite

重新安装后端依赖，然后仅公开本机回环地址上的 MySQL 端口：

```sh
docker compose -f compose.yaml -f compose.mysql-local.yaml up --detach --wait --wait-timeout 180 mysql
```

本机 Flask 默认连接 `127.0.0.1:3306`。默认用户名、密码、库名和 `.env.example` 相同。
自定义设置时，将 `backend/.env.example` 的变量导出到 API 和 worker 进程；Flask 不会自动加载它。
也可以使用 `DATABASE_URL=mysql+pymysql://用户:已URL编码的密码@地址:3306/数据库?charset=utf8mb4`。
`MYSQL_*` 独立配置通过 SQLAlchemy 构造 URL，密码中的特殊字符无需手动编码。

Windows，迁移前先停止本机 Flask/worker，并备份 `data/`：

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m flask --app backend.app migrate-sqlite --source sqlite:///data/h18abanana.db
```

macOS/Linux 将 Python 路径换为 `.venv/bin/python`。迁移前不要运行 `seed-tags`；
迁移成功后按原来的后端启动说明启动 API/worker。本机迁移和 Docker 迁移的源数据库不同，
请以实际业务使用的数据源为准。迁移命令只移动数据库记录，不复制上传文件；改变存储目录时
需完整复制文件并保持 storage key 对应关系。

## 数据库行为与验证

- 字符串采用明确的长度，证据/描述使用长文本，JSON 保留结构。
- 表使用 InnoDB、`utf8mb4` 和区分大小写的 `utf8mb4_0900_bin`，避免 ID 比较发生变化。
- 时间为 UTC `DATETIME(6)`；外键、唯一约束、CHECK 约束继续生效。
- MySQL 写事务首先锁定 `database_write_lock` 的单行，保留现有 SQLite 串行写入语义，
  保护版本校验、限流和文档租约。事务提交或回滚时释放锁。只读事务使用一致性快照。
  当前实现优先保持行为一致；写入并发能力仍受这一全局锁限制，后续可按资源细化锁。
- `init-db` 只创建缺少的表，不负责修改已有表结构。未来 schema 升级仍需单独的迁移。

默认测试使用临时 SQLite。真实 MySQL 回归需要一个专用测试库，名称必须以 `_test` 结尾。
该模式会清理测试库的项目表，不能使用业务库。

```powershell
$env:MYSQL_TEST_DATABASE_URL='mysql+pymysql://banana:测试密码@127.0.0.1:3306/banana_test'
.\.venv\Scripts\python.exe -m pytest backend/tests --run-mysql -q
```

CI 的 `backend_mysql_test` 分为三个独立任务，每个任务使用自己的 MySQL 8.4 服务。
按测试 ID 稳定分配，合计仍执行完整测试集，不遗漏或重复用例，避免单任务触及 Runner 的 10 分钟时限。
本地不传分组参数时仍运行全部测试；可用 `--shard-index 1 --shard-total 3` 单独复现第一个任务。
每个测试进程只在开始和结束时重建表，用例之间按外键顺序删除记录并保留事务锁行，
兼顾数据隔离和测试速度。CI 同时保存 JUnit 报告及最慢的十项耗时，方便定位后续性能问题。
分组使用 [GitLab parallel jobs](https://docs.gitlab.com/ci/yaml/#parallel)。
测试包含迁移成功、
逐值校验、失败回滚、拒绝覆盖、原密码登录，以及现有业务并发/权限回归。
`--run-docker` 另行验证完整容器栈、自动文档处理和容器重建后的持久化。

连接与事务配置参考 [SQLAlchemy MySQL 文档](https://docs.sqlalchemy.org/en/20/dialects/mysql.html)，
时间精度参考 [MySQL 时间小数秒文档](https://dev.mysql.com/doc/refman/8.4/en/fractional-seconds.html)。
