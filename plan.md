# AI 原生专业服务总包平台 · MVP 演示版计划

版本：V0.3  
日期：2026-11-08  
周期：5 个工作日  
目标：可本地运行、可一键重置、10 分钟演示的七阶段闭环。

---

## 1. 目标

用一个演示项目跑通：

**需求诊断 → 项目建议书 → 选服务 → 询价报价 → 签约与节点 → 履约与节点验收 → 归档**

三条底线：

1. AI 需配置 DeepSeek API Key；无 Key 时 AI 接口明确返回 503，不静默降级。
2. 法律类质询未经复核律师批准，后端拒绝发送。
3. 节点未通过，后续依赖任务保持锁定。

---

## 2. 范围

### 做

- 项目创建（国家/行业/出海方式配置化，仅启用泰国/制造业/自有投资）
- 对话式工作台：三栏布局、流式回复、引用 chip、右侧产物面板
- 文本上传与解析（txt/docx/文本型 PDF），事实表 + 原文引用跳转
- 30 项任务地图、依赖、关键路径
- 1 轮 AI 追问清单
- 项目建议书（8 章、预算区间、版本化、客户确认）
- 服务勾选、候选服务商（种子库）、中英 RFP、独立链接
- 报价录入/粘贴抽取、比价、客户总报价（40 万 + 管理费 7 万）
- 合同与节点双确认、交付看板、节点验收（1 名专家盲评）
- 答复审查、结论分级、法律类质询审批、逐条关闭
- 归档包（manifest + zip + 哈希）、项目只读
- 一键重置演示数据

### 不做

- 真实电子签名、支付、开票
- 真实邮件发送（改为复制链接）
- OCR、扫描件解析
- 向量检索、真实网络抓取
- 多专家汇总、服务包、移动端
- 完整评测体系
- 生产级并发与高可用

---

## 3. 技术栈

| 层 | 选型 |
| --- | --- |
| 前端 | Vue 3 + Vite + Element Plus + ECharts |
| 对话 UI | 自建 ChatShell（三栏）+ markdown-it + DOMPurify |
| 后端 | Flask + SQLAlchemy |
| 数据库 | SQLite 单文件 |
| 鉴权 | JWT（内部账号）+ 一次性令牌（外部链接） |
| 异步 | 无。AI 对话用流式响应，其余同步 |
| AI | DeepSeek V4.1 Flash（OpenAI 兼容接口） |
| PDF | 浏览器打印 |
| 归档 | Python zipfile |
| 测试 | pytest |
| 运行 | waitress 单进程 |

不引入 Redis、Celery、Docker、Alembic、pgvector。

### 3.1 AI 接入（DeepSeek V4.1 Flash）

- 走 OpenAI 兼容接口，统一在 `backend/app/ai/provider.py` 封装。
- 对话类步骤用流式（`stream=true`），结构化步骤用 JSON 输出。
- 模型名以服务商控制台为准；若走聚合网关，填网关提供的模型 ID（如 `deepseek-v4.1-flash`）。
- 配置：

```env
AI_BASE_URL=https://api.deepseek.com
AI_MODEL=deepseek-v4.1-flash
AI_API_KEY=
AI_TIMEOUT=60
AI_STREAM_DELAY_MS=10
```

- 未配置 `AI_API_KEY` 时，AI 接口返回 503，界面提示配置 Key。
- 调用失败重试 1 次；仍失败返回明确错误，不执行本地回退。
- 结构化步骤使用 JSON 输出并由后端校验；对话使用流式文本。
- 记录每次调用的步骤、模型、耗时、token 数到日志，MVP 不建独立表。
- 提示词放 `backend/app/ai/prompts/`，文件名带版本号。

### 3.2 界面风格

- 对话优先，不做传统后台表格页。
- 参考 DeepSeek / WorkBuddy：浅灰底、白色内容卡、细边框、无重阴影、单一强调色。
- 主界面三栏，见第 7 节。
- Markdown 渲染支持表格、列表、代码、引用；引用以可点击 chip 展示。
- 所有 AI 输出带“草稿”标签，必须 PM 点确认才能进入下一步。

目录：

```text
backend/app/{api,models,services,ai,seeds}
backend/tests
frontend/src/{views,components,api,router}
rag/
docs/
```

