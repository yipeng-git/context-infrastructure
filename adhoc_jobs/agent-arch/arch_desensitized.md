# Agent Runtime 架构（脱敏版）

> 仅展示架构模式。已脱敏：所有组件命名、目录结构、工具/Skill 具体职责。

## 总览：端到端主流程

```mermaid
flowchart TD
    A(["客户端请求"]) --> B["编排层<br/>构造 RunCommand"]
    B --> C["Runtime Scheduler"]

    C --> D["并行加载<br/>Profile / Session / Memory"]
    D --> E["Phase 工具裁剪"]
    E --> F["Runner Factory<br/>组装 LLM + Prompt + Tools"]
    F --> G["ReAct 主循环<br/>LLM ↔ Tool 交替执行"]

    G -->|流式输出| H["Event Fanout<br/>→ 客户端 SSE"]
    G --> I["持久化 + 异步后处理<br/>Trace 压缩 / 对话摘要"]

    G -.->|调用| J["LLM Gateway"]
    I -.->|写入| K[("持久化存储")]
    D -.->|读取| L[("KV 存储")]
```

## 组件关系：Runtime 内部结构

```mermaid
flowchart LR
    subgraph Scheduler["Runtime Scheduler"]
        direction TB
        PROFILE["Profile"]
        SESSION["Session"]
        MEMORY["Memory"]
    end

    subgraph Factory["Runner Factory"]
        direction TB
        MODEL["Model Factory"]
        PROMPT["Prompt Builder"]
        TOOLREG["Tool Registry"]
        SKILL["Skill Service"]
    end

    subgraph Runner["ReAct Runner"]
        direction TB
        LOOP["ReAct Loop"]
        EVENTS["Event Emitter"]
    end

    subgraph PostProcess["后处理"]
        direction TB
        PERSIST["Session 持久化"]
        COMPRESS["三层压缩"]
    end

    Scheduler --> Factory --> Runner --> PostProcess

    PROFILE -.-> PROMPT
    SESSION -.-> PROMPT
    MEMORY -.-> PROMPT
    SKILL -.-> TOOLREG
    MODEL -.-> LOOP
    TOOLREG -.-> LOOP
    PROMPT -.-> LOOP
    LOOP -.-> EVENTS
```

## Prompt 三段构建 + Prefix Cache 设计

```mermaid
flowchart LR
    classDef stable fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    classDef variable fill:#fff8e1,stroke:#f57f17,stroke-width:2px
    classDef boundary fill:#ffebee,stroke:#c62828,stroke-width:2px,stroke-dasharray: 5 5

    subgraph STABLE["稳定前缀（可命中 Prefix Cache）"]
        direction TB
        M1["M1 — Persona<br/>Agent 人格 / 角色设定<br/><i>同一 Profile 版本内字节不变</i>"]
        M2["M2 — Tool Spec + Available Skills<br/>工具 JSON Schema + Skill 列表 XML<br/><i>同一 Profile 版本内字节不变</i>"]
    end

    CACHE["── Prefix Cache Boundary ──"]

    subgraph DYNAMIC["每轮变化区"]
        direction TB
        HIST["历史消息<br/>（append-only，含压缩后内容）"]
        M3["M3 — Dynamic Context<br/>Memory Snapshot 注入<br/>&lt;dynamic_context&gt; XML 包裹"]
        INPUT["本轮用户输入"]
    end

    M1 --> M2 --> CACHE
    CACHE --> HIST --> M3 --> INPUT

    INPUT --> BUILD["MessageBuilder.Build<br/>输出完整消息序列"]

    class STABLE stable
    class DYNAMIC variable
    class CACHE boundary
```

**设计意图**：M1 + M2 构成稳定前缀，同一 Profile 版本内字节完全相同，可命中 LLM Provider 侧的 Prefix Cache 降低首 token 延迟。M3 以独立 system message 注入，不破坏缓存前缀。

## ReAct 主循环

```mermaid
flowchart TD
    A(["用户输入"]) --> B["Prompt Builder<br/>构建完整消息序列"]
    B --> C["LLM 推理"]
    C --> D{输出类型?}
    D -->|tool_call| E["Tool 执行（按序）"]
    E --> F["tool_result 注入上下文"]
    F --> G{已达 MaxStep?}
    G -->|否| C
    G -->|是| H(["强制结束"])
    D -->|text| I(["最终文本回复"])
```

