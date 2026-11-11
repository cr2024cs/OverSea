# FLOW.md · 当前实现的业务流程与代码归属

最后更新：2026-11-08  
用途：说明 MVP 现在实际怎么走、每个阶段由谁触发、状态何时变化、对应代码在哪里。

---

## 1. 先理解三层

系统里有三套容易混淆的东西：

| 层 | 含义 | 存在哪里 |
| --- | --- | --- |
| 项目阶段 `phase` | 业务大阶段 1–7 | `projects.phase` |
| 项目状态 `status` | 阶段内的细化状态 | `projects.status` |
| 业务对象状态 | 建议书、合同、节点、质询各自状态 | `proposals.status`、`contracts.status`、`milestones.status` 等 |

**对话不会推进阶段。** AI 聊天只是问答；只有明确的业务动作（生成任务地图、生成建议书、确认建议书、生成合同、双方确认等）才改变 `phase/status`。

---

## 2. 角色与入口

| 角色 | 首页 | 主要职责 |
| --- | --- | --- |
| 客户 | `/` 我的项目 | 建项目、填问卷、上传资料、AI 问答、选服务、确认需求/建议书/报价/合同/节点 |
| PM | `/` 全部项目 | 诊断、任务地图、需求确认书、建议书、询价、合同、审查、验收、归档 |
| 律师 | `/lawyer` | 审批/驳回法律类质询 |
| 管理员 | `/admin` | 账号、审计、指标导出、一键重置 |
| 服务商 | `/provider` | 报价、确认委托、提交交付物、回复质询 |
| 专家 | `/expert` | 盲评打分 |

一次性链接仍保留，用于不登录的临时协作。

---

## 3. 一张总表

| # | 阶段 | 谁 | 动作 | 接口/代码 | 阶段变化 | 状态变化 |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 建项 | 客户 | 基本信息 + 8 节 41 题问卷 | `POST /api/projects` · `api/projects.py` + `services/questionnaire.py` | `phase=1` | `draft` |
| 1 | 诊断 | PM | 生成任务地图 | `POST /api/projects/{id}/tasks/refresh` · `api/diagnosis.py` | 仍 1 | `diagnosing` |
| 2 | 诊断 | PM | 生成需求确认书 | `POST /api/projects/{id}/requirement` · `api/diagnosis.py` | 仍 1 | `requirement_pending` |
| 3 | 诊断 | 客户 | 确认需求 | `POST /api/projects/{id}/client-portal/requirement/confirm` 或链接 | **仍 1** | 仍 `requirement_pending`，记录确认时间 |
| 4 | 建议书 | PM | 生成正式建议书 | `POST /api/projects/{id}/proposals` · `api/proposals.py` | **1 → 2** | `proposal_pending` |
| 5 | 建议书 | PM | 审核 → 发送 | `/proposals/{id}/review`、`/send` | 仍 2 | 建议书 `generated → pm_reviewed → sent` |
| 6 | 建议书 | 客户 | 确认建议书 | `POST /api/projects/{id}/client-portal/proposal/confirm` 或链接 | **2 → 3** | `service_selecting` |
| 7 | 选服务 | 客户/PM | 勾选服务 | `POST /projects/{id}/selection` · `api/sourcing.py` | 仍 3 | 仍 `service_selecting` |
| 8 | 询价 | PM | 生成候选、生成 RFP、批准、发送 | `api/sourcing.py`、`api/procurement.py` | 仍 3 | RFP `draft → approved → sent` |
| 9 | 报价 | 服务商 | 提交报价 | `/provider/rfps/{id}/quote` 或 RFP 链接 | 仍 3 | RFP `replied`，报价 `received` |
| 10 | 总报价 | PM | 生成客户总报价 | `POST /projects/{id}/client-quotes` · `api/procurement.py` | **3 → 4** | `quote_pending` |
| 11 | 总报价 | 客户 | 确认总报价 | `client-portal/quote/confirm` 或链接 | **仍 4** | `quote_confirmed` |
| 12 | 合同 | PM | 生成合同与节点、复核 | `POST /projects/{id}/contracts` · `api/contracts.py` | **4 → 5** | `contracting` |
| 13 | 合同 | 客户 | 确认合同 | `client-portal/contract/confirm` 或合同链接 | 仍 5 | 合同 `pending_client → pending_provider` |
| 14 | 合同 | 服务商 | 确认委托 | `/provider/contracts/{id}/confirm` 或合同链接 | **5 → 6**（全部服务商确认后） | `executing` |
| 15 | 履约 | 服务商/PM | 提交交付物、初审、审查答复 | `api/delivery.py`、`api/queries.py` | 仍 6 | 节点、发现、质询各自状态 |
| 16 | 验收 | PM/专家 | 邀请专家、盲评、汇总 | `api/experts.py`、`api/delivery.py` | 仍 6 | 节点 `passed/conditional/failed` |
| 17 | 节点确认 | 客户 | 确认节点 | `client-portal/milestones/{id}/confirm` | 仍 6 | 记录客户确认时间 |
| 18 | 归档 | PM | 生成复盘、归档包 | `POST /projects/{id}/archives` · `api/archives.py` | **6 → 7** | `closed`、`archived=true` |

