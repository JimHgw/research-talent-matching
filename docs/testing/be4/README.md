# Sprint 3 BE-4 并发版本控制与事务原子性验收

执行日期：2026-11-16（Australia/Sydney）。基线提交 `ab6b0d3beff6414d39504cfa70ec52ba61c44eaa`；本分支随后合并了 `origin/main`（含 BE-2 导入服务），以下 BE-4 结果与证据均在合并后的代码上重新生成。所有测试使用独立临时数据库：SQLite 为 pytest 临时文件；MySQL 为一次性 `mysql:8.4` 容器中以 `_test` 结尾的数据库，不读取或修改本地业务数据库。

测试文件：[`backend/tests/test_sprint3_be4.py`](../../../backend/tests/test_sprint3_be4.py)。

## 1. 事务边界

所有带版本比较的写操作都在 `Database.transaction(write=True)` 内完成，一个 HTTP 请求只有一个写事务，身份验证、所有权检查、版本比较、子表写入和响应序列化共享同一个 Session。

| 数据库 | 写保护 | 何时获得 | 释放 |
| --- | --- | --- | --- |
| SQLite | `BEGIN IMMEDIATE`（RESERVED 锁），其他写事务在 busy timeout 内等待 | Session 的第一条语句之前（连接延迟开始事务） | COMMIT / ROLLBACK |
| MySQL 8.4 (InnoDB, REPEATABLE READ) | `SELECT id FROM database_write_lock WHERE id = 1 FOR UPDATE` | 事务第一条语句 | COMMIT / ROLLBACK |

MySQL 说明：加锁读取（`FOR UPDATE`）不会建立 REPEATABLE READ 的一致性快照；快照在随后的第一条普通 SELECT 时建立，因此一定晚于获得写锁，能看到前一个写者已提交的版本。真实 MySQL 测试验证了这一点：被阻塞的请求返回的 `currentRevision` 等于胜者提交后的版本。

### 新增保护：`require_write_lock`

`transaction()` 在 `session.info` 中记录是否持有写锁。以下 6 处版本比较在比较前调用 `require_write_lock(db)`：

| 写操作 | 位置 |
| --- | --- |
| `PUT /me/profile` | `features/profile/routes.py` `profile_put` |
| `POST /me/profile/confirmation` | `features/profile/routes.py` `profile_confirm` |
| `PUT /me/privacy` | `features/privacy/routes.py` `privacy_put` |
| `POST /me/documents/{id}/apply` | `features/documents/routes.py` `document_apply_post` |
| `PUT /opportunities/{id}` | `features/opportunities/service.py` `check_revision` |
| `POST /opportunities/{id}/publish` | `features/opportunities/service.py` `check_revision` |

如果 BE-2/BE-3 把这些业务操作迁移到服务层时误用只读事务，请求会以 500 失败并回滚，而不会静默丢失更新。测试 `test_every_revision_write_refuses_to_run_without_the_lock` 对 6 个入口逐一验证。

## 2. 审计结论（需求 1、2）

| 写操作 | 写锁先于读取？ | 版本语义 |
| --- | --- | --- |
| 档案保存 | 是：锁 → 会话 → 档案 → 比较 | 真实变化 +1 并清除确认；完全相同的保存为 no-op，保留版本、确认时间与来源 |
| 档案确认 | 是 | 不改变版本；只确认请求提交的当前版本；重复确认保留原 `confirmedAt` |
| 隐私设置 | 是 | 独立的隐私版本；真实变化 +1 |
| 文档导入 | 是 | 每次成功导入恰好 +1 并清除确认，永远不是 no-op |
| 机会保存 / 发布 | 是 | 真实变化或发布 +1；相同内容保存不变 |

`test_writer_lock_is_the_first_statement_of_every_revision_write` 记录每个请求在其连接上执行的全部 SQL，断言第一条就是写锁语句，且整个请求只有一个写事务。两个数据库的结果见证据文件中的 `lock_first:*` 记录。审计未发现先读后锁的路径，因此保留现有全局写锁，没有引入更细粒度锁（因此不需要额外的性能测量与正确性对比）。

## 3. 区分重复确认、no-op 保存与重复导入（需求 4）

| 请求 | 结果 |
| --- | --- |
| 对当前版本重复确认 | 200，版本、`confirmedRevision`、原 `confirmedAt` 不变 |
| 与已存内容完全相同的保存 | 200，版本、确认状态、确认时间、来源均不变 |
| 用已成功导入前的旧版本重试同一导入 | 409 `REVISION_CONFLICT`，不新增标签、不再递增版本，全部表快照不变 |
| 以最新版本再次显式导入相同内容 | 200，版本 +1，并清除确认；相同标签复用已有个人标签，不重复创建 |

