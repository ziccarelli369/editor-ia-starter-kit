Google Antigravity with a Gemini model. Read `kit.config.json` at the start of
every task: it sets the language, the model profile, the transcription
provider, the default brand and the delivery contract. Speak to the user in
`language` (default `es`). Skills, docs and code stay in English.

Skills live in `.agents/skills/<name>/SKILL.md`. Each one is also a slash
command (`/new-video`). When a row of the Map names a skill, read its
`SKILL.md` in full before you act.
