# PD-ECR 系统 开发边界文档 V1.0

> 本文档取代此前的《PDCR 系统前后端交接与需求确认文档 V0.1》。
>
> **命名统一**：系统正式名称为 **PD-ECR**（Product Design – Engineering Change Request），代码命名空间为 `pd_ecr`。此前文档中的 "PDCR" 为笔误，全部更正为 **PD-ECR**。
>
> **本文档的定位**：这是一份「开发边界」文档，不是「需求愿望清单」。它的核心职责是划清四条线——
> **✅ 已实现**（代码在仓库里、可运行）｜**🟡 部分实现**（骨架有、需补齐）｜**⬜ 待开发**（本期要做、尚未动工）｜**❌ 本版不做**（明确排除，避免范围蔓延）。
>
> 每一项「已实现」都锚定到实际文件/接口，读者可直接核对。

---

## 0. 文档修订说明

| 项 | V0.1（旧） | V1.0（本文） |
|---|---|---|
| 命名 | PDCR | **PD-ECR**（与代码一致） |
| 结构 | 需求罗列，几乎全部「待确认/待设计」 | 每项能力带**现状列**，划清已实现/待开发边界 |
| 现状还原度 | 低——大量已实现能力被写成「待设计」 | 以代码为准，逐条锚定文件/接口 |
| 待确认项 | 混在正文，Q1–Q12 大半高优先级悬空 | 抽到 §12 决策日志，区分「阻塞项」与「可迭代项」 |

---

## 1. 系统概述与技术栈

PD-ECR 是一套结构化的工程变更请求（ECR）协同管理系统，覆盖变更的**识别 → AI 生成草稿 → 多部门确认 → 执行分派 → 审核 → 领导审批 → 实施 → 关闭**全生命周期，并内置 RAG 检索历史案例辅助生成。

| 层 | 技术 | 现状 |
|---|---|---|
| 后端 | FastAPI + SQLModel + Alembic | ✅ 已实现 |
| 数据库 | SQLite（开发）/ PostgreSQL（可切换，`USE_SQLITE` 开关） | ✅ 已实现 |
| 前端 | React + Vite + TanStack Router + Chakra UI | ✅ 已实现 |
| 认证 | JWT（pyjwt）+ pwdlib(argon2/bcrypt) | ✅ 已实现 |
| AI/LLM | Azure OpenAI（OpenAI 兼容端点）| ✅ 已实现 |
| RAG | sentence-transformers + FAISS + BM25（LangChain EnsembleRetriever）+ LangGraph 编排 | ✅ 已实现 |
| 审批编排 | 内置状态机（V1 不接外部流程引擎） | ✅ 已实现（Flowable/Activiti 已移除） |
| 邮件/通知 | emails + Jinja2 模板 | ✅ 已实现 |

---

## 2. 角色与权限（RBAC）

**现状：🟡 部分实现**——认证体系与角色模型已在代码中，权限**枚举已定义**，但细粒度的接口级鉴权校验需按下表补齐。