## 工具系统

```mermaid
flowchart TD
    subgraph 注册["工具注册"]
        direction LR
        S1["工具组 A<br/>业务能力"]
        S2["工具组 B<br/>上下文读写"]
        S3["工具组 C<br/>动态注入"]
    end

    S1 & S2 & S3 --> REG["Tool Registry<br/>统一注册表"]
    REG --> PHASE["Phase Filter<br/>当前阶段 → 白名单裁剪"]
    PHASE --> AVAIL["当前可用工具集"]

    META["Tool Metadata<br/>when_to_use / avoid / side_effect"]
    META -.->|可选：渲染进 Prompt| PROMPT["System Prompt"]
```

**关键模式**：
- **ReAct Loop**：LLM → tool_call → 执行 → 结果注入 → 再次推理，循环直到输出纯文本或达 MaxStep
- **Tool 按序执行**：工具调用不并行，保证状态一致性
- **Phase 过滤**：根据当前对话阶段裁剪可用工具白名单
- **Skill 按需加载**：LLM 在 Prompt 中看到 Skill 摘要列表，主动 tool_call 读取完整 SOP

## Skill 按需加载时序

```mermaid
sequenceDiagram
    autonumber
    participant LLM as LLM
    participant Tool as Skill 读取工具
    participant Svc as Skill 服务
    participant DB as 持久化存储

    Note over LLM: M2 中已包含 Skill 摘要列表
    LLM->>Tool: tool_call: 读取指定 Skill
    Tool->>Svc: 查询已启用的 Skill
    Svc->>DB: 按名称 + enabled 过滤
    DB-->>Svc: Skill 记录
    Svc-->>Tool: Skill 内容（Markdown SOP）
    Tool-->>LLM: 返回 SOP 文本
    LLM->>LLM: 按 SOP 指导后续工具调用
```

## 三层历史压缩

```mermaid
flowchart TD
    classDef l1 fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    classDef l2 fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef l3 fill:#fce4ec,stroke:#c62828,stroke-width:2px

    subgraph L1_RULE["L1 — 规则压缩（无 LLM 调用）"]
        RAW["原始 tool_result<br/>（完整 JSON）"]
        RULE["按工具类型分派<br/>提取关键字段"]
        COMPACT1["轻量文本摘要<br/>保留 ID / 计数 / 核心字段"]
        RAW --> RULE --> COMPACT1
    end

    subgraph L2_TRACE["L2 — 单轮 Trace 压缩（LLM，异步）"]
        TRACE["单轮 Trace<br/>多条 tool_call + tool_result"]
        CHECK2{"trace 条数 ≥ 阈值?"}
        LLM2["LLM 生成单段摘要"]
        STORE2["写入 CompressedTrace 字段<br/>下次构建历史时替代原始 Trace"]
        KEEP2["保留原始"]
        TRACE --> CHECK2
        CHECK2 -->|是| LLM2 --> STORE2
        CHECK2 -->|否| KEEP2
    end

    subgraph L3_SESSION["L3 — 跨轮次对话摘要（LLM，异步）"]
        MSGS["Session 全部消息"]
        CHECK3{"累积 token > 阈值?"}
        LLM3["增量摘要<br/>保留最近 N 轮原文"]
        STORE3["写入 Summary 字段<br/>+ 摘要游标 MessageID"]
        KEEP3["保留原始"]
        MSGS --> CHECK3
        CHECK3 -->|是| LLM3 --> STORE3
        CHECK3 -->|否| KEEP3
    end

    COMPACT1 -.->|"输入"| TRACE
    STORE2 -.->|"输入"| MSGS

    class L1_RULE l1
    class L2_TRACE l2
    class L3_SESSION l3
```

**协同机制**：L1 在每次构建上下文时实时执行（纯规则，零延迟）→ L2 在每轮回复持久化后异步触发 → L3 在满足 token 阈值时异步触发。三层协同控制上下文窗口线性增长。

## Session + Memory 读写流

