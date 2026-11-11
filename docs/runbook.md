# 运行手册（MVP / A 项）

## 1. 环境要求

- Windows 10/11
- Python 3.10+
- Node.js 18+（当前验证 22.15.1）
- 无需 Redis、Docker、PostgreSQL

## 2. 首次安装

```cmd
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env

cd ..\frontend
npm install
```

`.env` 中必须填写 `AI_API_KEY`；留空时 AI 接口返回 503，非 AI 页面仍可使用。
`AI_MODEL` 必须填写服务商控制台中的实际模型 ID；若返回 400/404，先核对模型名与 `AI_BASE_URL`。

## 3. 初始化数据

```cmd
cd backend
.venv\Scripts\python.exe -m app.seeds.seed
```

预期输出：

```json
{
  "config_items": 12,
  "users": 6,
  "providers": 10,
  "task_templates": 30,
  "knowledge_chunks": 140,
  "projects": 2,
  "tasks": 60,
  "findings": 16,
  "rfps": 31,
  "quotes": 31,
  "documents": 10,
  "facts": 10,
  "knowledge_documents": 9
}
```

重置演示项目：

```cmd
.venv\Scripts\python.exe -m app.seeds.seed --reset-demo
```

完全重建数据库：

```cmd
.venv\Scripts\python.exe -m app.seeds.seed --drop
```

> 旧数据库升级：后端启动时会自动为已存在的表补齐新增列；随后执行一次 `python -m app.seeds.seed` 补账号与归属关系。仅当表结构冲突或需要完全重建时使用 `--drop`。

## 4. 启动

后端：

```cmd
cd backend
.venv\Scripts\waitress-serve.exe --port=5000 wsgi:app
```

前端：

```cmd
cd frontend
npm run dev
```

访问：

- 前端：http://localhost:5173
- 健康检查：http://localhost:5000/api/health

## 5. 内置账号

| 账号 | 密码 | 角色 |
| --- | --- | --- |
| client@demo.local | demo1234 | 客户 |
| pm@demo.local | demo1234 | PM |
| lawyer@demo.local | demo1234 | 复核律师 |
| admin@demo.local | demo1234 | 管理员 |
| provider@demo.local | demo1234 | 服务商（/provider） |
| expert@demo.local | demo1234 | 验收专家（/expert） |

### 5.1 登录与令牌调试

```cmd
curl -X POST http://127.0.0.1:5000/api/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"pm@demo.local\",\"password\":\"demo1234\"}"
```

返回 `data.token` 后：

```cmd
curl http://127.0.0.1:5000/api/auth/me ^
  -H "Authorization: Bearer <JWT>"

curl -X POST http://127.0.0.1:5000/api/access-tokens ^
  -H "Authorization: Bearer <JWT>" ^
  -H "Content-Type: application/json" ^
  -d "{\"project_id\":\"<PROJECT_ID>\",\"role_type\":\"client\",\"subject_id\":\"client-a\"}"
```

`role_type` 只接受 `client`、`provider`、`expert`。返回的 `data.token` 仅在创建时出现一次，数据库只存哈希。

外部链接访问：

```cmd
curl http://127.0.0.1:5000/api/link/<TOKEN>/whoami
curl http://127.0.0.1:5000/api/link/<TOKEN>/project
```

### 5.2 对话与产物

创建会话：

```cmd
curl -X POST http://127.0.0.1:5000/api/projects/<PROJECT_ID>/conversations ^
  -H "Authorization: Bearer <JWT>" ^
  -H "Content-Type: application/json" ^
  -d "{}"
```

流式对话（`-N` 关闭缓冲）：

```cmd
curl -N -X POST http://127.0.0.1:5000/api/chat ^
  -H "Authorization: Bearer <JWT>" ^
  -H "Content-Type: application/json" ^
  -d "{\"conversation_id\":\"<CONVERSATION_ID>\",\"message\":\"请生成任务地图\"}"
```

产物面板：

```cmd
curl "http://127.0.0.1:5000/api/projects/<PROJECT_ID>/artifacts?type=tasks" ^
  -H "Authorization: Bearer <JWT>"
```

可用 `type`：`facts`、`tasks`、`proposal`、`quotes`、`milestones`、`findings`。

