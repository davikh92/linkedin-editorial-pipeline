# ESTADO ATUAL — Handoff entre sessões

> ## ⏸️ SISTEMA PAUSADO EM 05/10/2026
> Decisão do Davi: *"não tá funcionando muito essa abordagem que a gente tem,
> a gente precisa rever — só pausa aí pra não ficar rodando e dando erro."*
>
> **Desligado:** todos os crons do GitHub Actions (publish, health-check,
> metricas-mensal, refresh-linkedin) e a tarefa local "LinkedIn Gerar".
> Nada roda sozinho. Nenhum arquivo foi apagado.
>
> **O que a pausa encontrou (importante para a revisão):**
> - **Publicação parada há 19 dias** (última: 16/09), com o `publish.yml`
>   reportando *success* em todas as execuções. Falha silenciosa — mesmo
>   padrão do bug das métricas: sai verde e não faz nada.
> - Token do LinkedIn vence em **06/10/2026** (não é a causa do buraco de
>   19 dias — a publicação já tinha parado antes).
> - A fila tem 8 posts gerados até 19/10 que nunca foram ao ar.
>
> **Para religar:** descomentar os crons em `.github/workflows/*.yml` e
> `Enable-ScheduledTask -TaskName "LinkedIn Gerar"`. Antes disso, investigar
> por que o publish sai verde sem publicar.

**Última atualização:** 2026-08-12 (reorganização da casa)
**Leia primeiro:** este arquivo + `CLAUDE.md`. Conteúdo: `shared/CEREBRO_PROJETO.md` (v2).
Prospecção: `PROSPECCAO.md`.

---

## 🎯 O OBJETIVO (re-ancorado em 12/08)

**Cliente para a consultoria — não interação em post.**

