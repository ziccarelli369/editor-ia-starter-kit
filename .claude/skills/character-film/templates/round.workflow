export const meta = {
  name: 'character-film-round',
  description: 'One production round of a character film: owners build or fix in parallel, the scene is assembled while motion is still in work, an integrator renders review frames, a critic panel judges only the rendered frames',
  whenToUse: 'character-film Gate 3 to Gate 5: the build round and every fix round. Pass the round as args.',
  phases: [
    { title: 'Owners', detail: 'each role edits only its own files, in parallel' },
    { title: 'Assemble', detail: 'scene assembly starts as soon as the asset owners finish' },
    { title: 'Integrate', detail: 'bake motion, model check, stills, animatic, contact sheets' },
    { title: 'Critique', detail: 'four lens critics in parallel, then a head critic merges one verdict' },
  ],
}

// args (all paths absolute, forward slashes):
// {
//   kit, project, film,              // kit root, project folder, one-line film description
//   round, mode,                     // 1, 'build' | 'fix'
//   roles: [{ key, owns: [files], model, effort, brief, stage, until, report }],
//                                    // brief = the director's notes for this owner;
//                                    // stage 'motion' for motion and camera owners, else 'assets';
//                                    // until = 'HH:MM' local timebox; report = done, skip the agent
//   integrator: { model, effort, brief, prep },   // prep = extra notes for the assembly step
//   critic: { prior: [issues], open: [items], rulings: [lines], stills: 'frame list or empty', lenses },
//   reportLines                      // line cap for owner reports (shrink each round: 60, 45, 35)
// }
// Taste roles (UI design, result, hero, look, set, motion, camera, sound, every critic) run on the
// design model. Mechanical roles (scene assembly, checker code, render plumbing) may run on the
// engineer model from kit.config.json.
// Staging: the asset owners (stage 'assets') feed the scene assembly, which starts while the motion
// owners (stage 'motion') still work; the bake and the renders wait for both. With no motion-stage
// role the assembly step is skipped and the integrator does everything.

const A = args || {}
for (const k of ['kit', 'project', 'film', 'round', 'mode', 'roles', 'integrator']) {
  if (A[k] === undefined) throw new Error(`round.workflow: args.${k} is required`)
}
const ENGINE = `${A.kit}/.claude/skills/film-engine`
const CRITIC = `${A.kit}/.claude/skills/film-critic/SKILL.md`
const CAP = A.reportLines || 45
const REVIEW = `${A.project}/reviews/round-${A.round}`

const COMMON = `You are one agent in a small film crew. The film: ${A.film}
Project folder (run everything from here): ${A.project}
This is ${A.mode === 'build' ? 'the BUILD round' : `FIX ROUND ${A.round}`}.
Read DESIGN.md (the brief and the director's rulings) and timeline.py (the contract) first, then the files you own.
The engine is ${ENGINE}: read its API.md before you call it. Engine code is shared; if it has a bug, report it under ENGINE with a repro; change it only if your role says so.

Crew rules:
- Write only the files you own. Never edit timeline.py, DESIGN.md or checks_config.py (the director owns the contract and every threshold). Put a needed change under CONTRACT CHANGES with the exact new value and the reason.
- Never write build/ or renders/ outputs that another owner produces, and never while a Blender render reads them. Scratch work goes under scratch/<your-role>/.
- Measure, never guess: every claim of a fix carries a number before and after. Look at every image you produce (Read the PNG) before you call it done.
- The GPU is shared: test renders stay small (<= 50 % size, <= 16 samples, few frames) unless your role says otherwise. Time a render only when nvidia-smi shows the GPU idle.
- Python entry scripts start with sys.dont_write_bytecode = True. Write big files in parts of about 300 lines per tool call. Say "quick check", never the other phrase.
Final answer: a plain-text report of at most ${CAP} lines with the headings CHANGED (file: what, why) / CHECKED (command -> number before -> after; images looked at) / CONTRACT CHANGES / ENGINE / OPEN.`

// A role that already carries `report` (a string) is done: no agent runs for it. Give every role a
// report to resume a stalled round from its integration.
// A role with `until` ("HH:MM", local time, from the director) has a timebox.
const timebox = r => r.until ? `\nTIMEBOX: stop by ${r.until} local time. Check the clock (date +%H:%M) before every long step. At the timebox, finish the edit in hand, leave every file you own consistent and importing, and report what is left under OPEN.` : ''
const ownerAgent = r => typeof r.report === 'string' ? Promise.resolve(r.report) : agent(
  `${COMMON}\n\nROLE: ${r.key.toUpperCase()}. You own: ${r.owns.join(', ')}.${timebox(r)}\n\n${r.brief}`,
  { label: `${A.mode}${A.round}:${r.key}`, phase: 'Owners', model: r.model || 'opus', effort: r.effort || 'high' })
