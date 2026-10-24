# Infographic provenance

Generated with the built-in image-generation tool on 25 October 2026. These illustrations explain architecture; they are not Skyrim screenshots. Final PNGs are stored in this repository. Actual captures are identified separately in the README.

## Four systems

Use case: infographic-diagram.
Create a polished, readable landscape architecture infographic for the Whiterun Society Skyrim research prototype, intended to explain the actual division of responsibilities to its owner. Title: "A living town: four systems, one NPC". Subtitle: "Working prototype → ambitious society simulation".
Visual style: sophisticated illustrated technical infographic; warm medieval town vignettes (resident, bakery, market, bench) combined with crisp contemporary typography and uncluttered flow arrows. Off-white background, ink text, four distinct muted accent colors, abundant spacing. No invented screenshot. Prioritize legible short labels over dense prose.

Main layout: four large numbered columns with the following exact headings and concise content:
"1 · Observe & simulate"
"Deterministic code"
"Needs · inventory · relationships · remembered events"
"Event or timer triggers a review"

"2 · Decide"
"Jev decision model"
"Choose from feasible, validated options"
"Work · eat · visit · rest · talk · defer"

"3 · Express"
"Language model + voice"
"LLM proposes dialogue; Jev selects"
"Kokoro turns the chosen words into speech"
Show this column as an optional speech branch from Decide, not a prerequisite for every action.

"4 · Act in Skyrim"
"Game engine + our bridge"
"Native navigation · walking · animations"
"Our code requests tasks and verifies outcomes"

Clearly connect Observe to Decide to Act; optional Decide→Express→Act. Underneath, strong return arrow from Act back to Observe labelled "Observed result → verified consequence → memory → next decision".
A prominent small boundary note: "Choosing a destination ≠ calculating every footstep."
Another small note: "Models cannot directly mint money or declare an action successful."

Bottom third: two clearly separated compact bands.
"BUILT FOUNDATION"
"29 initialized residents · verified native journeys · finite trade and food · short generated voiced exchanges"
"NEXT EXPANSION"
"Connected businesses · more production chains · richer relationships · longer conversations · sustained town life"
Footer: "Event-driven intelligence. Skyrim keeps moving between decisions. Architecture illustration, not an in-game screenshot."
Do not imply full human psychology, full autonomous economy, lip sync, or all Skyrim NPCs are implemented. No fake metrics or claims of infinite choices.

Final correction: add a direct arrow labelled `Non-speaking actions` from Decide to Act, bypassing Express, while preserving the optional dialogue path and feedback loop.

## Whole simulation

Use case: infographic-diagram. Asset: large landscape README architecture illustration for Whiterun Society. Title "Whiterun Society · the whole simulation". Subtitle "System blueprint — current foundation and future expansion".
Create a beautiful, precise illustrated system map, matching an elegant medieval town + modern technical diagrams style: warm parchment, dark ink, muted green/blue/rust/gold, sharp readable type. Central small isometric Whiterun-like town illustration with market stalls, homes, workshop, a walking resident and two conversing residents. Surround it with SIX substantial clearly readable panels connected by named arrows. Keep copy short and generous spacing. This is a conceptual architecture illustration, NOT a game screenshot. No fake UI metrics.

Exact six panel texts:
"PEOPLE"
"Needs · Big Five traits · private memories"
"Relationships · goals · commitments"
"Now: authored state for 29 residents"

"ECONOMY"
"Inputs + labour → goods"
"Wages · purchases · consumption"
"Now: finite inventories and one bread recipe"

"DECISIONS"
"Events trigger reviews"
"Jev selects feasible actions"
"LLM proposes dialogue"
"Quiet periods need no model calls"

"CONVERSATION"
"Approach → consent → speak → listen"
"Local voice synthesis + subtitles"
"Appraisal changes later context"
"Now: short two-turn exchanges"

"PHYSICAL WORLD"
"Skyrim navigation, movement and animation"
"Our bridge requests and checks actions"
"Now: up to seven journeys observed together"

"HISTORY & OBSERVER"
"Verify outcomes → checkpoint → memory"
"Select · follow · zoom · inspect"
"Loading a save restores its recorded history"

Use a restrained loop of arrows with specific directional labels connecting People→Decisions ("needs and beliefs"), Decisions→Physical World ("chosen task"), Decisions→Conversation ("optional dialogue"), Physical World→Economy ("verified goods and payments"), Conversation→People ("heard claims and appraisals"), Economy→People ("resources and need relief"), Physical World→History & Observer ("receipts"), History & Observer→Decisions ("next context"). Avoid clutter: arrows around the outer ring or across white space, not crossing text.
A separate clearly marked strip along bottom:
"TARGET EXPANSION — NOT YET IMPLEMENTED"
"Farm-to-market chains · competing firms · longer social lives · families · politics · player intervention"
Footer small: "Game outcomes are authoritative. Speech is not proof. More generated sentences do not mean more meaningful actions."
No claims of scientific validation, full human intelligence, a completed sustainable economy or all Skyrim NPCs being controlled. Do not depict invented video screenshots.

Final correction: remove all inter-panel arrows and floating connection labels, preserving panel text and artwork. The generated connector routing was ambiguous; the overview now shows module responsibilities, while the source-controlled Mermaid diagram in the system guide specifies the flow.
