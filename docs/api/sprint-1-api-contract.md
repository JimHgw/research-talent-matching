# H18ABANANA — Sprint 1 前后端接口约定

版本：`0.1.0-draft`

整理日期：2026-10-03

前端语言：JavaScript；后端语言：Python

范围：当前 Sprint 1 的 **US-01～US-09，24 个 HTTP 接口**。这是用于团队评审和并行开发的接口草案，不代表后端已经实现，也不代表团队已同意所有设计选择。

本文件可单独分享：接口、字段表、请求和响应示例、权限、错误码及联调要求均包含在内。配套的 `openapi.json` 提供同一版本的机器可读结构。

## 1. 范围和协作约定

### 1.1 当前版本覆盖什么

| 用户故事 | Jira 主任务 | 本版接口支持 |
|---|---|---|
| US-01 登录与人才资料 | H18ABANANA-9 | 会话、登录、退出、资料读取与保存、统一标签 |
| US-02 研究机会管理 | H18ABANANA-10 | 创建草稿、编辑、发布、列表、详情 |
| US-03 审核与确认 | H18ABANANA-11 | 确认当前资料版本；修改后重新确认 |
| US-04 人才寻找机会 | H18ABANANA-13 | 排序后的机会推荐、逐项解释 |
| US-05 团队寻找人才 | H18ABANANA-12 | 某个机会下的人才排序、逐项解释 |
| US-06 Sprint 流程测试 | H18ABANANA-14 | 使用本文件的接口和合成样例测试；不新增公开测试接口 |
| US-07 隐私与字段可见性 | H18ABANANA-15 | 是否允许被发现、允许公开哪些资料字段 |
| US-08 逐项匹配证据 | H18ABANANA-1 | Matched / Partial / Gap / Unknown、证据、排序与分数 |
| US-09 上传与信息提取 | H18ABANANA-2 | PDF/DOCX 上传、处理状态、提取草稿、人工审核后导入 |

“全部接口”在本文件中指 **Sprint 1 的全部接口**。Backlog 中的收藏、高级筛选、语义匹配、完整注册/密码重置、复杂身份切换不纳入 v0.1。机会删除、下架、团队成员管理也未在此版本约定。

客户 2026-09-30 会议记录允许 Demo 1 在提取未完成时使用手工录入；当前 Jira 已把 US-09 放入 Sprint，因此这里保留其完整接口。提取不可用时，前端仍应允许手动填写。

### 1.2 并行开发分工

| 前端模块 | 主要调用接口 | Python 后端负责 |
|---|---|---|
| FE-1 页面框架与登录 | 01～03 | 身份认证、会话、角色检查 |
| FE-2 人才资料、审核、隐私 | 04～09、14 | 持久化、校验、版本冲突、确认和隐私规则 |
| FE-3 机会创建与管理 | 04、16～20 | 机会所有权、编辑、发布 |
| FE-4 双向匹配与解释 | 21～24 | 计算排序、状态、证据和团队端数据过滤 |
| FE-5 上传与提取审核入口 | 10～15，并衔接 05～07 | 私有文件保存、提取、导入资料 |

前端使用模拟返回值即可先做页面；真实联调时只切换 API 地址和请求适配层。**权限、确认状态、证据选择、排序分数的最终判定均由 Python 后端执行**，前端显示后端结果。模拟实现不能代替服务端权限控制。

### 1.3 本草案提出的默认选择

以下是为避免两端自行猜测而明确提出的方案，需要团队确认后共同锁定版本；不是从 Jira 中读取到的既定技术要求。

| 项目 | v0.1 草案选择 |
|---|---|
| API 风格 | REST + JSON，统一前缀 `/api/v1` |
| 登录 | 预置账号，Cookie 会话；账号角色由后端决定 |
| 团队关系 | 一个 `RESEARCH_TEAM` 账号代表一个研究团队 |
| 资料确认粒度 | 确认整份资料当前版本；内容修改后整份资料待重新确认 |
| 上传 | PDF 与 DOCX；单个文件最多 10 MiB；本版不接收旧 `.doc` |
| 原型学科范围 | STEM、BUSINESS，与最近客户会议分工一致 |
| 匹配基线 | 结构化技能/兴趣标签；不依赖 embeddings |
| 分数 | 必须项权重 2、偏好项 1；Matched=1、Partial=0.5、其他=0 |
| 已发布机会编辑 | 保存后立即影响下一次匹配；不自动变回草稿 |

## 2. 所有接口共用的规则

### 2.1 地址、数据与命名

- 本文路径均相对 `/api/v1`。例如 `GET /me/profile` 实际调用 `/api/v1/me/profile`。
- 请求和响应使用 UTF-8；普通请求为 `application/json`，上传为 `multipart/form-data`，原始文件下载为二进制。
- JSON 字段使用 `camelCase`，如 `researchInterests`。Python 内部可以使用其他命名，但对外字段必须保持一致。
- 枚举大小写固定：`TALENT`、`RESEARCH_TEAM`、`CONFIRMED` 等。
- 时间统一为 UTC RFC3339 字符串，如 `2026-10-03T00:00:00Z`；前端负责转换当地时间。
- 所有 ID 均为不透明字符串：1～64 位，允许英文字母、数字、下划线和连字符。前端不能解析 ID 推断业务含义。
- 表格标为“必填”的字段必须存在；允许 `null` 与“可省略”是两回事。空数组 `[]` 代表没有记录或显式清空。
- 对象只接受本文件列出的字段。后端拒绝未知字段、重复记录 ID、重复技能 tagId 和不匹配的标签类别，返回 422。
- 文本默认是纯文本，前端按文本显示，不能作为 HTML 插入页面。
- 成功响应直接返回业务对象，**不再包一层 `data` 或 `success`**。204 无响应体。

### 2.2 会话、权限和请求头

`h18_session` 为不透明的服务端会话 Cookie，设置 `HttpOnly; SameSite=Lax; Path=/`，不设置 Domain；HTTPS 环境加 `Secure`。本地 HTTP 开发环境可不加 Secure。浏览器不读取 Cookie 内容；响应 JSON 不包含会话 ID。

调用顺序：

1. 页面启动调用 `GET /auth/session`。未登录时仍返回 200，`user: null`，同时初始化匿名会话并返回 `csrfToken`。
2. 登录请求带 `X-CSRF-Token`；登录成功时后端轮换会话和 CSRF token。
3. 前端使用登录响应中的新 `csrfToken`。所有 POST/PUT，包括上传和退出，都带此请求头。
4. 后端校验 CSRF token 和允许的 Origin。登录角色来自账号，不接受前端传入角色改变权限。
5. 退出后后端使会话失效并过期 Cookie。前端清空账号及个人数据缓存，下次登录重新读取 session。

```http
Accept: application/json
Content-Type: application/json
X-CSRF-Token: <session 返回的 csrfToken，仅变更请求需要>
```

推荐同源访问：JavaScript 前端请求相对路径 `/api/v1`，开发代理转发至 Python 服务，例如 `http://127.0.0.1:8000`。代理保持浏览器 Origin；Python 服务显式允许该前端 Origin。Cookie 请求使用 `credentials: 'include'`。不要给 FormData 手写 Content-Type，浏览器会生成 boundary。

权限缩写：

| 标记 | 含义 |
|---|---|
| 匿名 | 无需登录，仅用于读取会话、登录 |
| 已登录 | TALENT 或 RESEARCH_TEAM |
| 人才本人 | TALENT；后端从会话定位本人资料，不能通过请求体冒充其他人 |
| 团队本人 | RESEARCH_TEAM；只能操作自己创建的机会 |

账号未登录/过期返回 401；角色错误返回 403；资源不存在或属于他人时统一返回 404。登录失败使用通用提示，不透露账号是否存在。所有个性化响应设置 `Cache-Control: no-store`。

### 2.3 分页、排序与空结果

列表参数统一为 `page`（默认 1，最小 1）和 `pageSize`（默认 20，范围 1～100）。超出范围或非整数返回 422，不静默修正。没有数据或请求页超出总页数时返回 200、`items: []`。

```json
{ "items": [], "page": 1, "pageSize": 20, "total": 0 }
```

- `total` 是当前用户有权查看的全部结果数，不是当前页数量。
- 普通机会列表按 `updatedAt` 降序、`id` 升序；文件列表按 `createdAt` 降序、`id` 升序。
- 匹配列表按 `score` 降序、`unknownWeightPercent` 升序、对象 ID 升序；无分数的项排最后。
- `rank` 是分页前的全局名次，从 1 开始；第二页不会重新从 1 排名。
- 每次请求读取当时数据，不承诺跨分页请求快照。资料、机会、隐私发生变化后，两端应重新获取列表。
- 标签表数量小，返回全部标签，不分页。

### 2.4 保存、版本冲突和重试

资料、隐私设置、机会各自有独立的 `revision`。读取后携带该值作为 `expectedRevision` 保存；导入提取结果使用 `expectedProfileRevision`。

后端在一次原子操作/数据库事务中比较版本、检查权限并写入。旧版本返回 `409 REVISION_CONFLICT`，响应包含服务器 `currentRevision`。前端保留本地输入，提示用户重新载入并比较，不能自动覆盖最新内容。

普通 PUT 的实际内容未变时不增加版本；实际修改增加 1。新资料和隐私从 revision 0 开始，机会创建成功为 revision 1。确认资料不增加内容版本。发布草稿增加机会版本。导入文件提取字段即使值相同也增加资料版本并重新要求确认。

写入请求遇到网络超时，不自动重发 POST：请求可能已在服务端成功。先重新读取资源；创建/上传可通过最新列表人工核对。v0.1 未约定 Idempotency-Key，因此不能宣称创建请求天然幂等。

## 3. 接口总表

