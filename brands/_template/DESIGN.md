# Brand: _template

Copy this folder to `brands/<brand-slug>/` and fill it in. One brand per client.
The agent reads only the brand named in the project's `project.json`.

## Who

- Name: Your brand
- Audience: who watches, in one line
- Voice: three adjectives (for example: direct, warm, no jargon)
- Language of on-screen text: es

## Look

Tokens live in `tokens.css`. Keep both files in sync.

| Token | Value | Use |
| --- | --- | --- |
| `--brand-bg` | #0d0f12 | Full-screen backgrounds and takeovers |
| `--brand-fg` | #f4f6f8 | Body text and captions |
| `--brand-accent` | #ff5a36 | One accent only: keyword highlights, progress, CTA |
| `--brand-muted` | #9aa3ad | Secondary text, eyebrows |

Fonts: `--font-display` for headlines, `--font-body` for captions and text.
Put font files in `fonts/` or use a Google Fonts link. Never mix more than two.

## Assets

- `logo.svg` or `logo.png`: clearspace equal to the logo height, never recolored.
- Watermark position: bottom-right, 4% margin, 60% opacity.

## Rules the agent must keep

- Captions: one or two lines, max 5 words per line, centered in the lower third,
  safe from the platform UI (keep 220 px clear at the bottom of a 1080x1920 frame).
- Keyword highlight uses `--brand-accent` only.
- Cover: hero frame plus the hook sentence in `--font-display`, logo bottom-right.
- Never use another brand's colors, fonts or assets in this brand's projects.
