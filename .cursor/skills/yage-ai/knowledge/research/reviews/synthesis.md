# Synthesis Review

## Accepted Mental Models

### 1. Context Infrastructure
- Definition: 模型智能跨过门槛后，输出深度主要来自长期积累、分层蒸馏、按需加载的个人 context。
- Triple gate: cross-context recurrence PASS; generative power PASS; exclusivity PASS。
- Evidence anchors: `context-infrastructure` 的对照实验；`stop-using-chatgpt` 的文件系统工作流；`life-api` 的现实输入管线；`ai-book` 的群聊语料到知识产品。
- What it sees first: 当前 AI 是否拿到了足够密度的判断原则、历史材料、失败记录和项目状态。
- What it filters out: 单次 prompt 技巧、只追最新模型、把 AI 平庸归因于模型不够聪明。
- Failure mode: 对没有长期数据积累的人，短期复制难；也可能把私人生活过度数据化。

### 2. 可观测性先于优化
- Definition: 当现实被压缩成主观感觉或少量样本时，先建立观测接口，再讨论优化。
- Triple gate: cross-context recurrence PASS; generative power PASS; exclusivity PASS。
- Evidence anchors: 摄影/天文信噪比与校准帧；音频的人耳/房间响应；时间记录和年终总结；AI 工作流的日志、diff、验收。
- What it sees first: 哪个变量不可见，哪个中间状态缺失，如何用脚本/传感器/日志/可视化展开现实。
- What it filters out: 高手直觉、单点参数崇拜、只看结论不看测量方法。
- Failure mode: 可能把关系、情绪和体验压成数据问题。

### 3. 成本结构决定策略重构
- Definition: 最佳实践往往是旧成本结构下的局部最优；AI 改变行动成本后，策略要重算。
- Triple gate: cross-context recurrence PASS; generative power PASS; exclusivity PASS。
- Evidence anchors: 一次性软件；AI 财务自动化；AI 教育基建；AI-native 软件工程对 DRY 的重新解释。
- What it sees first: 哪个动作以前太贵、太慢、太繁琐，现在变便宜。
- What it filters out: 只比较工具性能、只谈效率提升、不问行为是否改变。
- Failure mode: 低估人和组织迁移到新策略的心理成本、配置成本和训练成本。

### 4. 闭环工作流产生结果确定性
- Definition: AI 时代的可靠性不来自规定每一步，而来自把任务拆分、观察、验证、重试和纠错纳入闭环。
- Triple gate: cross-context recurrence PASS; generative power PASS; exclusivity PASS。
- Evidence anchors: `result-certainty` 的翻译系统；`closed-loop-learnings` 的学习闭环；`ai-management` 系列；天文导星和控制系统。
- What it sees first: 任务有没有反馈信号、验收标准、中间状态和恢复路径。
- What it filters out: 只靠 prompt 约束模型、只靠提醒人小心。
- Failure mode: 过度流程化会提高启动成本，短任务可能不划算。

### 5. 工具是现实的接口
- Definition: 代码、相机、传感器、日志、agent 都是把不可见现实转成可操作对象的接口。
- Triple gate: cross-context recurrence PASS; generative power PASS; exclusivity PASS。
- Evidence anchors: life API；智能家居与传感器；摄影/天文工具链；OpenClaw/MCP/agentic runtime。
- What it sees first: 系统有哪些输入、输出、状态、动作器和可调用能力。
- What it filters out: 把工具当孤立消费品或功能清单。
- Failure mode: 容易把生活和创作过度工程化。

### 6. 物理/系统约束优先于概念热度
- Definition: 新概念只有进入端到端链路并通过约束核算，才构成真实能力。
- Triple gate: cross-context recurrence PASS; generative power PASS; exclusivity PASS。
- Evidence anchors: Web layout 中的 CSS 历史 tradeoff；音频/摄影/咖啡的测量边界；MCP/OpenClaw 的协议和安全约束；汽车底盘技术路线。
- What it sees first: 底层约束、环境变量、反馈延迟和部署边界。
- What it filters out: 品牌、规格、热词、demo 和单点 benchmark。
- Failure mode: 可能让判断显得偏硬核，低估用户的情绪和审美偏好。

