# COMP3900 / COMP9900 — H18ABANANA

**🍌 Explainable Two-Sided Research Matching · Sprint 1 Developer Specification**

澳大利亚高校科研人才与科研机会的可解释双向匹配系统。

## Contents

[[_TOC_]]

## Change Log

- **2026-10-06**：参照 `README_1531.md` 的目标、迭代任务、数据设计、接口、测试和验收结构，整理完整 Sprint 1 开发说明；覆盖 US-01–US-09 和 24 个 HTTP 操作。
- 本版以 Sprint 1 API 契约为准，将原文的注册扩展方案调整为预置账户登录，不再把未纳入契约的注册接口、固定会话时限或账户名称同步规则列作 Sprint 1 要求。

> **文档状态：开发规格，不是实现完成报告。** 对应 API 版本为 `0.1.0-draft`。接口默认方案仍需团队评审；下文的测试和验收清单均为待执行要求，不表示已经通过。

## 🫡 0. Aims — 本轮目标

1. 完成科研人才和研究团队两种角色可操作的前后端流程。
2. 将手工输入及用户审核后的文件提取结果保存为结构化人才档案。
3. 实现人才寻找机会、团队寻找人才两个方向的匹配，并逐项展示要求、证据和状态。
4. 保证只有当前已确认资料参与匹配，并在团队匹配前应用发现权限及字段可见性。
5. 使用共同 API 契约开展 JavaScript 前端与 Python 后端开发，通过可复现的测试验证关键流程。

## 🌈 1. Overview — 项目与范围

### 1.1 项目背景

科研人才的学历、课程、科研经历、技能、研究兴趣和成果通常分散在简历、成绩单和个人描述中；研究团队则需要将这些信息与机会要求进行比较。本系统把两侧信息结构化，提供双向发现和可追溯的匹配解释。

原项目以澳大利亚 Go8 高校科研环境为背景。按 2026-09-30 客户会议分工及当前契约，BANANA 原型使用 **STEM / BUSINESS** 两个学科组。匹配结果用于辅助发现科研机会，不代表录取决定、申请提交或学历认证。

### 1.2 本文依据与使用方式

