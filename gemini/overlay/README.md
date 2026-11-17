# editor-ia-starter-kit-gemini

Edita videos cortos (Reels, Shorts) con Gemini, dentro de Google Antigravity.
Dejas tus clips en `inbox/`, hablas con el agente, y el video final sale en
`outbox/`. [English below](#english).

Este repo es un espejo de
[editor-ia-starter-kit](https://github.com/ziccarelli369/editor-ia-starter-kit)
(la versión para Claude Code). Se genera con un script; ver `MIRROR.txt`.

## Qué necesitas

| Herramienta | Para qué | Enlace |
| --- | --- | --- |
| Antigravity (la app) | El agente de Gemini que edita. Entra con tu cuenta de Google. | [antigravity.google/download](https://antigravity.google/download) |
| Node 22 o más nuevo | Los scripts del kit y HyperFrames | [nodejs.org](https://nodejs.org) |
| FFmpeg | Cortar, medir y codificar | [ffmpeg.org/download.html](https://ffmpeg.org/download.html) |
| Chrome | HyperFrames renderiza con él | [google.com/chrome](https://www.google.com/chrome/) |
| Git | Bajar el kit | [git-scm.com](https://git-scm.com) |

El chat normal de Gemini no sirve para esto: el kit necesita un agente que
ejecute programas en tu PC, y eso lo hace Antigravity.

En Windows, FFmpeg se instala con un comando en PowerShell:

```powershell
winget install Gyan.FFmpeg
```

## Instalar

1. Baja el kit:

   ```bash
   git clone https://github.com/ziccarelli369/editor-ia-starter-kit-gemini.git
   ```

2. Abre Antigravity y añade la carpeta `editor-ia-starter-kit-gemini` como proyecto.
3. Escribe en el chat:

   ```text
   /onboard
   ```

El agente instala lo que falta (`npm install`), revisa tu máquina y te pide los
datos de tu marca. No crea ningún video todavía.

## Hacer un reel

1. Copia tus clips a la carpeta `inbox/`.
2. Copia una canción que tengas derecho a usar a la carpeta `music/` (mp3 o
   wav). Una canción de Spotify no vale. Sin canción, el reel usa el sonido de
   los clips.
3. Escribe en el chat:

   ```text
   /new-video Toma el footage de inbox/ y haz un reel de Instagram que enganche.
   ```

4. Responde cuando el agente pregunte. Te pide un sí antes de mover archivos,
   antes de poner texto en pantalla, y antes de dar una versión por final.
5. Recoge el video y la portada en `outbox/<proyecto>/`.

Cuando Antigravity pida permiso para ejecutar `node`, `npm`, `npx` o `ffmpeg`,
acepta: son las cuatro herramientas del kit.

## Lo que el kit nunca hace

- Publicar, subir o postear. El final se queda en `outbox/`.
- Llamar a un servicio de pago sin tu sí en el chat.

## Modo experto (opcional)

Nada de esto hace falta para el primer reel. Cada punto está en
[docs/EXPERTO.md](docs/EXPERTO.md):

- **Subtítulos de voz**: whisper.cpp (gratis) o ElevenLabs.
- **ElevenLabs**: voz, efectos de sonido y transcripción medida. Por clave o por MCP.
- **Kie.ai**: música y clips generados.
- **Película 3D con Blender**: un personaje de juguete arma el video.
- **Copiar el estilo de un video que te gusta.**

## Carpetas

| Carpeta | Qué hay |
| --- | --- |
| `inbox/` | Todo lo que entra. Sin orden. |
| `video-projects/` | Trabajo en curso, un proyecto por carpeta. |
| `staging/` | Versiones de revisión (v1, v2…) para comparar. |
| `outbox/` | Solo finales: video, portada, texto, subtítulos. |
| `brands/` | Una carpeta por marca: colores, fuentes, logo. |
| `music/` | Tus canciones con licencia. |
| `.agents/skills/` | Las habilidades del agente. |
| `docs/` | El manual de edición y las guías. |

## Créditos y licencias

Espejo de editor-ia-starter-kit, que parte de un kit de edición con licencia
MIT (ver `LICENSE` y el permiso de uso en `licenses/`) y de
[HyperFrames](https://github.com/heygen-com/hyperframes) de HeyGen (Apache-2.0).
Ver `LICENSE`, `THIRD_PARTY_NOTICES.md` y `licenses/`. Los archivos Python de
`.agents/skills/film-engine/` usan la licencia GPL-3.0-or-later.

---

## English

Short-form video editing (Reels, Shorts) with Gemini inside Google Antigravity.
This repo is a generated mirror of
[editor-ia-starter-kit](https://github.com/ziccarelli369/editor-ia-starter-kit),
the Claude Code version; see `MIRROR.txt`.

1. Install [Antigravity](https://antigravity.google/download), Node 22+, FFmpeg, Chrome and Git.
2. Clone this repo and add the folder to Antigravity as a project.
3. Type `/onboard` once. The agent installs dependencies and checks the machine.
4. Put clips in `inbox/` and a track you own in `music/`.
5. Type `/new-video` and describe the reel. Finals land in `outbox/<project>/`.

Optional paths (voice captions, ElevenLabs, Kie.ai, the Blender 3D film) are in
[docs/EXPERTO.md](docs/EXPERTO.md). Licenses: `LICENSE`,
`THIRD_PARTY_NOTICES.md`, `licenses/`.
