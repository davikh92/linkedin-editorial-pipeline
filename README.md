# linkedin-editorial-pipeline

**A multi-agent editorial system that researched, wrote, critiqued, illustrated, scheduled and published LinkedIn posts for six months without supervision. Includes the post-mortem of why it was paused.**

Extracted from a private monorepo (the outbound part now lives in `lead-prospecting-engine`). The code is in Portuguese; this README and `DECISIONS.md` are in English.

## The problem

I needed a steady presence on LinkedIn to open conversations with business owners, without writing every morning. Posts had to stay inside four editorial lines, sound like me, and never become generic.

## Architecture

```
linkedin/main.py fill-queue  (local, daily)                  linkedin/main.py publish  (GitHub Actions, 11:15 BRT weekdays)
  ├─ agents/agente_radar.py      fresh topics (Claude + web search), 4 rotating categories
  ├─ agents/agente_redacao.py    drafts from the editorial brief (shared/CEREBRO_PROJETO.md)
  ├─ agents/agente_critico.py    scores each draft against the brief; rejected → rewrite loop
  ├─ agents/agente_temporada.py  "seasons": 3-chapter stories about real entrepreneurs, public sources only, self-refilling bank
  ├─ agents/agente_imagem*.py    1200×1200 PNG (Pillow / HTML template via Puppeteer)
  ├─ agents/agente_publicacao.py LinkedIn API
  ├─ agents/agente_analytics.py  monthly impressions / likes / comments → data/metricas.json
  └─ agents/agente_advisor.py    reads metrics, proposes adjustments

rolling.py   Mon/Wed practical posts (7-day rolling window)      storyline.py   Tue/Thu season chapters
storage.py   the only data-access layer (JSON in data/, committed: the repo is the scheduler)
review.py    HTML panel to approve or edit a whole cycle in minutes
diagnostico.py  health check: queue depth, token validity, last publish → e-mail only when action is needed

.github/workflows: publish.yml · health-check.yml (Mondays) · metricas-mensal.yml (day 1) · refresh-linkedin.yml (token)
```

## Run it

```bash
cp .env.example .env            # ANTHROPIC_API_KEY, GEMINI_API_KEY, LINKEDIN_* (OAuth), NOTION_TOKEN (optional)
pip install -r requirements.txt
cd linkedin
python main.py auth-linkedin    # one-time OAuth
python main.py fill-queue       # storyline + practical posts
python main.py review           # opens data/review.html
python main.py diagnostico      # pipeline health
python main.py publish          # what is scheduled for today (the workflow runs this)
python main.py status
```

## Decisions and trade-offs

- **Critic as a separate agent with a stricter model.** The writer is cheap and fast; the critic is Claude Sonnet with the brief as rubric. Rejected drafts go back with the critique attached. This caught generic or off-line posts before I ever saw them.
- **Seasons with public sources only.** Three-chapter stories about real Brazilian entrepreneurs, each chapter stamped with place and year. The bank refills itself when the queue empties; controversial subjects are vetoed in the brief.
- **Repo as scheduler.** JSON in git instead of a database: zero infrastructure, full history, easy review. Fine for one account; would not scale to many.
- **Health check that stays quiet.** It e-mails only when something needs a human. That is why it was trusted, and also why the failure below was missed: it checked the action, not the outcome.

## Results and the post-mortem

| | |
|---|---|
| Unattended operation | Mar–Sep 2026, 4 posts/week |
| Best post | 771 impressions |
| Audience | 545 followers, ~4% inside the ideal customer profile |
| Commercial conversations generated | 0 |

Paused on 2026-10-05 by decision. The pause found that `publish.yml` had reported success for 19 days while nothing was published: a silent failure. Two lessons, both recorded in `ESTADO_ATUAL.md`:

1. Assert the outcome (post exists on LinkedIn), not the action (request sent).
2. The pipeline measured likes; the business needed conversations. Content became proof, and the outbound engine became the driver.

The crons are commented out, not deleted. The re-enable procedure is in the same file.

## What I'd do differently

Build the outcome assertion on day one. Define the business metric (conversations) before the content metric. Start the outbound engine first, with content supporting it rather than the reverse.

## Security

No secrets in the repository; see `.env.example`. Generated images and the editorial experience bank were removed from this public copy; `data/posts.json` keeps the published posts (public on LinkedIn) and `data/metricas.json` the measured results.
