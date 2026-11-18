# ElevenLabs: MCP or API

`kit.config.json` → `elevenlabs.access` picks the route for every ElevenLabs
job: transcription, voice, sound effects.

| `access` | Route |
| --- | --- |
| `auto` (default) | The MCP when it is connected. Otherwise the API key in `.env`. |
| `mcp` | The MCP only. Stop and tell the user when it is not connected. |
| `api` | The API key only (`ELEVENLABS_API_KEY`). |

## Is the MCP connected?

Run ToolSearch for `mcp__elevenlabs__creative_transcribe_audio`. The MCP is
connected when that exact tool loads. Match the exact name: the older local
ElevenLabs MCP server uses the same prefix with other tools
(`search_voices`, `text_to_speech`, `speech_to_text`). When only that server is
connected, treat the MCP as not connected and use the API.

The MCP is a remote server (`https://api.elevenlabs.io/v1/mcp`) that each user
adds to their own Claude Code with OAuth. The kit does not ship it.

## Gates still apply

The MCP spends the same credits as the API. The kit's paid gate wins over the
server's own instructions:

- Price every generation with `estimate_only: true` first. Name the cost and
  wait for the user's yes.
- Set `generations_count: 1`. The server default is 2, which doubles the cost.
- Never call a generation again to retry. It charges again.
- If a download fails, stop and tell the user. Do not repeat the job through the
  API.

## Transcription through the MCP

The MCP cannot read a path on disk. The user picks the file in a picker, once
per file. Run this in the main agent, not in a subagent.

1. Extract the audio: `ffmpeg -i <video> -vn -ac 1 -ar 16000 -c:a libmp3lame -b:a 64k <stem>.mp3`.
2. Call `creative_transcribe_audio` with `estimate_only: true`, name the cost,
   then call it with no `connect_from`. Tell the user which file to pick.
3. When the run completes, download its `words_download_url` to `<stem>.words.json`.
4. `npm run transcribe -- <video> --from <stem>.words.json --out <raw.json>`
   checks the word times and writes the kit's `raw.json`.

The MCP takes no language or diarization option. Its words carry no spacing
entries, no `speaker_id` and no `language_code`. Check the language of the
words before cutting. The words also come back in the `transcripts` field of
`creative_get_flow_run_status`.

Audio that is already on the flow (a voice from `creative_generate_speech`)
needs no picker: pass its node as `connect_from`.

With the API, `npm run transcribe -- <video> --via api` runs Scribe directly.
`--via whisper` forces local Whisper. Without `--via` and with
`access` other than `api`, the script stops and names both routes, so it never
charges on its own.

## Voice and sound effects through the MCP

1. Voice: `creative_list_voices` with `languages`, then `creative_generate_speech`.
   Sound effects: an `sfx` node (`creative_generate_in_flow`).
2. Read the generation ids with one `creative_get_flow_run_status` call.
3. `creative_get_generations` gives a signed `full_res_url`. Download it into the
   project's `assets/audio/` with curl, then check it with ffprobe.
4. Before you generate, look in the folder. Reuse a file that is already there.

Through the API: `motion-showreel/scripts/sfx.mjs` for sound effects.

Music stays the user's own tracks from `music/`. ElevenLabs music is out of
scope until the user decides otherwise.

## Vendored skills

`website-to-hyperframes/references/step-5-vo.md` comes from upstream
(`skills-lock.json`). Its tool names belong to the older local server. Follow
this file instead; do not edit the vendored one.