### 7. 解释力优先于正确性
- Definition: 正确但不能改变判断的共识输出价值很低；好的分析要解释机制、提供反例、改变行动。
- Triple gate: cross-context recurrence PASS; generative power PASS; exclusivity PASS。
- Evidence anchors: `correctness-is-meaningless`；`context-infrastructure` 对 consensus 的批判；`life-api-part4-followup` 对伪深刻的自我审计；AI 产品体验错位。
- What it sees first: 这个说法有没有压缩不确定性、能否解释反例、能否改变下一步。
- What it filters out: 平衡陈述、安全总结、没有行动含义的正确废话。
- Failure mode: 过度追求非共识可能把主观 bias 包装成 insight。

## Candidate Heuristics
- If 任务反复在聊天框失败, then 搬进文件系统和 agentic runtime, because 聊天缺工具、状态和验收。
- If 只能抽样判断, then 先问能不能造一次性观测工具, because 抽样常是旧成本结构下的妥协。
- If 工具 demo 很强但用户体验没变, then 检查它是否进入真实工作流, because 能力不等于可感价值。
- If AI 输出看似正确但无聊, then 检查 context density, because consensus 是默认态。
- If 新技术看起来颠覆, then 回到底层约束和端到端链路, because 概念热度常遮蔽部署边界。
- If 学习或协作没有进展, then 建立反馈闭环, because 内容供给不是能力形成的充分条件。

## Demoted / Discarded Observations
- “yage.ai 只是 AI 博主”：discarded。早期摄影、天文、硬件、生活系统化是后期 AI 方法论的底座。
- “他主要靠 prompt 技巧”：discarded。证据反复指向文件系统、context、工具和验收。
- “外部口碑完整”：discarded。当前 source scope 不支持。
- “即兴对话风格高置信度”：demoted。缺少长访谈和未编辑问答。

## Unresolved Contradictions
- 高系统化带来复利，也可能压缩生活的非工具性部分。
- 一次性软件鼓励局部粗糙，但长期 context infrastructure 需要严谨维护。
- 有品味的 bias 是深度来源，也可能退化为未经验证的偏见。
- 关心普通用户体验，但自己的方法论常要求较高 builder 能力。

## Evidence Gaps
- Conversations: 缺少公开长访谈、播客、AMA。
- External Views: 缺少独立第三方评价、读者长反馈、课程学员原始反馈。
- Voice: 缺少音频/视频，不能验证现场表达。

## Known-Answer Anchors
- 为什么停止和 AI 聊天：应回答为工作流迁移，而非模型替换。
- 为什么 Deep Research 不等于深度：应回答为信息覆盖和认知框架不同层。
- 为什么一次性软件合理：应回答为代码成本下降后，决策解析度变贵。

## Edge-Case Question
- 非技术创作者团队如何迁移这套方法：应先降低工具摩擦、建立最小闭环和可复用 context，而不是直接复制 Cursor/OpenCode 高技术工作流。

## Intellectual Genealogy Seeds
- Influenced by: 软件工程、系统设计、机器学习实验、摄影/天文信噪比、硬件 DIY、个人时间管理和知识管理。
- Diverged from: prompt engineering 速成论、模型中心主义、DRY 绝对主义、教程内容主义、单点指标崇拜。
- Influenced: Agentic AI、Cursor、个人 context infrastructure、AI-native 写作/课程/工具工作流的实践者。

## Agentic Protocol Seeds
- 先分类：成本结构问题、可观测性问题、context density 问题、闭环可靠性问题、物理/系统约束问题、表达解释力问题。
- 先调查：旧流程最贵动作、不可见中间状态、已有 context 密度、验收标准、端到端链路、长期资产。
- 再应用：用 mental models 逐层解释，不强行抹平矛盾。
- 最后校准：一手博客反复出现的模型高置信；即兴对话和外部口碑低置信。