### 5.3 阶段 1：诊断与需求确认

上传资料（txt/md/docx/文本型 pdf，默认上限 50MB）：

```cmd
curl -X POST http://127.0.0.1:5000/api/projects/<PROJECT_ID>/documents ^
  -H "Authorization: Bearer <JWT>" ^
  -F "file=@D:\path\to\file.docx"
```

抽取事实、生成追问、提交回答：

```cmd
curl -X POST http://127.0.0.1:5000/api/projects/<PROJECT_ID>/facts/extract ^
  -H "Authorization: Bearer <JWT>"

curl -X POST http://127.0.0.1:5000/api/projects/<PROJECT_ID>/interview ^
  -H "Authorization: Bearer <JWT>" ^
  -H "Content-Type: application/json" ^
  -d "{\"conversation_id\":\"<CONVERSATION_ID>\"}"

curl -X POST http://127.0.0.1:5000/api/projects/<PROJECT_ID>/interview/answers ^
  -H "Authorization: Bearer <JWT>" ^
  -H "Content-Type: application/json" ^
  -d "{\"answers\":[{\"question\":\"是否已确定园区外买地？\",\"answer\":\"不知道\"}]}"
```

生成任务地图（租厂房 / 园区外买地）：

```cmd
curl -X POST http://127.0.0.1:5000/api/projects/<PROJECT_ID>/tasks/refresh ^
  -H "Authorization: Bearer <JWT>" ^
  -H "Content-Type: application/json" ^
  -d "{\"scenario\":\"land_purchase\"}"

curl http://127.0.0.1:5000/api/projects/<PROJECT_ID>/task-graph ^
  -H "Authorization: Bearer <JWT>"
```

生成需求确认书与客户确认链接：

```cmd
curl -X POST http://127.0.0.1:5000/api/projects/<PROJECT_ID>/requirement ^
  -H "Authorization: Bearer <JWT>"

curl -X POST http://127.0.0.1:5000/api/access-tokens ^
  -H "Authorization: Bearer <JWT>" ^
  -H "Content-Type: application/json" ^
  -d "{\"project_id\":\"<PROJECT_ID>\",\"role_type\":\"client\",\"subject_id\":\"client-a\"}"
```

浏览器打开 `http://localhost:5173/link/<TOKEN>`，即可查看并确认需求范围。

### 5.4 阶段 2：项目建议书

知识库检索：

```cmd
curl "http://127.0.0.1:5000/api/knowledge/search?q=BOI%%20投资优惠&country=TH&limit=3" ^
  -H "Authorization: Bearer <JWT>"
```

生成、审核、发送建议书：

```cmd
curl -X POST http://127.0.0.1:5000/api/projects/<PROJECT_ID>/proposals ^
  -H "Authorization: Bearer <JWT>"

curl -X POST http://127.0.0.1:5000/api/proposals/<PROPOSAL_ID>/review ^
  -H "Authorization: Bearer <JWT>"

curl -X POST http://127.0.0.1:5000/api/proposals/<PROPOSAL_ID>/send ^
  -H "Authorization: Bearer <JWT>"
```

创建客户链接并确认：

```cmd
curl -X POST http://127.0.0.1:5000/api/access-tokens ^
  -H "Authorization: Bearer <JWT>" ^
  -H "Content-Type: application/json" ^
  -d "{\"project_id\":\"<PROJECT_ID>\",\"role_type\":\"client\",\"subject_id\":\"client-a\"}"
```

浏览器打开 `http://localhost:5173/proposal-link/<TOKEN>`，客户可确认或提交修改意见。

### 5.5 阶段 3–4：选服务、询价、报价

保存服务选择（PM 必须填原因）：

```cmd
curl -X POST http://127.0.0.1:5000/api/projects/<PROJECT_ID>/selection ^
  -H "Authorization: Bearer <JWT>" ^
  -H "Content-Type: application/json" ^
  -d "{\"codes\":[\"T11\",\"T14\"],\"override_reason\":\"客户口头选择\"}"
```

生成候选与询价书：

