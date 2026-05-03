# 播客 / Transcript 到高质量思维导图工作流

> Status: experimental draft. 这是播客到脑图流程的实验草稿，不属于正式 skill，不应被 agent 自动当成稳定工作流调用。
>
> Promotion criteria:
> - 至少跑通 3 期播客，覆盖下载、转写、QA 和脑图生成
> - 路径、命令、依赖和产物契约稳定
> - 用户确认产物质量和流程边界
> - 再迁回 `context-infrastructure/rules/skills/` 并登记 `skills/INDEX.md`

## 元数据
- 类型: Workflow Draft
- 适用场景: 小宇宙播客下载、ASR 转写、QA 修正、`mindmap.md` 提炼
- 创建日期: 2026-04-30
- 最后更新: 2026-05-01

## 何时触发

- 用户分享小宇宙链接（`xiaoyuzhoufm.com/episode/xxx`）
- 用户说「转写这期播客」「下载这期播客」「帮我听一下这期」
- 用户提供音频文件或已存在的播客目录，希望转写并生成脑图
- 用户提供 `transcript.txt`，说「生成脑图」「生成思维导图」「做个大纲」
- 播客收集流程完成后，需要继续产出 `mindmap.md`

## 路径约定

- 数据输出：`collected-contents/<播客名>/<集标题>/`
- 核心输入：小宇宙 URL、音频文件、已有 episode 目录，或同目录的 `transcript.txt`
- 辅助输入：同目录 `metadata.json`，优先读取 `title`、`duration`、`description`
- 工具脚本：`context-infrastructure/tools/podcast_pipeline.py`、`context-infrastructure/tools/xiaoyuzhou_download.py`、`context-infrastructure/tools/transcribe_audio.py`
- Python venv：`context-infrastructure/.venv`。命令默认从 workspace 根目录运行，优先使用 `context-infrastructure/.venv/bin/python`

## 入口判断

先判断用户手里有什么，再选择最短路径：

| 用户输入 | 起点 | 目标产物 |
|---|---|---|
| 小宇宙链接 | 下载音频和元数据 | `transcript.txt` + `mindmap.md` |
| 已有音频 | ASR 转写 | `transcript.txt` + `mindmap.md` |
| 已有 episode 目录 | 补齐缺失步骤 | 缺什么补什么 |
| 已有 `transcript.txt` | 脑图生成 | `mindmap.md` |
| 用户只要转写 | 停在阅读层 | `transcript.txt`，可选 `_pipeline/transcript_qa.md` |

不要因为用户说「思维导图」就重新跑 ASR。如果 `transcript.txt` 已经存在，直接进入脑图生成阶段；只有用户明确要求重新转写，或 transcript 质量明显不可用时，才回到转写阶段。

## 核心原则

这套流程把播客处理成五层产物：

1. **原始素材层** → `audio.*`、`metadata.json`
2. **事实层** → `_pipeline/transcript_raw.jsonl`，按需生成 `_pipeline/transcript_raw.txt`
3. **修正层** → `_pipeline/corrections.yaml`、`_pipeline/lexicon.yaml`
4. **阅读层** → `transcript.txt`
5. **知识层** → `mindmap.md`，按需生成 `_pipeline/transcript_qa.md`

默认可见产物只保留 `metadata.json`、`transcript.txt` 和 `mindmap.md`。音频文件按来源保留，内部缓存、QA 和修正文件统一放进 `_pipeline/`，避免 episode 根目录堆满中间产物。

事实层不手改，阅读层可重复生成。发现转写、说话人或术语不准时，优先写入 `_pipeline/corrections.yaml` 或 `_pipeline/lexicon.yaml`，再重新生成 `transcript.txt`。

脑图阶段的目标不是把 transcript 机械缩短，而是提炼出框架、机制、因果链、反直觉判断、关键证据和行动建议。每个节点都要能回到 transcript 找到依据。

## Stage 1: 下载与转写

### 一键全流程

```bash
context-infrastructure/.venv/bin/python context-infrastructure/tools/podcast_pipeline.py run "https://www.xiaoyuzhoufm.com/episode/xxx" --output-dir collected-contents --num-speakers 2
```

这个命令会自动：

- 下载音频和元数据
- 运行 ASR + 说话人分离
- 写入 `_pipeline/transcript_raw.jsonl`
- 根据 `_pipeline/corrections.yaml` / `_pipeline/lexicon.yaml` 生成 `transcript.txt`
- 按需生成 `_pipeline/transcript_raw.txt` 和 `_pipeline/transcript_qa.md`

### 已有音频或目录

```bash
context-infrastructure/.venv/bin/python context-infrastructure/tools/podcast_pipeline.py run collected-contents/播客名/集标题 --num-speakers 2
```

