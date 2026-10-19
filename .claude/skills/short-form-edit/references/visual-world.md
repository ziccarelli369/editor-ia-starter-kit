# The visual world

Read this when you choose the visual direction and design the graphics and footage. For a minimal, Apple-style brief, also read [premium-motion-and-footage.md](premium-motion-and-footage.md): restrained type, negative space, real object depth, directional light, and soft contact shadows, with motion and sound that stay rich and purposeful.

## Direction and layout

- Choose a visual direction from the subject, audience, source material, and brand brief, and record why it suits this story. Documentary footage, visual comedy, product demonstrations, and designed objects are options, not quotas. Use coherent colours, type, and transitions; paper is one material among many.
- Choose full speaker, split, or full supporting footage by the current attention target. Keep expressions, gestures, and the evidence visible in each requested ratio.
- Plan rhythm by sequence: burst, anticipation, reveal, breathing room. Treat 1-2 s per event as a pacing diagnostic, not a cutting schedule. Hold longer when a developing action or performance earns it, and record the reason. Assign each transition by its editorial purpose.
- Escalate and release. Short moments of relative stillness land a conviction or a reveal. A short reel ends without the long-form 4-6 s outro.
- Use an object **callback**: the unfinished model planted in the hook resolves at the payoff. Show relationships and transformations, so a muted viewer still follows the central idea.
- Keep text in the phone-safe region. For 1080x1920 start with x=90..930, y=200..1600; this leaves the right edge and bottom for social UI. Place captions by the actual face position in every layout. Use short phrase groups and exact word onsets; keyword emphasis keeps the speaker's wording.

## Layers and actions

Give the eye one clear attention target. Use depth, occlusion, light, and camera movement when they make the action easier to follow. Keep type readable; use dimensional type only when the material world calls for it. For a paper brief, inspect fibres, edges, folds, contact shadows, and perspective in the encoded output.

Give every extended graphic beat an **action with an outcome**: a key seats and a project starts, criteria turn into checks, a card opens to reveal a result, a stack assembles into a system. A card such as "Define good" can swivel so its edge and moving contact shadow stay visible as its criteria resolve. Secondary motion supports the main action; each object moves for its own reason, not with a shared idle bob.

Study how attention moves in a human-edited reference: wide context, isolated detail, interaction, visible consequence, then back to the speaker. Before delivery, name what makes each sequence entertaining beyond looking professional; a new heading or caption alone is not an answer.

Review adjacent shots as silhouettes and actions, with headings hidden. If two still look like the same card reveal, redesign the weaker one. Vary the mechanism: tear to reveal, unfold to show scale, press to create, connect to enable, process to produce a result. Keep a coherent world with clear cause and effect, and spend the strongest action on the most important spoken idea. A user's engagement score is feedback for iteration, not something a validator certifies.

## Named people

Audit the transcript for named people, products, and places before storyboarding. When recognizing a real person matters, use a verified portrait: prefer their own site or an attributable source, save provenance, and inspect the image. Animate the photograph as a physical object, with a callback when it fits. A moving portrait is a photographic layer, not moving B-roll. Never generate a likeness and present it as an authentic photo.

## Product stories

Seek real source material: public product pages, official documentation, authentic screen recordings, official logos. Record real scrolls, selections, or interactions when useful. Keep source URLs, and label authentic product footage, illustrative interfaces, and generated B-roll separately. Hide every real credential in captured UI. An animated screenshot can be one layer of a composition; when the brief requires video, it does not replace moving B-roll.

## Brand assets

Use only the authentic mark. Take the user-supplied asset first; otherwise get it from the brand's official site or media kit. A search engine finds sources but does not prove authenticity. Save the source URL or path, the original file, and its checksum. Inspect the artwork, keep its shape and proportions, and animate the asset or the surface that carries it. Audit every logo occurrence in the encoded reel against its source, small marks included. When no verified asset exists, use plain brand-name text. Never invent, trace, approximate, or generate an existing brand's logo (a radial star is not the Claude mark), and never alter its geometry to add depth.

## Graphics and moving footage

Choose the mix from the story and the evidence; there is no default percentage. Keep a duration ledger of authentic footage, generated illustration, designed graphics, and speaker-only time. State the denominator and count split panels once. Captions over footage are still footage. A still with a camera move is a photographic layer, not moving B-roll.

Use each distinct B-roll scene once per reel. A new crop, filename, speed, reverse, or grade is the same scene; the same scene in both requested ratios is expected. Record scene identity, file hash, and selected interval in `assets/footage-ledger.json` (row fields in [premium-motion-and-footage.md](premium-motion-and-footage.md)), and pass `validate-footage.mjs`. A graphic callback develops the original idea into a new state and composition, never a replay of footage.

Contain the full source frame when a tighter crop hides context. Keep the subject, action, and consequence visible through the selected interval, with captions outside the action. Inspect start, middle, and end in each ratio at phone size. If dense demo text is needed to understand an insert, isolate a visible action or give it more time. Solve vertical framing by composition rather than a duplicated, blurred background video.

Prefer a specific action with a readable consequence. Compare adjacent shots with headings hidden; replace the weakest insert when the sequence repeats one mechanism or could belong in any AI advertisement. Generated metaphors add surprise; captured evidence carries proof. Prioritize authentic human reactions where they support the story.
