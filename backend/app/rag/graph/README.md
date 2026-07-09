# PD-ECR RAG 生成流程（LangGraph 骨架）

从零重建的 RAG 编排层。**LangGraph 做主干（多模块分步生成），LangChain 做检索/LLM 积木，Embedding + 向量库仍用本地 sentence-transformers + FAISS。**

## 目录

```
rag/
├── retrieval/          # 查询 -> 相似历史案例上下文
│   └── retriever.py    #   retrieve_cases()：当前复用已建好的 FAISS 索引
├── graph/              # ⭐ LangGraph 编排
│   ├── state.py        #   PdEcrState：全局共享状态
│   ├── schemas.py      #   各模块 LLM 结构化输出的 Pydantic 模型
│   ├── llm.py          #   ChatOpenAI 工厂（走 .env 的 Azure 配置）
│   ├── nodes.py        #   每个模块一个节点
│   ├── graph.py        #   组装图 + 条件边
│   └── run_demo.py     #   最小可跑示例
└── ingest/             # （待填）离线：文档 -> 向量库
```

## 流程

```
classify -> retrieve -> impact_analysis --self_check--> validation_plan -> implementation_plan -> END
                             ^                  |
                             └── 不合格&有重试 ──┘
```

- **classify**：判定变更类型，作为检索的额外信号
- **retrieve**：检索相似历史 PD-ECR 案例，拼成上下文
- **impact_analysis**：逐一评估 8 个影响维度（结构化输出）
- **self_check**：检查是否覆盖全部维度，不合格自动重跑（最多 2 次）
- **validation_plan / implementation_plan**：验证计划、各部门实施计划

## 安装依赖

```bash
cd backend
uv sync            # 或 pip install langgraph langchain langchain-openai langchain-community
```

## 跑通

```bash
cd backend
python -m app.rag.graph.run_demo
```

## 扩展点

- **加模块**：在 `nodes.py` 照 `validation_plan_node` 写一个节点，在 `graph.py` 加一条 `add_edge`。
- **接 Flowable 审批**：在 `implementation_plan` 之后加一个 `to_flowable` 节点，调用现有 Flowable 集成。
- **迁到 LangChain 原生 FAISS**：只改 `retrieval/retriever.py` 的 `retrieve_cases`，保持返回 `list[RetrievedChunk]`，graph 层无感知。
- **只跑影响分析**：把 `graph.py` 里 `impact_self_check` 的 `"ok"` 分支从 `validation_plan` 改成 `END`。