O funil real: abordagem dirigida → conversa → diagnóstico gratuito → proposta → cliente.
Os posts são a prova social que sustenta a conversa; o site
(**https://www.operacaocerta.com.br/** — domínio próprio, corrigido 12/08) é o
destino de quem quer aprofundar; quem ABRE a conversa é a prospecção ativa
(`PROSPECCAO.md`) — que nunca foi executada. DMs comerciais até hoje: **0**.
É a frente prioritária.

## 📍 AS FRENTES

| # | Frente | Estado | Onde |
|---|---|---|---|
| 1 | Posts (ser visto) | ✅ roda sozinho — não mexer | `linkedin/` |
| 2 | Rede/audiência (ser visto por quem compra) | ❌ 545 seguidores, 4% ICP | atacada via frente 3 |
| 3 | **Prospecção ativa (conversar)** | 🟡 desenho completo (ICP = comprador do site, PDF por alvo) — faltam 2 respostas + 1º garimpo | `PROSPECCAO.md` |
| 4 | Conversão (site + diagnóstico) | ✅ site ok (preços reais; análise 12/08) — código em outro repo, Davi decide migrar/conectar | operacaocerta.com.br |
| 5 | Medição de negócio | ⚠️ mede likes, não DMs/diagnósticos | `linkedin/metricas.py` |
| 6 | Multi-rede + avatar (Instagram/X) | ⏸️ CONGELADO até o funil provar | `ROADMAP.md` |
| — | Comentários automáticos | 🚫 despriorizado (12/08): "pedra que requer muito" — contornar | `routines/comentar/ESTADO.md` |

---

## ⚙️ FRENTE 1 — a máquina de posts (não mexer, só supervisionar)

**4 posts/semana:** seg+qua práticos (rolling, janela 7 dias, 4 categorias
rotativas) | ter+qui capítulo de temporada.

| Automação | Quando | Onde |
|---|---|---|
| Geração local (fill-queue) | diário 8h + ao logar, PC do Davi | Task Scheduler "LinkedIn Gerar" |
| Publicação | 11h15 BRT seg-sex — token válido até **06/10** | `.github/workflows/publish.yml` |
| Diagnóstico de saúde | segunda 8h BRT, e-mail só quando há ação | `health-check.yml` |
| Métricas | dia 1 do mês, 8h BRT | `metricas-mensal.yml` |

**Temporadas (formato 12/08):** 3 capítulos por pessoa BRASILEIRA do mundo dos
negócios; leitor primeiro, pessoa como prova; selo "Lugar, ano." abrindo cada
capítulo; só fato público com fonte. O banco se alimenta sozinho
(`agents/agente_temporada.py` → `data/temporadas.json`) quando a fila esvazia.

**Fila hoje:** Krigsner (O Boticário) agendada 20/25/27-08 com imagens prontas →
Caito Maia (Chilli Beans) → Guilherme Paulus (CVC) → Ray Kroc (fallback).

**Supervisão:** `python main.py temporadas` (fila + risco + fontes),
`--propor` (espiar proposta), `--propor --salvar` (põe na fila),
`status`, `review`.

## 🚀 FRENTE 3 — prospecção ativa (A PRIORIDADE)

Desenho completo em 12/08 com o Davi (`PROSPECCAO.md`): ciclo semanal
garimpo multi-fonte (Maps/LinkedIn/Instagram/notícias) → dossiê interno +
**mini-diagnóstico em PDF específico do alvo** (ideia do Davi; render na
infra Puppeteer existente) → sequência: observação sem link → respondeu →
PDF → agenda DIRETO na conversa (formulário do site é só inbound) → CRM com
follow-up (7d + 10d, máx 2, depois nutrição). ICP = comprador do site
(dono no operacional, ~2-10 pessoas, categorias do formulário). Zero
mensagem padrão; envio 100% humano. Começa com 5/semana.
**Faltam 2 respostas** (geografia, dia da sessão semanal) e rodar o 1º garimpo.

## 📊 FRENTE 5 — o que falta na medição

`metricas.py` coleta likes/comentários via API. Falta a métrica de negócio:
convites → aceites → conversas → diagnósticos → propostas → clientes
(registro manual na tabela de `PROSPECCAO.md` enquanto o volume é baixo).

---

## 🗂️ DOCUMENTOS — quem manda em quê

| Doc | Papel |
|---|---|
| `shared/CEREBRO_PROJETO.md` | **Governa conteúdo** (v2) — prevalece em conflito de conteúdo |
| `PROSPECCAO.md` | **Governa prospecção** |
| `CEREBRO_PROJETO.md` (raiz) | 📦 HISTÓRICO (v1) — só consulta; funil/prospecção já migrados |
| `DECISOES_ARQUITETURA.md` | 📦 HISTÓRICO — descreve a v1 morta (Airtable, API paga) |
| `ROADMAP.md` | ⏸️ congelado 12/08 — multi-rede só depois do funil provar |
| `PERFORMANCE.md` | histórico de métricas (defasado desde abril; `metricas` mensal retoma) |

## Decisões recentes (12/08)

- Temporadas: pessoas reais brasileiras, 3 caps, formato selo+decisão+fecho de
  conversa; banco auto-gerado; Cacau Show vetado (controvérsia ativa);
  "três negócios" (biografia do Davi) removida — histórias próprias só como
  linha de leitura, nunca temporada.
- Casa reorganizada em 6 frentes com o cliente como objetivo; prospecção
  restaurada da v1 (tinha sido apagada na reescrita v2 sem decisão).
- Geração 100% Claude CLI local (plano, custo zero); só publicação usa API.
  `pipeline.py`/`agente_temas.py` (v1, API paga) seguem no repo — aposentar.

## 🗓️ ORDEM DE TRABALHO (estabelecida 12/08 — seguir nesta sequência)

### Agora (esta semana)
1. ~~Template do mini-diagnóstico PDF~~ ✅ feito 12/08 (`prospeccao/gerar_pdf.js`)
2. ~~Geografia + dia~~ ✅ decidido 13/08: Brasil (foco prático SP);
   ciclo SEG(garimpo) → TER(mensagens) → QUA-QUI(respostas/PDF prep) →
   SEX(PDFs + pipeline).
3. **Davi:** confirmar segmento da semana 1 (sugestão: móveis planejados /
   arquitetura, SP) → rodar o 1º ciclo completo na próxima SEG.

### Ritmo semanal (a partir do ciclo 1)
- Ciclo SEG-SEX de `PROSPECCAO.md`. Rampa: 10/semana no mês 1 →
  20-25 → 40-50 (meta: 5 consultorias/mês ≈ 200 abordagens/mês).
- Posts: rodam sozinhos (frente 1). Supervisão passiva — Krigsner publica
  20/25/27-08.

### Frente nova (paralela, sem data): Instagram da Operação Certa
Pré-requisito do canal de abordagem nº 2 (na visão do Davi, será MAIOR que o
LinkedIn pra esses ICPs). Precisa de conteúdo ESPECÍFICO (não réplica do
LinkedIn) rodando antes de qualquer abordagem por lá. Planejar em sessão
própria; o pipeline `instagram/` existente usa persona antiga — reconectar
à estratégia v2 quando essa frente abrir.

### Setembro
- Dia 1: `metricas` mensal roda — **incluir o funil de prospecção**
  (tabela de métricas do pipeline.md) na análise.
- Revisar cadência: aceite > 40% → subir pra 8-10/semana; < 20% → corrigir
  critério/mensagem antes de subir volume.

### Fim de setembro — CHECKPOINT
- 3 temporadas publicadas + 1 mês de prospecção rodando = primeira base real
  de dados. Decidir: ROADMAP (multi-rede/avatar) descongela? Site migra pro
  repo? Cadência definitiva.

### Backlog (não fazer antes do checkpoint)
- Aposentar `pipeline.py`, `agente_temas.py`, `new-cycle.yml` (API paga por
  acidente) — aguarda ok do Davi, sem urgência.
- Renovar token LinkedIn **antes de 06/10** (`python main.py auth-linkedin`).
- Doc do site no repo (migrar ou conectar — decisão do Davi).
- Comentários automáticos: despriorizado; só rever se a prospecção pedir.
- Instagram / X / avatar: congelados (`ROADMAP.md`).
