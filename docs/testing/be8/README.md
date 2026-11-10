# Sprint 3 BE-8 查询、过滤与分页验收

后续发现并修复了 MySQL 2/3 分片的测试表结构污染；根因、完整分片复现和最新验证见 [CI 修复记录](ci-fix.md)。下文保留最初性能测量与定向验收记录。

执行日期：2026-11-09（Australia/Sydney）。基线提交 `74ef7bdd781f484b7f1d786d56c49990f617c62a`，优化结果包含当前工作区修改。测量和测试均使用独立临时数据库，不读取或修改本地业务数据库。

## 实现与等价规则

普通机会列表先检查角色、scope 与所有权，再用同一参考时间筛选可用机会。无文本过滤时，数据库执行精确 COUNT、`updated_at DESC, id ASC` 排序与 LIMIT/OFFSET；只对当前页读取需求、标签和自由文本技能。超大页码在计算 total 后直接返回空页，不将超大整数绑定到数据库。

`disciplineGroup` 和截止时间的组合条件进入 SQL：同一参数内为 OR，不同参数间为 AND；截止区间下界包含、上界不包含；NULL 截止时间不满足区间过滤。可用性继续要求 PUBLISHED、没有保留的 `expired_at`，且截止时间为 NULL 或严格晚于本次参考时间。

Unicode 文本保留 `normalise_title` 的 NFKC、Unicode 空白折叠和 casefold 规则。数据库的 LOWER/排序规则无法跨 SQLite、MySQL 等价实现这些规则，因此文本条件扫描仅包含 ID 和必要文本列的有序投影，在 Python 中精确计数，并只保存当前页的匹配 ID。随后批量读取当前页完整记录。这里的 total 与文本分页在应用层完成，不声称已经全部下推至 SQL；扫描不加载 ORM 机会对象、需求或 JSON 子记录。`%`、`_`、引号仍作为普通字符比较。

本人推荐也先应用条件过滤，再读取符合条件的机会及其需求。所有符合条件的候选仍进入同一个请求内的结构化与真实语义评分批次，之后按最终分数、unknownWeightPercent、ID 稳定排序，最后分页。每 1,000 条机会批量读取一次子记录；不会按页面或任意上限截断评分池。本人评分不再查询未使用的完整 `resume_description`，个人兴趣关联仍限定本人。

团队匹配只将可精确等价的 `interestTagId` 条件前移至 SQL，并同时要求当前 `researchInterests` 字段可见。共享兴趣 ID 内为 OR，不会用隐藏兴趣、个人标签或自由文本代替共享 ID。发现授权、当前确认版本、账户角色及 active 状态仍先于过滤与评分检查。技能否定、大学别名及可见字段递归文本搜索继续使用现有投影与比较规则。未带此条件时，保留原有批量查询和完整评分流程。

`ranked_page` 只为当前页创建带 rank 的返回字典，仍在全体结果排序后计算全局名次；收藏和 shortlist 继续复用同一规则。没有新增跨请求档案或向量缓存。

## 索引与旧库升级

增加两个索引，保留已有索引和全部业务行：

| 索引 | 列及顺序 | 对应查询 |
| --- | --- | --- |
| `ix_opportunities_active_page` | status, expired_at, updated_at DESC, id ASC | 可用机会列表、计数与有序文本投影 |
| `ix_opportunities_owner_page` | owner_user_id, updated_at DESC, id ASC | 团队自己的机会列表 |

真实 SQLite EXPLAIN 记录保存在两个测量 JSON 中。基线普通列表使用 `ix_opportunities_status_updated`，出现 `USE TEMP B-TREE FOR LAST TERM OF ORDER BY`；优化后使用 `ix_opportunities_active_page (status=? AND expired_at=?)`，无需临时排序。owner 路径的执行计划也由回归测试验证。团队关联过滤复用 `(talent_id, field)` 与 `(talent_id, tag_id)` 主键索引，不为没有测量依据的文本条件增加索引。MySQL DDL 的 DESC 顺序已通过方言编译断言；本文不将 SQLite 的执行计划宣称为 MySQL 的实测计划。

全新数据库通过 `init-db` 建立索引。已有数据库使用原来的数据库配置，顺序执行：