```cmd
curl -X POST http://127.0.0.1:5000/api/projects/<PROJECT_ID>/candidates/generate ^
  -H "Authorization: Bearer <JWT>" ^
  -H "Content-Type: application/json" ^
  -d "{\"task_codes\":[\"T11\"]}"

curl -X POST http://127.0.0.1:5000/api/projects/<PROJECT_ID>/rfps ^
  -H "Authorization: Bearer <JWT>" ^
  -H "Content-Type: application/json" ^
  -d "{\"task_codes\":[\"T11\"]}"
```

批准并发送 RFP：

```cmd
curl -X POST http://127.0.0.1:5000/api/rfps/<RFP_ID>/approve ^
  -H "Authorization: Bearer <JWT>"

curl -X POST http://127.0.0.1:5000/api/rfps/<RFP_ID>/send ^
  -H "Authorization: Bearer <JWT>"
```

服务商报价页：`http://localhost:5173/rfp-link/<RFP_TOKEN>`。

生成总报价与客户确认链接：

```cmd
curl -X POST http://127.0.0.1:5000/api/projects/<PROJECT_ID>/client-quotes ^
  -H "Authorization: Bearer <JWT>" ^
  -H "Content-Type: application/json" ^
  -d "{\"management_fee_rate\":0.175}"

curl -X POST http://127.0.0.1:5000/api/client-quotes/<CLIENT_QUOTE_ID>/send ^
  -H "Authorization: Bearer <JWT>"
```

客户确认页：`http://localhost:5173/client-quote-link/<TOKEN>`；
客户选择页：`http://localhost:5173/selection-link/<TOKEN>`。

### 5.6 阶段 5：合同与节点

生成合同（要求客户总报价已确认、已选服务且已有报价）：

```cmd
curl -X POST http://127.0.0.1:5000/api/projects/<PROJECT_ID>/contracts ^
  -H "Authorization: Bearer <JWT>"
```

PM 复核：

```cmd
curl -X POST http://127.0.0.1:5000/api/contracts/<CONTRACT_ID>/review ^
  -H "Authorization: Bearer <JWT>"
```

客户确认：创建 client 令牌后打开
`http://localhost:5173/contract-link/<TOKEN>`，或：

```cmd
curl -X POST http://127.0.0.1:5000/api/link/<TOKEN>/contract/confirm
```

服务商确认：创建 provider 令牌时必须把 `subject_id` 设为服务商 ID：

```cmd
curl -X POST http://127.0.0.1:5000/api/access-tokens ^
  -H "Authorization: Bearer <JWT>" ^
  -H "Content-Type: application/json" ^
  -d "{\"project_id\":\"<PROJECT_ID>\",\"role_type\":\"provider\",\"subject_id\":\"<PROVIDER_ID>\"}"
```

打开 `http://localhost:5173/contract-link/<PROVIDER_TOKEN>` 确认。
只有客户确认且全部服务商确认后，合同才变为 `active`，项目进入 `executing`。

### 5.7 阶段 6：履约、审查与验收

看板：

```cmd
curl http://127.0.0.1:5000/api/projects/<PROJECT_ID>/board ^
  -H "Authorization: Bearer <JWT>"
```

提交交付物、PM 初审、运行审查：

```cmd
curl -X POST http://127.0.0.1:5000/api/milestones/<MILESTONE_ID>/submission ^
  -H "Authorization: Bearer <JWT>" ^
  -H "Content-Type: application/json" ^
  -d "{\"note\":\"服务商答复文本\"}"

curl -X POST http://127.0.0.1:5000/api/milestones/<MILESTONE_ID>/pm-review ^
  -H "Authorization: Bearer <JWT>" ^
  -H "Content-Type: application/json" ^
  -d "{\"decision\":\"accept\"}"

curl -X POST http://127.0.0.1:5000/api/milestones/<MILESTONE_ID>/review ^
  -H "Authorization: Bearer <JWT>" ^
  -H "Content-Type: application/json" ^
  -d "{}"
```

生成质询函 → 律师批准 → 发送：

