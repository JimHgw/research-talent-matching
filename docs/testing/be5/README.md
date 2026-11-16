# Sprint 3 BE-5 统一授权与团队可见数据边界验收

执行日期：2026-11-16（Australia/Sydney）。基线提交 `8b8a879f997b095b83c97b0f7f946bcf93599194`（分支 `YixuanWu-BE-5-UnifyAuthorisation`），以下结果基于本分支工作区修改。所有测试使用独立临时数据库：SQLite 为 pytest 临时文件；MySQL 为一次性 `mysql:8.4` 容器中以 `_test` 结尾的数据库，不读取或修改本地业务数据库。

测试文件：[`backend/tests/test_sprint3_be5.py`](../../../backend/tests/test_sprint3_be5.py)。

## 1. 访问矩阵（需求 1）

身份检查全部复用 `shared/security.py`：`current_session`（Cookie → 未撤销、未过期的会话 → 活跃账户）、`require_user(db, role)`（无会话 401，角色错误 403）、`require_csrf`（写操作校验 Origin 与 `X-CSRF-Token`，失败 403 `CSRF_INVALID`）。资源归属在查询条件中完成，不可访问与不存在返回同一个 404 响应体（仅 `requestId` 不同），不泄露存在性。

下表是 `test_access_matrix` 的可执行矩阵，SQLite 与 MySQL 的实际状态码均写入 JUnit 属性 `be5_access_matrix`，与预期完全一致。

| 读取端点（`/api/v1`） | 匿名 | 伪造会话 | 过期会话 | 档案本人 (TALENT) | 其他人才 (未确认) | 机会所有团队 | 其他团队 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GET /me/profile` | 401 | 401 | 401 | 200 | 200（仅自己） | 403 | 403 |
| `GET /me/privacy` | 401 | 401 | 401 | 200 | 200（仅自己） | 403 | 403 |
| `GET /me/documents` | 401 | 401 | 401 | 200 | 200（仅自己的列表） | 403 | 403 |
| `GET /me/documents/{doc}` | 401 | 401 | 401 | 200 | 404 | 403 | 403 |
| `GET /me/documents/{doc}/file` | 401 | 401 | 401 | 200 | 404 | 403 | 403 |
| `GET /me/documents/{doc}/extraction` | 401 | 401 | 401 | 409 `EXTRACTION_NOT_READY`（到达资源） | 404 | 403 | 403 |
| `GET /me/recommendations` | 401 | 401 | 401 | 200 | 409 `PROFILE_UNCONFIRMED` | 403 | 403 |
| `GET /me/opportunity-matches/{opp}` | 401 | 401 | 401 | 200 | 409 `PROFILE_UNCONFIRMED` | 403 | 403 |
| `GET /me/saved-opportunities` | 401 | 401 | 401 | 200 | 200（仅自己） | 403 | 403 |
| `GET /opportunities/{draft}` | 401 | 401 | 401 | 404 | 404 | 200 | 404 |
| `GET /opportunities/{opp}/talent-matches` | 401 | 401 | 401 | 403 | 403 | 200 | 404 |
| `GET /opportunities/{opp}/talent-matches/{talent}` | 401 | 401 | 401 | 403 | 403 | 200 | 404 |
| `GET /opportunities/{opp}/shortlist` | 401 | 401 | 401 | 403 | 403 | 200 | 404 |
| `GET /opportunities/{opp}/shortlist/{talent}` | 401 | 401 | 401 | 403 | 403 | 200 | 404 |

写操作补充（`test_writes_reuse_session_role_and_csrf_checks`，以及既有 `test_us02/test_us05/test_collections` 用例）：

| 写操作 | 匿名 | 缺少/错误 CSRF 或 Origin | 错误角色 | 非所有者 |
| --- | --- | --- | --- | --- |
| `PUT /me/privacy`、`PUT /me/profile`、确认、文档上传/导入 | 401 | 403 `CSRF_INVALID` | 403 | 文档导入 404 |
| `PUT/DELETE /me/saved-opportunities/{opp}` | 401 | 403 `CSRF_INVALID` | 403 | 仅作用于本人记录 |
| `PUT/DELETE /opportunities/{opp}/shortlist/{talent}` | 401 | 403 `CSRF_INVALID` | 403 | 其他团队 404 |
| 机会创建/保存/发布/重开 | 401 | 403 `CSRF_INVALID` | 403 | 404 |

“团队可见”对象额外条件：人才 `role=TALENT`、账户 `active`、`discoverable=true`、`confirmation_status=CONFIRMED` 且 `confirmed_revision == revision`。不满足任一条件的人才在列表/短名单中消失，详情与短名单单项返回与“不存在”相同的 404（`test_inaccessible_resources_are_indistinguishable_from_missing_ones`）。

## 2. 统一的团队可见投影（需求 2、3）

所有研究团队读取人才数据的入口都经过 `features/matching/team_repository.py` 的唯一入口 `team_projection`：

```
eligible_talent_query()      SQL: 角色 + 活跃账户 + 发现同意 + 当前版本已确认
  └─ discoverable_profiles() SQL 下推: talent_id / 短名单 talent_ids / interestTagId(需 researchInterests 可见)
      └─ visible_profiles()  仅读取已授权字段的子表；逐键白名单复制
          └─ talent_matches_filters()   q / skill / university / skillTagId 只看投影
              └─ visible_snapshot() → evaluate_opportunity(team_evidence) → enrich_matches(模型输入)
                  └─ ranked_page()     全部合格候选打分后稳定排序再分页
