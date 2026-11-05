# Decisions

Newest first. The long-form reasoning is in `ESTADO_ATUAL.md` (current state and pause), `shared/DECISOES_ARQUITETURA.md` (architecture history) and `ROADMAP.md` (frozen multi-platform plan).

- **2026-11 · Published as its own repository.** The Instagram pipeline, the prospecting module and the comment routines were removed; they were separate products sharing a folder.
- **2026-10-05 · Paused.** Publish workflow reported success for 19 days with no post live. Decision: stop all crons, keep the code, document the re-enable steps, and fix "assert the outcome" before any restart.
- **2026-08-12 · Re-anchored the goal to conversations, not reach.** Metrics module measured likes; the business needed diagnostic calls. Content became proof; outbound became the engine (now `lead-prospecting-engine`).
- **2026-08-12 · Seasons format.** Three chapters per real Brazilian entrepreneur, "place, year" stamp, public facts only, auto-refilling bank, controversial subjects vetoed.
- **2026-07-15 · Multi-platform roadmap frozen.** Do not multiply channels before the current one proves traction.
- **2026-06 · v2: rolling queue + Claude writer, Gemini only for Instagram.** Replaced the v1 biweekly cycle with Airtable and a paid API; v1 code removed on 2026-09-01.
- **2026-03 · Critic agent with rewrite loop.** Separate model and prompt from the writer; drafts below threshold are rewritten with the critique attached.
