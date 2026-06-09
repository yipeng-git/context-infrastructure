# Design — Pi Agent Builder Video

## Mood
Technical warmth. Builder energy — someone who crafts tools for themselves. Not corporate-cold, not startup-hyper. Quiet confidence.

## Palette
- **Background:** `#0c0e17` (deep charcoal, warm undertone)
- **Foreground:** `#f0ece4` (warm off-white)
- **Dim:** `#a09585` (warm gray, secondary text)
- **Accent:** `#e8a040` (warm amber)
- **Accent Alt:** `#d4785c` (copper, for variation)
- **Surface:** `rgba(240, 236, 228, 0.06)` (cards, panels)
- **Surface border:** `rgba(240, 236, 228, 0.08)`

## Typography
- **Chinese:** "PingFang SC", "Source Han Sans SC", sans-serif
- **Serif Display (EN):** "Crimson Pro", serif
- **Monospace:** "JetBrains Mono", monospace
- **Headlines:** 700-900 weight, 64-120px
- **Body:** 300-400 weight, 32-40px
- **Code/Data:** 400-600 weight, 28-36px mono

## Constraints
- Dark canvas only
- Amber accent at full saturation for focal elements, 8-15% opacity for atmospheric glows
- No cyan, no purple, no neon
- No gradient text (background-clip: text)
- Monospace for all technical terms, API names, package names
- Serif display only for English brand names (Pi, pi.dev)

## What NOT to Do
- No left-edge accent stripes on callout cards (use left border on module cards only as structural, not decorative)
- No pure `#000` or `#fff` — always tint toward amber
- No identical card grids — vary card content and accent colors
- No centered-and-floating web layouts — anchor to edges, use split frames