---

## 4. 七阶段演示流程

所有阶段都在同一个对话工作台完成：用户在中间对话，右侧产物面板随阶段切换。

| 阶段 | 对话交互 | 右侧产物 | 演示点 |
| --- | --- | --- | --- |
| 1 需求诊断 | 输入“我要在泰国建厂…”，附上资料；系统流式追问 | 事实卡、追问卡、30 项任务地图 | 引用 chip 跳原文；租厂房改买地后任务图变化 |
| 2 建议书 | 点击“生成项目建议书” | 8 章建议书、预算区间 | 预算标注“非正式报价” |
| 3 选服务与询价 | 客户在链接页勾选；PM 对话确认 | 服务选择、5 家候选、中英 RFP | 1 家新发现；缺前置提示 |
| 4 报价比价 | 服务商链接提交；PM 输入“对比报价” | 并排比价表、总报价 | 40 万 + 7 万；改费率重算 |
| 5 签约节点 | 输入“生成合同和节点”，发双方链接 | 委托确认单、SLA、节点表 | 未双确认不能执行 |
| 6 履约验收 | 看板卡 + “生成催办” + 专家链接 | 节点状态、交付物、专家评分 | 盲评；不通过不解锁 |
| 6 审查质询 | 上传答复，输入“审查这份答复” | 发现列表、质询函 | 律师未批准不能发；无来源降级 |
| 7 归档 | 输入“归档项目” | 复盘、报价基准、归档包 | zip 离线可打开 |

建议书固定 8 章：项目理解 / 事实与待确认 / 服务清单 / 路线图与关键路径 / 里程碑与验收标准 / 预算区间 / 风险与前置条件 / 下一步。

---

## 5. 五条硬规则（必须有测试）

| # | 规则 | 实现 |
| --- | --- | --- |
| 1 | 法律类质询未经复核律师批准不能发送 | 发送接口校验 `approval_status=approved` 且审批人角色为律师 |
| 2 | “已核实错误”必须附可点击来源，否则降级为“需进一步核实” | `classify_conclusion()` 统一判断 |
| 3 | 节点未通过不能解锁依赖任务 | 验收通过时才写入任务解锁 |
| 4 | 专家接口不返回服务商名称、报价、内部备注 | 序列化白名单，不靠前端隐藏 |
| 5 | 向导选项只读配置表，不硬编码“泰国/制造业/自有投资” | `config_items.enabled` |

外加两条一般规则：

- 引用无法核对的发现不得进入质询函。
- 归档后项目写接口返回 409。

---

## 6. 数据模型（24 张表）

| 表 | 关键字段 |
| --- | --- |
| users | email, password_hash, role |
| config_items | type, code, name, enabled, sort |
| access_tokens | token, role_type, project_id, subject_id, expires_at, revoked |
| projects | client_name, contact, country, industry, entry_mode, phase, status, goal_text, investment_cents, selected_services_json, total_quote_json, archived |
| conversations | project_id, title, created_by |
| messages | conversation_id, project_id, role, content, intent, citations_json, model, cached |
| documents | project_id, filename, path, text_content |
| facts | project_id, key, value, status, doc_id, page, char_start, char_end, quote |
| task_templates | code, name, stage_no, duration_days, fee_min_cents, fee_max_cents, predecessor_codes_json, deliverables_json, required_info_json, legal_basis, last_reviewed |
| tasks | project_id, code, name, stage_no, status, is_critical, locked, due_date |
| proposals | project_id, version, status, content_json, client_confirmed_at, client_confirm_ip |
| providers | name, type, city, description, evidence_level, source_type |
| candidates | project_id, task_id, provider_id, match_score, reason, evidence_json, source_type, status, reject_reason |
| rfps | project_id, task_id, provider_id, content_zh, content_en, status, token, opened_at |
| quotes | rfp_id, provider_id, task_id, currency, amount_cents, items_json, assumptions, exclusions, status |
| client_quotes | project_id, version, provider_amount_cents, lawyer_amount_cents, management_fee_rate, management_fee_cents, total_cents, status, confirmed_at, confirm_ip |
| contracts | project_id, version, total_cents, terms_json, status, client_confirmed_at, provider_confirmed_at, file_hash |
| milestones | project_id, task_id, name, deliverable, acceptance_criteria, due_date, status, acceptor_type, expert_name, expert_scores_json, expert_comment, rounds |
| findings | project_id, category, severity, conclusion_level, quote_text, reason, question_zh, question_en, is_legal, sources_json, reviewer_status |
| query_letters | project_id, provider_id, finding_ids_json, content, approval_status, approved_by, status |
| knowledge_chunks | doc_code, title, heading_path, content, char_start, char_end |
| performance_events | project_id, provider_id, milestone_id, type, dimension, value, note, occurred_at |
| archives | project_id, version, manifest_json, zip_path, file_hash, retention_until, generated_by |
| audit_logs | project_id, actor, action, object_type, object_id, detail_json, created_at |