### 只重建阅读版

```bash
context-infrastructure/.venv/bin/python context-infrastructure/tools/podcast_pipeline.py render collected-contents/播客名/集标题
```

适用场景：修改了 `_pipeline/corrections.yaml` 或 `_pipeline/lexicon.yaml`，不想重跑 ASR。

### 只运行 QA

```bash
context-infrastructure/.venv/bin/python context-infrastructure/tools/podcast_pipeline.py qa collected-contents/播客名/集标题
```

### 只初始化修正文件

```bash
context-infrastructure/.venv/bin/python context-infrastructure/tools/podcast_pipeline.py init collected-contents/播客名/集标题
```

### 底层转写工具

```bash
context-infrastructure/.venv/bin/python context-infrastructure/tools/transcribe_audio.py collected-contents/播客名/集标题/audio.m4a --num-speakers 2
```

关键参数：

- `--num-speakers 2`：已知说话人数量，播客通常为 2
- `--no-diarize`：不做说话人分离，仅转写
- `--threshold 0.5`：说话人活动检测阈值
- `--max-group-seconds 90`：阅读版单段最长时长
- `--max-group-chars 1500`：阅读版单段最长字数
- `--corrections _pipeline/corrections.yaml`：应用结构化修正
- `--lexicon _pipeline/lexicon.yaml`：应用术语替换

## Stage 2: Transcript 输出与 QA

`transcript.txt` 面向阅读：

```text
00:00:00 speaker_00: 不要以为会用几个 AI 工具，就以为掌握了 AI，前期你要先有一个别的东西，才有可能用 AI 去放大它

00:01:21 speaker_01: 欢迎大家来到 AI 炼金术，这一期我们邀请来的是课代表立正同学
```

格式要求：

- 时间戳固定为 `HH:MM:SS`
- speaker 标签使用 `speaker_00` / `speaker_01` 小写形式
- 连续同一 speaker 的 ASR 短句合并为一个段落
- speaker 切换、超过最长时长或超过最长字数时开启新段落
- 段落之间保留一个空行

`_pipeline/transcript_raw.txt` 面向校对，只有需要人工检查 ASR 短句时才生成：

```text
[00:00] [speaker_00] 我朋友问我就是说 AI 时代你要掌握什么
[00:07] [speaker_00] 我说当然你要学 AI
```

`_pipeline/transcript_raw.jsonl` 面向机器处理，每行一个 segment：

```json
{"start": 0.0, "end": 6.5, "speaker": "speaker_00", "text": "我朋友问我就是说 AI 时代你要掌握什么", "confidence": null, "source": "mlx-whisper+sortformer"}
```

`_pipeline/transcript_qa.md` 会标记这些风险：

- `long_monologue`：同一 speaker 连续超过阈值
- `possible_speaker_drift`：疑似说话人漂移
- `unknown_speaker`：无法识别说话人
- `outro_noise`：片尾音乐、平台水印或非正文
- `term_suspect`：常见误识别术语
- `segment_too_long`：阅读版段落仍然过长

用户指出某个时间点不准时，不重跑整期，优先做局部修正：

1. 根据时间点定位 `_pipeline/transcript_raw.jsonl`
2. 在 `_pipeline/corrections.yaml` 记录 speaker remap、文本替换或删除范围
3. 运行 `context-infrastructure/.venv/bin/python context-infrastructure/tools/podcast_pipeline.py render <episode_dir>`
4. 运行 `context-infrastructure/.venv/bin/python context-infrastructure/tools/podcast_pipeline.py qa <episode_dir>` 复查

`_pipeline/corrections.yaml` 示例：

```yaml
corrections:
  - type: force_break
    start: "01:09:13"
    reason: separate host question from guest answer
  - type: speaker_remap
    start: "01:09:13"
    end: "01:12:14"
    from: speaker_01
    to: speaker_00
    reason: diarization drift
  - type: force_break
    start: "01:12:14"
    reason: separate answer from next topic
```

`_pipeline/lexicon.yaml` 示例：

```yaml
replacements:
  chargept: ChatGPT
  cloudcode: Claude Code
  达疑: 答疑
```

## Stage 3: 生成高质量脑图

### 输出契约

默认只产出 `mindmap.md`。它使用嵌套 bullet，不使用 `##` 章节标题。这样更接近脑图树结构，也方便继续编辑和投喂给 Agent。

```markdown
# {节目标题}

- {时间戳} {章节标题}
  - {二级主题}
    - {具体判断/证据/方法}
    - {具体判断/证据/方法}
  - {二级主题}
    - {具体判断/证据/方法}
```

常见脑图层级：