```cmd
curl -X POST http://127.0.0.1:5000/api/projects/<PROJECT_ID>/query-letters ^
  -H "Authorization: Bearer <JWT>" ^
  -H "Content-Type: application/json" ^
  -d "{\"milestone_id\":\"<MILESTONE_ID>\"}"

curl -X POST http://127.0.0.1:5000/api/query-letters/<LETTER_ID>/approve ^
  -H "Authorization: Bearer <LAWYER_JWT>"

curl -X POST http://127.0.0.1:5000/api/query-letters/<LETTER_ID>/send ^
  -H "Authorization: Bearer <JWT>"
```

服务商回复页：`http://localhost:5173/query-link/<PROVIDER_TOKEN>`
（令牌 `subject_id` 必须等于质询函的 provider_id）。

专家邀请与验收：

```cmd
curl -X POST http://127.0.0.1:5000/api/milestones/<MILESTONE_ID>/expert-invite ^
  -H "Authorization: Bearer <JWT>"

curl -X POST http://127.0.0.1:5000/api/milestones/<MILESTONE_ID>/finalize ^
  -H "Authorization: Bearer <JWT>"
```

专家评分页：`http://localhost:5173/expert-link/<EXPERT_TOKEN>`。
只有专家评分锁定后才能汇总；结论为 passed/conditional 时解锁依赖任务。

### 5.8 阶段 7：复盘、归档与指标

生成复盘、查看指标与报价基准：

```cmd
curl -X POST http://127.0.0.1:5000/api/projects/<PROJECT_ID>/retrospective ^
  -H "Authorization: Bearer <JWT>"

curl http://127.0.0.1:5000/api/projects/<PROJECT_ID>/metrics ^
  -H "Authorization: Bearer <JWT>"

curl "http://127.0.0.1:5000/api/benchmarks?country=TH&task_code=T11" ^
  -H "Authorization: Bearer <JWT>"

curl "http://127.0.0.1:5000/api/knowledge/qa?q=BOI" ^
  -H "Authorization: Bearer <JWT>"
```

生成归档包（要求所有节点通过、客户确认、无未关闭重大发现）：

```cmd
curl -X POST http://127.0.0.1:5000/api/projects/<PROJECT_ID>/archives ^
  -H "Authorization: Bearer <JWT>"

curl http://127.0.0.1:5000/api/projects/<PROJECT_ID>/archives ^
  -H "Authorization: Bearer <JWT>"

curl -o archive.zip http://127.0.0.1:5000/api/archives/<ARCHIVE_ID>/download ^
  -H "Authorization: Bearer <JWT>"
```

归档后项目所有写接口返回 409。管理员重置演示数据：

```cmd
curl -X POST http://127.0.0.1:5000/api/admin/demo/reset ^
  -H "Authorization: Bearer <ADMIN_JWT>"
```

## 6. 测试

```cmd
cd backend
.venv\Scripts\python.exe -m pytest
```

当前 108 项测试覆盖：

- 24 张表齐全
- 种子幂等与重置
- 仅泰国/制造业/自有投资启用
- 9 个 RAG 文档切块与字符区间
- 健康检查与配置接口
- 登录、错误密码、过期/无效 JWT
- 一次性令牌生成、哈希存储、过期、作废、IP 记录
- 角色限制与项目级令牌隔离
- 审计日志写入
- 文档上传与解析（txt/docx/扫描 PDF 拒绝/超限/类型）
- 事实抽取、引用核对、幂等
- 访谈 5 问/3 轮限制、未知回答不阻断
- 任务地图：关键路径、租地与买地变体、模板外任务、循环依赖
- 需求确认书生成、客户令牌确认、重复确认不覆盖
- RAG 关键词检索、同义词、国家过滤、知识块读取
- 建议书 8 章、预算区间、引用、版本、审核、发送、修改、客户确认、权限
- 服务目录、依赖提示、PM 代选原因、客户选择链接
- 客户建项问卷、条件显示、32 条任务规则、问卷欢迎消息
- 统一状态机：项目七阶段、建议书、合同、节点、RFP、报价、质询函
- 候选服务商 5 家/任务、新发现标签、拒绝原因、手工添加
- RFP 批准/发送拦截、链接打开追踪、报价文本解析、比价、总报价与管理费
- 总报价版本、发送、客户确认、重复确认不覆盖
- 合同生成、节点覆盖、文件哈希、PM 复核、客户/服务商双确认、未双确认不能执行
- 端到端彩排脚本：七阶段全流程、指标、归档、重置

