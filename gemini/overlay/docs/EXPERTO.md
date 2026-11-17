# Modo experto

Todo aquí es opcional. El primer reel sale sin nada de esto.

## Subtítulos de voz (transcripción)

Solo hace falta cuando alguien habla en el video.

- **Gratis, en tu PC: whisper.cpp.** En Windows descarga
  `whisper-blas-bin-x64.zip` de la
  [versión v1.8.3](https://github.com/ggml-org/whisper.cpp/releases/tag/v1.8.3),
  descomprime, y apunta `HYPERFRAMES_WHISPER_PATH` en `.env` al
  `whisper-cli.exe`. Detalles en [SETUP.md](SETUP.md), paso 3.
- **De pago, más preciso: ElevenLabs Scribe.** Ver abajo.

## ElevenLabs

Sirve para tres cosas: transcripción medida, efectos de sonido y voz generada.

**Por clave (lo que usan los scripts del kit):**

1. Crea una clave en
   [elevenlabs.io/app/settings/api-keys](https://elevenlabs.io/app/settings/api-keys).
2. Ponla en `.env`: `ELEVENLABS_API_KEY=...`
3. En `kit.config.json`, cambia `transcription.provider` a `elevenlabs`.

El agente te dice el coste y espera tu sí antes de cada llamada de pago.

**Por MCP (el agente usa ElevenLabs como herramienta):**

Sigue el README del servidor oficial,
[github.com/elevenlabs/elevenlabs-mcp](https://github.com/elevenlabs/elevenlabs-mcp).
En Antigravity: Customizations → Installed → MCP Servers → Add MCP Server. El
archivo del proyecto es `.agents/mcp_config.json`. Deja la clave fuera de ese
archivo si vas a compartir la carpeta.

Más en [TOOLS-AND-API-KEYS.md](TOOLS-AND-API-KEYS.md).

## Kie.ai (música y clips generados)

Clave en [docs.kie.ai](https://docs.kie.ai/), luego `KIE_API_KEY=...` en `.env`.
Sin clave, la música sale de `music/` y los gráficos los diseña el agente.

## Copiar el estilo de un video

Baja el video a `inbox/` y di: "quiero editar como este video". El agente lo
mide, escribe las reglas en `styles/drafts/<nombre>/` y te ofrece una prueba de
3 segundos. Si te gusta, pasa a `styles/core/`.

## Película 3D con Blender

Un personaje de juguete arma un gráfico sobre una app gigante. Es pesado:
[Blender 5.x](https://www.blender.org/download/), una GPU que Cycles soporte,
[Python 3.10+](https://www.python.org/downloads/) y unos 5 GB por película.

1. Instala Blender 5.x.
2. `npm run film:install`
3. `npm run setup -- --film` y arregla cada línea `FAIL`.
4. Di "quiero una película 3D". El agente usa la habilidad `character-film`.

Detalles en [SETUP.md](SETUP.md), "Film path".

**Límite de este espejo.** Las plantillas `*.workflow` de `character-film` y
`film-brief` reparten cada ronda entre varios agentes con una herramienta que
solo existe en Claude Code. En Antigravity el agente hace los mismos pasos uno
tras otro, leyendo la plantilla como lista de tareas. Esta ruta no está probada
con Gemini.

## Sin probar con Gemini

- `website-to-hyperframes` (video desde una web): adaptado al navegador de
  Antigravity, sin prueba real.
- El perfil `team` (subagentes de nivel flash).

## Bloqueo de texto antes de escribir (hook)

El kit ya impide entregar un video con texto en pantalla sin tablero de texto
aprobado. Este hook añade el mismo control antes de cada escritura del agente.
Para activarlo, copia `.agents/hooks.example.json` a `.agents/hooks.json` y
reinicia Antigravity. Si el agente deja de poder escribir archivos o ejecutar
comandos, borra `.agents/hooks.json`: el formato del hook no está probado con
una instalación real.