导入不做 no-op 判断：它代表用户再次确认了来源文档。重试安全来自版本协议：客户端携带的旧版本在第一次导入后已经过期。

## 4. 并发测试方法

每个竞争场景使用同一账户的两个独立登录会话（两个 Flask test client），请求分别在两个线程上运行，因此使用连接池中的两个独立数据库连接。交错顺序由引擎事件和 `threading.Event` 屏障控制，不用 sleep 制造竞争：

1. 第一个写者执行完所有读取和写入，在 COMMIT 前（`commit` 事件）停住，此时仍持有写锁；
2. 启动第二个写者，在它发出写锁请求（SQLite `BEGIN IMMEDIATE` / MySQL `... FOR UPDATE`）时发信号；
3. MySQL 上再从第三个连接查询 `information_schema.PROCESSLIST`，确认第二个请求的加锁语句正在执行（即被阻塞）；
4. 释放第一个写者，等待两个线程结束后检查响应与数据库。

MySQL 的观测循环每 2 ms 查询一次状态，只用于观察，不决定交错顺序。SQLite 的 busy 等待发生在 C 层，无法从 Python 观测；但第二个写者发出 `BEGIN IMMEDIATE` 时第一个写者一定仍持有 RESERVED 锁（它停在屏障上），所以两个请求必然重叠。

**反向对照**：`test_negative_control_without_the_writer_lock_violates_the_invariant` 去掉写锁（普通 BEGIN、无 FOR UPDATE），用屏障让两个请求都在通过版本检查后、写入档案前会合。两个数据库上都不再满足"一个 200、一个 409"：SQLite 出现 `OperationalError`（database is locked）导致 500，MySQL 出现 `IntegrityError`（两个写者插入同一来源行）导致 500。这说明屏障确实制造了写锁需要防止的重叠。

### 场景（每个 10 轮，轮次之间交替先后顺序）

| 测试 | 场景 | 断言 |
| --- | --- | --- |
| `test_concurrent_profile_saves_have_one_complete_winner` | 两个保存，同一版本，都改变全部分区并新增不同个人标签 | 先提交者 200、另一个 409 且 `currentRevision` = 新版本；最终档案与胜者响应完全一致；败者的个人标签不存在；来源全部为 MANUAL |
| `test_import_competing_with_manual_save_obeys_the_revision` | 导入 vs 手动保存，两种先后顺序 | 同上；导入只 +1；导入胜出时 7 个分区来源为 `USER_REVIEWED_DOCUMENT` 并指向该文档 |
| `test_concurrent_confirmation_and_edit_have_a_valid_serial_outcome` | 编辑先 / 确认先，档案未确认 / 已确认 4 种组合 | 编辑先：确认 409；确认先：确认 200（不改版本，重复确认保留原时间），编辑 200；两种顺序最终都是新版本 + `UNCONFIRMED` |
| `test_duplicate_concurrent_imports_and_stale_retry_never_replay` | 两个相同导入并发，之后用旧版本重试 | 200/409/409；重试前后全表快照一致；个人标签只有一个；版本只 +1 |
| `test_concurrent_privacy_writes_have_one_winner` | 两个隐私设置写入 | 一个 200、一个 409，最终值为胜者 |
| `test_concurrent_opportunity_writes_have_one_winner` | 第 0 轮：发布 vs 编辑草稿；之后：编辑 vs 编辑 | 一个 200、一个 409，最终值为胜者 |

## 5. 故障注入（需求 3）

在 `before_cursor_execute` 中，对目标表的第一条 INSERT/UPDATE/DELETE 抛出异常（真实 SQL 执行中途失败），或者在所有语句已 flush 后的最终序列化中抛出异常（`after-all-writes`）。起始状态是已确认、已有内容、来源、个人标签和文本组件的档案。每个用例断言：

- 响应 500，注入点确实被执行（否则用例失败，防止空测）；
- 除会话记录外，所有业务表的全部行与失败前完全一致（版本、确认、内容、个人标签及描述、共享兴趣、技能、文本、来源）；
- 档案 GET 与失败前一致；
- 同一请求随后重试一次即成功（没有遗留锁或半写入状态）。

