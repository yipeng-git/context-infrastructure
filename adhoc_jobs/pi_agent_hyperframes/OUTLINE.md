# Pi Agent — Builder 视角的深度讲解视频

## 元信息

| 维度 | 值 |
|---|---|
| 画幅 | 1080x1920 竖屏 |
| 时长 | ~155s（2 分 35 秒）|
| 风格 | Dark premium，简洁美观 |
| 配音 | 无，纯视觉 + 文字 |
| 语言 | 中文 |
| 内容角度 | Builder 视角：把 Pi 当 SDK 构建自己的 Agent 系统 |

## 核心叙事线

大多数人把 AI coding agent 当工具来用。Pi 的设计哲学是：让你自己造工具。从消费 agent，到编排 agent，到构建 agent——这是 builder 的三层进化。

## 节奏总览

```
Time:  0     25     48     72     100    120    142  155
       |------|------|------|------|------|------|-----|
Scene: HOOK   现状    Pi     架构    SDK    自我    哲学   CTA
Energy: ████░  ░░██░  ░███░  ████░  █████  ░██░░  ░█░░  ░░░░
Rhythm: SLAM   drift  build  BUILD  PEAK   breath breath resolve
Trans:  hard→  blur→  push→  zoom→  blur→  fade→  dip→  (end)
```

---

## Scene 1: Hook（0-8s）— SLAM

**概念**: 一句话抓住注意力。不铺垫，直接扔出反直觉的信息。

**文案**:
> 你用 AI Agent 写代码
> 但你试过让 Agent 自己给自己造功能吗？

**视觉**: 暗底 + 大号 kinetic type，文字以 slam 方式逐句砸入。背景有微弱的 code 元素暗纹（ghost type），暗示技术语境。

**转场 → Scene 2**: Hard cut（节奏断裂，唤起注意）

---

## Scene 2: 现状与问题（8-25s）— drift

**概念**: 铺设冲突。当前的 AI coding agent 都是封闭产品，用户是消费者，不是 builder。

**文案**:
> Claude Code · Cursor · Copilot · Codex
> 都是好工具
> 但它们有一个共同点——
> 你用它们，你改不了它们

**视觉**: 四个产品名用 monospace 字体横排或纵排排列，依次 fade in。然后一个分隔线扫过，引出转折文案。布局偏杂志编辑风——左对齐，信息层次分明。

**转场 → Scene 3**: Blur crossfade（话题转换，进入新世界）

---

## Scene 3: Pi 登场（25-48s）— build

**概念**: 正式介绍 Pi。重点不在功能列表，而在设计哲学——它故意没有什么。

**文案**:
> Pi — 开源终端 AI Coding Agent
> 58K stars · MIT License
>
> 核心只有 4 个工具：
> read · write · edit · bash
>
> 没有 sub-agent
> 没有 plan mode
> 没有内置的复杂 feature
>
> 不是简陋，是设计选择

**视觉**: 分两拍。第一拍：Pi 的名字 + star 数据以 stat callout 形式进入。第二拍：四个工具名用 monospace 大字排成 2x2 grid 或竖排，每个带一个极简 icon。背景有 terminal-like 的暗纹。最后一句「不是简陋，是设计选择」加粗/变色强调。

**转场 → Scene 4**: Push slide（编辑式推进，"下一个论点"）

---

## Scene 4: 模块化架构（48-72s）— BUILD

**概念**: 揭示 Pi 的真正身份——不是一个 agent，是一个 agent 构建工具包。能量开始上升。

**文案**:
> Pi 不只是一个 CLI
> 它是一整个 monorepo toolkit
>
> pi-ai
> 统一 15+ LLM 提供商的 API 层
>
> pi-agent-core
> Agent 运行时：工具调用、状态管理
>
> pi-coding-agent
> 终端 CLI + 可编程 SDK，同一个包
>
> pi-tui · pi-web-ui
> 终端和浏览器的 UI 组件

**视觉**: 架构图风格。split-frame 布局——左侧模块名（大号 monospace），右侧一句话说明。依次 stagger 进入，形成层叠的卡片感。背景有微弱的连线/节点图暗纹，暗示模块间的依赖关系。

**转场 → Scene 5**: Zoom through（能量到达顶峰前的加速）

