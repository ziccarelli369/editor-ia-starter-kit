# Goals: hooks and CTAs by what the video is for

`project.json` `goal` is one of `personal`, `sell`, `grow`. The goal sets the
hook family, the CTA, the pacing bias and the cover rule. Read this before
`DESIGN.md`; the brief wins over any line here.

## personal — a post for the user's own account

The viewer already knows the person. Prove a moment, not a lesson.

- Hooks: an emotional beat first ("Muy bien, Víctor"), a raw cue over motion,
  a time stamp ("Martes, 21:40, última ronda"), a confession ("Hoy me montaron 6 veces").
- Pacing: breathe. Fewer cuts, longer holds, one takeover at most.
- CTA: none, or a question in the caption ("¿Cuál te repiten más a ti?").
- Cover: a face or a real moment, one short line, no title card.
- Graphics: counters and labels only when they add a joke or a fact.

## sell — classes, a gym, a service

The viewer is a prospect. Show the thing they would pay for: the coach, the
room, the correction landing, the people. Every reel ends with a way in.

- Hooks: the problem the prospect has ("Si te montan siempre, es esto"), the
  coach on camera with one promise, a before/after inside one session, social
  proof ("12 personas nuevas este mes, así fue su primera clase").
- Required brand fields (from `brands/<slug>/DESIGN.md` → Offer): place,
  schedule, offer, handle or link. A sell reel with a missing field stops and
  asks for it.
- CTA, on screen and in the caption, in this order: offer, place, how to start.
  Example: "Clase de prueba gratis · Tatami Lab, Chamberí · DM 'PRUEBA'".
  Keep it on screen at least 2.5 s, above the 220 px safe zone.
- Pacing: medium. The correction must be readable; the coach's face must appear
  at least once in the first 5 s.
- Cover: coach or room plus the offer line.
- Caption: offer first, then two lines, then 3 hashtags including a local one.

## grow — a sport or skill account that wants reach

The viewer is a stranger who trains. Teach one thing and make it saveable.

- Hooks: a numbered promise ("3 detalles que el coach corrige"), a question with
  a visible answer slot, a counter-intuitive claim ("No levantes la cadera, aún"),
  a freeze on the exact moment.
- Structure: hook → payoff promise in 3 s → each point with one on-screen label
  → lesson card → CTA. Numbered points get a counter and a progress bar.
- Pacing: fast between points, still on the point. A freeze with an annotation
  beats three cuts.
- CTA: save, then follow. "Guárdalo para tu próxima clase" first; follow line
  second, smaller.
- Cover: the title plus one annotated frame. The cover must read at 150 px wide.
- Caption: the lesson in one line, the three points, 5 hashtags, no local tag.

## Picking when `goal` is empty

Ask once: "¿Esto es para tu cuenta, para vender clases, o para crecer la
cuenta?" Write the answer to `project.json` and go on.
