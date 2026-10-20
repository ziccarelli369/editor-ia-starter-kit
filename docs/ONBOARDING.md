# Primer arranque / First run

**Objetivo:** de cero a tu primer reel en una sesión. Tiempo: 20 a 40 minutos
la primera vez, la mayor parte instalando.

## Antes de abrir Claude Code

1. Instala Node 22+, ffmpeg y Chrome (`docs/SETUP.md`, pasos 1 y 2).
2. En esta carpeta: `npm install`.
3. Copia `.env.example` a `.env`. Si tienes clave de ElevenLabs, ponla ahí.
   Sin clave: instala whisper.cpp (`docs/SETUP.md`, paso 3).
4. Comprueba: `node scripts/setup.mjs`. Debe decir "Todo listo".

## En Claude Code

1. Abre Claude Code en esta carpeta.
2. Escribe `/onboard`. El agente revisa la máquina, te pregunta dos idiomas
   y los datos de tu primera marca. No crea ningún video.
3. Deja un video en `inbox/`.
4. Escribe `/new-video`. Elige **guiado**. Responde a las puertas cuando pregunte.
5. Recoge el video, la portada, el texto y los subtítulos en `outbox/<proyecto>/`.

## Qué esperar

- Un reel vertical de 25 a 45 s, con subtítulos de 1 a 3 palabras, en el
  estilo del manual de edición incluido.
- Un archivo `VERIFY.md` dentro del proyecto con cada comprobación y su prueba.
- Coste por video: unos 10 a 15 USD en tokens de Opus, más céntimos de ElevenLabs.

## Graba para el kit

Vertical, la cara del que habla en los primeros 5 segundos, luz de frente.
Un clip horizontal y oscuro funciona, pero el resultado tiene techo.

---

## English

Before Claude Code: install Node 22+, ffmpeg, Chrome; `npm install`; copy
`.env.example` to `.env` (ElevenLabs key, or whisper.cpp per `docs/SETUP.md`
step 3); run `node scripts/setup.mjs` until it says "Todo listo".

In Claude Code: open this folder, type `/onboard` (machine check, two languages,
first brand, no video made), drop footage in `inbox/`, type `/new-video`, choose
guided, answer the gates, collect the result in `outbox/<project>/`.

Expect a 25 to 45 s vertical reel with 1 to 3 word captions, a `VERIFY.md`
with every check, and about 10 to 15 USD of Opus tokens per video.
Shoot vertical, speaker's face in the first 5 s, light from the front.