```

| 入口 | 修改前 | 修改后 |
| --- | --- | --- |
| `GET .../talent-matches` | `visible_profiles(discoverable_profiles(filters))` | `team_projection(filters=...)` |
| `GET .../talent-matches/{talent}` | `visible_profiles(discoverable_profiles(talent_id))` | `team_projection(talent_id=...)` |
| `GET .../shortlist` | 读取**全部**合格人才后在 Python 中按短名单 ID 过滤 | `team_projection(talent_ids=短名单ID)`，ID 条件下推到同一条资格查询 |
| `GET/PUT .../shortlist/{talent}` | `discoverable_profiles(talent_id)` | 不变（同一资格查询，404 语义一致） |

短名单表只保存 `(opportunity_id, talent_id)`，不快照任何档案内容，因此每次读取都按当前同意、确认、活跃状态与字段可见性重新计算，已有短名单无法绕过检查。

隐藏内容从未进入打分：`visible_profiles` 在读取前按 `PrivacyVisibleField` 过滤子表，未授权字段在快照中只是空值；`visible_snapshot` 不含 `origins`、`revision`、`resumeDescription` 或 `courses`；证据工厂使用 `team_evidence`，只有 `field / recordId / valueSummary`。

## 3. 字段审计（需求 4）

| 数据 | 所有者 | 团队响应 | 团队过滤/打分/模型输入 | 依据 |
| --- | --- | --- | --- | --- |
| `resumeDescription` | `GET /me/profile` 可读 | 永不返回 | 永不读取（`visible_profiles` 只 `select` `research_interest_text` 列） | sentinel 断言 |
| 原始文档、文件名、存储键、下载 | 仅 `/me/documents*`（`own_document` 按 `TalentProfile.user_id` 连接） | 无 | 无 | 其他人才 404、团队 403 |
| 抽取结果 | 仅 `/me/documents/{id}/extraction` 与导入 | 无 | 无 | 同上 |
| 来源 `origins` / `documentId` / `sourceType` / `confirmedRevision` | `OwnerEvidence` 与档案 `origins` | 无（`TeamEvidence` 白名单） | 无（快照无 `origins`） | 私有键递归断言 |
| 技能记录 | 完整 | `id/title/evidenceText` 白名单（新增） | 同左 | 向存储 JSON 注入 `documentId` 后仍不外泄 |
| 研究兴趣、兴趣文本、个人兴趣标签 | 完整 | 仅当 `researchInterests` 可见；个人标签 `id/label/description` 白名单（新增） | 同左 | `interestTagId` 只接受共享标签 |
| 个人兴趣标签 ID | 仅本人可选择 | — | 其他账户保存 422、团队过滤 422、`/tags` 不列出 | `test_documents_and_personal_tags_are_owner_only` |
| 教育、课程、研究经历、成果 | 完整 | 仅可见字段，逐键复制 | 课程不参与打分；其他按可见性 | sentinel 断言 |
| 账户 e-mail | 会话接口 | 无 | 无 | 私有键断言 |
| 语义模型输入 | 本人：完整档案（不含简历描述） | — | 仅团队快照；文本与向量不跨请求保留 | `RecordingEncoder` 记录全部批次 |

## 4. 代码变更

| 文件 | 变更 |
| --- | --- |
| `backend/src/features/matching/team_repository.py` | 新增 `eligible_talent_query`、`team_projection`；`discoverable_profiles` 增加 `talent_ids` 下推；技能记录与个人兴趣标签按 `SKILL_KEYS` / `PERSONAL_TAG_KEYS` 逐键复制；模块文档写明边界 |
| `backend/src/features/matching/team_service.py` | 列表与详情改用 `team_projection`；`visible_snapshot` 写明模型输入边界 |
| `backend/src/features/collections.py` | 短名单列表改用 `team_projection(talent_ids=...)`，不再加载全部合格人才 |
| `backend/tests/test_sprint3_be5.py` | 9 个 BE-5 验收测试（见下节） |

API、OpenAPI 契约、数据库结构和错误码均无变化；无需数据库升级。函数 `discoverable_profiles` / `visible_profiles` / `visible_snapshot` 保留原签名（BE-8 等价性测试仍直接调用）。

## 5. 验收标准与测试

| 验收标准 | 测试 | 结果 |
| --- | --- | --- |
| 匿名 401、错误角色 403、不可访问 404 且不泄露存在性 | `test_access_matrix`、`test_inaccessible_resources_are_indistinguishable_from_missing_ones`、`test_writes_reuse_session_role_and_csrf_checks` | 通过 |
| 两份合格档案修改隐藏内容并各自重新确认后，团队过滤/分数/排名/证据不变 | `test_hidden_content_changes_do_not_affect_team_results`：比较列表、6 种过滤/分页查询、两份详情（去掉 `evaluatedAt`）和短名单，修改前后完全相等；模型输入批次也完全相等；对照组证明本人匹配确实使用了新私有内容（INTEREST/经历由 UNKNOWN 变为 MATCHED） | 通过 |
| 撤回同意或隐藏字段在下一次请求生效；集合不能绕过 | `test_revocation_and_hiding_apply_to_next_request_including_shortlist`；既有 `test_collections.py::test_current_privacy_and_no_documents`、`test_eligibility_changes_hide_existing_records` | 通过 |
| 编辑后未重新确认时团队不能使用旧确认内容；本人推荐/匹配拒绝未确认档案 | `test_edit_before_reconfirmation_hides_old_content_and_owner_matching_rejects`（列表、旧/新技能过滤、短名单、详情 404；本人两个端点 409 `PROFILE_UNCONFIRMED`；重新确认后只出现新内容） | 通过 |
| 团队响应与模型输入不含完整简历、原始文档路径/ID 或私有来源；其他账户不能读取文档或使用个人标签 | `test_scoring_inputs_are_built_from_the_team_projection`（替换 `evaluate_opportunity` / `enrich_matches` 记录真实入参，覆盖列表、详情、短名单）；`test_documents_and_personal_tags_are_owner_only` | 通过 |
| 用独立客户端验证登出、过期与账户切换 | `test_logout_expiry_and_account_switching_with_independent_clients`：独立 cookie jar；登出后原客户端与重放旧 Cookie 均 401，同账户另一会话不受影响；过期会话 401；同一客户端切换账户后旧 Cookie 失效、角色权限随之改变；停用账户后会话 401 且从团队结果消失 | 通过 |

### 反向（突变）验证

为证明测试能发现回归，临时破坏实现后运行 `test_sprint3_be5.py`，每次运行后恢复原文件（`git diff --stat` 确认无残留）：

| 人为破坏 | 结果 |
| --- | --- |
| 去掉技能记录白名单 | 1 failed |
| 忽略隐私可见字段（所有字段可见） | 3 failed |
| 去掉 `confirmed_revision == revision` 与 CONFIRMED 条件 | 1 failed |
| 去掉 `User.active` 条件 | 1 failed |
| 短名单直接读取档案、跳过资格查询 | 2 failed |

## 6. 执行记录

环境：macOS 26.6.2、Python 3.13.9、Flask 3.1.2、SQLAlchemy 2.0.44、PyMySQL 1.1.2、pytest 8.4.2、MySQL 8.4.13（Docker `mysql:8.4`，aarch64）。

| 运行 | 命令 | 结果 |
| --- | --- | --- |
| 修改前全量后端（SQLite） | `.venv/bin/python -m pytest -q backend/tests --ignore=backend/tests/test_docker_stack.py --ignore=backend/tests/test_docker_backend.py` | 981 passed, 21 skipped |
| 修改后全量后端（SQLite） | 同上，加 `-rs --junitxml=docs/testing/be5/sqlite-full.xml` | 990 passed, 21 skipped, 0 failed（= 原 981 + 新增 9；skip 集合与修改前相同）（[`sqlite-full.xml`](sqlite-full.xml)） |
| BE-5 + 团队/集合/BE-8 相关（MySQL） | 见下方 | 84 passed, 2 skipped（[`mysql-be5.xml`](mysql-be5.xml)） |

```bash
docker run -d --name be5-mysql-test -e MYSQL_DATABASE=banana_test -e MYSQL_USER=banana -e MYSQL_PASSWORD=be5_test_password -e MYSQL_ROOT_PASSWORD=be5_root_password -p 127.0.0.1:33085:3306 mysql:8.4 --character-set-server=utf8mb4 --collation-server=utf8mb4_0900_bin
```

```bash
MYSQL_TEST_DATABASE_URL='mysql+pymysql://banana:be5_test_password@127.0.0.1:33085/banana_test' .venv/bin/python -m pytest backend/tests/test_sprint3_be5.py backend/tests/test_us05.py backend/tests/test_collections.py backend/tests/test_us04.py backend/tests/test_sprint3_be8.py --run-mysql -q -rs --junitxml=docs/testing/be5/mysql-be5.xml
```

```bash
docker rm -f be5-mysql-test
```

Skip 说明（均与 BE-5 无关）：本机未安装真实 MiniLM 应用模型（`data/semantic/model`），相关 real-model 用例按既有规则 skip；`--run-mysql` 专用用例在 SQLite 运行中 skip；Docker 栈测试（`test_docker_*`）未在本次运行。BE-5 的模型输入断言使用记录型确定性编码器，验证的是“哪些文本被送入模型”，不依赖模型本身；真实模型验收属于 BE-7（需 `--require-application-model`）。

## 7. 风险与已知限制

- 本任务不改变 API 契约、数据库结构或错误码；回滚只需还原上述三个源文件。
- `discoverable_profiles` 仍返回 ORM `TalentProfile` 对象（教育/经历等 JSON 列随行加载在内存中）；它们只在 `visible_profiles` 中按可见字段逐键复制后才进入过滤/打分。若将来新增人才列，须同步审计 `visible_profiles` 的白名单。
- 前端隐藏按钮不作为证据；FE-4/FE-5 的账户切换与隐私撤回界面证据需由前端在联调报告中补充。
- 任务记录中的负责人与最终 MR/commit 需在评审合并时填写。

## 8. 验收结论

BE-5 后端验收标准全部有执行证据并通过（SQLite 全量回归 + MySQL 8.4 定向回归）。待填写：MR 链接、合并提交与评审人。
