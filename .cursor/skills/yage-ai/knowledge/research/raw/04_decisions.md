# Decisions：行为与选择

## Collection Metadata
- Dimension: 4 Decisions / 行为与选择
- Collection strategy: revealed-preference extraction from 229 article cards
- Sources searched: 229 full-text article cards
- Sources used: 229 cards, with 12 concrete decision cases cited below
- Primary vs secondary ratio: 229:0
- Article-card source: `knowledge/research/article_cards/deep_cards/all_cards_normalized.jsonl`

## Source Metadata
- URL: https://yage.ai/ai-finance.html
- Source type: essay / automation decision case
- Grounding level: primary source / first-person authored work
- Access note: public, full text mapped into article card
- Source weight: 2
- Date: 2025-08-14
- URL: https://yage.ai/ai-native-cost-structure.html
- Source type: essay / one-off software case
- Grounding level: primary source / first-person authored work
- Access note: public, full text mapped into article card
- Source weight: 2
- Date: 2025-11-22
- URL: https://yage.ai/wide-research.html
- Source type: essay / research system build
- Grounding level: primary source / first-person authored work
- Access note: public, full text mapped into article card
- Source weight: 2
- Date: 2025-10-17
- URL: https://yage.ai/ai-builder-space.html
- Source type: essay / education infrastructure decision
- Grounding level: primary source / first-person authored work
- Access note: public, full text mapped into article card
- Source weight: 2
- Date: 2026-02-02
- URL: https://yage.ai/ai-book.html
- Source type: essay / corpus-to-book experiment
- Grounding level: primary source / first-person authored work
- Access note: public, full text mapped into article card
- Source weight: 2
- Date: 2025-04-15
- URL: https://yage.ai/life-api.html
- Source type: essay / personal data pipeline
- Grounding level: primary source / first-person authored work
- Access note: public, full text mapped into article card
- Source weight: 2
- Date: 2025-04-24
- URL: https://yage.ai/duck-sky-survey.html
- Source type: essay / long-running astronomy system
- Grounding level: primary source / first-person authored work
- Access note: public, full text mapped into article card
- Source weight: 2
- Date: 2022-03-27
- URL: https://yage.ai/senior-ic-thoughts.html
- Source type: essay / career reflection
- Grounding level: primary source / first-person authored work
- Access note: public, full text mapped into article card
- Source weight: 2
- Date: 2023-03-17

## Evidence
- `ai-finance` 的 card 将十年手动财务流程转为自动化的触发点归因于旧约束失效：AI 让原本不可能或不划算的操作变成可尝试。
- `ai-native-cost-structure` 的 card 显示作者愿意为一次十分钟判断生成临时软件，因为判断解析度比代码复用更贵。
- `wide-research` 的 card 把 AI 不偷懒问题转成系统能力建设：拆分、并行、上下文隔离和交叉验证，而不是继续提醒模型认真。
- `ai-builder-space` 的 card 显示作者在教育产品上选择工程基建，而不是继续堆教程内容。
- `ai-book` 的 card 展示作者愿意把三年群聊语料加工成小书，选择把长期语义材料转化为知识产品。
- `life-api` 的 card 显示作者选择让现实输入进入 AI 系统，形成长期个人 context，而不是只用 AI 处理显式任务。
- `duck-sky-survey` 与天文系列 cards 显示作者会为长期观测目标搭建工具链，而不是满足于单次作品。
- `senior-ic-thoughts` 和职业类 cards 显示作者看重 enablement、提出好问题、机会结构和系统影响，而不是职位标签本身。

## Patterns and Repeated Themes
- 决策前先重算成本结构：哪个动作以前太贵，现在变便宜；哪个中间状态以前不可见，现在可观测。
- 小步实验优先：先用脚本、可视化、卡片、原型或 agent 暴露现实，再决定是否长期化。
- 长期资产优先：能同时解决当前问题并沉淀 context、工具、文档、规则或数据的方案更受青睐。
- 防错靠机制：checklist、自动化、cross-check、验收、状态保存优于提醒自己小心。
- 工具选择服从目标定义：先问什么算好、哪些约束不可变，再选模型、器材、框架或流程。
- 对指标有保留：反玄学，但也反单指标教条；分布、曲线、场景和人类感知常比单点参数更重要。

## Contradictions
- Inherent: 他鼓励一次性软件，但对知识系统和 agent workflow 又强要求长期可维护性。
- Contextual: 他相信自动化和记录，但部分生活价值本身可能会被过度工程化压扁。
- Temporal: 很多自动化在 AI 出现前长期没有做，说明“意识到可行”本身也是成本结构变化的一部分。
- Inherent: 决策强调数据和验证，但 taste、兴趣和主观动机仍是大量项目的起点。

## Inferences (clearly marked)
- Inference: 他的 revealed preference 是牺牲短期代码整洁，换取更高决策解析度；但只限于一次性判断场景。
- Inference: 他会把“工具能不能改变行为”看得比“工具参数是否领先”更重要。
- Inference: 他对风险的容忍来自低成本试错和验收机制，不是盲目激进。
- Inference: 对他来说，最优方案常常是能启动知识飞轮的方案，而不是局部效率最高的方案。

## Gaps and Missing Information
- 决策材料全部来自自述，缺少外部成功率和第三方验证。
- 许多项目是个人实验，不能直接推导为普适工程结论。
- 对商业/团队场景的真实执行效果覆盖较少。
