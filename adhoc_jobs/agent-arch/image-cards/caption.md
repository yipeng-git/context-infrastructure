# 小红书正文文案

分享一个在生产环境跑了半年多的 Agent 架构，8 张图讲完核心设计。不涉及具体业务，只聊通用的工程模式。

每张图一个主题：
1⃣ 端到端请求链路全景
2⃣ Prompt 三段式 + Prefix Cache 优化
3⃣ ReAct 推理-行动循环
4⃣ Phase 工具白名单裁剪
5⃣ Skill SOP 懒加载
6⃣ 三层历史压缩（规则→LLM→增量摘要）
7⃣ Session + Memory 双向记忆流
8⃣ 8 个模式一句话总结

做 Agent 这半年最大的体感：LLM 是 CPU，Prompt 是指令集，工具是外设，Memory 是寄存器，Session 是磁盘，压缩是 GC。想清楚这层类比，很多设计决策就自然了。

你们的 Agent 架构用了哪些类似的模式？有什么不一样的做法？评论区聊聊 👇

---

#Agent架构 #LLM #AI工程 #ReAct #大模型应用 #系统设计 #后端架构 #AIAgent #PromptEngineering #技术分享
