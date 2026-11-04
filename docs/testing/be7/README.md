# Sprint 3 BE-7 验收报告

执行日期：2026-11-04（Australia/Sydney）。基于提交 `c311f74`，包含本次工作区修改。

## 实现与规则

- 保留 REQUIRED=2、PREFERRED=1；最终分数仅为逐条需求分数的加权均值，整体兴趣诊断权重为 0。
- 修复十进制汇总：45 与 45.01 两项同权分数的均值为 45.005，HALF_UP 结果为 **45.01**。
- 中文技能标题的明确否定先于结构化和语义匹配解析；否定重复项在任意顺序下均优先。中文技能别名即使相似度很高，也不能获得正向技能分。
- 结构化状态/证据与语义分数独立；兴趣不能提供技能/学历证据。学历层级、机构和成果类型仍要求精确相等，学术条件不能拼接不同记录。
- 请求内去重、16 项调用批次、逐文本量化推理、校验本地模型、失败后 60 秒冷却、请求内文本/向量生命周期均保留。
- CI 同时准备历史 US-13 与当前应用模型；当前真实 HTTP 用例通过必跑开关执行，模型缺失/损坏不能跳过后报成功。

调用边界、完整规则和准备命令见[评分说明](../../semantic-matching.md)。

## 模型与版本

| 项目 | 实际配置 |
| --- | --- |
| 模型 | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| 固定 revision | `e8f8c211226b894fcb81acc59f3b34ba3efd5f42` |
| 模型版本 | `multilingual-minilm-requirements-onnx-v1` |
| 输入预处理版本 | `requirement-inputs-v1` |
| 评分算法版本 | `requirement-semantic-v1` |
| 阈值版本 | `requirement-thresholds-v1`；partial=0.45，relevant=0.75 |
| 推理 | CPU uint8 ONNX；384 维；128 token；masked mean pooling + L2 normalization |
| 环境 | Windows 11；Python 3.12.14；pytest 8.4.2；ONNX Runtime 1.23.2；tokenizers 0.22.1；NumPy 2.3.4 |

已执行模型准备命令并校验两个本地文件：

| 文件 | SHA-256 |
| --- | --- |
| `data/semantic/model/tokenizer.json` | `2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8` |
| `data/semantic/model/onnx/model_quint8_avx2.onnx` | `98a01d88b7de996cdea58c32ca71208c09968d143798814b2ea09d3439dc334f` |

模型资源留在 Git 忽略的 `data/` 下，不把二进制模型加入源码。

## 固定样例与真实 HTTP

[固定样例](../../../backend/tests/data/sprint3/be7-scoring.json)独立给出预期分数、权重、贡献、状态和总分，覆盖所有五种需求类型、缺失项分母、舍入边界、学术硬条件和多条件均值。

真实模型通过 Flask HTTP 测试客户端访问实际路由，使用隔离 SQLite、真实身份/确认/隐私/收藏流程；这些用例没有替换编码器。结果如下：

| 档案技能 | 需求 | 逐条分数 / 方法 |
| --- | --- | --- |
| 生物科技研究 | 生物技术研究 | **99.07 / SEMANTIC**；结构化状态仍为 UNKNOWN |
| 生物科技研究 | 法国文学研究 | **0** |
| 不会生物科技研究 | 生物技术研究 | **0 / EXPLICIT_GAP** |
| 生物科技研究；证据为“我不会生物科技研究” | 生物技术研究 | **0 / EXPLICIT_GAP** |
| 不会生物技术研究 | 生物技术研究 | **0 / EXPLICIT_GAP** |

列表、详情、团队列表、团队详情及 shortlist 使用相同结果；本人保存机会后继续复用同一匹配接口。两个机会先评分再分页，第一页选择同义表达的机会。兴趣字段撤回分享、取消发现授权和修改档案后需要重新确认的回归用例也在验收范围内。

## 故障与必跑门槛

故障矩阵包括文件缺失、文件校验失败、加载异常、推理异常、NaN、Infinity、零向量、错误批次数量及错误向量维数。推荐、本人详情、团队列表/详情和 shortlist 均返回通过现有契约校验的结构化回退；没有语义 matches、非有限数值或私有异常内容。

冷却 HTTP 用例通过可控时钟验证：首次推理失败后，第 59 秒的请求不会重新加载；第 60 秒可以恢复。冷却期间修改并重新确认的档案，恢复时使用新文本。另有两项独立子进程验收，分别提供缺失和损坏资源；必跑命令均以失败退出，没有 skip。请求下载入口设置了失败断言，回退测试不会访问网络。

复现 BE-7 验收：

```powershell
.\.venv\Scripts\python.exe -m backend.src.features.matching.prepare_semantic
.\.venv\Scripts\python.exe -m pytest backend/tests/test_requirement_scoring.py backend/tests/test_semantic_matching.py backend/tests/test_sprint3_be7.py --require-application-model -q -rs --junitxml=reports/be7-application-model.xml
```

缺少依赖时先运行 `python -m pip install -r backend/requirements-dev.txt`；非 Windows 环境使用 `.venv/bin/python`。配置自定义目录时，对准备与测试使用同一个 `SEMANTIC_MODEL_DIR`。

## 执行证据

完整回归实际执行命令：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests --require-application-model --require-frontend -q -rs --junitxml=docs/testing/be7/acceptance.xml
```

| 检查 | 最终结果 |
| --- | --- |
| 完整后端与真实前后端 HTTP 联调 | **766 passed，0 failed，14 skipped**；397.20 秒 |
| BE-7 三个评分/模型测试文件 | **57 passed，0 failed，0 skipped** |
| 其中本次 BE-7 专用测试文件 | **14 passed，0 failed，0 skipped** |
| 现有 API 示例契约校验 | **49 / 49 通过** |
| 模型准备、校验与探测推理 | **通过** |
| 修改内容空白检查 | **通过** |

14 个跳过项全部属于显式启用的外部环境检查：实际 Docker 栈 1 项、MySQL 专项 5 项、MySQL 旧表升级 8 项。应用模型和前端 HTTP 联调没有跳过。18 条现有警告来自 Sprint 2 / US-16 测试的 `record_property` 与 xunit2 元数据兼容提示，不影响通过结果。

初次受限进程运行无法启动 Git Bash/前端辅助进程；使用本机权限重新执行了上述完整命令，全部适用测试通过。保留的验收文件来自最终成功运行。

最终结果见 [JUnit 报告](acceptance.xml)及[执行元数据](execution.json)。后者记录完整命令、环境、各测试文件统计、实际分数以及 LF 归一化后的实现/样例 SHA-256。JUnit 中的 `BE7.*` suite properties 包含模型 revision、校验值、版本和真实中文 HTTP 分数，不使用历史 US-13 报告替代当前应用模型证据。

本次验收覆盖本地应用与 HTTP/前端联调；Docker 实际部署、独立 MySQL 集成和 GitLab 托管流水线的执行状态应以各自运行记录为准。