const reportOf = (roles, out) => roles.map((r, i) => `=== ${r.key}\n${out[i] || '(no report: the agent failed)'}`).join('\n\n')

const assetRoles = A.roles.filter(r => r.stage !== 'motion')
const motionRoles = A.roles.filter(r => r.stage === 'motion')
const motionWorking = motionRoles.some(r => typeof r.report !== 'string')

phase('Owners')
const assetsThenPrep = (async () => {
  const out = await parallel(assetRoles.map(r => () => ownerAgent(r)))
  const reports = reportOf(assetRoles, out)
  if (!motionWorking) return { reports, prep: '' }
  const prep = await agent(`${COMMON}

ROLE: INTEGRATOR, ASSEMBLY STEP. You own scene.py and the build/ outputs of the chain. The asset owners have finished; the motion and camera owners (${motionRoles.map(r => r.key).join(', ')}) are still working on their files, so do not import their modules' new interfaces as final.
Get everything that does not depend on motion ready now: run python -B build.py --upto sound (timeline, UI texture and contract, result and clock sequences, sound); make scene.py build every asset (heroes, set, panels, tiles, screens, sprites, materials and look) and bake with the motion module as it is today, so the blend step runs; fix integration glue; send owner bugs under OPEN with the owner's name. Do not render stills or the animatic yet.
Asset owner reports:\n${reports}\n\n${(A.integrator && A.integrator.prep) || ''}`,
    { label: `${A.mode}${A.round}:assemble`, phase: 'Assemble', model: A.integrator.model || 'opus', effort: A.integrator.effort || 'high' })
  return { reports, prep }
})()
const motionOut = parallel(motionRoles.map(r => () => ownerAgent(r)))
const [assets, motionDone] = await Promise.all([assetsThenPrep, motionOut])
const reports = [assets.reports, motionRoles.length ? reportOf(motionRoles, motionDone) : ''].filter(Boolean).join('\n\n')
log(`owners done: ${A.roles.length}; assembly ${assets.prep ? 'done' : 'skipped'}`)

phase('Integrate')
const integ = await agent(`${COMMON}

ROLE: INTEGRATOR. You own scene.py, the build/ outputs of the chain, renders/stills/, renders/animatic/ and reviews/round-${A.round}/.
1. Run the chain from the contract down: python -B build.py --upto check (timeline.json, UI texture and contract, result and clock sequences, sound, .blend, model check). Fix only integration glue; send owner bugs back under OPEN with the owner's name.
2. The model check must print VIOLATIONS: 0, or list each violation under OPEN with its owner.
3. Render the stills (${(A.critic && A.critic.stills) || 'the frame list in build.json'}) and the half-res animatic with sound, then the contact sheets and filmstrips into ${REVIEW}/. Measure them with the stills mask (stills.json).
4. Run the freshness check: every render newer than the .blend, the .blend newer than every input.
Never end your turn while a render or a build step runs: wait for it (a foreground command with a long timeout, or an until-loop on its output). Your final answer is the report after every render above exists; a report that says "now I wait" leaves the critic with stale frames.
${assets.prep ? `Your assembly step already ran; its report:\n${assets.prep}\n` : ''}Owner reports:\n${reports}\n\n${A.integrator.brief || ''}`,
  { label: `${A.mode}${A.round}:integrate`, phase: 'Integrate', model: A.integrator.model || 'opus', effort: A.integrator.effort || 'high' })