约定：

- 金额用整数分。
- 任务依赖存 `task_templates.predecessor_codes_json`，不建关系表。
- 客户选择、总报价直接存 `projects` 的 JSON 字段，不做多表版本。
- 专家评分直接存 `milestones`。
- 归档信息存 `projects` + 文件系统。
- 主键 UUID 字符串。

---

## 7. 界面（对话式工作台）

只做一个主界面，三栏布局：

```text
┌─────────┬──────────────────────────────┬───────────────┐
│ 项目/会话 │  项目名 + 七阶段步骤条          │  产物面板       │
│ 列表     │                              │  事实 / 任务     │
│ 新建对话  │  消息流（用户 / AI 流式）        │  建议书 / 报价   │
│         │                              │  节点 / 发现     │
│         │  ┌────────────────────────┐  │               │
│         │  │ 输入框  附件  发送       │  │               │
└─────────┴──────────────────────────────┴───────────────┘
```

- 左栏 220–260px：新建对话、项目列表、最近会话、用户菜单，可折叠。
- 中栏：顶部项目名与七阶段步骤条；消息流；底部输入框带附件与快捷指令。
- 右栏 360–480px：产物面板，Tab 切换事实 / 任务 / 建议书 / 报价 / 节点 / 发现；点击卡片全屏查看。
- 全屏产物页：建议书、报价单、合同、归档，统一打印样式。
- 公共链接页：单栏，沿用同一视觉体系，按令牌显示客户 / 服务商 / 专家内容。
- 登录：居中卡片，无背景图。

### 视觉规范

| 项 | 值 |
| --- | --- |
| 背景 / 卡片 | `#F7F8FA` / `#FFFFFF` |
| 边框 | `#E6E8EB` |
| 主文字 / 次文字 | `#1F2329` / `#6B7280` |
| 强调色 | `#4D6BFE`（仅按钮、链接、选中态） |
| 字体 | system-ui，正文 14px / 1.6 |
| 圆角 | 10px |
| 间距 | 8 / 12 / 16 / 24 |
| 阴影 | 无或极轻，不用渐变和装饰插图 |

### 消息规范

- 用户消息右对齐、浅灰气泡。
- AI 消息左对齐、无气泡、头像 + Markdown，流式光标。
- 步骤执行时在消息内显示“正在检索知识库…”“正在生成任务地图…”。
- 引用显示为 chip：`rag/01 · BOI 优惠`，点击右栏打开原文并高亮。
- 每条 AI 结果下方固定“草稿”标签与“确认 / 修改”按钮。

### 组件清单

`ChatShell`、`Sidebar`、`PhaseStepper`、`MessageList`、`MessageItem`、`Composer`、`ArtifactPanel`、`CitationChip`、`TaskGraph`、`ProposalView`、`QuoteTable`、`FindingList`、`ExpertForm`。

### 接口约定

- `POST /api/chat`：`text/event-stream` 流式返回；请求含项目 ID、消息、当前阶段。
- `GET /api/projects/{id}/artifacts?type=facts|tasks|proposal|quotes|milestones|findings`：右侧面板数据。
- 其余业务接口保持普通 JSON。

---

## 8. 种子数据