```powershell
.\.venv\Scripts\python.exe -m flask --app backend.app init-db
.\.venv\Scripts\python.exe -m flask --app backend.app upgrade-opportunity-search
.\.venv\Scripts\python.exe -m flask --app backend.app upgrade-query-indexes
```

其余既有升级（academic requirements、resume text）继续按项目原有发布流程执行。Docker entrypoint 已在机会字段升级后、API/Worker 启动前执行 `upgrade-query-indexes`。命令可重复执行，只创建缺少的两个索引；缺表或缺少 `expired_at` 时会明确失败。MySQL 使用数据库命名锁串行化升级；CREATE INDEX 会独立提交，不能依赖应用事务撤销 DDL。中断后重试补齐缺失索引，失败时 entrypoint 停止启动服务。测试覆盖两个升级命令失败时均不能启动服务。

## 固定数据与测量方法

[固定清单](../../../backend/tests/data/sprint3/be8-query.json)与[确定性生成器](../../../backend/tests/be8_data.py)定义 100、1,000 条机会及同数量人才，ID、顺序、分组、内容均可重建。参考时间固定为 `2030-01-15T00:00:00` UTC，与真实会话时钟分开控制。数据包含草稿、截止前/等于/之后、保留过期标记、缺少可选字段、重复更新时间、Unicode 文本，以及无发现授权、未确认、停用、错误角色、隐藏字段和旧版技能记录。

每个规模各测量三条真实 Flask HTTP 路由的无过滤与组合过滤，共 12 组；每组预热 3 次后测量 30 次。基线与优化各 360 次计时请求，另各有预热和一次内存采样。请求使用真实会话校验、事务、查询、序列化和本地应用 MiniLM，不替换编码器、不使用历史 US-13 模型。测量过程中没有并行运行测试套件。