1. 根节点：节目标题
2. 一级分支：按时间推进的章节，通常 6-10 个，以完整覆盖高价值论点为准
3. 二级分支：每章的概念组、论证模块或方法模块，通常 3-6 个
4. 叶子节点：具体判断、证据、案例、数字、行动建议，每个二级分支 1-3 条

层级服务表达。如果一个节点下面没有必要继续拆，就不要硬拆；如果一组叶子节点其实在服务同一个概念，应提炼出一个上位节点承载它们。

### Step 0: 收集上下文

1. 读取 `metadata.json`，提取标题、总时长、简介、时间轴。
2. 读取完整 `transcript.txt`。如果 transcript 超过 4000 行，先按 metadata 时间轴分段读取。
3. 如果用户提供了参考脑图图片，用 OCR 或人工读图确认目标层级。参考图只用于校准结构，不替代 transcript。

### Step 1: 建立全局骨架

先识别一级章节，再处理每章内部层级。不要边读边写。

章节边界优先级：

1. `metadata.description` 中的明确时间轴
2. 主持人的问题切换和过渡语
3. 嘉宾从概念解释转向案例、从方法论转向商业建议等语义切换
4. 行号比例估算时间戳，格式用 `MM:SS` 或 `H:MM:SS`

章节标题要写成「主题领域 + 核心洞察」，避免「嘉宾介绍」「商业模式探讨」这类空标签。标题允许比参考脑图更具体，但不能偏离该段主论点。

### Step 2: 提炼每章的知识单元

每章先提炼 3-6 个知识单元。知识单元可以是二级主题，也可以直接是高密度判断，形式服从内容。

优先抽取这些知识单元：

- 明确框架：如「AI 学习的三大门槛」「用户成长四阶段」
- 论证模块：如「商业价值的核心在于正确的非共识」
- 方法模块：如「构建私域流量与确定性连接」
- 风险与边界：如「区分 AI 的使用场景」
- 商业化模块：如「从 2C 转向 2B 的标准化服务」

判断标准：

- 如果某个节点下面还能自然挂出「原因、证据、例子、做法」，它适合作为中间节点。
- 如果一个观点本身已经完整、有强判断、有证据，就直接作为叶子节点。
- 如果参考脑图里只有抽象标签，而 transcript 里有更具体机制，优先用更具体机制替代。

### Step 3: 写出高密度节点

节点写具体信息，不写抽象概括。

优先级：

1. 嘉宾原创框架、模型、分类法
2. 反直觉判断或强观点
3. 关键数字、案例、业务数据
4. 具体行动建议
5. 原话中的高信息密度表达

写法要求：

- 每条 12-32 字，可略长，但必须自包含
- 用判断句或行动句，不写「相关讨论」「进一步分析」
- 同一组节点要互相支撑，避免并列无关
- ASR 有明显错字时，按上下文修正为真实含义
- 不要把 `metadata.description` 当最终答案。shownotes 是线索，最终表达必须回到 transcript 验证。

### Step 4: 质量自检并迭代

默认不能依赖外部参考脑图。参考脑图只在用户提供时使用；没有参考时，必须用 transcript 本身做质量自检。

通用自检维度：

1. **覆盖度**：是否覆盖 transcript 中的主论点、关键转折、原创框架、重要案例和数字？
2. **准确度**：每个节点是否能在 transcript 中找到依据？有没有把嘉宾观点说反、说泛、说偏？
3. **提炼度**：是否从话题标签升级为机制、因果链、框架或行动建议？例如「职业转型策略」应升级为「从技能出发改为从市场价值出发」。
4. **表达质量**：是否有空泛词、AI 味套话、重复节点？是否保留了原话中高信息密度的表达？

自检流程：

1. 先生成候选脑图。
2. 回看 transcript 的时间轴、metadata 要点和抽样原文段落，列出候选脑图遗漏或表达变形的地方。
3. 如果发现遗漏、误读、抽象标签过多或前重后轻，直接修订候选脑图。
4. 只有候选脑图通过上述自检，才写入 `mindmap.md`。

如果用户提供参考脑图、截图或旧版 `mindmap.md`，再额外做外部对比：参考中的关键论点要保留，参考遗漏但 transcript 中重要的机制和案例要补上。目标是在准确度和提炼度上得到更好的版本。

### 质量反例

```markdown
## 00:00 AI时代创业者的新形态与价值放大逻辑
- AI 是放大器而非起爆器
- 创业者不必做产品
- 一旦贴上"AI 做的"标签，品牌溢价垮掉
```

这个版本的问题不是少一级，而是信息关系没有表达出来：`AI 是放大器`、`创业者不必做产品`、`AI 标签损害溢价`属于不同论证模块，混在一起会降低知识提炼质量。更好的写法是：

