# Tools, accounts, and API keys

The kit's default for **transcription** is local Whisper through
`npm run transcribe -- <video>`. It needs no key and reads the footage language from `kit.config.json`. **ElevenLabs Scribe**
(`npm run transcribe:elevenlabs`) is the optional paid path. **Kie.ai** is optional for
generated video and image assets. Bring your own accounts and credits, and
configure only what you use.

## What you need

| Tool or service | When you need it | Setup and cost |
| --- | --- | --- |
| Claude Code | Following the agent-guided editing skills | Your own assistant access. External service API credits are separate. |
| Node.js 22+, npm, Git, FFmpeg with ffprobe, and Chrome/Chromium | Local editing, preview, and rendering | Install on your computer. See [setup](SETUP.md). |
| HyperFrames and GSAP | Video compositions and animation | Installed by `npm install`. Rendering runs locally. Some templates use online fonts or CDNs; localize selected assets for final rendering. |
| Local Whisper (`npm run transcribe`) | The kit's default for speech transcription | No key. Runs on your computer; the first run downloads a model, which needs disk space and local compute. |
| ElevenLabs Scribe | Optional paid transcription | Your own key with `speech_to_text` access and available usage. The included helper sends audio to ElevenLabs. |
| Kie.ai | Optional generated moving B-roll, images, and other supported assets | Your own account, key, and credits. Existing footage, supplied assets, or motion graphics built in HyperFrames can be used instead. |
| Your footage, logos, fonts, music, and sound effects | Building the actual edit | Supply assets you can use. The kit does not include a stock-media or music subscription. |

The kit's checks need no paid transcription or generation API.
Choose a provider only when the next stage needs it.

## Local Whisper: the default

From the repository root, run:

```sh
npm run transcribe -- video-projects/<yyyy-mm-dd>-<slug>/assets/raw.mp4
```

The command uses whisper.cpp on your computer and sends no audio to a cloud
service. Use `--model medium.en` for noisy English audio. Use a model without
the `.en` suffix and pass `--language` for other languages. See the
[transcript guide](../.claude/skills/hyperframes/references/transcript-guide.md)
for model choice and the mandatory quality check.

## ElevenLabs: the optional paid helper

Create a key in [ElevenLabs API settings](https://elevenlabs.io/app/settings/api-keys)
and put it in the root `.env` as `ELEVENLABS_API_KEY`. Then run:

```sh
npm run transcribe -- video-projects/<yyyy-mm-dd>-<slug>/assets/raw.mp4
```

The helper writes word-level JSON beside the input. Reuse a verified transcript
instead of paying to transcribe the same take again. See the official
[Scribe API documentation](https://elevenlabs.io/docs/api-reference/speech-to-text/convert)
for current model options and usage details. The helper only calls ElevenLabs;
changing the key does not switch its provider.

## Transcript format for the cutting tools

The cutting tools require this common format, with **word-level times in seconds**
on the exact source recording's timeline:

```json
{
  "text": "Hello world.",
  "audio_duration_secs": 2.0,
  "words": [
    { "text": "Hello", "start": 0.2, "end": 0.6 },
    { "text": "world.", "start": 0.7, "end": 1.2 }
  ]
}
```

Ask the assistant to map a provider's `word` field to `text` when necessary,
preserve numeric start/end times, and get full source duration from ffprobe.
Paragraphs, SRT subtitles, and segment-only transcripts do not supply the required
word timing. Request word timestamps or perform alignment; do not invent timing.
Later edits must retime words using their EDL. Short-form plans additionally track
`sourceStart` and `sourceEnd`.

Copy either prompt:

> Use ElevenLabs instead of local Whisper for this recording. Use my locally
> configured key, request word timestamps, and normalize the result for this
> kit before cutting. Preserve the source and verify timing against its audio.

> Use local Whisper for transcription. Check the model download first, then
> normalize the word timestamps for this kit. Keep transcription local
> and use my supplied footage and assets without paid generation.

## Kie.ai: generated video and assets

[Kie.ai](https://kie.ai/) is the kit's optional provider for generated video and
image assets. Set `KIE_API_KEY` in `.env` if you choose it. Follow the
[official API guide](https://docs.kie.ai/) for keys, model-specific requests,
task status, and credits. If you have no Kie key, the agent builds motion
graphics in HyperFrames instead.

The short-form skill describes a Kie workflow; the kit does **not** bundle a
universal Kie generation script or connected account. The `motion-showreel` skill
includes a small client (`scripts/kie.mjs`) for its three showreel assets: Suno
instrumental music, Seedream stills from a logo reference, and Kling camera moves.
Ask the assistant to configure your selected model using current documentation. Adding a key alone does not
create an integration. Model inputs, formats, availability, and credit costs vary.

Prepare the proposed assets and expected cost before paid work that you have not
already authorized. Keep task IDs, reuse successful outputs, and save chosen
results inside your private project's assets. Inspect their motion, duration,
aspect ratio, and framing in the final edit.

> Use Kie.ai for moving B-roll in the approved scenes. Check my local configuration
> and current model documentation, then show me the assets you propose and expected
> credit cost. Reuse existing footage wherever it fits.

## Other optional tools referenced by bundled skills

These are workflow options, not requirements:

- **Narration:** HyperFrames guides describe local Kokoro TTS with extra runtime
  and model setup. ElevenLabs and HeyGen TTS are also mentioned; each needs your
  service access and a configured API or connector.
- **Sound effects:** `motion-showreel` can generate an SFX kit with ElevenLabs
  sound generation (`scripts/sfx.mjs`). It uses `ELEVENLABS_API_KEY`; the key needs
  sound-effects access as well as `speech_to_text`. Your own SFX library works too.
- **Helper runtimes:** some optional scripts require Python. Playwright is
  included for relevant browser workflows; browser binaries may need installation.

A skill's mention of an MCP tool does not install that integration. Ask the
assistant to check which connectors or API clients are available first.

## Configure only what you use

Copy [`.env.example`](../.env.example) to `.env`. It holds two entries:
`ELEVENLABS_API_KEY` and `KIE_API_KEY`. Leave unused entries blank. The
ElevenLabs helper loads the root `.env`; other providers need their own client
or environment loading configured by the assistant.
Keep credentials out of compositions, screenshots, and commits.

Check current provider pricing and your balance before paid calls. The kit does
not include transcription, generation, voiceover, or assistant credits.