环境：Windows 11 10.0.26200、Python 3.12.14、SQLAlchemy 2.0.44、独立文件 SQLite。模型为 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`，revision `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`，本地校验后加载；完整配置保存在 JSON 的 model 字段。模型缺失/推理探测失败会使测量命令失败，不会把回退当作真实模型测量。

P50 为中位数，P95 为 nearest-rank 第 29 个样本。时间包含 HTTP 处理与响应序列化，排除逐次结果指纹计算。内存为额外一次预热请求的 tracemalloc 峰值（MiB），表示 Python 分配峰值，**不包含 ONNX 原生内存或进程整体工作集**。SQL 数量包含身份验证查询，排除 BEGIN；关联 SQL 计机会需求/标签/技能明细，以及隐私可见字段、档案技能、共享兴趣和关联文本/选择表的独立读取语句，不重复计算 EXISTS 子查询。共享标签目录、本人来源和个人标签目录计入 SQL 总数。

## 前后测量

每格均为“基线 → 优化”；延迟单位 ms，内存单位 MiB。

| 候选规模 | 路由 | 过滤 | P50 | P95 | Python 内存峰值 | SQL 次数 |
| --- | --- | --- | --- | --- | --- | --- |
| 100 | opportunities | 无 | 12.153 → 8.556 | 14.086 → 10.469 | 0.395 → 0.208 | 6 → 7 |
| 100 | opportunities | 组合 | 12.166 → 10.215 | 14.410 → 14.265 | 0.398 → 0.212 | 6 → 7 |
| 100 | recommendations | 无 | 82.542 → 86.706 | 87.754 → 96.416 | 0.578 → 0.579 | 13 → 13 |
| 100 | recommendations | 组合 | 76.034 → 72.362 | 85.156 → 80.170 | 0.402 → 0.357 | 13 → 14 |
| 100 | talents | 无 | 129.384 → 124.822 | 143.582 → 142.276 | 0.717 → 0.723 | 14 → 14 |
| 100 | talents | 组合 | 78.119 → 79.043 | 88.182 → 85.900 | 0.600 → 0.439 | 15 → 15 |
| 1,000 | opportunities | 无 | 75.697 → 9.773 | 174.134 → 12.837 | 4.099 → 0.208 | 6 → 7 |
| 1,000 | opportunities | 组合 | 78.718 → 15.014 | 170.759 → 19.073 | 4.264 → 0.394 | 6 → 7 |
| 1,000 | recommendations | 无 | 503.070 → 490.968 | 558.219 → 546.434 | 5.227 → 5.229 | 13 → 13 |
| 1,000 | recommendations | 组合 | 320.356 → 283.551 | 423.395 → 409.921 | 4.097 → 3.079 | 13 → 14 |
| 1,000 | talents | 无 | 760.391 → 760.196 | 810.794 → 818.792 | 6.099 → 6.207 | 14 → 14 |
| 1,000 | talents | 组合 | 394.395 → 326.221 | 472.641 → 425.428 | 5.895 → 3.399 | 15 → 15 |

1,000 条数据下，普通列表无过滤 P50 降低 87.09%、Python 分配峰值降低 94.93%；组合过滤 P50 降低 80.93%。组合过滤本人推荐 P50 降低 11.49%、Python 峰值降低 24.85%；团队匹配分别降低 17.29%、42.34%。

没有将未过滤的推荐或团队匹配认定为明显性能提升：其全部候选依然需要评分，部分延迟/内存值持平或略高。100 条数据的部分组也没有明确收益。保留正确的全局评分与原有批量团队读取，不使用预先分页、截断或跨请求缓存换取指标。上述是本机实测值，不保证相同比例适用于其他负载、原生进程内存或 MySQL 部署。

## 候选数量与关联 SQL 上界

下面为 1,000 条固定数据、pageSize=20 的实际记录。“完整对象”不含只用于文本比较的标量投影。

| 路径 | 完整对象加载：前 → 后 | 评分候选：前 → 后 | 精确 total：前 → 后 | 关联 SQL：前 → 后 |
| --- | --- | --- | --- | --- |
| 普通列表，无过滤 | 600 → 20 个机会 | 0 → 0 | 600 → 600 | 3 → 3 |
| 普通列表，组合过滤 | 600 → 20 个机会 | 0 → 0 | 342 → 342 | 3 → 3 |
| 本人推荐，无过滤 | 600 → 600 个机会 | 600 → 600 | 600 → 600 | 6 → 6 |
| 本人推荐，组合过滤 | 600 → 342 个机会 | 342 → 342 | 342 → 342 | 6 → 6 |
| 团队匹配，无过滤 | 600 → 600 份档案 | 600 → 600 | 600 → 600 | 9 → 9 |
| 团队匹配，组合过滤 | 600 → 333 份档案 | 209 → 209 | 209 → 209 | 9 → 9 |

普通非空列表固定 **3 次子记录查询**，与当前页条数无关；含身份验证总计 7 次（身份 2 + COUNT/有序标量扫描 1 + 当前页对象 1 + 子记录 3）。空页只有身份 2 + COUNT/标量扫描 1，不加载完整机会或子记录。测试同时验证 pageSize=1、20、100。

推荐机会的子记录为 `3 × ceil(符合条件机会数 / 1000)` 次；本人档案另有固定的技能、兴趣、文本等查询，旧版技能缺少新表记录时多一次批量适配。团队档案读取使用现有共享批次，样本中的子记录查询为 9 次（包括当前机会的 3 次），不会随返回人才逐条增加。前移共享兴趣过滤使用 EXISTS，并未增加独立往返次数。文本推荐额外一次标量扫描使 SQL 总数 13 → 14；这项成本已包含在报告中。

## 结果验证与复现

基线 [before.json](before.json) 和优化 [after.json](after.json) 保存每组全部 30 个原始延迟、P50/P95、峰值、查询数、完整对象/评分候选数量、精确 total、响应 SHA-256 和执行计划。`--compare` 自动验证固定清单、模型配置、12 组响应指纹、total 与评分候选数全部相同。

独立的测试预言保留优化前“全部序列化后过滤/分页”的流程，在两个规模上比较普通列表全部页面、本人推荐及团队匹配全部页面。断言完整返回内容、顺序、total、rank、分数、无重复或遗漏；覆盖 Unicode、字面量通配符、空结果、超大页码、并列时间、所有权及隐私即时撤回。真实应用模型测试再次比较过滤后的完整分数与名次。现有 US-14/US-20 用例继续覆盖截止前、等于、之后，延后截止不会自动重新开放、显式 reopen、旧客户端省略字段及详情/收藏相关行为。

```powershell
# 首次记录基线：在基线实现和基线索引状态下执行。
.\.venv\Scripts\python.exe scripts/benchmark-be8.py --label before --output docs/testing/be8/before.json