```markdown
- 00:00 AI时代创业者的新形态与价值放大逻辑
  - AI 的本质是放大器
    - 必须先有核心业务或隐性知识，AI 才能放大价值
    - 仅掌握 AI 技术难以创造核心竞争力
  - 商业模式的重构：从产品思维转向服务思维
    - 不必执着开发 APP，应关注用户需求并提供确定性解决方案
    - 解决方案的确定性是高客单价的关键
```

## 输出物

```text
collected-contents/
└── 播客名/
    └── 集标题/
        ├── audio.mp3                  # 音频文件，按来源可选保留
        ├── metadata.json              # 元数据
        ├── transcript.txt             # 阅读层：合并段落
        ├── mindmap.md                 # 高质量脑图正文
        └── _pipeline/
            ├── transcript_raw.jsonl   # 事实层：原子 segment，默认保留
            ├── transcript_raw.txt     # 校对层：短句版，按需生成
            ├── corrections.yaml       # 修正层：speaker / 文本 / 删除范围，按需创建
            ├── lexicon.yaml           # 修正层：术语替换，按需创建
            └── transcript_qa.md       # QA 报告，按需生成
```

## 质量检查清单

- [ ] 已根据用户输入选择最短路径，没有重复跑已完成步骤
- [ ] 如果跑过 ASR，已检查 `_pipeline/transcript_qa.md` 中的高风险项
- [ ] 用户指出的错误已写入 `_pipeline/corrections.yaml` 或 `_pipeline/lexicon.yaml`，而不是直接改事实层
- [ ] 已完成基于 transcript 的脑图自检，而不是只生成第一版
- [ ] transcript 中的主论点、原创框架、关键案例和数字已覆盖
- [ ] 如果用户提供参考脑图，已额外对比并吸收其中有效信息
- [ ] 抽象标签已尽量升级为机制、因果链、框架或行动建议
- [ ] 节点保留了关键数字、案例、原话中的高信息密度表达
- [ ] 没有照搬 `metadata.description`，已根据 transcript 补全层级
- [ ] 去掉片头片尾寒暄、广告、BGM 歌词
- [ ] 全文没有前重后轻，后半段章节同样充分展开
- [ ] 层级服务表达，不为凑层级而牺牲准确和密度
- [ ] 章节数服从内容密度；长播客可超过 8 章，但不能用碎片章节凑篇幅

## 处理长 Transcript 的策略

- `< 2000` 行：可一次读完，直接建立全局骨架
- `2000-4000` 行：分 3-4 次读取，读完后统一建树
- `> 4000` 行：先用 metadata 时间轴定位章节，再按章节读取对应行段

写任何章节前，必须先知道全文内容分布。否则容易前半段过细、后半段缩水。

## 关键决策

| 决策点 | 选择 | 原因 |
|--------|------|------|
| 转写引擎 | mlx-whisper | Apple Silicon MLX 加速，比 whisperX CPU 快数倍 |
| 说话人分离 | mlx-audio Sortformer | MLX 原生加速，无需 HF_TOKEN / pyannote |
| 脑图提炼 | Cursor Agent 直接完成 | 需要回看 transcript 做判断和自检 |

## 与 bilibili_whisper_transcription 的区别

| | 本工作流 | bilibili_whisper_transcription |
|---|---|---|
| 来源 | 小宇宙播客 / 已有 transcript | B 站 / YouTube 视频 |
| ASR | mlx-whisper（Apple Silicon） | openai-whisper（CPU） |
| 说话人分离 | Sortformer（MLX 加速） | 无 |
| 额外能力 | QA 修正 + 高质量脑图 | LLM 后处理（分段、纠错） |
| 并发 | 单集处理 | 多进程批量转录 |

## 踩坑记录

| 问题 | 现象 | 解决方案 |
|------|------|----------|
| ASR 首次运行慢 | mlx-whisper 需下载模型（约 1.5GB） | 首次耐心等待，模型缓存在 `~/.cache/huggingface/` |
| Sortformer 首次运行慢 | 需下载 Sortformer 模型 | 首次耐心等待，后续使用缓存 |
| venv 未激活 | `ModuleNotFoundError` | 使用 `context-infrastructure/.venv/bin/python` |
| 只看 shownotes | 章节像节目简介，缺少论证 | shownotes 只用于定位，最终节点必须回到 transcript 验证 |

## 依赖

- Python 依赖（在 `context-infrastructure/.venv` 中，见 `context-infrastructure/tools/requirements.txt`）：`httpx`, `mlx-whisper`, `mlx-audio`
- 硬件要求：Apple Silicon Mac（M1/M2/M3/M4）