| 编号 | 方法 | 路径（省略 /api/v1） | 用途 | 权限 |
|---|---|---|---|---|
| [01](#api-01) | GET | `/auth/session` | 读取登录状态并获取 CSRF token | 匿名 |
| [02](#api-02) | POST | `/auth/login` | 使用预置账号登录 | 匿名 |
| [03](#api-03) | POST | `/auth/logout` | 退出当前会话 | 已登录 |
| [04](#api-04) | GET | `/tags` | 读取统一技能和兴趣标签 | 已登录 |
| [05](#api-05) | GET | `/me/profile` | 读取本人资料 | 人才本人 |
| [06](#api-06) | PUT | `/me/profile` | 保存本人完整资料 | 人才本人 |
| [07](#api-07) | POST | `/me/profile/confirmation` | 确认当前资料版本 | 人才本人 |
| [08](#api-08) | GET | `/me/privacy` | 读取发现权限和字段可见性 | 人才本人 |
| [09](#api-09) | PUT | `/me/privacy` | 保存发现权限和字段可见性 | 人才本人 |
| [10](#api-10) | GET | `/me/documents` | 读取本人上传记录 | 人才本人 |
| [11](#api-11) | POST | `/me/documents` | 上传 PDF 或 DOCX 并开始提取 | 人才本人 |
| [12](#api-12) | GET | `/me/documents/{documentId}` | 查询文件处理状态 | 人才本人 |
| [13](#api-13) | GET | `/me/documents/{documentId}/extraction` | 读取待审核提取建议 | 人才本人 |
| [14](#api-14) | POST | `/me/documents/{documentId}/apply` | 保存用户审核后的提取字段 | 人才本人 |
| [15](#api-15) | GET | `/me/documents/{documentId}/file` | 下载本人的原始文件 | 人才本人 |
| [16](#api-16) | GET | `/opportunities` | 浏览已发布机会或团队自有机会 | 已登录 |
| [17](#api-17) | POST | `/opportunities` | 创建研究机会草稿 | 团队本人 |
| [18](#api-18) | GET | `/opportunities/{opportunityId}` | 读取机会详情 | 已登录 |
| [19](#api-19) | PUT | `/opportunities/{opportunityId}` | 保存研究机会修改 | 团队本人 |
| [20](#api-20) | POST | `/opportunities/{opportunityId}/publish` | 发布研究机会 | 团队本人 |
| [21](#api-21) | GET | `/me/recommendations` | 获取本人推荐机会排序 | 人才本人 |
| [22](#api-22) | GET | `/me/opportunity-matches/{opportunityId}` | 读取本人逐项匹配解释 | 人才本人 |
| [23](#api-23) | GET | `/opportunities/{opportunityId}/talent-matches` | 获取团队机会的匹配人才 | 团队本人 |
| [24](#api-24) | GET | `/opportunities/{opportunityId}/talent-matches/{talentId}` | 读取获准公开的人才资料与匹配解释 | 团队本人 |

## 4. 逐个接口详情

每个接口的请求体和响应体引用第 6 节字段表，字段表规定完整结构与必填性；下面的 JSON 是可解析的示例，不省略字段、不使用伪 JSON。示例 ID 和账号均为合成数据。各段示例用于说明结构，只有第 7 节的流程说明承诺调用顺序，不应把所有独立示例串成同一段数据库历史。

所有接口均可能返回 500；有参数校验的接口可返回 422。下面同时列出本接口声明的状态码。统一错误结构见第 5 节。


<a id="api-01"></a>

### 01. 读取登录状态并获取 CSRF token

`GET /api/v1/auth/session`

权限：**匿名**。

首次请求可初始化匿名会话。未登录不是错误，返回 user=null。csrfToken 用于下一次变更请求；真实会话 ID 只能存于 HttpOnly Cookie。


路径/查询参数：无。

请求体：无。

成功响应：**200**，[Session](#model-session)。

```json
{
  "user": null,
  "csrfToken": "mock-csrf-token-not-a-real-credential"
}
```


错误状态：`500`。

关联 Jira 子任务：H18ABANANA-16、H18ABANANA-18。

<a id="api-02"></a>

### 02. 使用预置账号登录

`POST /api/v1/auth/login`

权限：**匿名**。

先读取 session，再带其 CSRF token 登录。后端验证预置账号密码并轮换会话与 CSRF token；前端立即替换旧 token。响应角色由后端账号信息决定。失败统一返回 401 INVALID_CREDENTIALS。


| 参数 | 位置 | 必填 | 类型 / 可选值 | 约束 |
|---|---|---|---|---|
| `X-CSRF-Token` | header | 是 | string | 最短 1 |

请求体：`application/json`，[LoginRequest](#model-loginrequest)。

```json
{
  "email": "talent@example.test",
  "password": "EXAMPLE_ONLY_NOT_A_REAL_PASSWORD"
}
```


成功响应：**200**，[Session](#model-session)。

```json
{
  "user": {
    "id": "user_demo_001",
    "displayName": "Demo Talent A",
    "email": "talent@example.test",
    "role": "TALENT"
  },
  "csrfToken": "mock-csrf-after-login"
}
```


错误状态：`400`、`401`、`403`、`415`、`422`、`429`、`500`。

关联 Jira 子任务：H18ABANANA-16、H18ABANANA-18。

<a id="api-03"></a>

### 03. 退出当前会话

`POST /api/v1/auth/logout`

权限：**已登录**。

使当前服务端会话失效并过期 Cookie。前端清空资料、文件、推荐等用户缓存。返回 204，没有 JSON。


| 参数 | 位置 | 必填 | 类型 / 可选值 | 约束 |
|---|---|---|---|---|
| `X-CSRF-Token` | header | 是 | string | 最短 1 |

请求体：无。

成功响应：**204 No Content**，无响应体。

错误状态：`401`、`403`、`422`、`500`。

关联 Jira 子任务：H18ABANANA-16、H18ABANANA-18。

<a id="api-04"></a>

### 04. 读取统一技能和兴趣标签

`GET /api/v1/tags`

权限：**已登录**。

获取前后端共用的标准词表。不传 kind 时返回两类；传 SKILL 或 INTEREST 时只返回相应类型。提交资料和机会时使用 id，不用 label 作为匹配键。v0.1 没有新增/编辑标签接口。


| 参数 | 位置 | 必填 | 类型 / 可选值 | 约束 |
|---|---|---|---|---|
| `kind` | query | 否 | `SKILL` / `INTEREST` | — |

请求体：无。

成功响应：**200**，[TagList](#model-taglist)。

```json
{
  "items": [
    {
      "id": "skill_python",
      "label": "Python",
      "kind": "SKILL",
      "disciplineGroups": [
        "STEM",
        "BUSINESS"
      ]
    },
    {
      "id": "skill_sql",
      "label": "SQL",
      "kind": "SKILL",
      "disciplineGroups": [
        "STEM",
        "BUSINESS"
      ]
    },
    {
      "id": "skill_interviews",
      "label": "Research interviews",
      "kind": "SKILL",
      "disciplineGroups": [
        "STEM",
        "BUSINESS"
      ]
    },
    {
      "id": "skill_r",
      "label": "R",
      "kind": "SKILL",
      "disciplineGroups": [
        "STEM",
        "BUSINESS"
      ]
    },
    {
      "id": "interest_ml",
      "label": "Machine learning",
      "kind": "INTEREST",
      "disciplineGroups": [
        "STEM",
        "BUSINESS"
      ]
    }
  ]
}
```


错误状态：`401`、`403`、`422`、`500`。

关联 Jira 子任务：H18ABANANA-27、H18ABANANA-28。

<a id="api-05"></a>

### 05. 读取本人资料

`GET /api/v1/me/profile`

权限：**人才本人**。

人才账号初始化时即有资料对象；未填写返回 revision=0、UNCONFIRMED、空数组、displayName=""、disciplineGroup=null，不返回 404。只允许本人读取。


路径/查询参数：无。

请求体：无。

成功响应：**200**，[Profile](#model-profile)。

```json
{
  "talentId": "talent_demo_001",
  "revision": 3,
  "content": {
    "displayName": "Demo Talent A",
    "disciplineGroup": "STEM",
    "education": [
      {
        "id": "edu_001",
        "institution": "UNSW",
        "qualification": "Master of IT",
        "discipline": "Computer Science",
        "startYear": 2025,
        "endYear": null
      }
    ],
    "courses": [],
    "researchExperience": [
      {
        "id": "exp_001",
        "title": "Sample research project",
        "organisation": "Demo lab",
        "description": "Used Python to prepare a small synthetic dataset."
      }
    ],
    "skills": [
      {
        "tagId": "skill_python",
        "claim": "HAS",
        "evidenceText": "Used Python in a user-reviewed demo project."
      },
      {
        "tagId": "skill_interviews",
        "claim": "DOES_NOT_HAVE",
        "evidenceText": "I have not conducted research interviews."
      }
    ],
    "researchInterests": [
      "interest_ml"
    ],
    "researchOutputs": []
  },
  "confirmation": {
    "status": "CONFIRMED",
    "confirmedRevision": 3,
    "confirmedAt": "2026-10-03T00:00:00Z"
  },
  "origins": [
    {
      "field": "education",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "courses",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "researchExperience",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "skills",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "researchInterests",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "researchOutputs",
      "sourceType": "MANUAL",
      "documentId": null
    }
  ],
  "updatedAt": "2026-10-03T00:00:00Z"
}
```


错误状态：`401`、`403`、`422`、`500`。

关联 Jira 子任务：H18ABANANA-21、H18ABANANA-27。

<a id="api-06"></a>

### 06. 保存本人完整资料

`PUT /api/v1/me/profile`

权限：**人才本人**。

content 是完整替换对象，必须提供全部 8 个字段。前端先读取，再保留未编辑字段提交。实际内容改变后 revision+1，confirmation 变为 UNCONFIRMED，confirmedRevision 和 confirmedAt 清空；未变则保持。修改的资料章节 provenance 变为 MANUAL；未修改章节保留来源。


| 参数 | 位置 | 必填 | 类型 / 可选值 | 约束 |
|---|---|---|---|---|
| `X-CSRF-Token` | header | 是 | string | 最短 1 |

请求体：`application/json`，[ProfileWrite](#model-profilewrite)。

```json
{
  "expectedRevision": 3,
  "content": {
    "displayName": "Demo Talent A",
    "disciplineGroup": "STEM",
    "education": [
      {
        "id": "edu_001",
        "institution": "UNSW",
        "qualification": "Master of IT",
        "discipline": "Computer Science",
        "startYear": 2025,
        "endYear": null
      }
    ],
    "courses": [],
    "researchExperience": [
      {
        "id": "exp_001",
        "title": "Sample research project",
        "organisation": "Demo lab",
        "description": "Used Python to prepare a small synthetic dataset."
      }
    ],
    "skills": [
      {
        "tagId": "skill_python",
        "claim": "HAS",
        "evidenceText": "Reviewed and corrected Python evidence."
      },
      {
        "tagId": "skill_interviews",
        "claim": "DOES_NOT_HAVE",
        "evidenceText": "I have not conducted research interviews."
      }
    ],
    "researchInterests": [
      "interest_ml"
    ],
    "researchOutputs": []
  }
}
```


成功响应：**200**，[Profile](#model-profile)。

```json
{
  "talentId": "talent_demo_001",
  "revision": 4,
  "content": {
    "displayName": "Demo Talent A",
    "disciplineGroup": "STEM",
    "education": [
      {
        "id": "edu_001",
        "institution": "UNSW",
        "qualification": "Master of IT",
        "discipline": "Computer Science",
        "startYear": 2025,
        "endYear": null
      }
    ],
    "courses": [],
    "researchExperience": [
      {
        "id": "exp_001",
        "title": "Sample research project",
        "organisation": "Demo lab",
        "description": "Used Python to prepare a small synthetic dataset."
      }
    ],
    "skills": [
      {
        "tagId": "skill_python",
        "claim": "HAS",
        "evidenceText": "Reviewed and corrected Python evidence."
      },
      {
        "tagId": "skill_interviews",
        "claim": "DOES_NOT_HAVE",
        "evidenceText": "I have not conducted research interviews."
      }
    ],
    "researchInterests": [
      "interest_ml"
    ],
    "researchOutputs": []
  },
  "confirmation": {
    "status": "UNCONFIRMED",
    "confirmedRevision": null,
    "confirmedAt": null
  },
  "origins": [
    {
      "field": "education",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "courses",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "researchExperience",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "skills",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "researchInterests",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "researchOutputs",
      "sourceType": "MANUAL",
      "documentId": null
    }
  ],
  "updatedAt": "2026-10-03T00:00:00Z"
}
```


错误状态：`400`、`401`、`403`、`409`、`415`、`422`、`500`。

关联 Jira 子任务：H18ABANANA-21、H18ABANANA-27、H18ABANANA-29。

<a id="api-07"></a>

### 07. 确认当前资料版本

`POST /api/v1/me/profile/confirmation`

权限：**人才本人**。

确认 expectedRevision 指定的当前整份资料。至少有非空姓名和一个非空学术/研究章节，否则 422。成功令 confirmedRevision=revision，不增加 revision；重复确认同一版本保持原结果和确认时间。确认表示用户审核，不代表第三方验证学历或资质。


| 参数 | 位置 | 必填 | 类型 / 可选值 | 约束 |
|---|---|---|---|---|
| `X-CSRF-Token` | header | 是 | string | 最短 1 |

请求体：`application/json`，[RevisionRequest](#model-revisionrequest)。

```json
{
  "expectedRevision": 4
}
```


成功响应：**200**，[Profile](#model-profile)。

```json
{
  "talentId": "talent_demo_001",
  "revision": 4,
  "content": {
    "displayName": "Demo Talent A",
    "disciplineGroup": "STEM",
    "education": [
      {
        "id": "edu_001",
        "institution": "UNSW",
        "qualification": "Master of IT",
        "discipline": "Computer Science",
        "startYear": 2025,
        "endYear": null
      }
    ],
    "courses": [],
    "researchExperience": [
      {
        "id": "exp_001",
        "title": "Sample research project",
        "organisation": "Demo lab",
        "description": "Used Python to prepare a small synthetic dataset."
      }
    ],
    "skills": [
      {
        "tagId": "skill_python",
        "claim": "HAS",
        "evidenceText": "Reviewed and corrected Python evidence."
      },
      {
        "tagId": "skill_interviews",
        "claim": "DOES_NOT_HAVE",
        "evidenceText": "I have not conducted research interviews."
      }
    ],
    "researchInterests": [
      "interest_ml"
    ],
    "researchOutputs": []
  },
  "confirmation": {
    "status": "CONFIRMED",
    "confirmedRevision": 4,
    "confirmedAt": "2026-10-03T00:01:00Z"
  },
  "origins": [
    {
      "field": "education",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "courses",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "researchExperience",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "skills",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "researchInterests",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "researchOutputs",
      "sourceType": "MANUAL",
      "documentId": null
    }
  ],
  "updatedAt": "2026-10-03T00:01:00Z"
}
```


错误状态：`400`、`401`、`403`、`409`、`415`、`422`、`500`。

关联 Jira 子任务：H18ABANANA-21、H18ABANANA-29。

<a id="api-08"></a>

### 08. 读取发现权限和字段可见性

`GET /api/v1/me/privacy`

权限：**人才本人**。

新账号默认 discoverable=false、visibleFields=[]、revision=0。隐私设置只返回给本人。隐私版本与资料版本独立。


路径/查询参数：无。

请求体：无。

成功响应：**200**，[Privacy](#model-privacy)。

```json
{
  "revision": 0,
  "discoverable": false,
  "visibleFields": [],
  "updatedAt": "2026-10-03T00:00:00Z"
}
```


错误状态：`401`、`403`、`422`、`500`。

关联 Jira 子任务：H18ABANANA-21、H18ABANANA-30。

<a id="api-09"></a>

### 09. 保存发现权限和字段可见性

`PUT /api/v1/me/privacy`

权限：**人才本人**。

完整保存 discoverable 与 visibleFields。实际改变时隐私 revision+1，内容无变化时不递增。不影响资料确认。关闭被发现后，下一次团队列表/详情立即排除该人才；后端使旧匹配缓存失效。任何隐藏字段不得参与团队可见评分或解释。


| 参数 | 位置 | 必填 | 类型 / 可选值 | 约束 |
|---|---|---|---|---|
| `X-CSRF-Token` | header | 是 | string | 最短 1 |

请求体：`application/json`，[PrivacyWrite](#model-privacywrite)。

```json
{
  "expectedRevision": 0,
  "discoverable": true,
  "visibleFields": [
    "displayName"
  ]
}
```


成功响应：**200**，[Privacy](#model-privacy)。

```json
{
  "revision": 1,
  "discoverable": true,
  "visibleFields": [
    "displayName"
  ],
  "updatedAt": "2026-10-03T00:00:00Z"
}
```


错误状态：`400`、`401`、`403`、`409`、`415`、`422`、`500`。

关联 Jira 子任务：H18ABANANA-21、H18ABANANA-30。

<a id="api-10"></a>

### 10. 读取本人上传记录

`GET /api/v1/me/documents`

权限：**人才本人**。

只返回当前人才本人上传记录，按 createdAt 降序、id 升序。返回文件元数据，不返回公开下载地址。


| 参数 | 位置 | 必填 | 类型 / 可选值 | 约束 |
|---|---|---|---|---|
| `page` | query | 否 | integer | 最小 1；默认 1 |
| `pageSize` | query | 否 | integer | 最小 1；最大 100；默认 20 |

请求体：无。

成功响应：**200**，[DocumentPage](#model-documentpage)。

```json
{
  "items": [
    {
      "id": "doc_demo_001",
      "kind": "CV",
      "fileName": "synthetic-cv.pdf",
      "mediaType": "application/pdf",
      "sizeBytes": 2048,
      "status": "READY",
      "createdAt": "2026-10-03T00:00:00Z",
      "updatedAt": "2026-10-03T00:00:00Z",
      "error": null
    }
  ],
  "page": 1,
  "pageSize": 20,
  "total": 1
}
```


错误状态：`401`、`403`、`422`、`500`。

关联 Jira 子任务：H18ABANANA-22、H18ABANANA-23。

<a id="api-11"></a>

### 11. 上传 PDF 或 DOCX 并开始提取

`POST /api/v1/me/documents`

权限：**人才本人**。

使用 multipart/form-data 上传单文件。file 与 kind 均必填；kind 为 CV 或 TRANSCRIPT。草案限 10 MiB（10,485,760 字节），只收 PDF/DOCX，不收旧 .doc。后端检查实际内容、格式和大小，不只看扩展名。接收成功立即返回 202 和 QUEUED 文档对象，之后异步处理。上传与提取不会自动覆盖、确认或公开资料。


| 参数 | 位置 | 必填 | 类型 / 可选值 | 约束 |
|---|---|---|---|---|
| `X-CSRF-Token` | header | 是 | string | 最短 1 |

请求体：`multipart/form-data`。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| file | binary | 是 | 单个 PDF/DOCX 文件，非空，最多 10 MiB |
| kind | string | 是 | CV / TRANSCRIPT |

```javascript
const form = new FormData();
form.append("file", selectedFile);
form.append("kind", "CV");
await fetch("/api/v1/me/documents", {
  method: "POST",
  credentials: "include",
  headers: { "X-CSRF-Token": csrfToken },
  body: form
});
```


成功响应：**202**，[Document](#model-document)。

```json
{
  "id": "doc_demo_001",
  "kind": "CV",
  "fileName": "synthetic-cv.pdf",
  "mediaType": "application/pdf",
  "sizeBytes": 2048,
  "status": "QUEUED",
  "createdAt": "2026-10-03T00:00:00Z",
  "updatedAt": "2026-10-03T00:00:00Z",
  "error": null
}
```


错误状态：`400`、`401`、`403`、`413`、`415`、`422`、`429`、`500`。

关联 Jira 子任务：H18ABANANA-22、H18ABANANA-23、H18ABANANA-24。

<a id="api-12"></a>

### 12. 查询文件处理状态

`GET /api/v1/me/documents/{documentId}`

权限：**人才本人**。

状态流为 QUEUED → PROCESSING → READY 或 FAILED。视图打开时前端每 2 秒轮询，终态停止；等待 60 秒后暂停自动轮询并显示手动刷新，不能把前端等待超时当作后端 FAILED。FAILED 的 error 给出可展示错误，其他状态 error=null。


| 参数 | 位置 | 必填 | 类型 / 可选值 | 约束 |
|---|---|---|---|---|
| `documentId` | path | 是 | string | 正则 `^[A-Za-z0-9_-]{1,64}$` |

请求体：无。

成功响应：**200**，[Document](#model-document)。

```json
{
  "id": "doc_demo_001",
  "kind": "CV",
  "fileName": "synthetic-cv.pdf",
  "mediaType": "application/pdf",
  "sizeBytes": 2048,
  "status": "PROCESSING",
  "createdAt": "2026-10-03T00:00:00Z",
  "updatedAt": "2026-10-03T00:00:00Z",
  "error": null
}
```


错误状态：`401`、`403`、`404`、`422`、`500`。

关联 Jira 子任务：H18ABANANA-22、H18ABANANA-23、H18ABANANA-24。

<a id="api-13"></a>

### 13. 读取待审核提取建议

`GET /api/v1/me/documents/{documentId}/extraction`

权限：**人才本人**。

只允许本人读取。READY 返回 200；QUEUED/PROCESSING 返回 409 EXTRACTION_NOT_READY；FAILED 返回 422 EXTRACTION_FAILED。suggestedSections 是待审核建议，不改变资料。无法可靠识别的项放 uncertainFields，不凭空补正向技能。


| 参数 | 位置 | 必填 | 类型 / 可选值 | 约束 |
|---|---|---|---|---|
| `documentId` | path | 是 | string | 正则 `^[A-Za-z0-9_-]{1,64}$` |

请求体：无。

成功响应：**200**，[Extraction](#model-extraction)。

```json
{
  "documentId": "doc_demo_001",
  "status": "READY",
  "suggestedSections": {
    "education": [
      {
        "id": "edu_001",
        "institution": "UNSW",
        "qualification": "Master of IT",
        "discipline": "Computer Science",
        "startYear": 2025,
        "endYear": null
      }
    ],
    "skills": [
      {
        "tagId": "skill_python",
        "claim": "HAS",
        "evidenceText": "Used Python in a user-reviewed demo project."
      }
    ]
  },
  "uncertainFields": [
    {
      "field": "researchOutputs",
      "status": "NOT_RECOGNISED",
      "reason": "No reliable output information was found."
    }
  ],
  "warnings": [
    "Review suggestions before saving."
  ],
  "reviewRequired": true
}
```


错误状态：`401`、`403`、`404`、`409`、`422`、`500`。

关联 Jira 子任务：H18ABANANA-22、H18ABANANA-24。

<a id="api-14"></a>

### 14. 保存用户审核后的提取字段

`POST /api/v1/me/documents/{documentId}/apply`

权限：**人才本人**。

只接受属于本人的 READY 文档。校验 expectedProfileRevision；未就绪返回 409，提取失败返回 422。sections 至少含一个章节；仅替换传入章节，未传章节保留，显式 [] 清空该章节。字段值是用户审核/纠正后的值，并非必须原样复制提取建议。后端原子保存、revision+1、整份资料 UNCONFIRMED，并标记这些章节 USER_REVIEWED_DOCUMENT 来源。之后必须另调确认接口。


| 参数 | 位置 | 必填 | 类型 / 可选值 | 约束 |
|---|---|---|---|---|
| `documentId` | path | 是 | string | 正则 `^[A-Za-z0-9_-]{1,64}$` |
| `X-CSRF-Token` | header | 是 | string | 最短 1 |

请求体：`application/json`，[ApplyExtractionRequest](#model-applyextractionrequest)。

```json
{
  "expectedProfileRevision": 3,
  "sections": {
    "skills": [
      {
        "tagId": "skill_python",
        "claim": "HAS",
        "evidenceText": "Used Python in a user-reviewed demo project."
      }
    ]
  }
}
```


成功响应：**200**，[Profile](#model-profile)。

```json
{
  "talentId": "talent_demo_001",
  "revision": 4,
  "content": {
    "displayName": "Demo Talent A",
    "disciplineGroup": "STEM",
    "education": [
      {
        "id": "edu_001",
        "institution": "UNSW",
        "qualification": "Master of IT",
        "discipline": "Computer Science",
        "startYear": 2025,
        "endYear": null
      }
    ],
    "courses": [],
    "researchExperience": [
      {
        "id": "exp_001",
        "title": "Sample research project",
        "organisation": "Demo lab",
        "description": "Used Python to prepare a small synthetic dataset."
      }
    ],
    "skills": [
      {
        "tagId": "skill_python",
        "claim": "HAS",
        "evidenceText": "Used Python in a user-reviewed demo project."
      }
    ],
    "researchInterests": [
      "interest_ml"
    ],
    "researchOutputs": []
  },
  "confirmation": {
    "status": "UNCONFIRMED",
    "confirmedRevision": null,
    "confirmedAt": null
  },
  "origins": [
    {
      "field": "education",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "courses",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "researchExperience",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "skills",
      "sourceType": "USER_REVIEWED_DOCUMENT",
      "documentId": "doc_demo_001"
    },
    {
      "field": "researchInterests",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "researchOutputs",
      "sourceType": "MANUAL",
      "documentId": null
    }
  ],
  "updatedAt": "2026-10-03T00:03:00Z"
}
```


错误状态：`400`、`401`、`403`、`404`、`409`、`415`、`422`、`500`。

关联 Jira 子任务：H18ABANANA-21、H18ABANANA-22、H18ABANANA-24、H18ABANANA-29。

<a id="api-15"></a>

### 15. 下载本人的原始文件

`GET /api/v1/me/documents/{documentId}/file`

权限：**人才本人**。

每次检查文件所有权；团队账号即使能发现此人才也不能下载原件。通过已认证接口下载，不提供公开链接。响应流的 Content-Type 对应实际 PDF/DOCX；Content-Disposition 使用 attachment 与安全编码的文件名；设置 X-Content-Type-Options: nosniff。


| 参数 | 位置 | 必填 | 类型 / 可选值 | 约束 |
|---|---|---|---|---|
| `documentId` | path | 是 | string | 正则 `^[A-Za-z0-9_-]{1,64}$` |

请求体：无。

成功响应：**200**，文件二进制流。

```http
Content-Type: application/pdf
Content-Disposition: attachment; filename="synthetic-cv.pdf"
Cache-Control: no-store
X-Content-Type-Options: nosniff

<PDF binary bytes>
```


错误状态：`401`、`403`、`404`、`422`、`500`。

关联 Jira 子任务：H18ABANANA-23。

<a id="api-16"></a>

### 16. 浏览已发布机会或团队自有机会

`GET /api/v1/opportunities`

权限：**已登录**。

默认 scope=published，只返回已发布机会；scope=mine 仅限团队账号，返回本人草稿和已发布机会。人才使用 mine 返回 403。v0.1 的 PUBLISHED 视为活跃机会。此接口不做个性化排序；人才推荐使用接口 21。


| 参数 | 位置 | 必填 | 类型 / 可选值 | 约束 |
|---|---|---|---|---|
| `scope` | query | 否 | `published` / `mine` | — |
| `page` | query | 否 | integer | 最小 1；默认 1 |
| `pageSize` | query | 否 | integer | 最小 1；最大 100；默认 20 |

请求体：无。

成功响应：**200**，[OpportunityPage](#model-opportunitypage)。

```json
{
  "items": [
    {
      "id": "opp_demo_001",
      "revision": 2,
      "status": "PUBLISHED",
      "content": {
        "title": "Research assistant in data analysis",
        "university": "UNSW",
        "disciplineGroup": "STEM",
        "discipline": "Computer Science",
        "researchArea": "Research data analysis",
        "description": "Synthetic opportunity for the prototype demonstration.",
        "requirements": [
          {
            "id": "req_python",
            "label": "Python experience",
            "kind": "SKILL",
            "importance": "REQUIRED",
            "tagIds": [
              "skill_python"
            ]
          },
          {
            "id": "req_analysis",
            "label": "Python and SQL",
            "kind": "SKILL",
            "importance": "REQUIRED",
            "tagIds": [
              "skill_python",
              "skill_sql"
            ]
          },
          {
            "id": "req_interviews",
            "label": "Research interview experience",
            "kind": "SKILL",
            "importance": "PREFERRED",
            "tagIds": [
              "skill_interviews"
            ]
          },
          {
            "id": "req_r",
            "label": "R experience",
            "kind": "SKILL",
            "importance": "PREFERRED",
            "tagIds": [
              "skill_r"
            ]
          }
        ]
      },
      "createdAt": "2026-10-03T00:00:00Z",
      "updatedAt": "2026-10-03T00:00:00Z"
    }
  ],
  "page": 1,
  "pageSize": 20,
  "total": 1
}
```


错误状态：`401`、`403`、`422`、`500`。

关联 Jira 子任务：H18ABANANA-19、H18ABANANA-28。

<a id="api-17"></a>

### 17. 创建研究机会草稿

`POST /api/v1/opportunities`

权限：**团队本人**。

仅团队账号可创建。后端生成机会 id、所有者、revision=1、status=DRAFT；请求不能自行指定所有者或状态。基础字段必填，草稿允许 requirements=[]。


| 参数 | 位置 | 必填 | 类型 / 可选值 | 约束 |
|---|---|---|---|---|
| `X-CSRF-Token` | header | 是 | string | 最短 1 |

请求体：`application/json`，[OpportunityContent](#model-opportunitycontent)。

```json
{
  "title": "Research assistant in data analysis",
  "university": "UNSW",
  "disciplineGroup": "STEM",
  "discipline": "Computer Science",
  "researchArea": "Research data analysis",
  "description": "Synthetic opportunity for the prototype demonstration.",
  "requirements": [
    {
      "id": "req_python",
      "label": "Python experience",
      "kind": "SKILL",
      "importance": "REQUIRED",
      "tagIds": [
        "skill_python"
      ]
    },
    {
      "id": "req_analysis",
      "label": "Python and SQL",
      "kind": "SKILL",
      "importance": "REQUIRED",
      "tagIds": [
        "skill_python",
        "skill_sql"
      ]
    },
    {
      "id": "req_interviews",
      "label": "Research interview experience",
      "kind": "SKILL",
      "importance": "PREFERRED",
      "tagIds": [
        "skill_interviews"
      ]
    },
    {
      "id": "req_r",
      "label": "R experience",
      "kind": "SKILL",
      "importance": "PREFERRED",
      "tagIds": [
        "skill_r"
      ]
    }
  ]
}
```


成功响应：**201**，[Opportunity](#model-opportunity)。

```json
{
  "id": "opp_demo_001",
  "revision": 1,
  "status": "DRAFT",
  "content": {
    "title": "Research assistant in data analysis",
    "university": "UNSW",
    "disciplineGroup": "STEM",
    "discipline": "Computer Science",
    "researchArea": "Research data analysis",
    "description": "Synthetic opportunity for the prototype demonstration.",
    "requirements": [
      {
        "id": "req_python",
        "label": "Python experience",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python"
        ]
      },
      {
        "id": "req_analysis",
        "label": "Python and SQL",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python",
          "skill_sql"
        ]
      },
      {
        "id": "req_interviews",
        "label": "Research interview experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_interviews"
        ]
      },
      {
        "id": "req_r",
        "label": "R experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_r"
        ]
      }
    ]
  },
  "createdAt": "2026-10-03T00:00:00Z",
  "updatedAt": "2026-10-03T00:00:00Z"
}
```


错误状态：`400`、`401`、`403`、`415`、`422`、`500`。

关联 Jira 子任务：H18ABANANA-19、H18ABANANA-28。

<a id="api-18"></a>

### 18. 读取机会详情

`GET /api/v1/opportunities/{opportunityId}`

权限：**已登录**。

已发布机会对登录用户可见；草稿仅其所有者可读取。其他人读取草稿返回 404。响应不包含内部团队账号或数据库对象。


| 参数 | 位置 | 必填 | 类型 / 可选值 | 约束 |
|---|---|---|---|---|
| `opportunityId` | path | 是 | string | 正则 `^[A-Za-z0-9_-]{1,64}$` |

请求体：无。

成功响应：**200**，[Opportunity](#model-opportunity)。

```json
{
  "id": "opp_demo_001",
  "revision": 2,
  "status": "PUBLISHED",
  "content": {
    "title": "Research assistant in data analysis",
    "university": "UNSW",
    "disciplineGroup": "STEM",
    "discipline": "Computer Science",
    "researchArea": "Research data analysis",
    "description": "Synthetic opportunity for the prototype demonstration.",
    "requirements": [
      {
        "id": "req_python",
        "label": "Python experience",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python"
        ]
      },
      {
        "id": "req_analysis",
        "label": "Python and SQL",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python",
          "skill_sql"
        ]
      },
      {
        "id": "req_interviews",
        "label": "Research interview experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_interviews"
        ]
      },
      {
        "id": "req_r",
        "label": "R experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_r"
        ]
      }
    ]
  },
  "createdAt": "2026-10-03T00:00:00Z",
  "updatedAt": "2026-10-03T00:00:00Z"
}
```


错误状态：`401`、`403`、`404`、`422`、`500`。

关联 Jira 子任务：H18ABANANA-19、H18ABANANA-28。

<a id="api-19"></a>

### 19. 保存研究机会修改

`PUT /api/v1/opportunities/{opportunityId}`

权限：**团队本人**。

仅所有者可编辑；以 expectedRevision 防止覆盖，并完整替换 content。内容变化 revision+1，不变则保留。保持当前发布状态；已发布机会编辑后下次匹配使用新版本，至少保留一个有效 requirement，否则 422。


| 参数 | 位置 | 必填 | 类型 / 可选值 | 约束 |
|---|---|---|---|---|
| `opportunityId` | path | 是 | string | 正则 `^[A-Za-z0-9_-]{1,64}$` |
| `X-CSRF-Token` | header | 是 | string | 最短 1 |

请求体：`application/json`，[OpportunityWrite](#model-opportunitywrite)。

```json
{
  "expectedRevision": 2,
  "content": {
    "title": "Research assistant in research data systems",
    "university": "UNSW",
    "disciplineGroup": "STEM",
    "discipline": "Computer Science",
    "researchArea": "Research data analysis",
    "description": "Synthetic opportunity for the prototype demonstration.",
    "requirements": [
      {
        "id": "req_python",
        "label": "Python experience",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python"
        ]
      },
      {
        "id": "req_analysis",
        "label": "Python and SQL",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python",
          "skill_sql"
        ]
      },
      {
        "id": "req_interviews",
        "label": "Research interview experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_interviews"
        ]
      },
      {
        "id": "req_r",
        "label": "R experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_r"
        ]
      }
    ]
  }
}
```


成功响应：**200**，[Opportunity](#model-opportunity)。

```json
{
  "id": "opp_demo_001",
  "revision": 3,
  "status": "PUBLISHED",
  "content": {
    "title": "Research assistant in research data systems",
    "university": "UNSW",
    "disciplineGroup": "STEM",
    "discipline": "Computer Science",
    "researchArea": "Research data analysis",
    "description": "Synthetic opportunity for the prototype demonstration.",
    "requirements": [
      {
        "id": "req_python",
        "label": "Python experience",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python"
        ]
      },
      {
        "id": "req_analysis",
        "label": "Python and SQL",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python",
          "skill_sql"
        ]
      },
      {
        "id": "req_interviews",
        "label": "Research interview experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_interviews"
        ]
      },
      {
        "id": "req_r",
        "label": "R experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_r"
        ]
      }
    ]
  },
  "createdAt": "2026-10-03T00:00:00Z",
  "updatedAt": "2026-10-03T00:02:00Z"
}
```


错误状态：`400`、`401`、`403`、`404`、`409`、`415`、`422`、`500`。

关联 Jira 子任务：H18ABANANA-19、H18ABANANA-28。

<a id="api-20"></a>

### 20. 发布研究机会

`POST /api/v1/opportunities/{opportunityId}/publish`

权限：**团队本人**。

仅所有者可发布，检查当前版本、基础字段和至少一个有效 requirement；标签必须存在且类型正确。DRAFT → PUBLISHED 增加 revision。已经发布且 expectedRevision 为当前版本时，重复调用不再递增；旧版本仍返回 409。


| 参数 | 位置 | 必填 | 类型 / 可选值 | 约束 |
|---|---|---|---|---|
| `opportunityId` | path | 是 | string | 正则 `^[A-Za-z0-9_-]{1,64}$` |
| `X-CSRF-Token` | header | 是 | string | 最短 1 |

请求体：`application/json`，[RevisionRequest](#model-revisionrequest)。

```json
{
  "expectedRevision": 1
}
```


成功响应：**200**，[Opportunity](#model-opportunity)。

```json
{
  "id": "opp_demo_001",
  "revision": 2,
  "status": "PUBLISHED",
  "content": {
    "title": "Research assistant in data analysis",
    "university": "UNSW",
    "disciplineGroup": "STEM",
    "discipline": "Computer Science",
    "researchArea": "Research data analysis",
    "description": "Synthetic opportunity for the prototype demonstration.",
    "requirements": [
      {
        "id": "req_python",
        "label": "Python experience",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python"
        ]
      },
      {
        "id": "req_analysis",
        "label": "Python and SQL",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python",
          "skill_sql"
        ]
      },
      {
        "id": "req_interviews",
        "label": "Research interview experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_interviews"
        ]
      },
      {
        "id": "req_r",
        "label": "R experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_r"
        ]
      }
    ]
  },
  "createdAt": "2026-10-03T00:00:00Z",
  "updatedAt": "2026-10-03T00:00:00Z"
}
```


错误状态：`400`、`401`、`403`、`404`、`409`、`415`、`422`、`500`。

关联 Jira 子任务：H18ABANANA-19、H18ABANANA-28。

<a id="api-21"></a>

### 21. 获取本人推荐机会排序

`GET /api/v1/me/recommendations`

权限：**人才本人**。

仅人才本人。当前资料未确认或 confirmedRevision 不等于 revision，返回 409 PROFILE_UNCONFIRMED；否则基于本人已确认资料计算全部已发布机会。本人私有字段可用于本人的推荐。按全局匹配规则排序并分页；没有机会返回 200 空列表。


| 参数 | 位置 | 必填 | 类型 / 可选值 | 约束 |
|---|---|---|---|---|
| `page` | query | 否 | integer | 最小 1；默认 1 |
| `pageSize` | query | 否 | integer | 最小 1；最大 100；默认 20 |

请求体：无。

成功响应：**200**，[RecommendationPage](#model-recommendationpage)。

```json
{
  "items": [
    {
      "rank": 1,
      "opportunity": {
        "id": "opp_demo_001",
        "revision": 2,
        "status": "PUBLISHED",
        "content": {
          "title": "Research assistant in data analysis",
          "university": "UNSW",
          "disciplineGroup": "STEM",
          "discipline": "Computer Science",
          "researchArea": "Research data analysis",
          "description": "Synthetic opportunity for the prototype demonstration.",
          "requirements": [
            {
              "id": "req_python",
              "label": "Python experience",
              "kind": "SKILL",
              "importance": "REQUIRED",
              "tagIds": [
                "skill_python"
              ]
            },
            {
              "id": "req_analysis",
              "label": "Python and SQL",
              "kind": "SKILL",
              "importance": "REQUIRED",
              "tagIds": [
                "skill_python",
                "skill_sql"
              ]
            },
            {
              "id": "req_interviews",
              "label": "Research interview experience",
              "kind": "SKILL",
              "importance": "PREFERRED",
              "tagIds": [
                "skill_interviews"
              ]
            },
            {
              "id": "req_r",
              "label": "R experience",
              "kind": "SKILL",
              "importance": "PREFERRED",
              "tagIds": [
                "skill_r"
              ]
            }
          ]
        },
        "createdAt": "2026-10-03T00:00:00Z",
        "updatedAt": "2026-10-03T00:00:00Z"
      },
      "summary": {
        "score": 50,
        "unknownWeightPercent": 16.67,
        "requiredGapCount": 0,
        "evaluationStatus": "EVALUATED",
        "algorithmVersion": "tag-coverage-v1"
      }
    }
  ],
  "page": 1,
  "pageSize": 20,
  "total": 1
}
```


错误状态：`401`、`403`、`409`、`422`、`500`。

关联 Jira 子任务：H18ABANANA-20、H18ABANANA-31、H18ABANANA-32。

<a id="api-22"></a>

### 22. 读取本人逐项匹配解释

`GET /api/v1/me/opportunity-matches/{opportunityId}`

权限：**人才本人**。

仅人才本人，目标机会必须已发布，否则 404。当前资料必须已确认，否则 409。逐项返回 requirement、status、reasonCode、reason 和 evidence；使用当前机会/资料版本，不能返回旧版本分数。本人的 evidence 可含本人文件来源引用，但不能捏造证据。


| 参数 | 位置 | 必填 | 类型 / 可选值 | 约束 |
|---|---|---|---|---|
| `opportunityId` | path | 是 | string | 正则 `^[A-Za-z0-9_-]{1,64}$` |

请求体：无。

成功响应：**200**，[OwnerMatch](#model-ownermatch)。

```json
{
  "opportunity": {
    "id": "opp_demo_001",
    "revision": 2,
    "status": "PUBLISHED",
    "content": {
      "title": "Research assistant in data analysis",
      "university": "UNSW",
      "disciplineGroup": "STEM",
      "discipline": "Computer Science",
      "researchArea": "Research data analysis",
      "description": "Synthetic opportunity for the prototype demonstration.",
      "requirements": [
        {
          "id": "req_python",
          "label": "Python experience",
          "kind": "SKILL",
          "importance": "REQUIRED",
          "tagIds": [
            "skill_python"
          ]
        },
        {
          "id": "req_analysis",
          "label": "Python and SQL",
          "kind": "SKILL",
          "importance": "REQUIRED",
          "tagIds": [
            "skill_python",
            "skill_sql"
          ]
        },
        {
          "id": "req_interviews",
          "label": "Research interview experience",
          "kind": "SKILL",
          "importance": "PREFERRED",
          "tagIds": [
            "skill_interviews"
          ]
        },
        {
          "id": "req_r",
          "label": "R experience",
          "kind": "SKILL",
          "importance": "PREFERRED",
          "tagIds": [
            "skill_r"
          ]
        }
      ]
    },
    "createdAt": "2026-10-03T00:00:00Z",
    "updatedAt": "2026-10-03T00:00:00Z"
  },
  "profileRevision": 3,
  "summary": {
    "score": 50,
    "unknownWeightPercent": 16.67,
    "requiredGapCount": 0,
    "evaluationStatus": "EVALUATED",
    "algorithmVersion": "tag-coverage-v1"
  },
  "requirements": [
    {
      "requirement": {
        "id": "req_python",
        "label": "Python experience",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python"
        ]
      },
      "status": "MATCHED",
      "reasonCode": "ALL_TAGS_SUPPORTED",
      "reason": "Confirmed Python claim supports this requirement.",
      "evidence": [
        {
          "field": "skills",
          "recordId": "skill_python",
          "valueSummary": "Has Python experience.",
          "confirmedRevision": 3,
          "sourceType": "MANUAL",
          "documentId": null
        }
      ]
    },
    {
      "requirement": {
        "id": "req_analysis",
        "label": "Python and SQL",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python",
          "skill_sql"
        ]
      },
      "status": "PARTIAL",
      "reasonCode": "SOME_TAGS_SUPPORTED",
      "reason": "Python is supported; there is insufficient evidence for SQL.",
      "evidence": [
        {
          "field": "skills",
          "recordId": "skill_python",
          "valueSummary": "Has Python experience.",
          "confirmedRevision": 3,
          "sourceType": "MANUAL",
          "documentId": null
        }
      ]
    },
    {
      "requirement": {
        "id": "req_interviews",
        "label": "Research interview experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_interviews"
        ]
      },
      "status": "GAP",
      "reasonCode": "EXPLICIT_NEGATIVE_CLAIM",
      "reason": "The user explicitly confirmed no research interview experience.",
      "evidence": [
        {
          "field": "skills",
          "recordId": "skill_interviews",
          "valueSummary": "Explicitly reports no research interview experience.",
          "confirmedRevision": 3,
          "sourceType": "MANUAL",
          "documentId": null
        }
      ]
    },
    {
      "requirement": {
        "id": "req_r",
        "label": "R experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_r"
        ]
      },
      "status": "UNKNOWN",
      "reasonCode": "INSUFFICIENT_EVIDENCE",
      "reason": "There is insufficient confirmed evidence for this requirement.",
      "evidence": []
    }
  ],
  "evaluatedAt": "2026-10-03T00:00:00Z"
}
```


错误状态：`401`、`403`、`404`、`409`、`422`、`500`。

关联 Jira 子任务：H18ABANANA-20、H18ABANANA-31、H18ABANANA-32。

<a id="api-23"></a>

### 23. 获取团队机会的匹配人才

`GET /api/v1/opportunities/{opportunityId}/talent-matches`

权限：**团队本人**。

仅已发布机会的所有者。不存在、非本人或未发布机会返回 404。先排除未同意被发现和当前未确认的人才，再用各自允许公开的字段计算、排序、分页与 total。隐藏字段当作证据不足处理。允许 visibleFields=[]，此时仍可出现匿名对象，但匹配为 UNKNOWN。


| 参数 | 位置 | 必填 | 类型 / 可选值 | 约束 |
|---|---|---|---|---|
| `opportunityId` | path | 是 | string | 正则 `^[A-Za-z0-9_-]{1,64}$` |
| `page` | query | 否 | integer | 最小 1；默认 1 |
| `pageSize` | query | 否 | integer | 最小 1；最大 100；默认 20 |

请求体：无。

成功响应：**200**，[TalentMatchPage](#model-talentmatchpage)。

```json
{
  "items": [
    {
      "rank": 1,
      "talent": {
        "talentId": "talent_demo_001",
        "fields": {
          "displayName": "Demo Talent A"
        }
      },
      "summary": {
        "score": 0,
        "unknownWeightPercent": 100,
        "requiredGapCount": 0,
        "evaluationStatus": "EVALUATED",
        "algorithmVersion": "tag-coverage-v1"
      }
    }
  ],
  "page": 1,
  "pageSize": 20,
  "total": 1
}
```


错误状态：`401`、`403`、`404`、`422`、`500`。

关联 Jira 子任务：H18ABANANA-20、H18ABANANA-30、H18ABANANA-31、H18ABANANA-33。

<a id="api-24"></a>

### 24. 读取获准公开的人才资料与匹配解释

`GET /api/v1/opportunities/{opportunityId}/talent-matches/{talentId}`

权限：**团队本人**。

每次重新检查机会所有权及发布状态、人才被发现授权、当前确认状态、字段可见性。人才关闭授权或变为待确认后返回 404，即使此前列表中出现过。只返回公开字段与 TeamEvidence；不返回邮箱、文件 ID、原始文件名、下载链接、隐藏字段值或来源元数据。


| 参数 | 位置 | 必填 | 类型 / 可选值 | 约束 |
|---|---|---|---|---|
| `opportunityId` | path | 是 | string | 正则 `^[A-Za-z0-9_-]{1,64}$` |
| `talentId` | path | 是 | string | 正则 `^[A-Za-z0-9_-]{1,64}$` |

请求体：无。

成功响应：**200**，[TeamMatch](#model-teammatch)。

```json
{
  "opportunityId": "opp_demo_001",
  "opportunityRevision": 2,
  "talent": {
    "talentId": "talent_demo_001",
    "fields": {
      "displayName": "Demo Talent A"
    }
  },
  "summary": {
    "score": 0,
    "unknownWeightPercent": 100,
    "requiredGapCount": 0,
    "evaluationStatus": "EVALUATED",
    "algorithmVersion": "tag-coverage-v1"
  },
  "requirements": [
    {
      "requirement": {
        "id": "req_python",
        "label": "Python experience",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python"
        ]
      },
      "status": "UNKNOWN",
      "reasonCode": "INSUFFICIENT_EVIDENCE",
      "reason": "There is insufficient shared evidence for this requirement.",
      "evidence": []
    },
    {
      "requirement": {
        "id": "req_analysis",
        "label": "Python and SQL",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python",
          "skill_sql"
        ]
      },
      "status": "UNKNOWN",
      "reasonCode": "INSUFFICIENT_EVIDENCE",
      "reason": "There is insufficient shared evidence for this requirement.",
      "evidence": []
    },
    {
      "requirement": {
        "id": "req_interviews",
        "label": "Research interview experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_interviews"
        ]
      },
      "status": "UNKNOWN",
      "reasonCode": "INSUFFICIENT_EVIDENCE",
      "reason": "There is insufficient shared evidence for this requirement.",
      "evidence": []
    },
    {
      "requirement": {
        "id": "req_r",
        "label": "R experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_r"
        ]
      },
      "status": "UNKNOWN",
      "reasonCode": "INSUFFICIENT_EVIDENCE",
      "reason": "There is insufficient shared evidence for this requirement.",
      "evidence": []
    }
  ],
  "evaluatedAt": "2026-10-03T00:00:00Z"
}
```


错误状态：`401`、`403`、`404`、`422`、`500`。

关联 Jira 子任务：H18ABANANA-20、H18ABANANA-30、H18ABANANA-31、H18ABANANA-33。

## 5. 统一错误处理

错误响应采用下面结构。前端按 `error.code` 分支，不匹配 message 的英文文本；message 用于展示。字段路径使用点号与数组下标，如 `content.education[0].institution`。无字段错误时 `fieldErrors=[]`。`currentRevision` 只在版本冲突时提供，不适用时省略。


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


| HTTP | error.code | 触发情况 | 前端处理 |
|---|---|---|---|
| 400 | BAD_REQUEST | JSON 无法解析、multipart 结构损坏 | 提示请求失败，保留当前输入 |
| 401 | UNAUTHENTICATED | 未登录、会话失效 | 清理账号缓存，返回登录入口 |
| 401 | INVALID_CREDENTIALS | 登录账号或密码错误 | 登录框显示通用错误 |
| 403 | FORBIDDEN | 角色无权限 | 显示无权限，不重试 |
| 403 | CSRF_INVALID | CSRF 或 Origin 校验失败 | 重新获取会话；提示重试，不自动重发写入 |
| 404 | NOT_FOUND | 不存在、别人的私有资源、已撤销可见性的人才 | 显示不可用并重新读取列表 |
| 409 | REVISION_CONFLICT | expectedRevision 过期 | 保留本地输入，重新载入和比较 |
| 409 | PROFILE_UNCONFIRMED | 请求本人推荐时当前资料未确认 | 引导用户审核并确认 |
| 409 | EXTRACTION_NOT_READY | 提取仍在等待/处理中 | 继续状态查询，不导入 |
| 413 | UPLOAD_TOO_LARGE | 超过 10 MiB | 提示大小限制 |
| 415 | UNSUPPORTED_FILE_TYPE | 文件不是受支持的 PDF/DOCX | 提示文件类型要求 |
| 415 | UNSUPPORTED_MEDIA_TYPE | 请求的 Content-Type 错误 | 修正请求适配层 |
| 422 | VALIDATION_ERROR | 字段无效、发布/确认前置条件不满足 | 就地显示 fieldErrors |
| 422 | EXTRACTION_FAILED | 已失败文档请求提取/导入 | 显示手动录入入口，保留已有资料 |
| 429 | RATE_LIMITED | 登录或上传频率受限 | 提示稍后再试，停止连续请求 |
| 500 | INTERNAL_ERROR | 后端意外异常 | 提示稍后再试，保留输入和 requestId |

后端不要把堆栈、数据库错误、文件系统路径放入 message。`requestId` 用于团队定位日志。`Document.error` 为 ErrorDetail（不嵌套 requestId）；文件状态 GET 本身可成功返回 200 和 status=FAILED，只有读取/导入失败的提取结果才返回 422。

## 6. 完整数据字段表

引用类型会链接到本节相应模型。数组条目必须符合该类型。所有对象都拒绝额外字段；“必填”指字段必须存在，允许 null 的字段仍按表中规定发送。

本节涵盖全部 47 个公共模型。`file` 上传字段为唯一额外的二进制请求形态，见接口 11。


<a id="model-id"></a>

### Id

所有业务 ID 使用此格式。后端生成顶层资源 ID；前端可为教育、课程、经历、成果、要求条目生成稳定的 UUID 字符串。条目编辑时保持 ID，不能用数组下标充当长期 ID。

类型：string。正则 `^[A-Za-z0-9_-]{1,64}$`。

<a id="model-profilefield"></a>

### ProfileField

本版本隐私控制单位为整个字段/章节，而不是某个教育记录或技能条目。此枚举是 visibleFields 的唯一白名单。

类型：`displayName` / `disciplineGroup` / `education` / `courses` / `researchExperience` / `skills` / `researchInterests` / `researchOutputs`。。

<a id="model-user"></a>

### User

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `id` | string | 是 | 对象标识；不得改变已有记录 ID；正则 `^[A-Za-z0-9_-]{1,64}$` |
| `displayName` | string | 是 | 展示姓名；在团队视图中也受可见性控制；最短 1 |
| `email` | string | 是 | 登录邮箱，仅账号本人可见；格式 email |
| `role` | `TALENT` / `RESEARCH_TEAM` | 是 | 账号角色，由后端决定 |

<a id="model-session"></a>

### Session

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `user` | [User](#model-user) / null | 是 | 匿名时 null；已登录时账号对象 |
| `csrfToken` | string | 是 | 仅供后续变更请求校验，不是登录会话 ID；最短 1 |

<a id="model-loginrequest"></a>

### LoginRequest

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `email` | string | 是 | 登录邮箱，仅账号本人可见；格式 email |
| `password` | string | 是 | 只用于请求，不回传或记录明文；最短 1；最长 200 |

<a id="model-tag"></a>

### Tag

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `id` | string | 是 | 对象标识；不得改变已有记录 ID；正则 `^[A-Za-z0-9_-]{1,64}$` |
| `label` | string | 是 | 供用户阅读的名称；最短 1 |
| `kind` | `SKILL` / `INTEREST` | 是 | 类别，按列出的枚举传值 |
| `disciplineGroups` | `STEM` / `BUSINESS`[] | 是 | 标签可用学科组；不可重复 |

<a id="model-taglist"></a>

### TagList

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `items` | [Tag](#model-tag)[] | 是 | 当前页内容（标签列表为全部结果） |

<a id="model-education"></a>

### Education

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `id` | string | 是 | 对象标识；不得改变已有记录 ID；正则 `^[A-Za-z0-9_-]{1,64}$` |
| `institution` | string | 是 | 学校/机构名称；最短 1；最长 200 |
| `qualification` | string | 是 | 学位/学历名称；最短 1；最长 200 |
| `discipline` | string | 是 | 学科名称；最长 200 |
| `startYear` | integer / null | 是 | 开始年份；未知为 null；最小 1900；最大 2200 |
| `endYear` | integer / null | 是 | 结束年份；在读或未知为 null；最小 1900；最大 2200 |

<a id="model-course"></a>

### Course

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `id` | string | 是 | 对象标识；不得改变已有记录 ID；正则 `^[A-Za-z0-9_-]{1,64}$` |
| `name` | string | 是 | 名称；最短 1；最长 200 |
| `code` | string / null | 是 | 课程代码；未知为 null（错误对象中为错误码）；最长 100 |
| `description` | string | 是 | 纯文本说明；最长 5000 |

<a id="model-researchexperience"></a>

### ResearchExperience

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `id` | string | 是 | 对象标识；不得改变已有记录 ID；正则 `^[A-Za-z0-9_-]{1,64}$` |
| `title` | string | 是 | 标题；最短 1；最长 200 |
| `organisation` | string | 是 | 研究机构/组织；最长 200 |
| `description` | string | 是 | 纯文本说明；最长 5000 |

<a id="model-skillclaim"></a>

### SkillClaim

未选择技能代表未知，不代表不具备。明确的 DOES_NOT_HAVE 声明仅由用户输入/审核，提取服务不得根据“没找到”自动创建。

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `tagId` | string | 是 | 统一标签 ID，不能使用显示文字代替；正则 `^[A-Za-z0-9_-]{1,64}$` |
| `claim` | `HAS` / `DOES_NOT_HAVE` | 是 | HAS 为用户声明具备；DOES_NOT_HAVE 为明确声明不具备，不能根据未填写推断 |
| `evidenceText` | string | 是 | 用户审核后的证据描述；可为空，此时只能引用用户标签声明；最长 2000 |

<a id="model-researchoutput"></a>

### ResearchOutput

URL 仅允许 http/https。前端打开新页时应采用适当的链接属性；服务端不因该字段自动抓取任意地址。

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `id` | string | 是 | 对象标识；不得改变已有记录 ID；正则 `^[A-Za-z0-9_-]{1,64}$` |
| `title` | string | 是 | 标题；最短 1；最长 300 |
| `type` | `PUBLICATION` / `PROJECT` / `OTHER` | 是 | 成果类型 |
| `url` | string / null | 是 | 成果链接，限 http/https；没有时 null；格式 uri；正则 `^https?://` |
| `description` | string | 是 | 纯文本说明；最长 5000 |

<a id="model-profilecontent"></a>

### ProfileContent

PUT 为完整替换，8 个字段全部必填。某章节未填写使用 []，未知学科组用 null。已有子记录编辑保留 id；新增条目用新 id；删除条目在数组中移除。每个章节最多 100 条。

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `displayName` | string | 是 | 展示姓名；在团队视图中也受可见性控制；最长 100 |
| `disciplineGroup` | `STEM` / `BUSINESS` / null | 是 | STEM 或 BUSINESS；人才尚未选择时可为 null |
| `education` | [Education](#model-education)[] | 是 | 教育记录列表；最多项数 100 |
| `courses` | [Course](#model-course)[] | 是 | 课程记录列表；最多项数 100 |
| `researchExperience` | [ResearchExperience](#model-researchexperience)[] | 是 | 研究经历列表；最多项数 100 |
| `skills` | [SkillClaim](#model-skillclaim)[] | 是 | 技能声明列表；tagId 唯一且必须是 SKILL 标签；最多项数 100 |
| `researchInterests` | string[] | 是 | 兴趣标签 ID 列表；必须是 INTEREST 标签；最多项数 100；不可重复 |
| `researchOutputs` | [ResearchOutput](#model-researchoutput)[] | 是 | 成果列表；最多项数 100 |

<a id="model-profilesections"></a>

### ProfileSections

局部导入对象，必须至少含一个章节；省略表示不改，[] 表示清空。只允许六个学术/研究章节，不修改 displayName 或 disciplineGroup。

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `education` | [Education](#model-education)[] | 否 | 教育记录列表；最多项数 100 |
| `courses` | [Course](#model-course)[] | 否 | 课程记录列表；最多项数 100 |
| `researchExperience` | [ResearchExperience](#model-researchexperience)[] | 否 | 研究经历列表；最多项数 100 |
| `skills` | [SkillClaim](#model-skillclaim)[] | 否 | 技能声明列表；tagId 唯一且必须是 SKILL 标签；最多项数 100 |
| `researchInterests` | string[] | 否 | 兴趣标签 ID 列表；必须是 INTEREST 标签；最多项数 100；不可重复 |
| `researchOutputs` | [ResearchOutput](#model-researchoutput)[] | 否 | 成果列表；最多项数 100 |

<a id="model-confirmation"></a>

### Confirmation

只有 status=CONFIRMED 且 confirmedRevision=Profile.revision 才能参与匹配。UNCONFIRMED 时 confirmedRevision 和 confirmedAt 必须同时为 null。

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `status` | `UNCONFIRMED` / `CONFIRMED` | 是 | 状态枚举；含义见业务规则 |
| `confirmedRevision` | integer / null | 是 | 已确认版本；待确认时为 null；最小 0 |
| `confirmedAt` | string / null | 是 | 用户确认时间；待确认时为 null；格式 date-time |

<a id="model-fieldorigin"></a>

### FieldOrigin

按章节记录来源，不冒充逐句文件引用或第三方验证。文档导入后用户修改某章节时，该章节来源改为 MANUAL。来源由后端写入，前端不能在 PUT 中自行指定。

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `field` | `education` / `courses` / `researchExperience` / `skills` / `researchInterests` / `researchOutputs` | 是 | 所属字段/章节 |
| `sourceType` | `MANUAL` / `USER_REVIEWED_DOCUMENT` | 是 | 后端维护的来源类别，MANUAL 或经用户审核的文档导入 |
| `documentId` | string / null | 是 | 本人文件来源引用；手工输入时为 null，不对研究团队公开；正则 `^[A-Za-z0-9_-]{1,64}$` |

<a id="model-profile"></a>

### Profile

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `talentId` | string | 是 | 人才标识，后端确定；正则 `^[A-Za-z0-9_-]{1,64}$` |
| `revision` | integer | 是 | 资源当前版本；与其他资源版本相互独立；最小 0 |
| `content` | [ProfileContent](#model-profilecontent) | 是 | 资源业务内容 |
| `confirmation` | [Confirmation](#model-confirmation) | 是 | 当前资料确认状态 |
| `origins` | [FieldOrigin](#model-fieldorigin)[] | 是 | 本人可见的章节来源元数据 |
| `updatedAt` | string | 是 | 最近更新的 UTC 时间；格式 date-time |

<a id="model-profilewrite"></a>

### ProfileWrite

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `expectedRevision` | integer | 是 | 前端最近读到的此资源版本；最小 0 |
| `content` | [ProfileContent](#model-profilecontent) | 是 | 资源业务内容 |

<a id="model-revisionrequest"></a>

### RevisionRequest

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `expectedRevision` | integer | 是 | 前端最近读到的此资源版本；最小 0 |

<a id="model-privacy"></a>

### Privacy

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `revision` | integer | 是 | 资源当前版本；与其他资源版本相互独立；最小 0 |
| `discoverable` | boolean | 是 | 是否允许团队发现；新账号默认 false |
| `visibleFields` | [ProfileField](#model-profilefield)[] | 是 | 允许团队看到并用于匹配的字段白名单；新账号为空；不可重复 |
| `updatedAt` | string | 是 | 最近更新的 UTC 时间；格式 date-time |

<a id="model-privacywrite"></a>

### PrivacyWrite

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `expectedRevision` | integer | 是 | 前端最近读到的此资源版本；最小 0 |
| `discoverable` | boolean | 是 | 是否允许团队发现；新账号默认 false |
| `visibleFields` | [ProfileField](#model-profilefield)[] | 是 | 允许团队看到并用于匹配的字段白名单；新账号为空；不可重复 |

<a id="model-fielderror"></a>

### FieldError

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `field` | string | 是 | 所属字段/章节 |
| `message` | string | 是 | 可展示说明；不要用于程序分支 |

<a id="model-errordetail"></a>

### ErrorDetail

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `code` | `UNAUTHENTICATED` / `INVALID_CREDENTIALS` / `FORBIDDEN` / `CSRF_INVALID` / `NOT_FOUND` / `VALIDATION_ERROR` / `REVISION_CONFLICT` / `PROFILE_UNCONFIRMED` / `EXTRACTION_NOT_READY` / `EXTRACTION_FAILED` / `UPLOAD_TOO_LARGE` / `UNSUPPORTED_FILE_TYPE` / `RATE_LIMITED` / `INTERNAL_ERROR` / `BAD_REQUEST` / `UNSUPPORTED_MEDIA_TYPE` | 是 | 课程代码；未知为 null（错误对象中为错误码） |
| `message` | string | 是 | 可展示说明；不要用于程序分支 |
| `fieldErrors` | [FieldError](#model-fielderror)[] | 是 | 字段校验问题；没有问题则空数组 |
| `currentRevision` | integer | 否 | 版本冲突时服务器版本；其他错误省略；最小 0 |

<a id="model-error"></a>

### Error

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `error` | [ErrorDetail](#model-errordetail) | 是 | 统一错误详情；Document 非 FAILED 时为 null |
| `requestId` | string | 是 | 后端生成的请求排查标识 |

<a id="model-document"></a>

### Document

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `id` | string | 是 | 对象标识；不得改变已有记录 ID；正则 `^[A-Za-z0-9_-]{1,64}$` |
| `kind` | `CV` / `TRANSCRIPT` | 是 | 类别，按列出的枚举传值 |
| `fileName` | string | 是 | 原始文件名，仅本人可见 |
| `mediaType` | `application/pdf` / `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | 是 | 实际文件 MIME 类型 |
| `sizeBytes` | integer | 是 | 文件字节数；最小 1；最大 10485760 |
| `status` | `QUEUED` / `PROCESSING` / `READY` / `FAILED` | 是 | 状态枚举；含义见业务规则 |
| `createdAt` | string | 是 | 创建时间；格式 date-time |
| `updatedAt` | string | 是 | 最近更新的 UTC 时间；格式 date-time |
| `error` | [ErrorDetail](#model-errordetail) / null | 是 | 统一错误详情；Document 非 FAILED 时为 null |

<a id="model-uncertainfield"></a>

### UncertainField

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `field` | `education` / `courses` / `researchExperience` / `skills` / `researchInterests` / `researchOutputs` | 是 | 所属字段/章节 |
| `status` | `UNKNOWN` / `NOT_RECOGNISED` | 是 | 状态枚举；含义见业务规则 |
| `reason` | string | 是 | 可展示解释，只依据当前有权使用的证据 |

<a id="model-extraction"></a>

### Extraction

suggestedSections 可以为空；此时只显示不确定项和手动录入入口，不能发空 sections 导入。提取完成、导入完成、资料确认是三个不同阶段。

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `documentId` | string | 是 | 本人文件来源引用；手工输入时为 null，不对研究团队公开；正则 `^[A-Za-z0-9_-]{1,64}$` |
| `status` | `READY` | 是 | 状态枚举；含义见业务规则 |
| `suggestedSections` | object（六个章节的可选子集） | 是 | 可包含六个资料章节中的任意子集；也可为空对象。结构与 ProfileSections 字段一致，但无至少一个字段的限制 |
| `uncertainFields` | [UncertainField](#model-uncertainfield)[] | 是 | 不能可靠提取的章节与原因 |
| `warnings` | string[] | 是 | 审核提示列表 |
| `reviewRequired` | `true` | 是 | 固定为 true，提取结果必须经过人工审核 |

<a id="model-applyextractionrequest"></a>

### ApplyExtractionRequest

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `expectedProfileRevision` | integer | 是 | 导入时读取到的本人资料版本；最小 0 |
| `sections` | [ProfileSections](#model-profilesections) | 是 | 只替换包含的章节；未传保留，[] 明确清空 |

<a id="model-requirement"></a>

### Requirement

本版只对 SKILL 和 INTEREST 标签要求做确定性评估。教育、课程、成果作为资料可展示，但不从自然语言臆测为某个技能证据。

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `id` | string | 是 | 对象标识；不得改变已有记录 ID；正则 `^[A-Za-z0-9_-]{1,64}$` |
| `label` | string | 是 | 供用户阅读的名称；最短 1；最长 300 |
| `kind` | `SKILL` / `INTEREST` | 是 | 类别，按列出的枚举传值 |
| `importance` | `REQUIRED` / `PREFERRED` | 是 | REQUIRED 必须项或 PREFERRED 偏好项 |
| `tagIds` | string[] | 是 | 同一要求内为 AND 关系；每个标签类别须与 kind 一致；最少项数 1；最多项数 20；不可重复 |

<a id="model-opportunitycontent"></a>

### OpportunityContent

已发布机会至少有一个要求；草稿允许空 requirements，但基础文本字段仍需填入。无关闭/删除/申请状态。

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `title` | string | 是 | 标题；最短 1；最长 200 |
| `university` | string | 是 | 机会所属大学；最短 1；最长 200 |
| `disciplineGroup` | `STEM` / `BUSINESS` | 是 | STEM 或 BUSINESS；人才尚未选择时可为 null |
| `discipline` | string | 是 | 学科名称；最短 1；最长 200 |
| `researchArea` | string | 是 | 研究方向名称；最短 1；最长 300 |
| `description` | string | 是 | 纯文本说明；最短 1；最长 10000 |
| `requirements` | [Requirement](#model-requirement)[] | 是 | 要求列表；草稿可为空，发布至少一项；最多项数 50 |

<a id="model-opportunity"></a>

### Opportunity

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `id` | string | 是 | 对象标识；不得改变已有记录 ID；正则 `^[A-Za-z0-9_-]{1,64}$` |
| `revision` | integer | 是 | 资源当前版本；与其他资源版本相互独立；最小 0 |
| `status` | `DRAFT` / `PUBLISHED` | 是 | 状态枚举；含义见业务规则 |
| `content` | [OpportunityContent](#model-opportunitycontent) | 是 | 资源业务内容 |
| `createdAt` | string | 是 | 创建时间；格式 date-time |
| `updatedAt` | string | 是 | 最近更新的 UTC 时间；格式 date-time |

<a id="model-opportunitywrite"></a>

### OpportunityWrite

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `expectedRevision` | integer | 是 | 前端最近读到的此资源版本；最小 0 |
| `content` | [OpportunityContent](#model-opportunitycontent) | 是 | 资源业务内容 |

<a id="model-matchstatus"></a>

### MatchStatus

类型：`MATCHED` / `PARTIAL` / `GAP` / `UNKNOWN`。。

<a id="model-ownerevidence"></a>

### OwnerEvidence

只用于人才本人的匹配详情。documentId 是来源引用，不是公开链接；sourceType=MANUAL 时 documentId=null。

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `field` | [ProfileField](#model-profilefield) | 是 | 所属字段/章节 |
| `recordId` | string | 是 | 证据记录 ID；skills/interests 用 tagId，其余用子记录 id；正则 `^[A-Za-z0-9_-]{1,64}$` |
| `valueSummary` | string | 是 | 证据的简短文本，不得加入来源没有的事实 |
| `confirmedRevision` | integer | 是 | 已确认版本；待确认时为 null；最小 0 |
| `sourceType` | `MANUAL` / `USER_REVIEWED_DOCUMENT` | 是 | 后端维护的来源类别，MANUAL 或经用户审核的文档导入 |
| `documentId` | string / null | 是 | 本人文件来源引用；手工输入时为 null，不对研究团队公开；正则 `^[A-Za-z0-9_-]{1,64}$` |

<a id="model-teamevidence"></a>

### TeamEvidence

严格比 OwnerEvidence 少字段，不包含 documentId、sourceType、confirmedRevision。证据必须来自当前公开字段，不能通过解释文案透露隐藏内容。

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `field` | [ProfileField](#model-profilefield) | 是 | 所属字段/章节 |
| `recordId` | string | 是 | 证据记录 ID；skills/interests 用 tagId，其余用子记录 id；正则 `^[A-Za-z0-9_-]{1,64}$` |
| `valueSummary` | string | 是 | 证据的简短文本，不得加入来源没有的事实 |

<a id="model-ownerrequirementresult"></a>

### OwnerRequirementResult

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `requirement` | [Requirement](#model-requirement) | 是 | 原始要求完整对象 |
| `status` | [MatchStatus](#model-matchstatus) | 是 | 状态枚举；含义见业务规则 |
| `reasonCode` | `ALL_TAGS_SUPPORTED` / `SOME_TAGS_SUPPORTED` / `EXPLICIT_NEGATIVE_CLAIM` / `INSUFFICIENT_EVIDENCE` | 是 | 稳定解释类别，前端可据此显示说明 |
| `reason` | string | 是 | 可展示解释，只依据当前有权使用的证据 |
| `evidence` | [OwnerEvidence](#model-ownerevidence)[] | 是 | 证据列表；UNKNOWN 时必须为空 |

<a id="model-teamrequirementresult"></a>

### TeamRequirementResult

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `requirement` | [Requirement](#model-requirement) | 是 | 原始要求完整对象 |
| `status` | [MatchStatus](#model-matchstatus) | 是 | 状态枚举；含义见业务规则 |
| `reasonCode` | `ALL_TAGS_SUPPORTED` / `SOME_TAGS_SUPPORTED` / `EXPLICIT_NEGATIVE_CLAIM` / `INSUFFICIENT_EVIDENCE` | 是 | 稳定解释类别，前端可据此显示说明 |
| `reason` | string | 是 | 可展示解释，只依据当前有权使用的证据 |
| `evidence` | [TeamEvidence](#model-teamevidence)[] | 是 | 证据列表；UNKNOWN 时必须为空 |

<a id="model-matchsummary"></a>

### MatchSummary

前端使用后端提供的 summary，不自行从当前页重算。保留两位小数，客户端显示可按产品方案决定是否展示数字，但必须保留整体排序与逐项解释。

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `score` | number / null | 是 | 0～100 的加权证据覆盖分，不代表录用概率；没有要求时 null；最小 0；最大 100 |
| `unknownWeightPercent` | number / null | 是 | UNKNOWN 要求所占权重百分比；没有要求时 null；最小 0；最大 100 |
| `requiredGapCount` | integer | 是 | 状态 GAP 且 importance=REQUIRED 的要求数量；最小 0 |
| `evaluationStatus` | `EVALUATED` / `INSUFFICIENT_CRITERIA` | 是 | 正常评估或缺少可评估要求 |
| `algorithmVersion` | `tag-coverage-v1` | 是 | 匹配算法约定版本 |

<a id="model-ownermatch"></a>

### OwnerMatch

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `opportunity` | [Opportunity](#model-opportunity) | 是 | 机会完整对象 |
| `profileRevision` | integer | 是 | 本次使用的已确认资料版本；最小 0 |
| `summary` | [MatchSummary](#model-matchsummary) | 是 | 匹配概况 |
| `requirements` | [OwnerRequirementResult](#model-ownerrequirementresult)[] | 是 | 要求列表；草稿可为空，发布至少一项 |
| `evaluatedAt` | string | 是 | 本次评估时间；格式 date-time |

<a id="model-visibleprofile"></a>

### VisibleProfile

fields 可包含 ProfileContent 的任意字段子集，全部可省略。其键的值遵循 ProfileContent 的同名类型。没有 displayName 时前端显示“匿名人才”，不能请求其他接口绕过隐私补全姓名。

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `talentId` | string | 是 | 人才标识，后端确定；正则 `^[A-Za-z0-9_-]{1,64}$` |
| `fields` | object（[ProfileContent](#model-profilecontent) 的字段子集） | 是 | 只包含获准公开的 ProfileContent 字段；隐藏键完全省略 |

<a id="model-teammatch"></a>

### TeamMatch

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `opportunityId` | string | 是 | 被匹配的机会 ID；正则 `^[A-Za-z0-9_-]{1,64}$` |
| `opportunityRevision` | integer | 是 | 评估使用的机会版本；最小 0 |
| `talent` | [VisibleProfile](#model-visibleprofile) | 是 | 过滤后的可见人才资料 |
| `summary` | [MatchSummary](#model-matchsummary) | 是 | 匹配概况 |
| `requirements` | [TeamRequirementResult](#model-teamrequirementresult)[] | 是 | 要求列表；草稿可为空，发布至少一项 |
| `evaluatedAt` | string | 是 | 本次评估时间；格式 date-time |

<a id="model-recommendationitem"></a>

### RecommendationItem

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `rank` | integer | 是 | 分页前全局名次，从 1 起；最小 1 |
| `opportunity` | [Opportunity](#model-opportunity) | 是 | 机会完整对象 |
| `summary` | [MatchSummary](#model-matchsummary) | 是 | 匹配概况 |

<a id="model-talentmatchitem"></a>

### TalentMatchItem

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `rank` | integer | 是 | 分页前全局名次，从 1 起；最小 1 |
| `talent` | [VisibleProfile](#model-visibleprofile) | 是 | 过滤后的可见人才资料 |
| `summary` | [MatchSummary](#model-matchsummary) | 是 | 匹配概况 |

<a id="model-opportunitypage"></a>

### OpportunityPage

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `items` | [Opportunity](#model-opportunity)[] | 是 | 当前页内容（标签列表为全部结果） |
| `page` | integer | 是 | 当前页码；最小 1 |
| `pageSize` | integer | 是 | 每页上限；最小 1；最大 100 |
| `total` | integer | 是 | 有权访问的全部结果数；最小 0 |

<a id="model-documentpage"></a>

### DocumentPage

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `items` | [Document](#model-document)[] | 是 | 当前页内容（标签列表为全部结果） |
| `page` | integer | 是 | 当前页码；最小 1 |
| `pageSize` | integer | 是 | 每页上限；最小 1；最大 100 |
| `total` | integer | 是 | 有权访问的全部结果数；最小 0 |

<a id="model-recommendationpage"></a>

### RecommendationPage

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `items` | [RecommendationItem](#model-recommendationitem)[] | 是 | 当前页内容（标签列表为全部结果） |
| `page` | integer | 是 | 当前页码；最小 1 |
| `pageSize` | integer | 是 | 每页上限；最小 1；最大 100 |
| `total` | integer | 是 | 有权访问的全部结果数；最小 0 |

<a id="model-talentmatchpage"></a>

### TalentMatchPage

| 字段 | 类型 / 可选值 | 必填 | 说明与约束 |
|---|---|---|---|
| `items` | [TalentMatchItem](#model-talentmatchitem)[] | 是 | 当前页内容（标签列表为全部结果） |
| `page` | integer | 是 | 当前页码；最小 1 |
| `pageSize` | integer | 是 | 每页上限；最小 1；最大 100 |
| `total` | integer | 是 | 有权访问的全部结果数；最小 0 |

## 7. 关键业务规则与调用顺序

### 7.1 手工资料流程

```text
GET /auth/session → POST /auth/login
GET /tags + GET /me/profile
编辑本地表单
PUT /me/profile（expectedRevision + 完整 content）
检查返回的新 revision 与 UNCONFIRMED 状态
用户审核 → POST /me/profile/confirmation（新 revision）
GET /me/recommendations → GET /me/opportunity-matches/{opportunityId}
```

用户只修改隐私时不需要重新确认资料。用户修改资料内容后，整份资料暂停参与匹配，直到确认当前版本；本版不提供“部分字段已确认、部分字段未确认”的混合匹配。

### 7.2 文件提取与手工录入共存

```text
POST /me/documents → 202 QUEUED
GET /me/documents/{documentId} → PROCESSING → READY / FAILED
READY → GET /me/documents/{documentId}/extraction
用户选择要导入的章节，修改/删除不正确建议
GET /me/profile（了解当前资料和版本）
POST /me/documents/{documentId}/apply（expectedProfileRevision + sections）
返回新的 UNCONFIRMED 资料 → 用户检查 → POST /me/profile/confirmation
```

- 前端应展示导入会替换哪些章节；要合并旧技能与新技能时，先在本地按 tagId 合并，让用户审核，提交合并后的完整 skills 数组。
- 提取结果到达时不能直接覆盖用户正编辑的表单。提交用最新已知版本，冲突时让用户比较；不偷偷覆盖。
- `READY` 只意味着提取完成，不意味着用户确认，也不意味着内容准确。
- `UNKNOWN` 表示无法确定，`NOT_RECOGNISED` 表示未识别出可靠内容；均不转换成正向技能或负向技能声明。
- 提取失败后仍保留手动录入功能。v0.1 没有单独“重试提取”接口，需要重传文件重新开始。

### 7.3 团队机会与人才发现流程

```text
团队登录 → GET /opportunities?scope=mine
GET /tags → POST /opportunities（创建 DRAFT）
PUT /opportunities/{opportunityId}（编辑）
POST /opportunities/{opportunityId}/publish（当前 revision）
GET /opportunities/{opportunityId}/talent-matches
GET /opportunities/{opportunityId}/talent-matches/{talentId}
```

创建机会不能直接传 status=PUBLISHED；先创建草稿再发布。团队看人才无需新增 `/talents/{id}` 公共全量资料接口，使用匹配详情内的 `VisibleProfile` 即可，避免绕过可见性控制。

### 7.4 隐私必须在计算前生效

人才本人推荐：使用本人当前已确认的完整资料。即使 discoverable=false，本人仍可获得推荐。

团队反向匹配：

1. 验证团队拥有该已发布机会。
2. 排除 discoverable=false 或当前版本未确认的人才。
3. 只取 visibleFields 允许的字段。
4. 基于这些字段计算状态、分数、解释，再排序、分页和统计 total。
5. 输出 VisibleProfile 和 TeamEvidence。每次列表/详情请求重新检查授权；结果缓存若存在，必须随资料、机会和隐私版本变化失效。

例如某人才本人可以得到 50 分，但只向团队公开姓名时，团队端全部要求为 UNKNOWN、score=0、unknownWeightPercent=100。这是不同证据权限下的正常结果。**不能先用私有技能算分，然后只在界面上隐藏技能。**

原始简历/成绩单、提取原文、文件来源和登录邮箱不在可公开字段白名单中。接口不能用“该用户隐藏了 Python”之类文案泄漏隐藏信息；隐藏与缺少证据使用同一通用解释。

隐私撤回作用于后续响应，不能声称收回别人已经看到或自行保存的信息。团队页面重新进入、刷新、聚焦时应重新请求，不长期保留过期结果。

### 7.5 四种状态的确定性规则

只使用符合当前权限且来自已确认版本的信息。一个 requirement 的多个 tagIds 是 AND 关系。SKILL 查找 skills 中对应声明；INTEREST 查找 researchInterests。其他章节在 v0.1 不自动推断成标签。

按以下顺序判断：

| 优先级 | 条件 | status | reasonCode |
|---|---|---|---|
| 1 | 任意所需技能有明确的 DOES_NOT_HAVE 声明 | GAP | EXPLICIT_NEGATIVE_CLAIM |
| 2 | 全部所需标签有正向证据 | MATCHED | ALL_TAGS_SUPPORTED |
| 3 | 部分标签有正向证据，剩余未知 | PARTIAL | SOME_TAGS_SUPPORTED |
| 4 | 没有可用的正向或明确负向证据 | UNKNOWN | INSUFFICIENT_EVIDENCE |

因此在一个 AND 要求中，同时有“具备 Python”和“明确不具备 SQL”时为 GAP；有 Python、SQL 没填时为 PARTIAL。全部未填为 UNKNOWN。未确认资料不会进入计算。缺少文档、未提及技能、技能被隐藏都不能自动变成 GAP。

MATCHED/PARTIAL 的 evidence 引用支持判断的实际声明；GAP 引用明确负向声明；UNKNOWN 的 evidence=[]。interest 的 recordId 为其 tagId。用户没有提供详细 evidenceText 时，可以解释为“用户确认具备该标签”，不能补写项目或课程经历。

### 7.6 分数与排序

```text
要求权重 w：REQUIRED = 2；PREFERRED = 1
状态取值 v：MATCHED = 1；PARTIAL = 0.5；GAP = 0；UNKNOWN = 0

score = round_half_up(100 × Σ(w × v) / Σ(w), 2)
unknownWeightPercent = round_half_up(100 × Σ(UNKNOWN 的 w) / Σ(w), 2)
requiredGapCount = REQUIRED 且 GAP 的要求数量
```

用十进制四舍五入保留两位，Python 实现可使用 Decimal 的 ROUND_HALF_UP，以免语言默认舍入差异。前端不重复计算正式结果。总权重为零时分数和未知百分比都为 null，evaluationStatus=INSUFFICIENT_CRITERIA；不能除零或返回 NaN。发布接口会拦截空要求，此分支用于防御旧数据。

示例：Python 必须项 MATCHED（权重 2），Python+SQL 必须项 PARTIAL（权重 2），访谈偏好项 GAP（权重 1），R 偏好项 UNKNOWN（权重 1）。结果为 score=50、unknownWeightPercent=16.67、requiredGapCount=0，详见接口 22 的完整响应。

本版 REQUIRED 代表较高权重和显式缺口计数，不直接过滤存在 GAP 的候选。若团队决定“必须项 GAP 应排除”，需修改算法版本与两端测试样例后统一实施。分数代表证据覆盖程度，不代表录用概率或资质认证。

## 8. JavaScript / Python 对接示例

### 8.1 JavaScript 请求封装示意

这段只展示协议对接；实际前端还应处理加载状态、字段错误、会话失效和取消请求。

```javascript
let csrfToken = '';

async function apiRequest(path, { method = 'GET', body } = {}) {
  const headers = { Accept: 'application/json' };
  const isForm = body instanceof FormData;
  if (body && !isForm) headers['Content-Type'] = 'application/json';
  if (method !== 'GET') headers['X-CSRF-Token'] = csrfToken;

  const response = await fetch(`/api/v1${path}`, {
    method,
    credentials: 'include',
    headers,
    body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
  });
  if (response.status === 204) return;
  const result = await response.json();
  if (!response.ok) {
    const error = new Error(result.error.message);
    Object.assign(error, result.error, { status: response.status });
    throw error;
  }
  if (result.csrfToken) csrfToken = result.csrfToken;
  return result;
}

await apiRequest('/auth/session');
await apiRequest('/auth/login', {
  method: 'POST',
  body: { email: 'talent@example.test', password: '<预置测试账号密码>' },
});
const profile = await apiRequest('/me/profile');
const content = structuredClone(profile.content);
content.displayName = 'Demo Talent A';
const saved = await apiRequest('/me/profile', {
  method: 'PUT',
  body: { expectedRevision: profile.revision, content },
});
// 用户实际审核并点击确认后才执行：
await apiRequest('/me/profile/confirmation', {
  method: 'POST', body: { expectedRevision: saved.revision },
});
```

### 8.2 Python 后端实现约束

此协议不绑定 Python Web 框架或数据库。后端需要实现以下行为：

- 对外 JSON 保持 camelCase；输出 UTC 字符串、标准 JSON boolean/null，不能直接返回 datetime 或数据库模型。
- 用会话得到账号和资源所有者，不信任前端传入的 talentId、ownerId、角色或确认状态。
- 在数据库事务中完成版本检查和更新；仅“先读取版本，再无条件 UPDATE”不能防并发覆盖。
- 为上传保存私有存储键，不生成对外公开静态链接；下载通过接口 15 重新鉴权。
- 提取过程可采用框架现有的后台任务机制；状态、结果必须可以通过约定接口读取。不要求前端知道任务队列实现。
- 按请求者权限构造独立响应：人才侧 OwnerEvidence，团队侧 TeamEvidence。不要序列化完整资料后交给前端过滤。
- 确认状态、隐私规则、评分在后端统一实现；前端只展示，避免两个版本算法漂移。
- 校验失败、框架默认错误都转换为第 5 节 Error 格式，包括 Python 框架默认的 422 响应。

## 9. 双方完成接口联调的判断标准

| 用例 | 预期结果 |
|---|---|
| 未登录进入页面 | session 返回 200 和 user=null；私有接口返回 401 |
| 人才/团队登录 | 返回正确角色；错误角色接口拒绝访问 |
| 新人才资料 | revision=0、待确认、默认不允许被发现 |
| 保存与再读资料 | 内容一致；刷新后可读到后端保存值 |
| 编辑已经确认的资料 | 状态变待确认；推荐接口 409；重新确认后恢复 |
| 两个页面同时编辑 | 旧版本保存 409，不覆盖较新数据 |
| 只更新隐私 | 资料确认保持；隐私 revision 独立递增 |
| PDF/DOCX 上传 | 202 后可以查询过程与终态 |
| 超大/错误类型文件 | 分别 413 / 415；不会导致已有资料丢失 |
| 提取失败或内容不确定 | 保留手动输入；不会自动生成已确认事实 |
| 审核并导入部分章节 | 只替换选中章节；其他字段保留；导入后待确认 |
| 机会创建、编辑、发布 | 只有发布后进入推荐池；无要求不能发布 |
| 四种匹配状态 | 同一合成案例显示 MATCHED / PARTIAL / GAP / UNKNOWN |
| 缺失/隐藏技能 | 不产生虚构证据，也不能直接判为 GAP |
| 团队查看人才 | 仅出现同意被发现且当前资料已确认的人才 |
| 团队姓名/技能不可见 | 响应省略对应键；隐藏技能不影响团队评分 |
| 人才关闭被发现 | 下一次列表中消失；旧详情 URL 返回 404 |
| 团队请求原始文件 | 拒绝；匹配响应中也没有文件链接/来源 ID |
| 分页、排序、空列表 | rank 全局连续，total 权限过滤后统计，空数据正常 200 |
| 退出再登录其他账号 | 不残留上一个账号资料或匹配缓存 |

US-06 负责准备合成/去标识数据和记录上述测试结果，不需要为了测试新增开放的管理接口。本文样例只证明约定结构，不代表真实后端或整个产品已通过这些验收。

## 10. 本文之外的后续范围

US-10～US-16 中的后续工作仍在 Backlog：更完整的文件/确认保护、系统化质量评估、收藏、语义匹配、高级搜索、完整注册/身份管理、全项目测试。与当前隐私/测试有重叠的基础规则已在本 Sprint 实现范围中约定，但未把后续故事整体提前加入。

新增能力时先更新接口版本、字段表、模拟样例和测试，再安排两端实现。尤其不要单方改变字段大小写、枚举、完整替换含义、确认粒度或隐藏字段参与评分的规则。

## 11. 配套文件与依据

- `openapi.json`：同版 OpenAPI 3.1.0 定义，可供接口工具和校验程序使用。
- `endpoint-index.json`：24 个接口的方法、路径与 Jira 对应关系。
- `examples/`：30 份合成请求/响应样例，`index.json` 标明每份对应模型。
- 业务依据：对话中提供的 Sprint 1 Jira 工作项、工作区客户会议记录 `Client_Meeting_Minutes_2026-09-30.docx` 及 Week 3 会议记录。没有假定未提供的后端已经存在。
- 格式依据：[OpenAPI 3.1.0 官方规范](https://spec.openapis.org/oas/v3.1.0.html)。Cookie 相关属性参见 [MDN Set-Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie)。

团队确认第 1.3 节的默认选择后，可以把版本改为 `0.1.0` 并按此开始并行开发。尚未确认前，模拟接口也应沿用本草案字段，避免边写页面边自行增加不一致的数据结构。