```mermaid
flowchart LR
    classDef persist fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    classDef memory fill:#e3f2fd,stroke:#1565c0,stroke-width:2px

    USER["用户消息"] --> APPEND1["Session.Append<br/>用户消息"]
    APPEND1 --> RUN["Runtime.Run"]
    RUN --> FINAL["最终回复 + Trace"]
    FINAL --> APPEND2["Session.Append<br/>助手回复（多 Part 分别存储）"]
    APPEND2 --> COMPACT["异步: Trace 压缩"]
    APPEND2 --> SUMM{"触发摘要?"}
    SUMM -->|是| ASYNC_SUMM["异步: 增量摘要"]

    RUN -.->|"工具调用: 写入上下文"| MEM_W["Memory.Write<br/>scope = User / Session / Tag"]
    MEM_W --> KV[("KV 存储")]

    NEXT["下一轮请求"] --> SNAP["Memory.LoadSnapshot"]
    SNAP --> KV
    SNAP --> DYN["注入 M3<br/>Dynamic Context"]

    class APPEND1,APPEND2 persist
    class MEM_W,SNAP memory
```

**关键设计**：
- **Session 多 Part 存储**：每条助手回复支持多个 Part，每个 Part 独立包含文本 + Trace，对应一次 ReAct 循环
- **Memory 双向流**：运行时通过工具写入 → 下一轮通过 Snapshot 加载注入 Prompt
- **异步后处理**：Trace 压缩和对话摘要均在主流程结束后异步执行，不阻塞响应

## 事件流 + Artifact 系统

```mermaid
flowchart TD
    classDef sink fill:#fce4ec,stroke:#c62828,stroke-width:2px
    classDef sse fill:#e8eaf6,stroke:#283593,stroke-width:2px

    RUNNER["Runner.RunStream"] -->|"StreamCallback<br/>HistoryMessage"| EMITTER["Event Emitter<br/>HistoryMessage → 结构化 Event"]

    EMITTER -->|AgentEvent| FANOUT["Event Fanout<br/>（一进多出）"]

    FANOUT --> SINK_M["Metrics Sink<br/>结构化日志打点"]
    FANOUT --> SINK_T["Trace Sink<br/>内存事件收集（供 Replay）"]
    FANOUT --> SINK_S["Stream Sink<br/>→ SSE / NDJSON"]

    SINK_S -->|"model_delta"| SSE1["流式文本片段"]
    SINK_S -->|"tool_call_started"| SSE2["工具调用事件"]
    SINK_S -->|"tool_call_ended"| SSE3["工具结果事件"]
    SINK_S -->|"artifact_created"| ART["Artifact Collector<br/>按 ID / payload 去重缓冲"]
    SINK_S -->|"run_completed"| FLUSH["flush Artifacts<br/>→ 结构化卡片 SSE"]
    SINK_S -->|"run_failed"| SSE4["错误事件"]

    FLUSH --> CLIENT(["客户端"])
    SSE1 & SSE2 & SSE3 & SSE4 --> CLIENT

    class SINK_M,SINK_T,SINK_S sink
    class SSE1,SSE2,SSE3,SSE4,FLUSH sse
```

**Artifact 双链路保障**：工具执行时可直接 emit 事件到前端流（快路径）；同时 Event Emitter 解析 tool_result 创建 Artifact，由 Stream Sink 在 `run_completed` 时统一 flush（兜底路径）。

## Model Factory + Replay

```mermaid
flowchart TD
    subgraph MODEL["Model Factory"]
        PROFILE["Profile 配置<br/>provider + model_name"]
        CMF["Composite Factory<br/>按 provider 路由"]
        NORM["Provider 归一化<br/>（多种 provider → 统一协议）"]
        OAI["OpenAI-compat Factory"]
        CM["LLM Client<br/>支持 Tool Calling"]

        PROFILE --> CMF --> NORM --> OAI --> CM
    end

    subgraph REPLAY["Replay / Eval"]
        HIST_S["历史 Session<br/>前 N 轮消息"]
        LAST["最后一条用户输入"]
        RE_RUN["重新执行 Runtime.Run<br/>（新 Profile 版本）"]
        SCORE["评估打分"]

        HIST_S --> RE_RUN
        LAST --> RE_RUN
        RE_RUN --> SCORE
    end

    CM --> RE_RUN
```

**Replay 用途**：复用历史 Session 的前 N 轮作为 context，重放最后一条用户输入，用于 Profile 版本对比和回归测试。