角色定义见 [models.py:26-31](../backend/app/models.py#L26-L31)（`User.pd_ecr_role` 字段）：

| 角色 (`pd_ecr_role`) | 含义 | 权限边界 | 现状 |
|---|---|---|---|
| `pd_ecr_manager` | 跨部门管理员 | 全部权限 | ✅ 已定义 |
| `department_leader` | 部长 | 管理本部门所有模块 | ✅ 已定义 |
| `department_member` | 部员 | 只编辑分配给自己的模块 | ✅ 已定义 |
| `reviewer` | 审核者 | 只读 + 审核 | ✅ 已定义 |
| `is_superuser` | 系统超级管理员 | 平台级全权 | ✅ 已实现（[models.py:18](../backend/app/models.py#L18)） |

**已实现**：登录/登出/找回密码（[login.py](../backend/app/api/routes/login.py)）、用户管理（[users.py](../backend/app/api/routes/users.py)）、`get_current_user` 依赖注入、超管校验。

**⬜ 待开发（本期）**：
- 各 PD-ECR 接口按 `pd_ecr_role` 做**行级/模块级**权限校验（当前部分接口仅校验登录态，未校验角色边界）。
- 「部员只能编辑分配给自己的模块」这条规则需在模块编辑/分派接口逐一落实。

**❌ 本版不做**：自定义角色、权限的运行时可视化配置（先用固定 4 角色）。

**🔲 待确认（见 §12-Q1）**：登录方式是自建账号体系还是对接企业 SSO / OneIDM。

---

## 3. 生命周期与状态机

**现状：✅ 已实现**——状态定义完整，共 **15 个状态**，远比 V0.1 提案更细。定义见 [models.py:213-229](../backend/app/models.py#L213-L229)。

```
draft（草稿）
  → generated（AI已生成）
  → submitted（已提交）
  → department_confirmation（部门确认中）
  → department_alignment（部门对齐）
  → execution_assignment（执行分派）
  → assignee_confirmation（执行人确认）
  → execution_in_progress（执行中）
  → in_review（评审中）
  → leader_review（领导审核）
  → changes_requested（要求修改，可回退）
  → approved（已批准）
  → implementation（实施中）
  → closed（已关闭）
  [cancelled（已取消）— 任意节点可进入]
```

**已实现的状态流转接口**（[pd_ecr.py](../backend/app/api/routes/pd_ecr.py)）：
- 通用流转：`POST /cases/{id}/transition` (:2052)
- 提交/发布部门/分派执行：`/cases/{id}/workflow/submit`(:2072)、`/workflow/publish-departments`(:2089)、`/workflow/assign-execution`(:2105)
- 我的任务：`GET /workflow/my-tasks` (:2127)
- 执行任务：确认分派/完成/要求修改 (:2135, :2148, :2165)
- 部门任务：确认/要求修改 (:2180, :2197)
- 领导任务：审核 `POST /workflow/leader-tasks/{id}/review` (:2212)

**⬜ 待开发**：状态机的**非法流转拦截**（当前允许通过 `/transition` 传任意目标态，建议加一张合法转移表约束）。

**🔲 待确认（§12-Q2）**：`changes_requested` 回退后是回到哪个节点、是否需要留痕版本。

---

## 4. 案例数据模型与模块

**现状：✅ 已实现**。

一个 PD-ECR 案例（`PdEcrCase`）默认拆成 **10 个模块**（[models.py:231-242](../backend/app/models.py#L231-L242)）：

| 模块 key | 名称 | 是否 AI 生成 |
|---|---|---|
| basic-information | 基本信息 | 部分 |
| change-description | 变更描述 | ✅ |
| reason-for-change | 变更原因 | ✅ |
| impact-analysis | 影响分析（8 维度） | ✅ |
| validation-plan | 验证与试运行计划 | ✅ |
| validation-result | 验证结果 | 人工 |
| implementation-plan | 实施计划 | ✅ |
| implementation-result | 实施结果 | 人工 |
| approval-signoff | 审批签核信息 | 人工 |
| close-summary | 关闭总结 | 人工 |

**已实现的模块接口**：模块列表/编辑/分派/提醒/重生成/应用生成结果（[pd_ecr.py](../backend/app/api/routes/pd_ecr.py) :2229–2404）、版本历史 `GET /cases/{id}/versions`(:2404)、活动日志 `GET /cases/{id}/activity`(:2434)。

**🔲 待确认（§12-Q3）**：模块是否可由管理员**动态增删/自定义**，还是固定这 10 个。

---

## 5. 影响分析（8 维度）

**现状：✅ 已实现**（AI 生成 + 自检重试）。

由 LangGraph 的 `impact_analysis_node` 生成，`impact_self_check` 节点校验是否覆盖全部 **8 个维度**，未覆盖则自动重试（最多 2 次）。见 [graph/nodes.py](../backend/app/rag/graph/nodes.py)。

**⬜ 待开发**：8 维度的**中文业务口径**需与业务方对齐并固化到 prompt（当前维度 key 已在 `IMPACT_KEYS`，但业务定义待确认）。

---

## 6. 文件上传与文档解析

**现状：✅ 已实现**。

- 上传：`POST /cases/upload-file` ([pd_ecr.py:2519](../backend/app/api/routes/pd_ecr.py#L2519))
- 历史案例导入：`POST /import/historical` (:2838)
- 源文档管理：预览/确认/删除 (:1171, :2798, :2817, :1194)
- PDF 解析：docling（[pyproject.toml:28](../backend/pyproject.toml#L28)）→ markdown

**🔲 待确认（§12-Q4）**：允许上传的文件类型/大小上限、是否做病毒扫描（企业合规）。

---

## 7. AI 生成与 RAG

**现状：✅ 已实现（已重建，端到端跑通）**。

**架构**：
```
离线建库 (app/rag/ingest/)
  源文档 → RecursiveCharacterTextSplitter 切分(chunk_size=800/overlap=120)
        → 本地 embedding → 双索引:
             ① raw FAISS (IndexFlatIP)          ② LangChain FAISS (MAX_INNER_PRODUCT)
在线检索 (app/rag/retrieval/)
  build_query → EnsembleRetriever[稠密 FAISS 0.4 + BM25 0.6, RRF 融合]
             → (可选)cross-encoder 重排 → top_k
编排 (app/rag/graph/, LangGraph)
  classify → retrieve → impact_analysis →(self_check 重试)→ validation_plan → implementation_plan
服务封装 (app/services/pd_ecr_rag_service.py)
  generate_pd_ecr() / agenerate_pd_ecr()   ← 后端直接 import 调用，无需 HTTP 接口
```

- Embedding：`paraphrase-multilingual-MiniLM-L12-v2`（384维，本地，离线）
- 检索接口：`retrieve_cases(request, top_k) -> list[RetrievedChunk]`（[retrieval/retriever.py](../backend/app/rag/retrieval/retriever.py)）
- LLM：Azure OpenAI，配置在 `.env`（`LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`）
- 相关接口：`POST /cases/generate-from-ai`(:1685)、`POST /generate-draft`(:6240)、`POST /retrieve`(:2871)、`POST /test-rag`(:6341)、知识库状态 `GET /knowledge-base/status`(:2601)

**已知局限（如实告知）**：小多语言 MiniLM 在本高度模板化的领域**稠密区分度弱**，实测 BM25 关键词更靠谱，故默认让 BM25 主导（0.4/0.6）。**质量提升的真正杠杆**是换更强 embedding（如 bge-large-zh）或启用 cross-encoder 重排（`app/rag/models/bge-reranker-base` 存在即自动启用）。

**⬜ 待开发/优化**：
- 放入更强 embedding 或 reranker 模型，回调稠密权重。
- AI 生成结果的**引用可追溯**（生成内容标注来自哪个历史案例 chunk）。

**🔲 待确认（§12-Q5）**：AI 生成的草稿是否**自动入向量库**沉淀为新知识（涉及数据质量与回流策略）。

---

## 8. 审批与流程编排

**现状：✅ 已实现（V1 内置状态机审批，已移除 Flowable/Activiti）**。

> **V1 决策（已拍板，Q6 关闭）**：审批链路完全由**代码内置状态机**驱动,**不接** Flowable / Activiti 等外部流程引擎。相关代码(`integrations/flowable/`、`pd_ecr_flowable_service.py`、`FLOWABLE_*` 配置、`flowable_*` 数据列)已整体移除,并新增迁移 `a1b2c3d4e5f6_drop_flowable_runtime_fields` 删除历史列,消除"内置状态机 vs 引擎"双写风险。

- 领导审批接口：`POST /cases/{id}/manager-approve`、`/manager-reject`、`/workflow/leader-tasks/{id}/review`
- 审批任务模型：`PdEcrApprovalTask` / `PdEcrLeaderReviewTask`（[models.py](../backend/app/models.py)）

**⬜ 待开发（本期）**：审批留痕/审计（谁、何时、何意见、批/退到哪个节点）。

**❌ 本版不做**：外部流程引擎（Flowable/Activiti）、运行时可配置审批路由/审批人矩阵。若未来出现"业务方自助配置审批流""按产品线/金额动态分叉"等需求再评估引入。

---

## 9. 通知与提醒

**现状：✅ 已实现**。

- 通知服务：[pd_ecr_notification_service.py](../backend/app/services/pd_ecr_notification_service.py)
- 邮件模板：`backend/app/email-templates/`
- 定时任务：[pd_ecr_schedule.py](../backend/app/services/pd_ecr_schedule.py)、到期提醒 `POST /notifications/run-due-reminders`(:2356)、模块提醒 `POST /cases/{id}/modules/{mid}/send-reminder`(:2329)

**🔲 待确认（§12-Q7）**：邮件里指向系统的**深链是否需要鉴权/一次性 token**（安全）；是否接企业邮件网关。

---

## 10. 前端页面清单

**现状：✅ 已实现**（TanStack Router，见 `frontend/src/routes/`）。

| 路由 | 页面 | 现状 |
|---|---|---|
| `/login` `/signup` `/recover-password` `/reset-password` | 认证 | ✅ |
| `/pd-ecr` | PD-ECR 首页 | ✅ |
| `/pd-ecr/dashboard` | 仪表盘 | ✅ |
| `/pd-ecr/cases` | 案例列表 | ✅ |
| `/pd-ecr/new` | 新建案例 | ✅ |
| `/pd-ecr/content` `/content/$moduleId` | 模块内容编辑 | ✅ |
| `/pd-ecr/drafts` | 草稿 | ✅ |
| `/pd-ecr/tasks` | 我的任务 | ✅ |
| `/pd-ecr/history-case` | 历史案例 | ✅ |
| `/pd-ecr/documents/$docId` | 文档详情 | ✅ |
| `/admin` `/settings` | 管理/设置 | ✅ |

**🔲 待确认（§12-Q8）**：是否需要**移动端/响应式**适配。

---

## 11. 集成与部署

| 项 | 现状 |
|---|---|
| 数据库切换（SQLite/PG） | ✅ 已实现（`USE_SQLITE`） |
| 环境配置（`.env`） | ✅ 已实现 |
| Sentry 监控 | ✅ 已接（sentry-sdk） |
| SSO / OneIDM 对接 | ⬜ 待开发（见 §12-Q1） |
| 产品主数据来源（PLM/ERP 等） | ⬜ 待开发（见 §12-Q9） |
| CI/CD、容器化部署 | 🔲 待确认（§12-Q10） |

**❌ 本版不做**：多租户、国际化多语言 UI（当前中英混排即可）。

---

## 12. 决策日志（待确认项）

> 规则：**阻塞项**必须在开发启动前拍板；**可迭代项**可先用默认值推进、后续调整。V0.1 的教训是把核心项长期悬空——这里明确标注优先级与默认假设。

| # | 问题 | 优先级 | 阻塞? | 当前默认假设（若不确认即按此推进） |
|---|---|---|---|---|
| Q1 | 登录：自建账号 vs 企业 SSO/OneIDM | 高 | **阻塞** | 先用自建 JWT 账号，SSO 作为后续增量 |
| Q2 | `changes_requested` 回退目标节点与留痕 | 高 | **阻塞** | 回退到 `submitted`，保留版本快照 |
| Q3 | 模块是否可动态自定义 | 中 | 否 | 固定 10 个默认模块 |
| Q4 | 上传文件类型/大小/安全扫描 | 中 | 否 | PDF/图片，≤20MB，暂不扫描 |
| Q5 | AI 草稿是否自动回流入知识库 | 中 | 否 | **不自动**，人工确认后才入库 |
| Q6 | 审批驱动：内置状态机 vs Flowable | 高 | ✅ **已定** | V1 仅用内置状态机，已移除 Flowable/Activiti |
| Q7 | 邮件深链鉴权 | 中 | 否 | 带一次性 token |
| Q8 | 移动端适配 | 低 | 否 | 本版仅桌面端 |
| Q9 | 产品主数据来源（PLM/ERP 接口） | 高 | **阻塞** | 手工录入 + 文件导入 |
| Q10 | 部署方式（容器/CI-CD） | 中 | 否 | Docker Compose |
| Q11 | 数据保留/审计合规要求 | 中 | 否 | 已有 activity 日志，暂不额外归档 |
| Q12 | 权限校验的粒度验收标准 | 高 | **阻塞** | 按 §2 的 4 角色边界 |

**阻塞项 Q6 已拍板（V1 仅内置状态机审批，移除 Flowable）。** 剩余阻塞项（Q1/Q2/Q9/Q12）需在本期开发启动前确认；其余可先按默认假设推进。

---

## 13. 边界总表（一页速览）

| 能力域 | ✅已实现 | 🟡部分 | ⬜待开发 | ❌本版不做 |
|---|---|---|---|---|
| 认证登录 | JWT/密码/找回 | — | 接口级角色鉴权 | 自定义角色 |
| RBAC | 4 角色枚举 | 校验落地 | 模块级行权限 | 运行时权限配置 |
| 生命周期 | 15 状态+流转接口 | — | 非法流转拦截 | — |
| 案例/模块 | 10 模块 CRUD/版本/活动 | — | — | 动态模块（待定） |
| 影响分析 | 8 维 AI+自检 | — | 中文口径固化 | — |
| 文件/解析 | 上传/导入/docling | — | — | — |
| AI/RAG | 建库+混合检索+编排+服务 | — | 更强模型/引用溯源 | — |
| 审批 | 内置状态机+审批接口 | — | 审批留痕/审计 | 外部流程引擎/审批路由配置 |
| 通知 | 邮件模板+定时提醒 | — | 深链鉴权 | — |
| 前端 | 全套 PD-ECR 页面 | — | — | 移动端 |
| 集成 | DB切换/Sentry | — | SSO/主数据接口 | 多租户/i18n |

---

*本文档基于仓库实际代码核对撰写；"已实现"项均可按所附文件/接口路径核验。后续每次迭代请同步更新「现状列」，保持文档与代码一致。*