---

## Scene 5: SDK 能力 + 实战案例（72-100s）— PEAK

**概念**: 视频高潮——展示 Pi 作为 SDK 的威力，用实际案例证明。

**文案**:
> 同一个 npm install
> CLI 和 SDK 一起拿走
>
> createAgentSession()
> steer() · abort() · event streaming
> 完整的编程控制权
>
> OpenClaw — 基于 Pi SDK 构建
> Ticket 诊断 Agent — 全自动，无人值守
> Telegram Bot — Pi 的 agent-core 驱动
>
> 你不是在用别人的 agent
> 你在造自己的

**视觉**: 能量最高的场景。代码片段以 typing effect 或 highlight 方式出现（API 调用）。三个案例用卡片依次 cascade 进入，每张卡片带项目名 + 一句话描述。最后的引用文案用 accent 色大字强调。背景加 glow pulse 呼应 PEAK 能量。

**转场 → Scene 6**: Blur crossfade（从高能量下来，进入思考空间）

---

## Scene 6: 自我进化（100-120s）— breathe

**概念**: 最独特的 insight——Pi 可以让 agent 自己给自己写 extension。安静但信息密度高。

**文案**:
> 最疯狂的部分：
> 你可以让 Pi 自己给自己写 Extension
>
> 告诉它你需要什么能力
> 它当场构建出来
>
> 不需要 MCP
> 不需要社区 marketplace
> Agent 自己动手

**视觉**: 节奏放缓。大的引用区块居中，文字逐句 fade in。背景用慢速 breathing 的 radial glow，暗示"生长"。整体留白多，让观众有呼吸空间。

**转场 → Scene 7**: Gentle crossfade（延续思考的连续性）

---

## Scene 7: 哲学收束（120-142s）— breathe

**概念**: 升华到更高层面——Pi 代表的范式转变。回扣 builder mindset。

**文案**:
> 用 agent → 编排 agent → 构建 agent
> 三层进化
>
> Pi 的赌注：
> 在 agent 时代
> 最有价值的不是封闭产品
> 是可组合的原语

**视觉**: 三层进化用简洁的层级图或阶梯式排列逐层亮起。后半段总结文案用 large serif 字体，沉稳有力。背景保持安静，ambient motion 极轻。

**转场 → Scene 8**: Color dip to dark（闭合的仪式感）

---

## Scene 8: CTA（142-155s）— resolve

**概念**: 干净利落的结尾。信息 + 行动号召。

**文案**:
> pi.dev
> 58K ★ · MIT License · 15+ Providers
>
> 下一个 Agent，你来造

**视觉**: pi.dev 域名用大号 display font 居中，下方三个数据 badge。最后一句 slogan 以 accent 色 fade in。所有元素从中心向外 breathe 后静止。

---

## 全局视觉规格

| 维度 | 选择 |
|---|---|
| 背景色 | `#0a0c14` 附近（深色，不是纯黑，tint 向暖）|
| Accent | Warm amber `#e8a040` 附近（避开 cyan/purple 的 AI 设计套路）|
| 前景色 | `#f0ece4` 附近（暖白，不是纯白）|
| 辅助色 | `#8a8073`（dim text，暖灰）|
| Headline 字体 | Serif（沉稳有力）|
| Code/数据字体 | Monospace |
| 中文字体 | PingFang SC / Source Han Sans SC |
| 背景处理 | 每个 scene 不同暗纹：grid, ghost type, node graph, radial glow |
| 动效基调 | 入场多样化（slam, fade, cascade, stagger），不加 exit animation（由转场接管）|

## 设计决策说明

1. **Builder 视角的叙事弧线**——不是功能清单式的产品介绍，而是从问题出发（封闭产品），引出解决方案（可编程的 agent 工具包），最后升华到哲学层面（从消费到构建的范式转变）。

2. **PEAK 放在 SDK + 实战案例**——builder 最关心的不是 feature 列表，而是"我能拿它做什么"。真实案例（OpenClaw、ticket agent、Telegram bot）比任何 feature 列表都有说服力。

3. **Scene 6 的"自我进化"单独成景**——这是 Pi 最独特的 narrative，值得一个独立的呼吸空间来消化，而不是塞在 feature list 里。