# 在优化实现和优化索引状态下，验证同一清单、模型及返回结果。
.\.venv\Scripts\python.exe scripts/benchmark-be8.py --label after --output docs/testing/be8/after.json --compare docs/testing/be8/before.json

# BE-8 必跑真实应用模型测试；缺少资源时明确失败。
.\.venv\Scripts\python.exe -m pytest backend/tests/test_sprint3_be8.py --require-application-model -q

# 完整回归与前端真实 HTTP 联调。
.\.venv\Scripts\python.exe -m pytest backend/tests --require-application-model --require-frontend -q -rs --junitxml=docs/testing/be8/acceptance.xml

# 独立 MySQL 8.4、真实 Docker 栈及 BE-8 MySQL 验收；不接受跳过项。
.\.venv\Scripts\python.exe scripts/test-environment.py --include-be8 --report docs/testing/be8/mysql-docker.xml
```

基线性能记录来自修改前实际运行；当前优化代码直接运行 `--label before` 只会得到当前实现的结果。要重测真实基线，应在上述基线提交准备相同清单、生成器和测量脚本，并且不要应用新增索引。测量脚本仅在独立临时库中建表和种入固定数据。非 Windows 使用 `.venv/bin/python`。模型准备方法沿用 [BE-7](../be7/README.md)；CI 的真实应用模型任务已加入 BE-8 测试文件。

## 最终执行记录

| 检查 | 最终结果 | 耗时 |
| --- | --- | --- |
| 完整后端、真实应用模型与前端 HTTP 回归 | **796 passed，0 failed，14 skipped** | 817.40 秒 |
| 最终 BE-8 SQLite / 真实模型回归 | **26 passed，0 failed，0 skipped** | 54.61 秒 |
| 实际 MySQL / Docker + BE-8 MySQL | **40 passed，0 failed，0 skipped** | 330.52 秒 |
| 前后性能记录 | 12 组响应、total、评分候选数及固定配置全部相同；前后各 360 次计时请求 | 见原始 JSON |

完整回归中的 14 个默认跳过项全部在最终 MySQL/Docker 运行中成功补跑：5 个迁移/存储、8 个旧表升级及 1 个真实 Docker 栈用例。后者还包含 26 个 BE-8 MySQL 用例，与 SQLite 的 BE-8 用例是不同数据库上的重复验证；不把这些重复执行合并为新增独立用例。完整回归的 18 个前端真实 HTTP 用例全部通过。18 条既有 warning 均为 record_property 与 xunit2 元数据兼容提示。

实际容器环境为 Docker Engine 29.8.2 / Linux，MySQL Community Server **8.4.11**（镜像 `mysql:8.4`，digest `mysql@sha256:0f51e63e537a1f176423fa03ef559aabe6fa4372a53160a44bc7e75da7d15364`）。BE-8 的 Unicode 组合过滤、完整页面、全局评分、隐私撤回、只读查询、实际查询次数和索引重复升级均在此 MySQL 上通过。Docker 栈实际构建并启动 API、Nginx 前端和独立 Worker，验证文档处理及重建容器后会话/档案/文档保留。

首次 MySQL 执行发现测试断言依赖 SQLite 的 OFFSET 关键字；已改为同时接受 MySQL 的 `LIMIT offset, size`，结果一致性、加载量和查询次数断言保持不变。修正后重新执行 SQLite 26 项和完整容器 40 项，均无失败。应用实现与性能测量时相同，完整回归后仅调整了该数据库语法断言和验收工具/文档。

Windows 最初限制了现有 Git Bash/前端辅助进程；完整回归与容器测试的最终记录来自允许启动这些进程的本机运行。测试使用两个独立临时环境，最终已确认没有剩余测试容器或测试项目数据卷；保留用户既有容器和卷。MySQL 的功能验证已实际执行；上文性能时间、Python 分配峰值和保存的 EXPLAIN 仍是 SQLite 实测，不作为 MySQL 性能或原生进程内存指标。

证据文件：[完整回归](acceptance.xml)、[最终 BE-8 SQLite 回归](targeted.xml)、[MySQL/Docker 验收](mysql-docker.xml)及[执行元数据和源码校验值](execution.json)。
