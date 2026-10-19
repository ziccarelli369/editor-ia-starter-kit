---
name: website-to-hyperframes
description: Website-to-video workflow for HyperFrames. Use when a URL or website is the source of a video, such as a promo, social ad, product tour, or launch teaser. Captures the site in the Claude desktop browser pane, then scripts, voices, and builds the video.
---

# Website to HyperFrames

Capture a website, then produce a professional video from it.

The capture uses the built-in browser pane of the Claude desktop app (`mcp__Claude_Browser__*` tools). You see screenshots visually but cannot save them to disk; the capture result is a text file, `site-capture.md`.

The workflow has 7 steps. Each produces an artifact that gates the next.

---

## Step 1: Capture & Understand

**Read:** [references/step-1-capture.md](references/step-1-capture.md)

Open the URL in the browser pane at 1440 px desktop width and at the mobile preset. Take screenshots at the top, at each scroll position, and zoom on key elements. Pull copy with `get_page_text` / `read_page`, and colors, fonts, and logo/favicon URLs with `javascript_tool` (`getComputedStyle`). Write it all to `site-capture.md`. Ask the user to save any screenshot needed as an asset.

**Gate:** `site-capture.md` exists. Print your site summary (name, top colors, fonts, key assets, one-sentence vibe).

---

## Step 2: Write DESIGN.md

**Read:** [references/step-2-design.md](references/step-2-design.md)

Write a simple brand reference for the captured website. 6 sections, ~90 lines. This is a cheat sheet, not the creative plan — that comes in Step 4.

**Gate:** `DESIGN.md` exists in the project directory.

---

## Step 3: Write SCRIPT

**Read:** [references/step-3-script.md](references/step-3-script.md)

Write the narration script. The story backbone. Scene durations come from the narration, not from guessing.

**Gate:** `SCRIPT.md` exists in the project directory.

---

## Step 4: Write STORYBOARD

**Read:** [references/step-4-storyboard.md](references/step-4-storyboard.md)

Write per-beat creative direction: mood, camera, animations, transitions, assets, depth layers, SFX. This is the creative north star — the document the engineer follows to build each composition.

**Gate:** `STORYBOARD.md` exists with beat-by-beat direction and an asset audit table.

---

## Step 5: Generate VO + Map Timing

**Read:** [references/step-5-vo.md](references/step-5-vo.md)

Generate TTS audio, transcribe for word-level timestamps, and map timestamps to beats. Update STORYBOARD.md with real durations.

**Gate:** `narration.wav` (or .mp3) + `transcript.json` exist. Beat timings in STORYBOARD.md updated.

---

## Step 6: Build Compositions

**Read:** The `/hyperframes` skill (invoke it — every rule matters)
**Read:** [references/step-6-build.md](references/step-6-build.md)

Build each composition following the storyboard. After each one: self-review for layout, asset placement, and animation quality.

**Gate:** Every composition has been self-reviewed. No overlapping elements, no misplaced assets, no static images without motion.

---

## Step 7: Validate & Deliver

**Read:** [references/step-7-validate.md](references/step-7-validate.md)

Lint, validate, preview. Create a HANDOFF.md for multi-session continuity.

**Gate:** `npx hyperframes lint` and `npx hyperframes validate` pass with zero errors.

---

## Quick Reference

### Video Types

| Type                  | Duration | Beats | Narration              |
| --------------------- | -------- | ----- | ---------------------- |
| Social ad (IG/TikTok) | 10-15s   | 3-4   | Optional hook sentence |
| Product demo          | 30-60s   | 5-8   | Full narration         |
| Feature announcement  | 15-30s   | 3-5   | Full narration         |
| Brand reel            | 20-45s   | 4-6   | Optional, music focus  |
| Launch teaser         | 10-20s   | 2-4   | Minimal, high energy   |

### Format

- **Landscape**: 1920x1080 (default)
- **Portrait**: 1080x1920 (Instagram Stories, TikTok)
- **Square**: 1080x1080 (Instagram feed)

### Reference Files

| File                                                    | When to read                                                                                                                                                   |
| ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [step-1-capture.md](references/step-1-capture.md)       | Step 1 — browser-pane capture, site-capture.md                                                                                                                       |
| [step-2-design.md](references/step-2-design.md)         | Step 2 — writing DESIGN.md                                                                                                                                     |
| [step-3-script.md](references/step-3-script.md)         | Step 3 — writing the narration script                                                                                                                          |
| [step-4-storyboard.md](references/step-4-storyboard.md) | Step 4 — per-beat creative direction                                                                                                                           |
| [step-5-vo.md](references/step-5-vo.md)                 | Step 5 — TTS, transcription, timing                                                                                                                            |
| [step-6-build.md](references/step-6-build.md)           | Step 6 — building compositions with self-review                                                                                                                |
| [step-7-validate.md](references/step-7-validate.md)     | Step 7 — lint, validate, preview, handoff                                                                                                                      |
| [techniques.md](references/techniques.md)               | Steps 4 & 6 — 10 visual techniques with code patterns (SVG drawing, Canvas 2D, 3D, typography, Lottie, video, typing, variable fonts, MotionPath, transitions) |
