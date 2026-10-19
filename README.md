# editor-ia-starter-kit

Kit de inicio para editar videos cortos (Reels, Shorts) con Claude Code.
Dejas el material en `inbox/`, hablas con el agente, y el video final sale en `outbox/`.

English below.

## Qué necesitas

- [Claude Code](https://claude.com/claude-code) en la app de escritorio de Claude.
- Node 22 o más nuevo: https://nodejs.org
- FFmpeg en el PATH: https://ffmpeg.org/download.html
- Chrome o Chromium (HyperFrames lo usa para renderizar).
- whisper.cpp para transcribir gratis en tu máquina: https://github.com/ggml-org/whisper.cpp/releases
  (en Windows descarga `whisper-bin-x64.zip`, descomprime y agrega la carpeta al PATH;
  en Mac `brew install whisper-cpp`). `npx hyperframes doctor` te dice si lo encuentra.

Sin ninguna clave de API el kit funciona completo: transcripción local con
Whisper y gráficos en movimiento diseñados por el agente.

## Instalar

```bash
npm install
```

```bash
npx hyperframes doctor
```

Copia `.env.example` a `.env`. Llena una clave solo si vas a usar ese servicio
(ElevenLabs para voz y efectos, Kie.ai para música y clips generados).

## Usar

1. Deja tu grabación en `inbox/`.
2. Abre Claude Code en esta carpeta y escribe `/new-video`.
3. Elige **guiado** (el camino conocido, con revisiones en cada paso) o
   **libre** (sin guion, tú diriges).
4. Elige la marca. La primera vez, el agente copia `brands/_template/` y te
   pide colores y fuentes.
5. Revisa cada borrador cuando el agente te lo pida.
6. Recoge el video, la portada, el texto y los subtítulos en `outbox/<proyecto>/`.

## Carpetas

| Carpeta | Qué hay |
| --- | --- |
| `inbox/` | Todo lo que entra. Sin orden. |
| `video-projects/` | Trabajo en curso, un proyecto por carpeta con fecha. |
| `outbox/` | Solo finales: video, portada, texto, subtítulos. |
| `brands/` | Una carpeta por cliente: colores, fuentes, logo, reglas. |
| `styles/` | Estilos de edición copiados de videos que te gustan. |
| `.claude/skills/` | Las habilidades del agente. |
| `docs/` | El manual de edición y las guías. |

## Ajustes

`kit.config.json`:

- `language`: idioma en que te habla el agente. `es` por defecto.
- `models.profile`: `solo` (un agente Opus 5.5 hace todo) o `team` (Opus dirige y
  diseña, Haiku 5.5 hace el trabajo mecánico en paralelo, más barato).
- `transcription.provider`: `whisper` (local, gratis) o `elevenlabs`.
- `defaults`: tamaño del video y marca por defecto.
- `outbox`: qué es obligatorio entregar.

## Copiar el estilo de un video que te gusta

Descarga el video a `inbox/` y di: "quiero editar como este video". El agente lo
mide con ffmpeg, escribe las reglas en `styles/drafts/<nombre>/` con la evidencia
de cada regla, y te ofrece una prueba de 3 segundos. Si te gusta, lo mueves a
`styles/core/`.

---

## English

A starter kit for short-form video editing (Reels, Shorts) with Claude Code and
HyperFrames. Drop footage in `inbox/`, talk to the agent, pick up finals in `outbox/`.

Install: Node 22+, FFmpeg, Chrome, and whisper.cpp (`whisper-cli` on PATH, or `WHISPER_PATH`). Then `npm install` and `npx hyperframes doctor`.
Copy `.env.example` to `.env` only if you want ElevenLabs or Kie.ai.

Use: put footage in `inbox/`, open Claude Code here, type `/new-video`, choose
guided or freeform, choose a brand, review drafts, collect the result in `outbox/`.

Settings live in `kit.config.json`: agent language, model profile (`solo` or
`team`), transcription provider, defaults, and the delivery contract.

Reverse-engineer a style: download a reference to `inbox/`, say "edit like this
video". The agent measures it, writes rules with evidence to `styles/drafts/`,
and offers a 3-second test. Promote to `styles/core/` by hand.

## Credits and licenses

Built on [Herk Edit Kit](https://github.com/nateherkai/herk-edit-kit) by Nate
Herk (MIT, plus the kit use permission in `licenses/`) and
[HyperFrames](https://github.com/heygen-com/hyperframes) by HeyGen (Apache-2.0).
The reverse-engineering method borrows from [REA](https://github.com/morluto/rea)
(MIT). See `LICENSE`, `THIRD_PARTY_NOTICES.md` and `licenses/`.
