# Writings：著作与系统思考

## Collection Metadata
- Dimension: 1 Writings / 著作与系统思考
- Collection strategy: web-only, Chinese-only, full-text article-card map-reduce
- Sources searched: 229 full-text Chinese blog posts from `/tmp/yage_ai_dot_skill/chinese_corpus.jsonl`
- Sources used: 229 article cards, with 12 representative primary essays cited below
- Primary vs secondary ratio: 229:0
- Article-card source: `knowledge/research/article_cards/deep_cards/all_cards_normalized.jsonl`

## Source Metadata
- URL: https://yage.ai/context-infrastructure.html
- Source type: essay
- Grounding level: primary source / first-person authored work
- Access note: public, full text mapped into article card
- Source weight: 2
- Date: 2026-03-15
- URL: https://yage.ai/stop-using-chatgpt.html
- Source type: essay
- Grounding level: primary source / first-person authored work
- Access note: public, full text mapped into article card
- Source weight: 2
- Date: 2026-03-03
- URL: https://yage.ai/openclaw.html
- Source type: essay
- Grounding level: primary source / first-person authored work
- Access note: public, full text mapped into article card
- Source weight: 2
- Date: 2026-02-14
- URL: https://yage.ai/result-certainty.html
- Source type: essay
- Grounding level: primary source / first-person authored work
- Access note: public, full text mapped into article card
- Source weight: 2
- Date: 2026-01-25
- URL: https://yage.ai/ai-native-cost-structure.html
- Source type: essay
- Grounding level: primary source / first-person authored work
- Access note: public, full text mapped into article card
- Source weight: 2
- Date: 2025-11-22
- URL: https://yage.ai/ai-software-engineering.html
- Source type: essay
- Grounding level: primary source / first-person authored work
- Access note: public, full text mapped into article card
- Source weight: 2
- Date: 2025-11-16
- URL: https://yage.ai/correctness-is-meaningless.html
- Source type: essay
- Grounding level: primary source / first-person authored work
- Access note: public, full text mapped into article card
- Source weight: 2
- Date: 2024-06-07
- URL: https://yage.ai/duck-sky-survey.html
- Source type: essay / astronomy system project
- Grounding level: primary source / first-person authored work
- Access note: public, full text mapped into article card
- Source weight: 2
- Date: 2022-03-27

## Evidence
- 229 张 article cards 显示，作者的系统思考不是 2025 后突然出现的 AI 话术，而是从早期时间管理、智能家居、摄影、天文、音频、咖啡和职业反思一路延展到 Agentic AI。
- `context-infrastructure` 的 card 将核心 thesis 提炼为：LLM 默认回到 consensus，有判断力的输出来自高密度个人 context 对训练先验的覆盖。
- `stop-using-chatgpt` 的 card 将“停止聊天”提炼为工作流迁移：从问答界面迁移到能读文件、运行工具、保存中间状态的 agentic 工作目录。
- `result-certainty` 的 card 把 AI 工作流可靠性解释为从过程确定性转向结果确定性，关键动作是拆分、检查、重试、保存状态和验收。
- `ai-native-cost-structure` 的 card 把一次性软件定义为高解析度决策工具：代码成本下降后，以前不划算的临时可视化和局部自动化变成理性策略。
- 2021-2023 卡片显示大量非 AI 文章围绕信噪比、校准、分布、曲线、端到端工作流和模块重组展开，构成后期 AI 方法论的工程前史。
- 2012-2019 卡片显示早期已经出现“先观测再优化”“生活可以系统化和接口化”“防错靠机制”的底层习惯。
- 全卡片聚类显示高覆盖模型：observability 109 篇、workflow closure 108 篇、physical constraints 102 篇、cost structure 95 篇、builder systems 81 篇、context infrastructure 63 篇。

## Patterns and Repeated Themes
- 写作结构稳定：具体经验进入，定位旧约束，抽象成系统机制，再提出可迁移工作流。
- 作者偏好“机制解释”而非“观点表达”：每个判断都倾向落到成本、状态、接口、反馈、信噪比、上下文、验收或物理约束。
- AI 文章不是脱离早期材料的新宇宙，而是把已有的工程直觉迁移到人机协作和知识工作。
- 他反复将工具从消费品重新理解为接口：相机是观察光学世界的接口，智能家居是生活系统接口，AI agent 是认知/行动接口。
- 教程、产品和写作都被纳入“是否形成闭环”的判断框架：只输入内容不足，必须有实践、反馈和复用。

## Contradictions
- Temporal: 早期文章更像兴趣和技术日志，后期文章更像方法论产品；同一套系统直觉从隐性习惯变成显性理论。
- Inherent: 作者追求非共识和有品味的 bias，但又要求判断能被观测、验证和复盘约束。
- Contextual: 对一次性软件非常宽容，但对长期 context infrastructure 又要求严格命名、文档、分层和质量门槛。
- Inherent: 强烈反对空洞正确性，但高层抽象本身也需要具体案例持续校准，否则会变成新的空话。

## Inferences (clearly marked)
- Inference: yage.ai 的核心写作能力是把一个局部案例重建为系统模型，而不是单纯总结经验。
- Inference: “成本结构”“可观测性”“反馈闭环”是跨 AI、摄影、硬件、生活管理的共同底层词汇。
- Inference: 后期 AI 方法论之所以有辨识度，是因为它继承了早期物理系统和工程工具链训练出的约束感。
- Inference: 最终 Skill 的 mental models 应跨年份取证，避免只用 2025-2026 的 AI 高密度文章定义他。

## Gaps and Missing Information
- 本 track 按用户要求只使用 yage.ai 中文博客；英文翻译和站外材料不纳入。
- 文章卡片是全文 map 后的结构化摘要，不保存长原文，版权安全优先。
- 少数早期短文机制密度低，只适合补 timeline 和 expression DNA，不适合作为强模型证据。
