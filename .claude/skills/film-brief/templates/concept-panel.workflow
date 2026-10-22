export const meta = {
  name: 'film-concept-panel',
  description: 'Four independent directors pitch a character film from four angles; a judge scores them and grafts the best ideas into one director brief',
  whenToUse: 'film-brief step 3, when the idea is open. Taste work: every agent runs on the design model.',
  phases: [
    { title: 'Pitch', detail: 'four independent angles' },
    { title: 'Judge', detail: 'score, pick, graft, write the brief' },
  ],
}

// args (paths absolute, forward slashes):
// {
//   kit, project,
//   theme,        // e.g. 'MMA and Brazilian jiu-jitsu'
//   audience,     // who must smile, and the authentic details they know (rituals, rules, gear, terms)
//   sources,      // [paths]: the prompt pack text, articles, the reference DESIGN.md, contact sheets
//   constraints,  // extra hard limits for this film (formats, length, legal), optional
//   angles,       // optional [{ key, angle }] to replace the four defaults
// }

const A = args || {}
for (const k of ['kit', 'project', 'theme', 'audience', 'sources']) {
  if (A[k] === undefined) throw new Error(`concept-panel: args.${k} is required`)
}

const BRIEF = `You are a film director (the design model: you own taste). Read every source first:
${A.sources.map(s => `- ${s}`).join('\n')}
Read the format rules: ${A.kit}/.claude/skills/character-film/SKILL.md and ${A.kit}/.claude/skills/film-brief/SKILL.md (section 4).

THE FORMAT: a toy 3D hero lives on a software workspace that lies flat like a giant glowing desk (each panel a floating slab). The hero operates the real tools; every hit lands on a beat frame and changes the RESULT playing on the app's viewer. At the end the software falls away and only the hero's work remains. BRAND block = HERO, APP, RESULT, SET.

THE THEME: ${A.theme}
THE AUDIENCE: ${A.audience}
A wrong fact about the theme loses this audience at once. Check every term, rule and ritual you use.

ENGINEERING LIMITS (do not fight them): Blender Cycles on one consumer GPU (about 1.8 s a 1080p frame). The hero is built in Python from rounded primitives: a toy with rigid parts and few hinge joints; no cloth, no hair, no realistic human, no mocap. Moves read through toy poses, hops, rolls, flips, slams, squash and stretch, and the camera. The APP is an HTML page screenshotted to a texture (real layout and labels, no logos). The RESULT is drawn on a 2D canvas per frame (text, shapes, glows, simple vector art; no photos, no footage). Sound is synthesized (no samples, no words). No real people's names or likenesses, no real organisations' names or logos.
${A.constraints ? `FILM CONSTRAINTS: ${A.constraints}` : ''}
Lessons from the reference film: keep the hero large (>= 10-15 % of the frame width); keep the RESULT in frame with the hero whenever a hit changes it; land the ending on ONE strong poster frame and hold it, never an idle wide; a move that changes nothing is cut.

DELIVER A PITCH (plain text, 600-900 words) with: 1 TITLE and on-screen TAGLINE; 2 ONE SENTENCE; 3 BRAND (HERO with sizes in cm and hex colours and what changes over the film, APP with every panel and state and the tools used, RESULT frame by frame as it accumulates, SET with the light sources); 4 BPM, duration and a BEATS table (time | picture | RESULT change | the theme move or ritual | sound); 5 CAMERA in 4-6 lines incl. the impacts; 6 LOOK in 3-5 lines; 7 SOUND sketch and the signature sound; 8 VERTICAL 9:16; 9 RISKS: the two things most likely to look bad or read wrong, and the mitigation.`

const ANGLES = A.angles || [
  { key: 'faithful', angle: 'FAITHFUL SWAP: keep the reference film\'s proven beat structure and change only the BRAND block. Map each beat to a theme equivalent, so the structure is proven and the theme is total.' },
  { key: 'journey', angle: 'THE JOURNEY: find the arc the theme is known for (a progression, a rank, a career) and compress it into the film, so the hero visibly changes as he masters each tool.' },
  { key: 'world', angle: 'THE WORLD: the SET is the theme\'s own place and event; the software is the arena or the opponent. Maximise impact, scale and spectacle.' },
  { key: 'double-meaning', angle: 'THE DOUBLE MEANING: find one sharp double meaning between the theme and software and build the whole film on it; every beat pays the joke off again, ending on its strongest version.' },
]

const PITCH = { type: 'object', properties: {
  title: { type: 'string' }, tagline: { type: 'string' }, one_sentence: { type: 'string' }, pitch: { type: 'string' },
}, required: ['title', 'tagline', 'one_sentence', 'pitch'] }

phase('Pitch')
const pitches = await parallel(ANGLES.map(a => () => agent(
  `${BRIEF}\n\nYOUR ANGLE: ${a.angle}\nBe bold and specific. Return the pitch.`,
  { label: `pitch:${a.key}`, phase: 'Pitch', schema: PITCH, model: 'opus', effort: 'high' },
)))
const got = pitches.map((p, i) => p ? { angle: ANGLES[i].key, ...p } : null).filter(Boolean)
log(`${got.length}/${ANGLES.length} pitches`)

phase('Judge')
const verdict = await agent(
  `${BRIEF}\n\nYOU ARE THE JUDGE AND HEAD DIRECTOR, not a pitcher. The pitches:\n\n${got.map((p, i) => `=== PITCH ${i + 1} (${p.angle}): ${p.title}, "${p.tagline}"\n${p.pitch}`).join('\n\n')}\n\n` +
  `Score each pitch 1-10 on: one-sentence clarity, theme truth (would an expert smile or wince?), visual boldness, causality (every hit changes the RESULT), feasibility (a procedural toy hero, a short Blender render), the sound hook, and the vertical cut. Pick a winner and graft the best specific ideas from the others. Check every theme fact.\n` +
  `Write the FINAL BRIEF following ${A.kit}/.claude/skills/film-brief/templates/DESIGN.md section by section (BEATS as a precise table with frames, frame = floor(t*fps + 0.5) + 1; RULINGS with numbers; a copy-ready SOUND prompt; a DO NOT list with clichés, wrong theme facts and legal risks).`,
  { label: 'judge', phase: 'Judge', model: 'opus', effort: 'max', schema: { type: 'object', properties: {
    scores: { type: 'array', items: { type: 'object', properties: {
      title: { type: 'string' }, scores: { type: 'string' }, total: { type: 'number' }, best_idea: { type: 'string' }, weakest_point: { type: 'string' },
    }, required: ['title', 'total', 'best_idea', 'weakest_point'] } },
    winner: { type: 'string' }, grafts: { type: 'array', items: { type: 'string' } },
    brief: { type: 'string', description: 'the full DESIGN.md in markdown' },
  }, required: ['scores', 'winner', 'grafts', 'brief'] } },
)
return { pitches: got, verdict }