- 配置项：泰国/制造业/自有投资启用，越南/马来西亚/印尼/并购/合资置灰。
- 30 项任务模板：直接取 `典型案例.md` 第十二节，种子脚本内置。
- 服务商 10 家：泰国律所 4、中国律所 2、泰国会计师 2、BOI 顾问 1、人力机构 1。
- 演示项目：长三角汽车零部件企业，3,000 万美元投资，800 万美元设备出资，14 个月试产，总报价 40 万 + 管理费 7 万。
- 8 条审查发现：取 `典型案例.md` 第十三节。
- AI 输出由真实 DeepSeek 生成，测试使用测试替身，不进入生产运行。
- 内置账号：客户 / PM / 律师 / 管理员 / 服务商 / 验收专家，密码 `demo1234`。

40 万 / 7 万只是演示设定，不写入历史报价基准。

---

## 9. 五天排期

| 天 | 内容 | 当天可演示 |
| --- | --- | --- |
| D1 | 前后端骨架、24 张表、种子、登录、配置、项目向导、对话式三栏外壳 | 登录 → 新建项目 → 对话界面可发消息 |
| D2 | DeepSeek 接入与流式输出、文档解析、事实抽取、引用跳转、任务地图与关键路径 | 阶段 1 在对话中完整走通 |
| D3 | 建议书、RAG 关键词检索、服务勾选、候选、RFP、报价比价、总报价 | 阶段 2–4 完整，产物面板可用 |
| D4 | 合同节点双确认、看板、答复审查、分级、质询审批 | 阶段 5–6 主流程 |
| D5 | 专家盲评、解锁、归档、一键重置、5 条规则测试、界面打磨、彩排 | 10 分钟脚本跑通 3 次 |

延期时按此顺序砍：建议书版本对比 → 英文 RFP → 催办草稿 → 候选证据展开。  
不砍：五条硬规则、状态机、重置。

---

## 10. 演示脚本（10 分钟）

| 时间 | 动作 |
| --- | --- |
| 0:00 | 登录，新建泰国/制造业/自有投资项目 |
| 0:40 | 在对话框输入建厂目标并附资料，AI 流式回复事实与追问 |
| 2:00 | 右侧打开 30 项任务地图，点击引用跳原文 |
| 2:40 | 点击“生成建议书”，展示 8 章与预算区间 |
| 3:20 | 输入“改为园区外买地”，展示任务图变化 |
| 4:00 | 客户链接勾选服务，生成 RFP 与服务商链接 |
| 5:00 | 服务商报价，对话输入“对比报价”，生成 40 万 + 7 万总报价 |
| 6:00 | 客户确认，生成合同与节点，双方确认 |
| 6:50 | 打开交付看板，提交交付物 |
| 7:30 | 专家盲评打分，通过后解锁后续任务 |
| 8:20 | 上传律师答复并审查，律师直接发送法律类质询被拦截，批准后发送 |
| 9:20 | 归档并打开 zip，一键重置 |

---

## 11. 验收

1. 10 分钟脚本连续 3 次跑通。
2. 配置 DeepSeek API Key 后，对话流式输出正常；无 Key 时明确提示。
3. 五条硬规则测试全绿。
4. 向导只显示启用项。
5. 节点不通过时依赖任务锁定。
6. 专家接口无服务商与报价字段。
7. 对话首屏 2 秒内可用，流式输出正常，引用 chip 可跳原文。
8. 归档 zip 可离线打开，归档后不可编辑。
9. 一键重置后回到初始状态。

---

## 12. 风险

| 风险 | 应对 |
| --- | --- |
| 5 天做不完 | 按第 9 节顺序砍功能，保五条规则与主流程 |
| DeepSeek 接口不可用或超时 | 重试 1 次后返回明确错误，不静默回退；演示前检查 Key 与网络 |
| 流式渲染不稳定 | 提供非流式兜底：一次性返回完整结果再逐字回放 |
| 聊天界面做过头 | 只用三栏 + 一张产物面板，不做主题定制、动画和移动端 |
| 扫描件无法解析 | 演示用文本型 PDF/docx，界面提示人工录入 |
| SQLite 并发 | 单进程 waitress |
| 演示数据被当成真实报价 | 所有预算/报价页面固定显示“演示数据，非正式报价” |

---

## 13. 交付物

- `backend/`、`frontend/`、`seeds/` 源代码
- `docs/runbook.md` 启动说明
- `docs/ui.md` 界面规范与组件说明
- `docs/demo-script.md` 演示脚本
- `pytest` 测试（五条硬规则 + 关键路径 + 总价计算）
- 种子数据
