const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

const cards = [
  {
    num: 2,
    diagram: 'card2-diagram.png',
    title: 'System Prompt 怎么设计\n才能命中 Prefix Cache？',
    insight: 'M1 + M2 在同一 Profile 版本内字节完全不变，可命中 LLM Provider 的 Prefix Cache，首 token 延迟降低约 50%。\nM3 用独立 system message 注入，不破坏缓存前缀。',
    tag: 'Prompt 构建'
  },
  {
    num: 3,
    diagram: 'card3-react-diagram.png',
    title: 'Agent 的核心循环\n推理 → 行动 → 观察',
    insight: 'LLM 输出 tool_call 就执行，输出 text 就结束。MaxStep 是安全阀防止无限循环。\n工具按序执行不并行——状态一致性比吞吐更重要。',
    tag: 'ReAct Loop'
  },
  {
    num: 4,
    diagram: 'card4-tools-diagram.png',
    title: '工具不是越多越好\nPhase 白名单裁剪',
    insight: '工具按来源分三组注册到统一 Registry。运行时读取 Dynamic Context 中的 phase，\n做白名单裁剪：早期只开上下文工具，后期逐步解锁更多能力。',
    tag: '工具编排'
  },
  {
    num: 5,
    diagram: 'card5-skill-diagram.png',
    title: 'LLM 自己决定\n要不要读 SOP',
    insight: 'Prompt 里只放 Skill 摘要列表（省 token），LLM 判断需要时主动 tool_call 拉完整 SOP。\n懒加载 = 省 token + 精准匹配。',
    tag: 'Skill 加载'
  },
  {
    num: 6,
    diagram: 'card6-compress-diagram.png',
    title: '长对话不爆 context window\n的三道防线',
    insight: 'L1 纯规则零延迟，去冗余 JSON 只留关键字段。L2 异步触发，单轮多步 trace 压成一段话。\nL3 远古历史压成增量摘要。三层协同把增长从 O(n) 压到 O(log n)。',
    tag: '历史压缩'
  },
  {
    num: 7,
    diagram: 'card7-memory-diagram.png',
    title: 'Agent 怎么\n跨轮次记住用户？',
    insight: 'Session 按轮次持久化，每条回复多 Part 存储。Memory 是结构化 KV，运行时写入 →\n下一轮 Snapshot 注入 Prompt。两者配合 = 短期记忆 + 长期偏好。',
    tag: '记忆管理'
  }
];

function generateHTML(card) {
  const diagramPath = path.resolve(__dirname, 'rendered', card.diagram);
  const diagramBase64 = fs.readFileSync(diagramPath).toString('base64');
  const titleLines = card.title.split('\n');
  const insightLines = card.insight.split('\n');

  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    width: 960px;
    height: 1280px;
    background: #12121f;
    font-family: -apple-system, "PingFang SC", "Noto Sans SC", sans-serif;
    color: #e8e8f0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .header {
    padding: 48px 56px 20px;
    flex-shrink: 0;
  }
  .tag {
    display: inline-block;
    background: linear-gradient(135deg, #4a6fa5, #5a8fd5);
    color: #fff;
    font-size: 18px;
    font-weight: 500;
    padding: 6px 18px;
    border-radius: 20px;
    margin-bottom: 20px;
    letter-spacing: 1px;
  }
  .title {
    font-size: 42px;
    font-weight: 700;
    line-height: 1.3;
    color: #ffffff;
    letter-spacing: 1px;
  }
  .diagram-area {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 10px 40px;
    min-height: 0;
  }
  .diagram-area img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    border-radius: 16px;
    filter: drop-shadow(0 4px 20px rgba(74, 111, 165, 0.3));
  }
  .footer {
    padding: 24px 56px 40px;
    flex-shrink: 0;
  }
  .insight {
    font-size: 20px;
    line-height: 1.65;
    color: #b0b8d0;
    border-left: 3px solid #4a6fa5;
    padding-left: 20px;
  }
  .page-num {
    text-align: right;
    font-size: 18px;
    color: #5a6a8a;
    margin-top: 16px;
    font-weight: 500;
  }
</style>
</head>
<body>
  <div class="header">
    <div class="tag">${card.tag}</div>
    <div class="title">${titleLines.join('<br>')}</div>
  </div>
  <div class="diagram-area">
    <img src="data:image/png;base64,${diagramBase64}" />
  </div>
  <div class="footer">
    <div class="insight">${insightLines.join('<br>')}</div>
    <div class="page-num">${card.num} / 8</div>
  </div>
</body>
</html>`;
}

async function main() {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  for (const card of cards) {
    const html = generateHTML(card);
    const page = await browser.newPage();
    await page.setViewport({ width: 960, height: 1280, deviceScaleFactor: 2 });
    await page.setContent(html, { waitUntil: 'networkidle0' });
    const outputPath = path.resolve(__dirname, 'rendered', `card${card.num}-final.png`);
    await page.screenshot({ path: outputPath, type: 'png' });
    await page.close();
    console.log(`Card ${card.num} → ${outputPath}`);
  }

  await browser.close();
  console.log('Done!');
}

main().catch(console.error);
