# Agent 架构小红书卡片内容稿

> 8 张卡片，每张包含：标题、Mermaid 源码（Card 2-7）或插画描述（Card 1/8）、洞察文字。

---

## Card 1 — 封面（baoyu 插画）

**标题**：一个生产级 Agent 从请求到回复经历了什么？

**内容要点**（供插画生成）：
- 一条请求从左到右经过 7 个阶段
- 编排 → 并行加载 → 阶段裁剪 → 依赖组装 → ReAct 循环 → 流式输出 → 异步压缩
- 强调 ReAct 循环是核心（最大的节点）
- 底部标注：LLM Gateway / 持久化存储 / KV 存储

**洞察**：请求进来后并行加载三份上下文，经阶段裁剪和依赖组装后进入 ReAct 循环，流式输出的同时异步压缩历史。

---

## Card 2 — Prompt 三段式 + Prefix Cache

**标题**：System Prompt 怎么设计才能命中 Prefix Cache？

```mermaid
flowchart TD
    M1["M1: Persona\n角色设定（稳定）"]
    M2["M2: Tool Spec + Skills\n工具定义 + 技能列表（稳定）"]
    CACHE["─── Prefix Cache 边界 ───"]
    HIST["历史消息\nappend-only"]
    M3["M3: Dynamic Context\n每轮变化的用户上下文"]
    INPUT["本轮用户输入"]

    M1 --> M2
    M2 --> CACHE
    CACHE --> HIST
    HIST --> M3
    M3 --> INPUT
```

**洞察**：M1 + M2 在同一 Profile 版本内字节完全不变，可命中 LLM Provider 的 Prefix Cache，首 token 延迟降低约 50%。M3 用独立 system message 注入，不破坏缓存前缀。

---

## Card 3 — ReAct 主循环

**标题**：Agent 的核心：推理 → 行动 → 观察

```mermaid
flowchart TD
    A(["用户输入"]) --> B["构建完整消息序列"]
    B --> C["LLM 推理"]
    C --> D{输出类型?}
    D -->|tool_call| E["执行工具（按序）"]
    E --> F["结果注入上下文"]
    F --> G{达到 MaxStep?}
    G -->|否| C
    G -->|是| H(["强制结束"])
    D -->|text| I(["最终回复"])
```

**洞察**：LLM 输出 tool_call 就执行，输出 text 就结束。MaxStep 是安全阀防止无限循环。工具按序执行不并行——状态一致性比吞吐更重要。

---

## Card 4 — 工具编排：注册 + 阶段过滤

**标题**：工具不是越多越好——Phase 白名单裁剪

```mermaid
flowchart TD
    subgraph reg ["工具注册（按来源分组）"]
        direction LR
        A["组 A\n业务能力"]
        B["组 B\n上下文读写"]
        C["组 C\n动态注入"]
    end

    A & B & C --> R["Tool Registry\n统一注册表"]
    R --> P["Phase Filter\n按当前阶段裁剪"]
    P --> T["当前可用工具集"]
```

**洞察**：工具按来源分三组注册到统一 Registry。运行时读取 Dynamic Context 中的 phase，做白名单裁剪：早期只开上下文工具，后期逐步解锁更多能力。工具元数据（when_to_use / avoid）可选渲染进 Prompt。

---

## Card 5 — Skill 按需加载

**标题**：LLM 自己决定要不要读 SOP

```mermaid
sequenceDiagram
    participant LLM
    participant SkillTool as Skill Tool
    participant Service as Skill Service
    participant Store as Storage

    Note over LLM: Prompt 中已列出 Skill 摘要
    LLM->>SkillTool: tool_call 读取 Skill
    SkillTool->>Service: 查询已启用 Skill
    Service->>Store: 按名称 + enabled 过滤
    Store-->>Service: Skill 记录
    Service-->>SkillTool: Markdown SOP
    SkillTool-->>LLM: 返回 SOP
    LLM->>LLM: 按 SOP 执行后续调用
```

**洞察**：Prompt 里只放 Skill 摘要列表（省 token），LLM 判断需要时主动 tool_call 拉完整 SOP。懒加载 = 省 token + 精准匹配。Skill 支持 CRUD 管理，content hash 校验防重复写入。

---

## Card 6 — 三层历史压缩

**标题**：长对话不爆 context window 的三道防线

```mermaid
flowchart LR
    subgraph L1 ["L1 规则压缩"]
        R1["原始 tool_result"] --> R2["提取关键字段"]
    end

    subgraph L2 ["L2 单轮 LLM 压缩"]
        T1["多步 Trace"] --> T2{"条数 >= 阈值?"}
        T2 -->|是| T3["LLM 摘要"]
        T2 -->|否| T4["保留原始"]
    end

    subgraph L3 ["L3 跨轮增量摘要"]
        S1["全部消息"] --> S2{"token > 阈值?"}
        S2 -->|是| S3["增量摘要\n保留最近 N 轮"]
        S2 -->|否| S4["保留原始"]
    end

    L1 --> L2 --> L3
```

**洞察**：L1 纯规则零延迟，去冗余 JSON 只留关键字段。L2 异步触发，单轮多步 trace 压成一段话。L3 异步触发，远古历史压成增量摘要。三层协同把上下文增长从 O(n) 压到 O(log n)。

---

## Card 7 — Session + Memory 双向流

**标题**：Agent 怎么跨轮次记住用户？

```mermaid
flowchart TD
    U["用户消息"] --> SA["Session 追加"]
    SA --> RUN["Runtime.Run"]
    RUN --> REPLY["回复 + Trace"]
    REPLY --> SB["Session 持久化\n多 Part 存储"]
    SB --> CMP["异步压缩"]

    RUN -.->|"工具写入"| MW["Memory.Write\nUser / Session scope"]
    MW --> KV[("KV Store")]

    NEXT["下一轮"] --> SNAP["Memory.LoadSnapshot"]
    SNAP --> KV
    SNAP --> DYN["注入 Prompt M3"]
```

**洞察**：Session 按轮次持久化，每条回复多 Part 存储（每 Part = 一次 ReAct 循环）。Memory 是结构化 KV，运行时通过工具写入 → 下一轮 Snapshot 注入 Prompt。两者配合 = 短期记忆 + 长期偏好。

---

## Card 8 — 结尾（baoyu 插画）

**标题**：8 个设计模式，一张图总结

**内容要点**（供插画生成）：
- 8 个关键设计点的一句话总结：
  1. Prompt 三段式 + Prefix Cache
  2. ReAct 推理-行动循环
  3. Phase 工具白名单裁剪
  4. Skill 懒加载（摘要 → 按需读取）
  5. 三层历史压缩（规则 → 单轮 LLM → 跨轮摘要）
  6. Session 多 Part + Memory KV 双向流
  7. 事件 Fanout 三通道
  8. Artifact 去重双链路
- 底部互动引导：你们的 Agent 用了哪些类似的模式？

**洞察**：这套架构的核心思路——把 LLM 当 CPU，Prompt 当指令集，工具当外设，Memory 当寄存器，Session 当磁盘，压缩当 GC。