| 操作 | 注入点 |
| --- | --- |
| 档案保存 | `talent_profiles`、`personal_interest_tags`、`personal_interest_tag_details`、`profile_interests`、`profile_skill_details`、`profile_text_details`、`profile_personal_interests`、`profile_origins`、`profile_component_origins`、全部写入之后 |
| 文档导入 | 同上 10 个注入点 |
| 档案确认 | `talent_profiles`（确认状态）、写入之后 |

`after-all-writes` 用例还断言 9 张表在失败前都已经写入（保存失败前已执行 10 条写语句，导入失败前已执行 17 条），然后全部回滚。每个注入点失败前已执行的写语句数量记录在证据文件 `faults` 中。

## 6. 结果

环境：macOS 26.6.2、Python 3.13.9、SQLAlchemy 2.0.44、PyMySQL 1.4.6、Flask 3.1.2。

| 数据库 | BE-4 测试 | 竞争轮次 | 第二写者被观测为阻塞 | 反向对照 | 故障注入 | 全量后端测试 |
| --- | --- | --- | --- | --- | --- | --- |
| SQLite 3.51.0 | 43 passed | 60 / 60 符合预期 | 不适用（见第 4 节） | [200, 500] OperationalError | 22 / 22 回滚 | 合并前：986 passed, 32 skipped；合并后：相关套件 262 passed |
| MySQL 8.4.13 | 43 passed | 60 / 60 符合预期 | 60 / 60 | [200, 500] IntegrityError | 22 / 22 回滚 | 合并后：1009 passed, 1 failed*, 20 skipped |

证据文件：

- SQLite：[`sqlite-evidence.json`](sqlite-evidence.json)、[`sqlite-be4.xml`](sqlite-be4.xml)
- MySQL 8.4：[`mysql-evidence.json`](mysql-evidence.json)、[`mysql-be4.xml`](mysql-be4.xml)

证据 JSON 中 `rounds` 为每轮的状态码、前后版本、是否观测到阻塞与耗时；`controls` 为写锁首语句与反向对照；`faults` 为每个注入点。

全量后端测试的 skip 与本任务无关：MySQL 下 20 个为 `--run-docker` 容器测试、本机未安装的真实语义模型、仅 Windows/PowerShell 的启动脚本，以及仅适用于非 MySQL 的启动路径；SQLite 下多出的 skip 为需要 `--run-mysql` 的 MySQL 专用测试。

\* 合并后 MySQL 全量运行中，前端浏览器端到端测试 `test_frontend_integration.py::test_real_frontend_workflow[19]` 因页面等待超时失败；该次运行与其他测试并行占用本机，期间所有后端请求均返回 200/201。单独重跑该测试在 MySQL 与 SQLite 上均通过，判断为负载导致的超时，与 BE-4 无关。合并后的 SQLite 全量运行被中途停止，只记录了 BE-1、BE-2、BE-4 与 US-01/02/09/11 相关套件（262 passed）。

## 7. 复现

SQLite：

```bash
BE4_EVIDENCE=docs/testing/be4/sqlite-evidence.json .venv/bin/python -m pytest backend/tests/test_sprint3_be4.py -q --junitxml=docs/testing/be4/sqlite-be4.xml
```

MySQL 8.4（一次性容器，端口仅绑定本机）：

```bash
docker run -d --name be4-mysql-test -e MYSQL_DATABASE=banana_test -e MYSQL_USER=banana -e MYSQL_PASSWORD=be4_test_password -e MYSQL_ROOT_PASSWORD=be4_root_password -p 127.0.0.1:33084:3306 mysql:8.4 --character-set-server=utf8mb4 --collation-server=utf8mb4_0900_bin
```

```bash
MYSQL_TEST_DATABASE_URL='mysql+pymysql://banana:be4_test_password@127.0.0.1:33084/banana_test' BE4_EVIDENCE=docs/testing/be4/mysql-evidence.json .venv/bin/python -m pytest backend/tests/test_sprint3_be4.py --run-mysql -q --junitxml=docs/testing/be4/mysql-be4.xml
```

`BE4_ROUNDS=<n>` 可提高轮数。CI 中 `backend_mysql_test` 已使用 `mysql:8.4` 运行全部后端测试（含本文件）。

## 8. 限制

- 当前使用全局写互斥：同一时间只有一个写事务。这是现有设计，本任务保留它；没有测量依据前不拆分为按档案/机会的细粒度锁。
- SQLite 的 busy 等待无法从 Python 直接观测，阻塞证明以 MySQL PROCESSLIST 为准；SQLite 的重叠由屏障保证。
- 文档 Worker 的租约与恢复属于 BE-6；本文件只覆盖档案、隐私、导入和机会的版本写入。
