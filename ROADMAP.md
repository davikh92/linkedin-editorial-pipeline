# ROADMAP — Expansão multi-plataforma (LinkedIn → +Instagram +X, com avatar)

> **⏸️ CONGELADO em 12/08/2026.** O objetivo foi re-ancorado em CLIENTE
> (funil: prospecção → diagnóstico → proposta — ver `PROSPECCAO.md`), e a
> regra deste próprio roadmap se aplica: não multiplicar canais antes de o
> canal atual provar tração. Reavaliar depois de: (a) 3 temporadas novas
> publicadas (fim de setembro) e (b) prospecção ativa rodando com pipeline
> preenchido. O checkpoint de ~15/08 abaixo está obsoleto.

**Criado:** 2026-07-15
**Horizonte:** ~4 semanas (checkpoint final ~15/08)
**Decisão do Davi:** deixar o LinkedIn rodando sozinho e sendo analisado enquanto se constrói, em paralelo e sem pressa, a capacidade de replicar o **mesmo conteúdo** em Instagram e X/Twitter com vídeo de avatar de IA. Ao final do mês, ligar tudo junto.

---

## Princípio central

**Gerar 1x, publicar em 3.** O LinkedIn (`linkedin/rolling.py` + `linkedin/storyline.py`) já é a fonte de conteúdo — prático 2x/semana + capítulo de temporada 2x/semana, seguindo a lente do `CEREBRO_PROJETO.md` v2. Instagram e X **não vão ter estratégia de conteúdo própria** — vão reaproveitar o texto/roteiro que o LinkedIn já gera, adaptado de formato (vídeo com avatar, texto mais curto no X), não reescrito do zero.

Avatar só se justifica economicamente com os 3 canais ativos (decisão já registrada em memória — ver nota de projeto sobre o avatar).

---

## Estado atual de cada peça (auditado nesta sessão)

| Peça | Estado | O que falta |
|---|---|---|
| **LinkedIn** | ✅ Rodando — v2 completa, gerando sozinho | Nada — só observar |
| **Instagram** | 🟡 Pipeline existe (`instagram/`) mas usa estratégia/persona antiga, publicação manual | Reconectar ao conteúdo do LinkedIn v2; automatizar publicação (API) |
| **X/Twitter** | 🔴 Não existe neste repositório | Construir do zero. O "Projeto X" citado na v1 antiga é externo — precisa localizar ou assumir como zero |
| **Avatar de vídeo** | 🔴 Não existe | Escolher plataforma, treinar avatar, construir etapa de geração de vídeo |

---

## Track A — LinkedIn (passivo, nenhum trabalho novo)

Roda sozinho a semana toda. Único cuidado:
- **Toda semana**, exportar o LinkedIn Analytics (impressões, alcance, seguidores) — igual fizemos na semana de 29/06-05/07 — pra ter uma série histórica real até o checkpoint final.
- Ao final das 4 semanas, essa série de dados informa se algum ajuste de conteúdo é necessário **antes** de multiplicar por 3 plataformas (não faz sentido escalar algo que ainda não provou tração).

---

## Track B — Construção paralela (4 semanas, sem pressa)

### Semana 1 — Decisões e acessos (bloqueia tudo depois)

Estas são decisões que só o Davi resolve — não dá pra programar em cima de incerteza:

1. **Avatar:** qual plataforma usar (HeyGen, Synthesia, D-ID, Argil, etc.)? Depende de orçamento e qualidade aceitável. Precisa de material de origem (vídeo + áudio do Davi) pra treinar a semelhança.
2. **Instagram:** já existe conta Business vinculada a app no Meta for Developers? Sem isso não dá pra automatizar publicação (hoje é manual).
3. **X/Twitter:** existe já uma conta ativa? O "Projeto X" antigo ainda existe em algum lugar (outro repositório, outro computador) ou começamos do zero aqui mesmo?
4. **Formato do texto no X:** replica o texto do LinkedIn quase igual (adaptado ao limite de caracteres) ou é uma versão bem resumida?

*Sem essas respostas, as semanas 2-4 não têm por onde começar.*

### Semana 2 — Avatar de vídeo

- Configurar a plataforma escolhida, treinar o avatar (rosto + voz do Davi)
- Construir a etapa que pega a copy já gerada pelo LinkedIn (prático ou capítulo de storyline) e transforma em roteiro de vídeo
- Gerar 2-3 vídeos de teste e avaliar qualidade antes de aprovar o pipeline
- Aplicar a regra já combinada: **sempre declarar** que é avatar de IA — nunca esconder

### Semana 3 — Instagram

- Decidir: aproveitar a infraestrutura de render que já existe (`instagram/templates/`) ou substituir por vídeo de avatar como formato principal?
- Conectar o Instagram à mesma fonte de conteúdo do LinkedIn (parar de gerar pauta própria via `agente_planejador.py`)
- Automatizar a publicação via API (hoje é manual — esse é o gap mais concreto)

### Semana 4 — X/Twitter + integração

- Construir a automação do zero: adaptar formato do texto, publicar via API do X
- Testar o fluxo completo ponta a ponta: 1 post do LinkedIn → vira vídeo de avatar → publica nos 3 lugares
- Ajustar timing (não precisa ser simultâneo — pode ter defasagem entre plataformas)

---

## Checkpoint final (~semana 4-5)

1. Revisar 4 semanas de dados reais do LinkedIn — algo no conteúdo precisa mudar antes de multiplicar?
2. Confirmar qualidade do avatar é boa o suficiente pra representar a marca
3. Ligar a publicação simultânea nas 3 plataformas
4. A partir daí, acompanhar como um sistema só — não 3 pipelines separados

---

## O que **não** está neste roadmap (fora de escopo por enquanto)

- Reescrever a estratégia de conteúdo — a lente v2 do LinkedIn já vale pros 3 canais
- Métricas avançadas ou dashboard — continua sendo export manual do Analytics por enquanto
- Qualquer mudança no que já está rodando no LinkedIn