端到端彩排（连续 3 次应输出 `REHEARSAL OK`）：

```cmd
backend\.venv\Scripts\python.exe eval\demo_rehearsal.py
```

## 7. 数据位置

| 内容 | 路径 |
| --- | --- |
| SQLite | `data/oversea.db` |
| 上传文件 | `data/uploads/` |
| 归档 | `data/archives/` |
| 种子数据 | `backend/app/seeds/` |

## 8. 当前完成范围（A + B + C + D + E + F + G + H + I）

- A01 Flask + Vue 骨架、健康检查
- A02 24 张表（含 conversations、messages、candidates、client_quotes、performance_events、archives）与 SQLite WAL
- A03 配置项、6 个账号、10 家服务商
- A04 30 项任务模板
- A05 9 个 RAG 文档切块（140 块）
- A06 演示项目、5 份文档、5 条事实、8 条发现、1 份 RFP 与报价
- A07 幂等种子与 `--reset-demo`
- B01 登录、JWT 签发/过期、当前用户接口
- B02 一次性令牌：哈希存储、过期、作废、IP 与访问时间
- B03 角色装饰器、项目级令牌隔离、报价/审批权限 helper
- B04 审计日志 helper（登录、令牌创建/作废已接入）
- C01 AIProvider：DeepSeek 调用、JSON 输出、重试 1 次、无 Key 返回 503
- C02 `/api/chat` SSE 流式对话、意图路由、消息持久化
- C03 服务端分块流式输出
- C04 前端登录页与三栏 ChatShell
- C05 右侧产物面板、事实来源跳转高亮、全屏
- D01 文档上传与解析、50MB 限制
- D02 AI 访谈：5 问/轮、3 轮上限、未知回答不阻断
- D03 事实抽取与引用核对（归一化 + 3-gram 0.85）
- D04 任务地图：30 项模板、依赖、关键路径、租地/买地变体、模板外任务
- D05 任务图 UI、关键路径高亮、变体差异提示
- D06 需求确认书、打印、客户链接确认、IP/时间记录、重复确认不覆盖
- E01 RAG 关键词检索、同义词、国家/行业过滤、时效提示
- E02 建议书 8 章、预算区间与依据、RAG 引用、不披露服务商
- E03 建议书版本、PM 审核、发送、客户确认/修改、客户意见
- E04 建议书 UI、章节导航、版本选择与章节级对比、打印、客户链接页
- F01 服务目录、客户选择、依赖提示、PM 代选原因
- F02 候选服务商匹配、5 家/任务、新发现、拒绝与手工添加
- F03 中英 RFP、批准与发送、服务商链接、打开追踪
- F04 报价表单/文本解析、PM 修正
- F05 同口径比价、最低价与价差
- F06 客户总报价版本、管理费率、发送、客户确认
- F07 报价 UI、客户选择/RFP/总报价三个公开链接页
- G01 合同/委托确认单、SLA、节点表、服务商委托单、文件哈希
- G02 PM 复核、客户确认、服务商确认、未双确认不能进入执行
- G03 合同 UI、确认记录、打印、合同公开确认页 `/contract-link/:token`
- H01 交付看板、逾期与关键路径、阶段汇总
- H02 到期/逾期提醒等级、催办草稿
- H03 审查规则引擎：七类检查、结论分级、引用核对、法律类标记
- H04 AI 审查调用与发现落库
- H05 三栏审查 UI、原文高亮、筛选与详情
- H06 质询函生成、律师批准/驳回、发送拦截、服务商逐条回复、关闭
- H07 交付物提交（PM 演示 + 服务商令牌接口）、PM 初审退回
- H08 专家邀请、盲评载荷脱敏
- H09 四维加权评分、意见必填、提交锁定
- H10 验收结论、整改、通过后解锁依赖任务、履约事件
- H11 节点验收 UI、专家评分页、客户确认记录
- I01 复盘报告、报价基准、已关闭质询检索
- I02 归档 manifest、zip、哈希、保管期限、项目只读
- I03 三项可算指标 + 两项“数据不足”
- I04 归档 UI、下载、只读状态、一键重置演示

J 项（测试补齐、文档与交付）尚未完成。
