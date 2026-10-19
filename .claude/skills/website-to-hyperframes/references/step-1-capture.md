# Step 1: Capture & Understand

Capture the site with the built-in browser pane of the Claude desktop app (tools `mcp__Claude_Browser__*`). No API keys, scripts, or external capture tools are used.

**What the pane can and cannot do:**

- You **see** each screenshot visually. You read it in context like an image.
- You **cannot** write a screenshot to disk from the pane. No PNG file appears in the project.
- The durable output of this step is a text file: `site-capture.md` in the project directory.
- If a screenshot must become a video asset, ask the user to save it (see "Assets" below).

## 1. Open the site at desktop width

1. `navigate` to the target URL.
2. `resize_window` with `width: 1440`, `height: 900`.
3. `navigate` to the URL again, so layout code runs at the new width.
4. If a cookie banner covers the page, decline non-essential cookies.

## 2. Take screenshots

1. `computer` → `screenshot` at the top of the page. This is the hero, the most important image. Note: is the background light or dark? What is the dominant visual element? What colors jump out?
2. `computer` → `scroll` down (about 5 ticks), then `screenshot`. Repeat until you reach the page footer.
3. `computer` → `zoom` on key elements: the logo, the primary button, a product UI image, a stat block. A zoom shows exact detail that a full screenshot loses.
4. `resize_window` with `preset: "mobile"`, reload, and take a top screenshot plus 2-3 scroll screenshots. Note how the layout changes.
5. `resize_window` with `preset: "desktop"` when you finish.

After the screenshots, write 3-4 sentences on the visual mood, layout patterns, color strategy, and overall feel.

## 3. Pull text and structure

- `get_page_text` — the headline, tagline, key selling points, statistics, and social proof.
- `read_page` with `filter: "all"` — heading order, section count, buttons and links (CTAs).
- `find` — locate one element (for example "Get started") when you need it.

## 4. Pull colors, fonts, and image URLs

Run this with `javascript_tool` (`action: "javascript_exec"`). It reads computed styles, so the values are what the browser actually renders.

```js
(() => {
  const pick = (el) => {
    if (!el) return null;
    const s = getComputedStyle(el);
    return {
      tag: el.tagName.toLowerCase(),
      text: (el.innerText || '').trim().slice(0, 60),
      color: s.color,
      background: s.backgroundColor,
      backgroundImage: s.backgroundImage !== 'none' ? s.backgroundImage.slice(0, 200) : null,
      font: s.fontFamily,
      size: s.fontSize,
      weight: s.fontWeight,
      radius: s.borderRadius,
    };
  };
  const q = (sel, n) => [...document.querySelectorAll(sel)].slice(0, n).map(pick);
  const fonts = new Set();
  document.querySelectorAll('body, h1, h2, h3, p, a, button').forEach((el) => fonts.add(getComputedStyle(el).fontFamily));
  const icons = [...document.querySelectorAll('link[rel~="icon"], link[rel="apple-touch-icon"]')].map((l) => l.href);
  const logos = [...document.querySelectorAll('header img, nav img, img[alt*="logo" i], img[src*="logo" i], header svg')]
    .slice(0, 5)
    .map((el) => el.currentSrc || el.src || el.outerHTML.slice(0, 300));
  const images = [...document.images]
    .filter((i) => i.naturalWidth >= 400)
    .slice(0, 15)
    .map((i) => ({ src: i.currentSrc || i.src, alt: i.alt, w: i.naturalWidth, h: i.naturalHeight }));
  return {
    title: document.title,
    body: pick(document.body),
    headings: q('h1, h2, h3', 8),
    buttons: q('button, a[class*="btn" i], a[class*="button" i], [role="button"]', 6),
    sections: q('main > section, body > section, main > div, section', 5),
    fontFamilies: [...fonts],
    fontFiles: [...document.fonts].filter((f) => f.status === 'loaded').map((f) => `${f.family} ${f.weight} ${f.style}`),
    favicons: icons,
    logos,
    images,
    counts: {
      sections: document.querySelectorAll('section').length,
      headings: document.querySelectorAll('h1, h2, h3').length,
      videos: document.querySelectorAll('video').length,
      canvases: document.querySelectorAll('canvas').length,
    },
  };
})();
```

Convert `rgb(...)` values to HEX when you write them down. If the page uses `<canvas>` or `<video>`, note it: the site may use WebGL effects or motion you can recreate with the patterns in [techniques.md](techniques.md).

## 5. Write `site-capture.md`

Write the results to `site-capture.md` in the project directory. Later steps read this file, so the raw tool output can leave your context.

```markdown
# Site Capture: <site name>

URL: <url> · Captured: <date>

## Visual summary
<3-4 sentences from the screenshots: mood, layout, color strategy, feel. Note the desktop vs mobile difference.>

## Colors
- `#0A0A0A` — body background
- `#FFFFFF` — heading text
- `#635BFF` — primary button background
...

## Fonts
- Headings: <family>, <weight>
- Body: <family>, <weight>

## Copy
- Headline: ...
- Tagline: ...
- Selling points: ...
- Stats / social proof: ...
- CTAs: ...

## Structure
<count> sections, <count> headings, <count> CTAs. One line per section: what it shows.

## Assets
| Asset | URL | What it shows | Saved as |
| ----- | --- | ------------- | -------- |
| Logo | https://... | white wordmark, SVG | assets/logo.svg (or "not saved") |
| Favicon | https://... | ... | ... |
| Hero image | https://... | ... | ... |

## Screenshots seen
One line per screenshot: position (top, scroll 1, ..., mobile top) — what it shows.
```

## Assets

Compositions need real files in `assets/`. The pane cannot save them for you. Two ways to get them:

1. **Image URLs (logo, favicon, hero images).** List them in `site-capture.md`. Ask the user once for permission to download them into `assets/`, and name each file, its source, and its type. On a clear yes, download them. On a no, mark them "not saved".
2. **Screenshots (product UI, a full section).** Ask the user to save the screenshot from the browser pane into `assets/` with a filename you give (for example `assets/hero-desktop.png`). Then record the filename in the Assets table.

Do not wait for assets to continue. Steps 2-4 can proceed, and the storyboard marks missing assets.

## Gate

`site-capture.md` exists. Print your site summary before you go to Step 2:

- **Site:** [name]
- **Colors:** [top 3-5 HEX values with roles]
- **Fonts:** [font families]
- **Sections:** [count] sections, [count] headings, [count] CTAs
- **Key assets:** [3-5 most useful assets for video, and whether each is saved]
- **Vibe:** [one sentence on the visual identity]