---

## 4. 阶段门禁（什么时候进入下一阶段）

| 进入 | 必要条件 | 代码 |
| --- | --- | --- |
| 阶段 2 建议 | PM 生成正式建议书 | `api/proposals.py` 的 `generate_proposal` 设置 `phase=2` |
| 阶段 3 选服务 | 客户确认建议书 | `client_portal.py` / `proposals.py` 的确认逻辑设置 `phase=3` |
| 阶段 4 报价 | PM 生成客户总报价 | `api/procurement.py` 的 `create_client_quote` 设置 `phase=4` |
| 阶段 5 签约 | PM 生成合同与节点 | `api/contracts.py` 的 `generate_contracts` 设置 `phase=5` |
| 阶段 6 履约 | 客户确认 + 全部服务商确认合同 | `api/contracts.py` / `api/provider.py` 在全部确认后设置 `phase=6` |
| 阶段 7 归档 | 全部节点通过、客户已确认、无未关闭重大发现 | `api/archives.py` 设置 `phase=7 / closed` |

**注意：**
- 客户确认需求不会立刻进入阶段 2；要等 PM 生成正式建议书。
- 客户确认总报价不会立刻进入阶段 5；要等 PM 生成合同。
- 合同生成后仍是阶段 5，只有双方确认完才进入阶段 6。
- 履约、审查、专家验收都在阶段 6 内完成，归档才进入阶段 7。

---

## 5. 对话与业务动作的区别

| 行为 | 是否写入业务表 | 是否改阶段 |
| --- | --- | --- |
| 中栏 AI 问答 | 只写 `messages` | 否 |
| 问卷提交 | 写 `projects.questionnaire_json` | 项目创建时 `phase=1` |
| 生成任务地图 | 写 `tasks` | 只改 `status=diagnosing` |
| 生成需求确认书 | 写 `projects.requirement_json` | 只改 `status` |
| 生成建议书 | 写 `proposals` | `phase=2` |
| 客户确认建议书 | 更新 `proposals` | `phase=3` |
| 生成合同 | 写 `contracts`、`milestones` | `phase=5` |
| 双方确认合同 | 更新 `contracts` | `phase=6` |
| 归档 | 写 `archives`、zip | `phase=7` |

前端对话页已有“下一步”引导条：根据 `phase/status` 提示 PM 生成任务地图、需求确认书、建议书，或跳转选服务/报价/合同/节点。

---

## 6. 代码归属

### 6.1 后端路由

