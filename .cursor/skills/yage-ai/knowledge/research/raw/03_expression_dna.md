# Expression DNA：语言指纹

## Collection Metadata
- Dimension: 3 Expression DNA / 语言指纹
- Collection strategy: full-corpus metrics plus 229 article cards
- Sources searched: 229 full-text Chinese blog posts
- Sources used: 229 article cards, full-corpus style metrics, 10 representative cards cited below
- Primary vs secondary ratio: 229:0
- Article-card source: `knowledge/research/article_cards/deep_cards/all_cards_normalized.jsonl`

## Source Metadata
- URL: https://yage.ai/web-layout-tradeoff.html
- Source type: essay / system design argument
- Grounding level: primary source / first-person authored work
- Access note: public, full text mapped into article card
- Source weight: 2
- Date: 2026-03-30
- URL: https://yage.ai/context-infrastructure.html
- Source type: essay / AI methodology argument
- Grounding level: primary source / first-person authored work
- Access note: public, full text mapped into article card
- Source weight: 2
- Date: 2026-03-15
- URL: https://yage.ai/ai-native-cost-structure.html
- Source type: essay / AI-native strategy argument
- Grounding level: primary source / first-person authored work
- Access note: public, full text mapped into article card
- Source weight: 2
- Date: 2025-11-22
- URL: https://yage.ai/life-api-part4-followup.html
- Source type: essay / self-correction
- Grounding level: primary source / first-person authored work
- Access note: public, full text mapped into article card
- Source weight: 2
- Date: 2025-05-08
- URL: https://yage.ai/fanren.html
- Source type: essay / data experiment
- Grounding level: primary source / first-person authored work
- Access note: public, full text mapped into article card
- Source weight: 2
- Date: 2025-06-07
- URL: https://yage.ai/deepseek-r1.html
- Source type: essay / model-use reflection
- Grounding level: primary source / first-person authored work
- Access note: public, full text mapped into article card
- Source weight: 2
- Date: 2025-02-08
- URL: https://yage.ai/duck-sky-survey.html
- Source type: essay / astronomy project
- Grounding level: primary source / first-person authored work
- Access note: public, full text mapped into article card
- Source weight: 2
- Date: 2022-03-27
- URL: https://yage.ai/why-do-people-need-a-sense-of-ritual.html
- Source type: essay / early reflection
- Grounding level: primary source / first-person authored work
- Access note: public, full text mapped into article card
- Source weight: 2
- Date: 2016-09-18

## Evidence
- 全文指标：229 篇约 819,169 字，平均每篇约 3,577 字；粗分句约 17,095 句，平均句长约 46.6 中文字符，中位数约 35，p90 约 70。
- 高频概念：AI 3026、系统 820、工具 515、数据 407、工程 276、决策 239、prompt 203、实验 177、成本 142、反馈 134、上下文 130、框架 130、测量 112、信噪比 109、验证 105。
- `web-layout-tradeoff` 的 card 展示典型结构：从一个“一行代码为什么做不到”的具体问题，转入抽象层次、可观测中间状态和系统设计取舍。
- `context-infrastructure` 的 card 展示另一个典型结构：对照实验引出变量，随后将变量命名为 context infrastructure，并把个人 bias 作为深度来源处理。
- `life-api-part4-followup` 的 card 显示自我修正风格：公开承认文章失败，然后把失败转成关于 AI 协作边界和创造/优化差异的机制分析。
- 2021-2023 chunk summary 显示作者在摄影、音频、天文和硬件文章中反复把主观体验拆成可观测变量、分布指标和端到端工作流。
- 2012-2019 chunk summary 显示早期表达更口语、自嘲和生活化，但已经习惯从生活痛点进入技术解释。

## Patterns and Repeated Themes
- 盲测路径：具体问题 -> 旧约束/失败模式 -> 系统变量 -> 可迁移策略 -> 诚实边界。
- 语气：第一人称实践者，有自嘲和理工圈口语，但中段快速进入系统分析。
- 分歧表达：常先说明一个流行说法为什么表面上顺，再指出它解释力不足。
- 比喻库：工程系统、摄影/天文、硬件、电路、医疗/医院、金融、修仙、游戏和日常生活。
- 抽象词需要案例支撑：成本结构、context density、闭环、可观测性这类词出现时，通常配有具体实验或工作流。
- 置信度语言：亲手实验和长期记录上更强；对外部评价、私下动机、即兴对话会显著降置信度。

## Contradictions
- Temporal: 早期口语、自嘲、折腾感更强；后期方法论密度更高，语气更像成体系文章。
- Inherent: 他反对 AI 味总结，但自己也频繁制造抽象概念，因此最需要靠案例和验证约束抽象。
- Contextual: 技术圈读者会觉得表达清晰，但非 builder 读者可能被工具链和概念密度挡住。
- Inherent: 文章既追求强观点，也会在证据不足处明确降低置信度。

## Inferences (clearly marked)
- Inference: 模仿 yage.ai 的关键不是复用词汇，而是复现“具体案例到系统机制”的推理动作。
- Inference: 如果输出只有“成本结构 / context / 闭环”等词而无案例，会比普通 AI 味更不像他。
- Inference: 他的幽默主要服务于降低入口门槛，不承担主要论证功能。
- Inference: 最终 Skill 的 voice 应保留第一人称工程实验感，但避免虚构生活细节。

## Gaps and Missing Information
- 没有音频/视频材料，无法分析语速、停顿和现场语言。
- 英文翻译按用户要求排除，因此不比较双语表达。
- 少数文章包含站点 boilerplate，卡片化时已尽量忽略；后续自动词频分析需继续清洗。
