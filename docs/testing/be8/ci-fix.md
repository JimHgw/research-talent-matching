# BE-8 MySQL CI 分片修复

日期：2026-11-09（Australia/Sydney）。原失败任务：[backend_mysql_test 2/3，#6301432](https://gitlab.cse.unsw.edu.au/coursework/comp3900/26t3/capstone-projects/3900-h18a-banana/project/-/jobs/6301432)，提交 `629a037b`，流水线 `3257265`。

## 根因

`test_query_upgrade_requires_legacy_column_upgrade` 为验证旧表升级的前置条件，删除了 `opportunities.expired_at` 以及 BE-8 索引，但没有恢复。

SQLite 的 app fixture 每次创建独立文件；MySQL 的 session fixture 建表一次，后续 app fixture 只清空业务行并复用表结构。删除列的测试本身通过后，同一分片后面的机会创建、查询及学术匹配测试继续使用缺列的表，因数据库 OperationalError 返回 500。该测试分配在 2/3 分片，解释了其他两个 MySQL 分片通过而这一分片出现 48 failures、5 errors 的现象。

之前的 40 项 MySQL/Docker 定向验收把 BE-8 文件放在最后，这个删列测试又位于文件末尾。验收没有执行其后的普通业务用例，因此未覆盖跨测试的表结构污染。原报告保留为历史定向验收记录，不能替代完整 MySQL 分片验证。

## 修复

- 用上下文管理器在 `finally` 中显式恢复机会字段和查询索引，兼顾正常退出、断言失败和部分 DDL 已提交的情况；不依赖 MySQL 事务回滚 DDL。
- 负向升级测试结束后，检查完整字段及两个索引，并通过真实 HTTP 创建、发布、查询机会，验证后续请求可继续使用数据库。
- 新增模拟异常中断用例，同样验证恢复后的表结构与 HTTP 行为。
- 验收工具增加 `--mysql-tests`（保留指定用例顺序）和 `--mysql-shard INDEX TOTAL`（按 CI 的完整目录和分片顺序运行），避免只验证孤立文件。

本次没有修改应用查询、评分、权限规则或生产升级逻辑，也没有通过跳过失败用例来使检查通过。

## 复现与验证

修复前在独立 MySQL 上按以下顺序运行：删列前置条件测试 → 研究团队注册后的机会创建测试。结果为 **1 passed，1 failed**，第二项得到与 CI 一致的 500；见 [修复前复现](ci-repro-before.xml)。

修复后保留这两项的顺序，并追加异常恢复用例，结果为 **3 passed，0 skipped**；见 [修复后复现](ci-repro-after.xml)。BE-8 的 SQLite / 真实应用模型回归为 **27 passed，0 skipped**；见 [SQLite 回归](ci-fix-sqlite.xml)。

完整 MySQL 2/3 分片的最终结果为 **262 passed，1 skipped，0 failures，0 errors**，共选中 263 项、548 项分配到其他分片，耗时 473.57 秒；见 [分片报告](ci-mysql-shard-2.xml)及[执行元数据](ci-fix-execution.json)。该检查运行完整 `backend/tests` 目录，使用 `--run-mysql --shard-index=2 --shard-total=3`。唯一跳过项专门验证非 MySQL 的启动路径，按设计在 MySQL 环境跳过；BE-8 及其后原失败区段均成功执行。

```powershell
# 启动独立临时 MySQL，按原失败分片顺序执行完整目录。
.\.venv\Scripts\python.exe scripts/test-environment.py --mysql-shard 2 3 --report docs/testing/be8/ci-mysql-shard-2.xml

# 验证原失败顺序以及中断后的恢复；无需运行完整 Docker 栈。
.\.venv\Scripts\python.exe scripts/test-environment.py --mysql-tests backend/tests/test_sprint3_be8.py::test_query_upgrade_requires_legacy_column_upgrade 'backend/tests/test_us01_registration.py::test_register_both_roles_atomic_defaults_and_email_id_login[RESEARCH_TEAM]' backend/tests/test_sprint3_be8.py::test_query_upgrade_precondition_restores_schema_after_exception --report docs/testing/be8/ci-repro-after.xml

.\.venv\Scripts\python.exe -m pytest backend/tests/test_sprint3_be8.py --require-application-model -q --junitxml=docs/testing/be8/ci-fix-sqlite.xml
```

此处是 Windows 主机执行测试、Docker 提供独立 MySQL 的本地验证，完整分片的目录、分区算法及顺序与 CI 一致；不将其称为 GitLab 云端的新运行结果。原失败任务仍对应旧提交；提交并推送修复后，流水线才会验证新代码。