| 依据 | 本文如何使用 |
|---|---|
| 用户提供的 [Jira 待办列表](https://unsw-comp3900-comp9900-26t3.atlassian.net/jira/software/projects/H18ABANANA/boards/103/backlog)截图 | 确定 Sprint 1 的 9 个父故事、点数与日期；本文记录截图范围，不声称实时 Jira 状态 |
| [Sprint 1 API 契约](docs/api/sprint-1-api-contract.md) | 接口路径、字段、权限、错误、状态及匹配算法的详细依据 |
| [OpenAPI](docs/api/openapi.json)、[接口索引](docs/api/endpoint-index.json)、[样例索引](docs/api/examples/index.json) | 机器可读接口和联调样例；接口索引包含契约中的实现子任务关联 |
| `client_meeting_0930.txt` | 客户背景、学科分工、解释要求及首轮演示的手工录入兜底 |
| 项目 109 说明 PDF | 理解结构化档案、双向发现、证据解释和用户审核的项目目标 |
| `README_1531.md` | 借鉴文档组织和接口说明形式；不沿用该课程的技术栈、评分比例、提交命令或迭代安排 |

开发时先读本文了解本轮任务，再按契约第 4、6 节实现具体接口和模型。本文是契约的开发导读；如需要调整协议，应同步修改契约、OpenAPI、样例和测试，不能只改 README 或某一端。

### 1.3 Sprint 1 边界

本轮使用预置 `TALENT` 与 `RESEARCH_TEAM` 账户；一个研究团队账户代表一个团队。人才可维护和确认档案、控制可见字段、查看机会推荐；研究团队可管理自己的机会并发现获准展示的人才。

本轮不包含完整注册、密码重置、复杂身份切换、收藏、语义向量匹配或高级筛选；也不增加机会删除、撤销发布、团队成员管理、申请或录取流程。只实现下文 US-01–US-09，不展开后续 Sprint。

**文件提取仍属于 Sprint 1。** 会议允许 Demo 1 在提取未就绪时临时使用手工录入，但 Jira 已将 US-09 纳入本轮。因此保留完整上传、提取、审核、导入流程；仅有上传按钮或静态提取样例不能视为 US-09 完成。演示若使用兜底，应明确记录尚未完成的部分。

## 🐶 2. Sprint 1 — Basic Functionality and Tests

### 2.1 Task — 本轮任务

截图显示 Sprint 1 为 **10 月 3 日至 10 月 15 日**，共 **9 个工作项、36 Story Points**。点数是工作量估计，不是评分权重或完成进度；截图中的事项均处于待办状态。

| 故事 | Jira | 点数 | 本轮必须交付的行为 |
|---|---|---:|---|
| US-01 User Login and Talent Profile Creation | [H18ABANANA-9](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-9) | 3 | 预置账户登录、会话和退出；人才读取、编辑、保存自己的结构化档案 |
| US-02 Create and Manage Research Opportunities | [H18ABANANA-10](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-10) | 3 | 团队创建草稿、修改、发布和查看自己的机会；已发布机会可被发现 |
| US-03 Review and Confirm Talent Profile Information | [H18ABANANA-11](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-11) | 2 | 用户审核并确认当前档案；内容变化后重新确认 |
| US-04 View Recommended Opportunities and Matching Explanations | [H18ABANANA-13](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-13) | 5 | 人才查看有序机会推荐及逐项匹配解释 |
| US-05 Discover Matching Research Talent | [H18ABANANA-12](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-12) | 3 | 团队针对自己已发布的机会，查看符合发现权限的人才列表和解释 |
| US-06 Test the Sprint 1 Profile and Matching Flows | [H18ABANANA-14](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-14) | 4 | 用合成或去标识数据测试档案、匹配、隐私和上传流程，记录实际结果 |
| US-07 Manage Profile Privacy and Field Visibility | [H18ABANANA-15](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-15) | 3 | 人才主动选择是否被发现，以及团队可查看和用于匹配的档案字段 |
| US-08 Requirement-Level Matching Results and Evidence | [H18ABANANA-1](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-1) | 5 | 按要求逐项展示候选信息、证据、原因，以及 Matched / Partial / Gap / Unknown |
| US-09 Resume / Transcript Upload and Information Extraction | [H18ABANANA-2](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-2) | 8 | 上传简历或成绩单、查询提取状态、审核纠错、导入所选部分，再确认档案 |
| **合计** | **US-01–US-09** | **36** | **24 个 HTTP 操作及对应前端流程** |

US-04、US-05 复用 US-08 的匹配规则，但因查看权限不同，两个方向的分数可以不同。US-06 贯穿所有功能，不新增公开测试或清空数据库接口。

### 2.2 Storing Data — 数据结构与状态

#### 2.2.1 逻辑模型

以下是数据职责，不是已经存在的数据库表或目录。契约不限定 Python 框架、数据库或 ORM；应保证保存后可重新读取，并用事务处理版本检查与更新。

| 数据 | 对外结构或关键字段 | 内部职责 |
|---|---|---|
| User / Session | `user: {id, displayName, email, role}` 或 `null`；`csrfToken` | 保存账户、角色及服务端会话；登录凭证不进入业务 JSON |
| Tag / TagList | `id`, `label`, `kind`, `disciplineGroups`；列表为 `{items}` | 技能和兴趣共用标签词表；标签类型为 `SKILL` / `INTEREST` |
| Profile | `talentId`, `revision`, `content`, `confirmation`, `origins`, `updatedAt` | 关联人才账户，保存档案内容、版本、确认状态和来源 |
| Privacy | `revision`, `discoverable`, `visibleFields`, `updatedAt` | 关联人才账户；隐私版本独立于档案版本 |
| Document / Extraction | 文件元数据及处理状态；`suggestedSections`, `uncertainFields`, `warnings`, `reviewRequired` | 关联上传者，私有保存原文件；提取建议与正式档案分开 |
| Opportunity | `id`, `revision`, `status`, `content`, `createdAt`, `updatedAt` | 内部保存所属团队；客户端不能指定归属或发布状态 |
| OwnerMatch / TeamMatch | 机会或人才信息、`summary`、逐项 `requirements`、`evaluatedAt` | 根据当前确认版本和访问权限计算；缓存随档案、隐私或机会变化失效 |

`ProfileContent` 的 **8 个字段全部必填**：

| 字段 | 类型与含义 |
|---|---|
| `displayName` | 字符串，最多 100 字符；草稿允许空字符串 |
| `disciplineGroup` | `STEM` / `BUSINESS` / `null` |
| `education` | 教育记录数组：`id`, `institution`, `qualification`, `discipline`, `startYear`, `endYear` |
| `courses` | 课程数组：`id`, `name`, `code`, `description` |
| `researchExperience` | 经历数组：`id`, `title`, `organisation`, `description` |
| `skills` | 技能声明数组：`tagId`, `claim`, `evidenceText`；claim 为 `HAS` / `DOES_NOT_HAVE` |
| `researchInterests` | `INTEREST` 类型标签 ID 数组 |
| `researchOutputs` | 成果数组：`id`, `title`, `type`, `url`, `description` |

六个数组分别最多 100 项。子字段的必填、可空、长度及枚举限制见契约 [ProfileContent](docs/api/sprint-1-api-contract.md#model-profilecontent) 及其关联模型。顶层资源 ID 由后端生成；教育、课程、经历、成果和要求的子记录可由前端生成稳定 ID，编辑时保留，不能用数组索引代替。

**保存结构不等于返回结构。** 服务端需保存归属和会话等内部数据，但不能直接把数据库对象返回给浏览器。尤其不能把完整人才档案返回给研究团队，再交给前端隐藏字段。

#### 2.2.2 状态与版本

| 对象或操作 | 初始状态 / 转换规则 |
|---|---|
| 预置人才档案 | `revision=0`，`displayName=""`，`disciplineGroup=null`，六个数组为空；`UNCONFIRMED`，确认版本和时间为 `null` |
| 隐私设置 | `revision=0`，`discoverable=false`，`visibleFields=[]` |
| 普通档案 / 隐私 / 机会 PUT | 原子校验 `expectedRevision`；实际变化才加 1，完全无变化不加版本 |
| 档案内容变化 | 重置为 `UNCONFIRMED`，清空 `confirmedRevision`、`confirmedAt`；停止使用旧确认资料匹配 |
| 档案确认 | 名称非空且六个学术 / 研究数组至少一个非空；设置 `confirmedRevision=revision`，不增加内容版本；重复确认保留原确认时间 |
| 隐私变化 | 仅影响隐私版本和后续团队访问，不取消档案确认 |
| 文件处理 | `QUEUED → PROCESSING → READY / FAILED`；READY 只表示提取完成 |
| 导入审核后的提取结果 | 校验 `expectedProfileRevision`；每次成功导入都增加档案版本并取消确认，即使值相同 |
| 科研机会 | 创建为 `DRAFT, revision=1`；发布为 `PUBLISHED` 并加 1；使用当前版本重复发布不再加版本 |
| 已发布机会编辑 | 保持 `PUBLISHED`；必须保留至少一个有效要求；后续匹配使用新内容 |

版本冲突统一返回 `409 REVISION_CONFLICT` 和当前版本，不覆盖更新后的数据。前端保留本地输入，重新读取并比较，不能静默重试覆盖。

### 2.3 Implementing Features — 实现顺序与职责

建议按可验证的小功能完成一个闭环，再扩展另一条流程：

1. 确认契约默认值，准备预置人才 / 团队账户、共享标签、合成档案和机会数据。
2. 完成会话、登录与权限，再完成手工档案保存、确认及隐私设置。
3. 完成机会创建、编辑、发布，再接入人才推荐和团队发现。
4. 实现 US-08 的状态、证据、评分和排序；确保隐私处理在团队评分之前。
5. 接入文件上传、异步提取、审核导入；保留手工入口。
6. 逐项执行 US-06 验收并修复缺陷，准备完整 Demo 1。

| 模块 | 主要接口编号 | 前端职责 | Python 后端职责 |
|---|---|---|---|
| FE-1 布局与登录 | 01–03 | 登录页、会话恢复、退出与账户缓存清理 | 会话、认证、角色与 CSRF 校验 |
| FE-2 档案、审核及隐私 | 04–09、14 | 表单、审核确认、冲突提示、可见字段选择 | 校验、保存、版本控制、确认与隐私 |
| FE-3 机会管理 | 04、16–20 | 创建 / 编辑表单、草稿和发布页面 | 团队归属、完整替换、发布条件 |
| FE-4 双向匹配及解释 | 21–24 | 排名列表、逐项解释、空状态 | 权限过滤、四种状态、证据、分数与排序 |
| FE-5 文件及提取审核 | 10–15，随后 05–07 | 上传、状态轮询、审核纠错及所选部分预览 | 私有文件、提取处理、来源记录、原子导入 |

这张表用于拆分职责，不代表已经分配给具体成员。后端内部可按认证、档案、机会、文件和匹配划分模块；文件名和框架由团队确定。认证模块可以沿用 `auth.py` 名称，但 HTTP 路由不应与纯匹配规则、存储细节互相耦合。

### 2.4 Testing Guidelines — 测试原则

- **按行为测试。** 检查响应、状态转换、权限和后续读取结果，不依赖内部函数名或数据库表名。
- **同时覆盖成功、失败和边界。** 测试空档案、空列表、重复确认、版本冲突、未知字段、重复 ID、错误标签类型、错误角色及资源越权。
- **测试隔离。** 每个测试使用独立数据或受控初始化；重置仅用于测试环境，不增加公共 `/clear` 接口。
- **按层验证。** 匹配规则使用确定性单元测试；接口验证请求、响应及权限；浏览器联调验证完整用户流程和缓存清理。
- **样例是输入，不是通过证明。** [30 个 JSON 样例](docs/api/examples/index.json) 可用于 mock 和协议检查，真实登录、持久化、文件处理及权限仍需接入后端测试。
- **记录可复现结果。** US-06 的记录至少包含故事编号、前置数据、步骤、预期结果、实际结果、通过 / 失败、关联缺陷及复测结果。

### 2.5 Sprint 1 Interface — 接口规格

#### 2.5.1 通用约定

- 下列路径均省略统一前缀 `/api/v1`；JSON 使用 UTF-8、`camelCase` 字段和约定的大小写枚举。
- 所有业务 ID 满足 `^[A-Za-z0-9_-]{1,64}$`；时间使用 UTC RFC3339 字符串。
- 成功响应直接返回业务对象，不套 `data` / `success`；204 无响应体。
- 必填且允许 `null` 的字段仍须出现；拒绝未知字段、重复记录 ID 和错误类型。普通文本按文本渲染。
- 所有 POST / PUT 携带 `X-CSRF-Token`，后端同时检查会话和允许的 Origin。
- 请求体默认 `application/json`；上传使用 `multipart/form-data`；原文件下载返回二进制。
- 分页参数为 `page=1`、`pageSize=20`；page ≥ 1，pageSize 为 1–100 的整数。不合法返回 422。
- 分页响应为 `{items, page, pageSize, total}`；无结果或超出末页仍返回 200 和 `items: []`；total 只统计有权访问的记录。
- 机会按 `updatedAt` 降序、ID 升序排列；文件按 `createdAt` 降序、ID 升序排列。匹配排序见 2.7。
- 超时后先读取当前状态，再决定是否重试 POST；本版没有 `Idempotency-Key` 或创建去重保证。

下面保留 README_1531 的“功能、参数、返回、错误”形式。编号与原契约一致；模型名称均以契约第 6 节为准。通用错误见 2.5.6，表中另列关键业务错误；每个接口的完整状态码见对应链接。

#### 2.5.2 会话、标签、人才档案与隐私

| 编号 / 接口及用途 | 请求参数或请求体 | 成功返回 | 权限与关键错误 |
|---|---|---|---|
| [01](docs/api/sprint-1-api-contract.md#api-01) `GET /auth/session`：读取会话及 CSRF | 无 | **200 Session**：`{user, csrfToken}` | 匿名可用；未登录为 `user=null`，不是 401 |
| [02](docs/api/sprint-1-api-contract.md#api-02) `POST /auth/login`：预置账户登录 | `{email, password}`；先取得匿名 CSRF | **200 Session**，设置新 Cookie | 凭证错误：401 `INVALID_CREDENTIALS`；限流：429 |
| [03](docs/api/sprint-1-api-contract.md#api-03) `POST /auth/logout`：退出 | 无请求体 | **204**，撤销会话并清 Cookie | 两种已登录角色 |
| [04](docs/api/sprint-1-api-contract.md#api-04) `GET /tags`：读取共享标签 | 可选 query：`kind=SKILL/INTEREST` | **200 TagList**：`{items}`，不分页 | 两种已登录角色；参数不合法：422 |
| [05](docs/api/sprint-1-api-contract.md#api-05) `GET /me/profile`：读取自己的档案 | 无 | **200 Profile** | TALENT 本人；新档案返回初始对象，不是 404 |
| [06](docs/api/sprint-1-api-contract.md#api-06) `PUT /me/profile`：保存完整档案 | **ProfileWrite**：`{expectedRevision, content}`，8 个内容字段齐全 | **200 Profile** | TALENT 本人；旧版本：409；非法内容：422 |
| [07](docs/api/sprint-1-api-contract.md#api-07) `POST /me/profile/confirmation`：确认当前档案 | **RevisionRequest**：`{expectedRevision}` | **200 Profile** | TALENT 本人；旧版本：409；确认条件不足：422 |
| [08](docs/api/sprint-1-api-contract.md#api-08) `GET /me/privacy`：读取隐私 | 无 | **200 Privacy** | TALENT 本人 |
| [09](docs/api/sprint-1-api-contract.md#api-09) `PUT /me/privacy`：保存隐私 | **PrivacyWrite**：`{expectedRevision, discoverable, visibleFields}` | **200 Privacy** | TALENT 本人；旧版本：409；非法 / 重复字段：422 |

登录 `password` 为 1–200 字符；角色由服务器读取，不能由请求选择。`visibleFields` 只能包含 2.2 中的八个 ProfileContent 字段，不支持邮箱、原文件或单条技能级别的授权。

档案 PUT 是**完整替换**：未编辑内容也要带回，`[]` 表示清空。实际修改的学术部分来源改为 `MANUAL`，`documentId=null`；未改部分保留来源。不接受客户端伪造确认状态或来源。

#### 2.5.3 文件上传、提取、审核与导入

| 编号 / 接口及用途 | 请求参数或请求体 | 成功返回 | 权限与关键错误 |
|---|---|---|---|
| [10](docs/api/sprint-1-api-contract.md#api-10) `GET /me/documents`：自己的文件列表 | query：`page`, `pageSize` | **200 DocumentPage** | TALENT 本人；只返回元数据，不返回公开下载地址 |
| [11](docs/api/sprint-1-api-contract.md#api-11) `POST /me/documents`：上传并开始提取 | FormData：`file` + `kind=CV/TRANSCRIPT` | **202 Document**，初始 `QUEUED` | TALENT 本人；超限：413；不支持格式：415；限流：429 |
| [12](docs/api/sprint-1-api-contract.md#api-12) `GET /me/documents/{documentId}`：处理状态 | path：`documentId` | **200 Document** | 文件所有者；不存在 / 他人文件：404 |
| [13](docs/api/sprint-1-api-contract.md#api-13) `GET /me/documents/{documentId}/extraction`：审核建议 | path：`documentId` | **200 Extraction** | 文件所有者；处理中：409 `EXTRACTION_NOT_READY`；失败：422 `EXTRACTION_FAILED` |
| [14](docs/api/sprint-1-api-contract.md#api-14) `POST /me/documents/{documentId}/apply`：导入审核内容 | path：`documentId`；**ApplyExtractionRequest**：`{expectedProfileRevision, sections}` | **200 Profile**，新版本且未确认 | 文件所有者；版本冲突 / 未就绪：409；提取失败 / 无效 sections：422 |
| [15](docs/api/sprint-1-api-contract.md#api-15) `GET /me/documents/{documentId}/file`：下载原文件 | path：`documentId` | **200 二进制文件** | 文件所有者；团队不可下载；不存在 / 他人文件：404 |

上传接受非空 **PDF / DOCX，最多 10 MiB（10,485,760 bytes）**，不支持旧 `.doc`。后端验证实际内容、格式和大小，不能只看扩展名。前端用 FormData 时不要手动设置 Content-Type。

页面打开时每 2 秒轮询状态，进入 READY / FAILED 后停止；60 秒后暂停自动轮询并提供手动刷新。前端等待超时不能把后端状态改成 FAILED。状态接口返回 200 + FAILED 是成功读取到失败状态，和读取失败的提取结果返回 422 不同。

提取返回的 `reviewRequired` 始终为 `true`。不确定内容放入 `uncertainFields`（`UNKNOWN` / `NOT_RECOGNISED`）；不自动推断正面或负面技能声明。

导入 `sections` 只能选择六个学术 / 研究数组，且至少包含一个部分：**只替换提交的部分，省略部分保持原样，显式 `[]` 清空该部分**。用户可以纠正建议；若要合并已有技能，前端按 tagId 合并、让用户审核后提交完整 skills 数组。导入后记录 `USER_REVIEWED_DOCUMENT` 来源，并要求单独确认。

原文件私有存储，每次下载重新检查归属；使用正确媒体类型、`Content-Disposition: attachment` 及 `X-Content-Type-Options: nosniff`。提取失败保留手工录入；本轮无专用重试接口，再上传启动新的尝试。

#### 2.5.4 科研机会管理

| 编号 / 接口及用途 | 请求参数或请求体 | 成功返回 | 权限与关键错误 |
|---|---|---|---|
| [16](docs/api/sprint-1-api-contract.md#api-16) `GET /opportunities`：机会列表 | query：`scope=published/mine`，默认 published；`page`, `pageSize` | **200 OpportunityPage** | 两种已登录角色；mine 仅团队可用，否则 403 |
| [17](docs/api/sprint-1-api-contract.md#api-17) `POST /opportunities`：创建草稿 | **OpportunityContent**，直接提交内容对象 | **201 Opportunity**，`DRAFT, revision=1` | RESEARCH_TEAM；服务端设置 ID 与归属 |
| [18](docs/api/sprint-1-api-contract.md#api-18) `GET /opportunities/{opportunityId}`：机会详情 | path：`opportunityId` | **200 Opportunity** | 已登录可读发布内容；草稿仅所属团队可读，否则 404 |
| [19](docs/api/sprint-1-api-contract.md#api-19) `PUT /opportunities/{opportunityId}`：完整修改内容 | path：`opportunityId`；**OpportunityWrite**：`{expectedRevision, content}` | **200 Opportunity** | 所属团队；其他团队：404；旧版本：409；内容不合法：422 |
| [20](docs/api/sprint-1-api-contract.md#api-20) `POST /opportunities/{opportunityId}/publish`：发布 | path：`opportunityId`；`{expectedRevision}` | **200 Opportunity**，`PUBLISHED` | 所属团队；旧版本：409；无有效要求：422 |

`OpportunityContent` 必须包含 `title`、`university`、`disciplineGroup`、`discipline`、`researchArea`、`description`、`requirements`。草稿可以 `requirements=[]`，但基本文本仍必填；发布后至少保留一条有效要求。

每条要求包含 `id`、`label`、`kind=SKILL/INTEREST`、`importance=REQUIRED/PREFERRED` 和 `tagIds`。要求最多 50 条；每条 1–20 个不重复、类型正确的标签，同一条内为 **AND** 关系。不要将原项目提到但本契约没有定义的机会类型、资助或时间字段自行加入请求。

#### 2.5.5 双向匹配与逐项解释

| 编号 / 接口及用途 | 请求参数 | 成功返回 | 权限与关键错误 |
|---|---|---|---|
| [21](docs/api/sprint-1-api-contract.md#api-21) `GET /me/recommendations`：个人机会排名 | query：`page`, `pageSize` | **200 RecommendationPage** | TALENT 本人；当前档案未确认：409 `PROFILE_UNCONFIRMED` |
| [22](docs/api/sprint-1-api-contract.md#api-22) `GET /me/opportunity-matches/{opportunityId}`：个人匹配解释 | path：`opportunityId` | **200 OwnerMatch** | TALENT 本人；未确认：409；机会未发布 / 不存在：404 |
| [23](docs/api/sprint-1-api-contract.md#api-23) `GET /opportunities/{opportunityId}/talent-matches`：人才排名 | path：`opportunityId`；query：`page`, `pageSize` | **200 TalentMatchPage** | 已发布机会所属团队；未发布 / 不属于本团队：404 |
| [24](docs/api/sprint-1-api-contract.md#api-24) `GET /opportunities/{opportunityId}/talent-matches/{talentId}`：人才可见资料及解释 | path：`opportunityId`, `talentId` | **200 TeamMatch** | 已发布机会所属团队；人才撤销发现 / 当前未确认：404 |

`RecommendationPage.items` 包含 `rank, opportunity, summary`；`TalentMatchPage.items` 包含 `rank, talent, summary`。详情逐项返回完整 `requirement`、`status`、`reasonCode`、`reason` 和 `evidence`，前端按条目展示，不能只显示总分。

人才自己的详情使用 **OwnerEvidence**：`field, recordId, valueSummary, confirmedRevision, sourceType, documentId`。团队使用 **TeamEvidence**：仅 `field, recordId, valueSummary`；人才资料使用 **VisibleProfile**：`{talentId, fields}`，隐藏字段整个键省略。

#### 2.5.6 Errors — 统一错误

```json
{
  "error": {
    "code": "REVISION_CONFLICT",
    "message": "Reload the latest resource before saving.",
    "fieldErrors": [],
    "currentRevision": 4
  },
  "requestId": "req_demo_001"
}
```

前端按 `error.code` 分支，不依赖 message 文案；`fieldErrors` 始终存在，`currentRevision` 只用于版本冲突。字段路径使用 `content.education[0].institution` 形式。

| HTTP | error.code | 前端处理 |
|---|---|---|
| 400 | `BAD_REQUEST` | 请求无法解析；保留输入并提示失败 |
| 401 | `UNAUTHENTICATED` / `INVALID_CREDENTIALS` | 清理过期会话缓存、返回登录；错误凭证使用统一提示 |
| 403 | `FORBIDDEN` / `CSRF_INVALID` | 拒绝越权；CSRF 错误重新读取会话后由用户重试，不自动重放修改 |
| 404 | `NOT_FOUND` | 资源不存在或不可访问，刷新列表 |
| 409 | `REVISION_CONFLICT` / `PROFILE_UNCONFIRMED` / `EXTRACTION_NOT_READY` | 分别处理版本比较、资料确认或等待提取 |
| 413 | `UPLOAD_TOO_LARGE` | 提示 10 MiB 上限 |
| 415 | `UNSUPPORTED_FILE_TYPE` / `UNSUPPORTED_MEDIA_TYPE` | 选择支持文件或修正请求媒体类型 |
| 422 | `VALIDATION_ERROR` / `EXTRACTION_FAILED` | 展示字段错误，或提供手工录入 |
| 429 | `RATE_LIMITED` | 停止重复请求，提示稍后重试 |
| 500 | `INTERNAL_ERROR` | 保留输入及 requestId，便于排查 |

不能返回堆栈、数据库错误、服务器路径、密码或会话凭证。Python 框架自带的校验错误也要转换成上述结构；`Document.error` 仅使用 ErrorDetail，不嵌套 requestId。

### 2.6 Authorisation — 会话、角色与隐私

#### 2.6.1 Cookie 会话

```text
GET /auth/session       → 建立 / 读取匿名会话，返回 csrfToken
POST /auth/login        → 携带 Cookie + CSRF，登录后轮换两者
GET /auth/session       → 返回当前 User；会话 ID 只在 Cookie 中
POST /auth/logout       → 撤销服务端会话、清 Cookie，返回 204
```

Cookie 名为 `h18_session`，属性为 `HttpOnly; SameSite=Lax; Path=/`，不设 Domain；HTTPS 使用 Secure，本地 HTTP 可省略。浏览器请求使用 `credentials: 'include'`；登录成功后替换 CSRF token，登录会话值不放到 localStorage、URL 或 JSON 中。

`user.id` 和 `talentId` 是资源标识，不能代替认证；`csrfToken` 也不是登录凭证。当前账户、角色和资源所有者由后端根据会话确定，不信任客户端传入的 owner、role 或确认状态。会话过期时间和账户预置方式属于实现配置，本契约未指定固定值。

私有接口缺少有效会话返回 401，角色不符返回 403，资源不存在或不可访问返回 404。个性化响应使用 `Cache-Control: no-store`；退出、登录为另一账户时清理档案、文件、推荐等前端缓存。

#### 2.6.2 先过滤权限，再计算团队匹配

团队请求的处理顺序必须为：

1. 验证团队拥有该已发布机会。
2. 排除 `discoverable=false` 或当前版本未确认的人才。
3. 按 `visibleFields` 选出本次可用资料。
4. 只用这些字段生成状态、分数和解释，然后排序、分页、计算 total。
5. 每次详情请求重新校验；档案、机会或隐私变化后使旧结果缓存失效。

隐藏字段不能参与团队分数、排名或解释。缺少证据和隐藏证据都使用通用的“证据不足”描述，不说“此用户隐藏了 Python”。`displayName` 不可见时显示匿名人才；即使 `visibleFields=[]`，只要允许发现且当前已确认，也可返回匿名人才和 UNKNOWN 结果。

人才本人推荐可使用自己的完整已确认资料，即使 `discoverable=false` 也能查看推荐。团队任何响应不得暴露登录邮箱、原文件名、文档 ID、下载链接、原始提取文本或来源信息。撤销发现影响后续请求：下次列表不出现该人才，旧详情链接返回 404；进入、刷新或重新聚焦团队页面时应重新读取结果。

### 2.7 Matching Rules — 状态、证据与排名

本轮算法版本为 `tag-coverage-v1`。仅从**当前已确认且本次有权使用的资料**判断 SKILL / INTEREST 标签，不从课程或项目自由文本自行推断技能。

按以下优先级判断每条 AND 要求：

| 优先级 | 条件 | API status / 页面显示 | reasonCode |
|---:|---|---|---|
| 1 | 任一要求技能存在明确 `DOES_NOT_HAVE` | `GAP` / Gap | `EXPLICIT_NEGATIVE_CLAIM` |
| 2 | 全部标签有肯定证据 | `MATCHED` / Matched | `ALL_TAGS_SUPPORTED` |
| 3 | 部分有肯定证据，其余未知 | `PARTIAL` / Partial | `SOME_TAGS_SUPPORTED` |
| 4 | 无可用的肯定或明确否定证据 | `UNKNOWN` / Unknown | `INSUFFICIENT_EVIDENCE` |

例如 Python+SQL：有 Python 且明确没有 SQL 为 GAP；有 Python、SQL 未知为 PARTIAL；两者均无信息为 UNKNOWN。没有上传文件、未填写或隐藏技能都不能自动变成 GAP；未确认档案不进入匹配。

MATCHED / PARTIAL 引用真实支持证据，GAP 引用明确否定声明，UNKNOWN 的 `evidence=[]`。`evidenceText` 为空时只能引用确认过的标签声明，不能编造经历；兴趣的 evidence.recordId 使用 tagId。

```text
权重 w：REQUIRED = 2，PREFERRED = 1
状态值 v：MATCHED = 1，PARTIAL = 0.5，GAP = 0，UNKNOWN = 0

score = round_half_up(100 × sum(w × v) / sum(w), 2)
unknownWeightPercent = round_half_up(100 × UNKNOWN 要求权重之和 / sum(w), 2)
requiredGapCount = REQUIRED 且为 GAP 的要求数量
```

后端采用十进制 half-up 保留两位，前端直接展示返回结果。总权重为 0 时，两项百分比返回 `null`，`evaluationStatus=INSUFFICIENT_CRITERIA`，不返回 NaN；正常为 `EVALUATED`。发布接口阻止空要求，此分支用于防御遗留数据。

排序按 **score 降序 → unknownWeightPercent 升序 → 对象 ID 升序**，null 分数放最后；排序后分页，`rank` 为全局排名，不随页面重置。REQUIRED 提高权重并计入 requiredGapCount，本轮不因一个 GAP 自动排除人才。

契约的四状态样例：Python REQUIRED 为 MATCHED、Python+SQL REQUIRED 为 PARTIAL、访谈 PREFERRED 为 GAP、R PREFERRED 为 UNKNOWN，得到 **score=50、unknownWeightPercent=16.67、requiredGapCount=0**。若人才只共享姓名，团队的四项均为 UNKNOWN，score=0、unknownWeightPercent=100。分数代表证据覆盖程度，不是录取概率。

### 2.8 Working in Parallel — 协作与联调

前端依据 [OpenAPI](docs/api/openapi.json) 和 [样例](docs/api/examples/index.json) 开发 mock，后端实现同一协议。身份鉴别、确认、证据选择、权限过滤和评分以服务端为准。前端请求 `/api/v1`，开发代理转发给 Python 服务并保留 Origin；实际监听地址由团队配置。

每个功能建议使用独立分支和 Merge Request，关联 Jira 事项，并附本轮适用的测试结果。接口变更在一个协调改动中更新契约版本、OpenAPI、样例及两端测试。团队在锁定版本前评审契约 1.3 的 Cookie 会话、整份档案确认、10 MiB 上传限制和评分权重等默认值。

**手工档案主流程：**

```text
读取会话 → 人才登录 → 读取标签和档案
→ PUT 完整档案 → 用户审核 → POST 确认当前版本
→ GET 推荐列表 → GET 逐项匹配解释
```

**文件提取流程：**

```text
上传 → 查询处理状态 → READY 后读取提取建议
→ 用户选择、纠错并确认替换哪些部分
→ 读取当前档案版本 → apply 导入 → 再次审核并确认档案
→ 重新读取推荐
```

**团队发现与隐私流程：**

```text
人才确认档案 → 主动开启 discoverable 并选择可见字段
团队登录 → 读取自己的机会 → 创建草稿 → 修改 → 发布
→ 读取人才排名及解释
人才撤销发现 → 团队刷新后不再看到该人才，旧详情返回 404
```

样例中的 ID、邮箱和密码均为虚构值，不是已开通的测试账户；各样例展示独立请求 / 响应，不能假定所有 revision 构成同一连续数据库历史。调用时使用实际读取到的版本。

### 2.9 Acceptance Criteria — 验收标准

以下是 Sprint 1 的功能验收标准，不套用 COMP1531 的分数或 MR 数量要求。

| 验收项 | 对应故事 | 必须观察到的结果 |
|---|---|---|
| 匿名及预置账户登录 | US-01 | 匿名 session 为 200 + user=null；私有请求 401；两种角色登录正确；登录轮换会话，退出后旧会话失效 |
| 档案初始化及保存 | US-01 | 新档案版本 0、未确认、默认不被发现；保存后刷新读取一致；完整替换不会丢失未编辑字段 |
| 审核、重复确认及重确认 | US-03 | 空档案不能确认；重复确认不改版本 / 原确认时间；真实修改后推荐返回 409，重确认后恢复 |
| 并发保存 | US-01、US-02、US-07 | 档案、隐私、机会均拒绝旧版本 409；新数据未被覆盖；普通无变化保存不加版本 |
| 机会生命周期 | US-02 | 草稿不可被人才查看或推荐；无要求不能发布；所属团队可编辑发布内容，其他团队无法修改 |
| 人才推荐 | US-04 | 使用当前已确认资料及发布机会；关闭 discoverable 不影响本人推荐；无机会为 200 空列表 |
| 团队发现 | US-05 | 仅已确认且同意被发现的人才进入结果；无可见字段仍可为匿名 UNKNOWN；total 在权限过滤后计算 |
| 四状态与证据 | US-08 | 四状态样例结果符合 2.7；明确否定优先；缺失不算 GAP；UNKNOWN 无证据；不编造课程 / 项目事实 |
| 排名、分页及边界 | US-04、US-05、US-08 | 排序确定、跨页 rank 连续、非法分页 422、超出末页为空；零要求评分安全返回 null |
| 隐私变化 | US-07 | 只修改隐私不取消档案确认；隐藏 skills 后团队分数及解释随之变化，响应中隐藏键被省略 |
| 撤销发现与缓存 | US-05、US-07 | 下次列表剔除人才，旧详情 404；机会 / 档案 / 隐私修改后不使用过期结果 |
| 原文件访问 | US-07、US-09 | 上传者能下载；其他人才和团队被拒绝；团队响应无邮箱、文件、来源信息 |
| 上传与处理 | US-09 | PDF / DOCX 接受后 202，状态可查询；超限 413、不支持格式 415；能观察到 READY 或 FAILED |
| 提取不确定及失败 | US-09 | 不自动确认或覆盖资料；保留手工录入；60 秒停止自动轮询不等于后端失败 |
| 审核导入 | US-03、US-09 | 只替换选择部分，省略保留、空数组清空；导入增加版本且需重确认；旧版本导入 409 |
| 认证、CSRF 及账户切换 | US-01、US-07 | 修改请求缺 CSRF / 错误 Origin 被拒绝；仅知道 ID 不能越权；切换账户无前一账户缓存 |
| 协议与错误 | US-06 及相关故事 | 路径、字段、枚举、响应状态与契约一致；错误均为统一结构，不泄露内部信息 |
| 测试记录与缺陷复测 | US-06 | 保存可复现步骤与实际结果；失败项关联 Jira，修复后记录复测 |

### 2.10 Dryrun — 演示前自查

当前仓库包含文档、OpenAPI 和样例，尚未提供应用源码、依赖清单、启动脚本或测试运行器。因此本文不把 `npm test`、`pytest` 或课程 dryrun 命令写成现有可执行步骤。

实现接入后，应补齐实际运行说明：依赖和版本、环境变量模板、数据初始化方法、预置账户获取方式、前后端启动命令、访问地址、测试命令及测试数据重置方式。不要把真实密码写入 README。

演示前按以下顺序执行：

1. 初始化隔离测试数据，至少准备两个独立人才账户和两个团队账户，用于验证跨账户、跨团队访问。
2. 以人才账户完成手工保存、确认、查看推荐和逐项解释。
3. 上传测试 PDF / DOCX，演示处理、审核纠错、导入和重新确认；同时检查失败时的手工入口。
4. 以团队账户创建并发布机会，查看人才排名和可见资料。
5. 调整人才字段可见性，展示团队分数与解释变化；再撤销发现，验证旧详情不可访问。
6. 验证并发旧版本保存、四种匹配状态、空列表、超限文件、越权和退出后缓存清理。
7. 将实际结果记入 US-06；演示中明确标示 mock、未完成项或临时兜底。

可直接参考的样例：

| 场景 | 仓库样例 |
|---|---|
| 保存、确认及隐私 | [profile-write.json](docs/api/examples/profile-write.json)、[confirm-request.json](docs/api/examples/confirm-request.json)、[privacy-write.json](docs/api/examples/privacy-write.json) |
| 创建机会 | [opportunity-create.json](docs/api/examples/opportunity-create.json) |
| 提取与导入 | [extraction-ready.json](docs/api/examples/extraction-ready.json)、[apply-extraction-request.json](docs/api/examples/apply-extraction-request.json) |
| 四种匹配状态 | [owner-match-four-statuses.json](docs/api/examples/owner-match-four-statuses.json) |
| 隐藏技能后的团队结果 | [team-match-hidden-skills.json](docs/api/examples/team-match-hidden-skills.json) |
| 冲突及未确认错误 | [error-revision-conflict.json](docs/api/examples/error-revision-conflict.json)、[error-unconfirmed.json](docs/api/examples/error-unconfirmed.json) |

### 2.11 Sprint 1 Delivery — 交付清单

- [ ] US-01–US-09 的前端行为和对应后端接口已实现；Jira 附可追溯的 MR、测试或演示证据。
- [ ] 24 个 HTTP 操作与 `0.1.0-draft` 契约或团队共同更新后的版本一致。
- [ ] 人才手工录入、文件审核导入、团队机会管理及双向解释流程可演示。
- [ ] 确认、隐私、归属、版本冲突与会话规则通过实际测试。
- [ ] US-06 有成功、异常、边界、权限和缺陷复测记录。
- [ ] 实际安装、启动、数据初始化和测试命令已补入运行说明。
- [ ] 演示数据不含未经授权的真实个人信息；账号和密钥通过合适渠道提供。
- [ ] 文档明确已完成项、已知限制、mock 及手工兜底，不把计划功能标记为完成。

Jira 截图中的 10 月 15 日是 Sprint 结束日期；正式 Demo、提交渠道和课程截止时间以课程及团队通知为准，本文不另外推定。
