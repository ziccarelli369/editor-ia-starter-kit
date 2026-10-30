# Resource provenance

editor-ia-starter-kit is a derivative of an MIT-licensed teaching kit; its
copyright notice is kept in `LICENSE` as that license requires. The original kit's example
media and AIS brand assets are not included. The reverse-engineer-style skill
borrows its evidence method (observed / inferred / unknown claims, ledgers,
fail-closed verification) from REA by morluto (https://github.com/morluto/rea, MIT).

- HyperFrames: https://github.com/heygen-com/hyperframes (Apache-2.0).
  The hyperframes, hyperframes-cli, hyperframes-registry, and gsap skill packages
  were bundled with the original workspace from the HyperFrames skill ecosystem.
  The upstream Apache license is included in licenses/HYPERFRAMES-LICENSE.
- GSAP is installed from npm; its own license applies. See the license files in
  node_modules/gsap and https://gsap.com/community/standard-license/.
- Some library styles reference Google Fonts. Font licenses remain with their
  publishers. Install and preserve applicable licenses when localizing fonts.
- The style templates are not official brand assets or endorsed by any creator
  or organization.

No blanket relicensing of third-party components is implied. See LICENSE for the
MIT permission for the original kit material. Imported pipeline resources
retain the grant in licenses/PIPELINE-USE-PERMISSION.txt. This includes the added
pipeline skills, style library, templates, shared editing tools, and new short-form
workflow. Third-party notices override these grants for their respective assets.

Library names, handles, statistics, and source labels inside cards are illustrative
placeholders. Replace them with your own verified copy before publishing a video.

## Film path tools (optional, none bundled)

The 3D character film (`character-film`) uses these tools. The kit ships none of
them. Each keeps its own license.

- Blender: https://www.blender.org (GPL-3.0-or-later as distributed, from the
  `license/license.md` of Blender 5.2; its source files carry GPL-2.0-or-later
  headers). The user installs it. The Python files in
  `.claude/skills/film-engine/` use its Python API or load together with files
  that do, so they are GPL-3.0-or-later (see `LICENSE` and
  `licenses/GPL-3.0.txt`), and they run inside the user's own Blender.
- pedalboard by Spotify: https://github.com/spotify/pedalboard (GPL-3.0, from
  its `.venv` metadata). `npm run film:install` installs it into the user's `.venv`.
- numpy: https://numpy.org (BSD-3-Clause; its wheel also lists 0BSD, MIT, Zlib
  and CC0-1.0 for bundled parts) and scipy: https://scipy.org (BSD-3-Clause).
  Both from their `.venv` metadata, installed into the user's `.venv`.
- Pillow: https://python-pillow.org (MIT-CMU, from its `.venv` metadata),
  installed into the user's `.venv`.
- puppeteer-core: https://github.com/puppeteer/puppeteer (Apache-2.0, from
  `node_modules/puppeteer-core/package.json`). `npm install` installs it.
- Chrome: https://www.google.com/chrome/ The user installs it. Its use falls
  under the Google Terms of Service and the Chrome Additional Terms
  (https://www.google.com/chrome/terms/).

The character-film format comes from a study of the "No After Effects" prompt
pack by Clawd Motion Lab and the article "Motion Engineering: Build a Video
Studio Around Opus 5.5" by @0xwhrrari
(https://x.com/0xwhrrari/status/2105643919119696297).