| 业务 | 文件 |
| --- | --- |
| 登录、JWT | `backend/app/api/auth.py`、`services/auth.py`、`api/deps.py` |
| 项目创建/列表 | `backend/app/api/projects.py` |
| 客户问卷规则 | `backend/app/services/questionnaire.py` |
| 客户确认门户 | `backend/app/api/client_portal.py` |
| 阶段 1 调研 | `backend/app/api/diagnosis.py`、`services/citation.py`、`services/task_graph.py` |
| 阶段 2 建议/RAG | `backend/app/api/proposals.py`、`services/proposal.py`、`services/rag.py` |
| 阶段 3–4 选服务/询价/报价 | `backend/app/api/sourcing.py`、`api/procurement.py`、`services/sourcing.py`、`services/quotes.py` |
| 阶段 5 合同 | `backend/app/api/contracts.py` |
| 阶段 6 履约/审查/质询/验收 | `backend/app/api/delivery.py`、`api/queries.py`、`api/experts.py`、`services/review.py` |
| 阶段 7 复盘/归档/指标 | `backend/app/api/archives.py`、`services/retrospective.py`、`services/archive.py` |
| 服务商工作台 | `backend/app/api/provider.py` |
| 律师工作台 | `backend/app/api/lawyer.py` |
| 管理员控制台 | `backend/app/api/admin.py` |
| 一次性链接 | `backend/app/api/link.py`、各业务链接端点 |
| 权限 | `backend/app/services/permissions.py`、`services/tokens.py` |
| 统一状态机 | `backend/app/services/state_machine.py` |

### 6.2 数据模型

| 模型 | 文件 |
| --- | --- |
| 用户、令牌、审计 | `models/core.py` |
| 项目、文档、事实、任务、建议书 | `models/project.py` |
| 服务商、RFP、报价、合同 | `models/procurement.py` |
| 节点、发现、质询 | `models/delivery.py` |
| 候选服务商、客户总报价 | `models/sourcing.py` |
| 履约事件 | `models/performance.py` |
| 归档 | `models/archive.py` |
| 会话、消息 | `models/conversation.py` |
| 知识块 | `models/knowledge.py` |

### 6.3 前端

| 页面/能力 | 文件 |
| --- | --- |
| 登录 | `frontend/src/views/LoginView.vue` |
| 项目列表 | `frontend/src/views/ProjectListView.vue` |
| 新建项目 + 问卷 | `components/CreateProjectDialog.vue`、`components/QuestionnaireForm.vue` |
| 对话工作台 + 下一步引导 | `views/ChatView.vue` |
| 右侧产物面板 | `components/ArtifactPanel.vue` |
| 律师审批台 | `views/LawyerView.vue` |
| 管理员控制台 | `views/AdminView.vue` |
| 服务商工作台 | `views/ProviderView.vue` |
| 专家工作台 | `views/ExpertView.vue` |
| 客户确认页 | `views/ClientPortal` 相关标签与链接页 |
| 公开确认页 | `views/*LinkView.vue` |
| 路由与角色跳转 | `frontend/src/router/index.js` |

---

## 7. 统一状态机

所有关键状态流转已集中到：

```text
backend/app/services/state_machine.py
```

管理范围：

| 对象 | 事件 |
| --- | --- |
| 项目 `phase/status` | 任务地图、需求确认书、生成建议书、客户确认建议书、客户总报价、合同生成、合同生效、归档 |
| 建议书 | 审核、发送、客户确认、要求修改 |
| 合同 | PM 复核、客户确认、生效 |
| 节点 | 提交、PM 通过/退回、审查、专家提交、验收结论、整改 |
| RFP | 批准、发送、收到回复 |
| 报价 | 收到 |
| 客户总报价 | 发送、确认 |
| 质询函 | 发送、回复、关闭 |

非法流转统一抛出 `FlowError`，API 返回：

```json
{ "code": "invalid_transition", "message": "当前状态不允许该操作：..." }
```

HTTP 状态码为 409。

### 仍需注意

1. 有些步骤按设计不改项目 `status`，例如客户确认需求、客户确认总报价；阶段推进仍由后续业务动作触发。
2. 对话可以无限继续，但只有引导条/右侧业务按钮能推进阶段。
3. 客户确认需求目前不强制阻止生成建议书；PM 可以在客户确认前生成，后续可加门禁。
4. 归档要求“全部节点通过 + 客户确认 + 无未关闭重大发现”，归档时统一校验。

---

## 8. 一句话总结

```text
客户建项+问卷 → PM 诊断(任务/需求) → PM 生成建议书 → 客户确认 → 选服务/询价/报价
→ PM 生成合同 → 客户+服务商确认 → 履约/审查/专家验收 → PM 归档
```

阶段推进由“业务动作”控制，不由聊天控制。
