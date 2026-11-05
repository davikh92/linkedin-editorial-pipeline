# CLAUDE.md

Guidance for Claude Code when working in this repository.

Read `ESTADO_ATUAL.md` first: it holds the current state (paused since 2026-10-05), the decisions behind the pause and the re-enable procedure. `README.md` has the architecture; `DECISIONS.md` the dated decision log; `shared/CEREBRO_PROJETO.md` the editorial brief that every agent obeys.

## Layout

- `linkedin/` is the whole system. Run commands from inside it: `cd linkedin && python main.py <command>`.
- `linkedin/agents/` one file per agent (radar, redacao, critico, temporada, imagem, publicacao, analytics, advisor).
- `linkedin/storage.py` is the only data-access layer. Data is JSON under `linkedin/data/`, committed by the workflows.
- `shared/llm_client.py` Gemini client with retry/backoff; `linkedin/llm_client.py` Claude client.
- `.github/workflows/` publish (11:15 BRT weekdays), health-check (Mondays), metricas-mensal (day 1), refresh-linkedin (token). Crons are commented out while paused.

## Commands

```bash
cd linkedin
python main.py fill-queue      # storyline + practical posts
python main.py next-post       # one practical post with fresh research
python main.py storyline       # generate and schedule a season
python main.py temporadas      # season bank supervision (--propor / --propor --salvar)
python main.py review          # HTML review panel
python main.py diagnostico     # pipeline health (--strict in CI)
python main.py publish         # publish today's scheduled posts
python main.py metricas        # monthly metrics (--mes YYYY-MM)
python main.py status
python main.py auth-linkedin   # renew the LinkedIn token
```

## Rules

- Content rules live in `shared/CEREBRO_PROJETO.md` and win over anything else.
- Never write secrets in files; `.env` locally, repository secrets in CI. See `.env.example`.
- Any change to publishing must assert the outcome (post exists on LinkedIn), not the action.