phase('Critique')
const C = A.critic || {}
const LENSES = C.lenses || [
  { key: 'framing', focus: 'framing and camera: the model report, hero size and margins, the result text boxes in frame at every press, stillness at hits, crossings and whips, the 9:16 cut on its own terms; measure through the stills mask and the engine camera module' },
  { key: 'look', focus: 'look, set and legibility: colours against their targets (stills.json), blown pixels, separation of the hero from what is under him, the screen text readable at phone size, the set and its lights, texture and continuity of materials' },
  { key: 'story', focus: 'story, motion and theme: the hook in the first 2 s, every hit changing the result, each key pose reading as its position to a practitioner, the acting and timing in the animatic filmstrips, the payoff and the poster frame' },
  { key: 'sound', focus: 'sound and sync: the sound report and check PNG, the hit table, picture hits against sound cues in the animatic, the loudness contour; say what a human must listen for' },
]
const ISSUES = { type: 'object', properties: {
  fresh: { type: 'object', properties: { ok: { type: 'boolean' }, detail: { type: 'string' } }, required: ['ok', 'detail'] },
  issues: { type: 'array', items: { type: 'object', properties: {
    severity: { type: 'string', enum: ['blocker', 'major', 'minor'] }, frames: { type: 'string' }, owner: { type: 'string' },
    evidence: { type: 'string' }, fix: { type: 'string' }, predicted: { type: 'string' },
  }, required: ['severity', 'frames', 'owner', 'evidence', 'fix'] } },
  prior: { type: 'array', items: { type: 'object', properties: {
    id: { type: 'string' }, status: { type: 'string', enum: ['fixed', 'partly', 'not_fixed', 'not_my_lens'] }, evidence: { type: 'string' },
  }, required: ['id', 'status'] } },
  score: { type: 'number' },
}, required: ['fresh', 'issues', 'score'] }
const CONTEXT = `Review folder: ${REVIEW}/ (plus renders/stills/, renders/animatic/, stills.json, the model reports, build/sound_report.txt and sound_check.png).
Prior issues to confirm:\n${JSON.stringify(C.prior || [], null, 1)}
The integrator's OPEN list:\n${JSON.stringify(C.open || [], null, 1)}
Director's rulings in force:\n${(C.rulings || []).join('\n') || '(see DESIGN.md)'}
Integrator report:\n${integ}`
const lensOut = await parallel(LENSES.map(l => () => agent(`${COMMON}

ROLE: CRITIC, LENS ${l.key.toUpperCase()}. You did not build this film. Read ${CRITIC} and follow it, judging through your lens only: ${l.focus}. Mark prior issues outside your lens as not_my_lens.
${CONTEXT}`,
  { label: `${A.mode}${A.round}:critic-${l.key}`, phase: 'Critique', model: 'opus', effort: 'xhigh', schema: ISSUES })))

const VERDICT = {
  type: 'object',
  properties: {
    fresh: { type: 'object', properties: { ok: { type: 'boolean' }, detail: { type: 'string' } }, required: ['ok', 'detail'] },
    prior: { type: 'array', items: { type: 'object', properties: {
      id: { type: 'string' }, status: { type: 'string', enum: ['fixed', 'partly', 'not_fixed'] }, evidence: { type: 'string' },
    }, required: ['id', 'status', 'evidence'] } },
    open_items: { type: 'array', items: { type: 'object', properties: {
      item: { type: 'string' }, status: { type: 'string', enum: ['confirmed', 'denied'] }, evidence: { type: 'string' },
    }, required: ['item', 'status', 'evidence'] } },
    issues: { type: 'array', items: { type: 'object', properties: {
      id: { type: 'string' }, severity: { type: 'string', enum: ['blocker', 'major', 'minor'] },
      frames: { type: 'string' }, owner: { type: 'string' }, evidence: { type: 'string' },
      fix: { type: 'string' }, predicted: { type: 'string' },
    }, required: ['id', 'severity', 'frames', 'owner', 'evidence', 'fix'] } },
    top3: { type: 'array', items: { type: 'string' } },
    scores: { type: 'object', properties: {
      hook: { type: 'number' }, readability: { type: 'number' }, continuity: { type: 'number' },
      motion: { type: 'number' }, sound_sync: { type: 'number' }, theme: { type: 'number' },
    } },
    ready_for_final: { type: 'boolean' },
  },
  required: ['fresh', 'prior', 'open_items', 'issues', 'top3', 'ready_for_final'],
}
const verdict = await agent(`${COMMON}

ROLE: HEAD CRITIC. Four lens critics judged round ${A.round} independently:
${LENSES.map((l, i) => `=== ${l.key}\n${JSON.stringify(lensOut[i] || '(lens failed)', null, 1)}`).join('\n\n')}

Read ${CRITIC}. Merge their findings into one verdict: deduplicate (same defect seen through two lenses is one issue), give every issue an id (r${A.round}-<n>), keep the strongest evidence, resolve disagreements by looking at the frames yourself, confirm or deny each prior issue and OPEN item, name the three largest defects (top3), score each axis 1-10. ready_for_final is true only when no blocker remains.
${CONTEXT}`,
  { label: `${A.mode}${A.round}:critic-head`, phase: 'Critique', model: 'opus', effort: 'xhigh', schema: VERDICT })

return { owners: reports, assembly: assets.prep, integrator: integ, lenses: lensOut, verdict }
