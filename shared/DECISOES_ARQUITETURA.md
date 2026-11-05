# DECISÕES DE ARQUITETURA — LinkedIn Editorial Davi Hoffmann
**Propósito:** Registrar o raciocínio por trás de cada decisão técnica e operacional. Evita reabrir discussões já resolvidas e explica o "por quê" para qualquer agente ou colaborador que entre no projeto.

---

## 1. STACK TÉCNICA

### Python puro — não Make, n8n ou outro orquestrador visual
**Decisão:** O pipeline roda em Python com APScheduler ou cron job.

**Por quê:**
- Make e n8n são plataformas pagas com limite de operações
- Python tem custo zero, controle total, sem dependência de plataforma externa
- Claude Code consegue construir, testar e depurar código real — não consegue configurar interfaces visuais
- Mais fácil de versionar, modificar e escalar no futuro

**O que foi descartado:** Make (plano existente), n8n

---

### Claude API — não Perplexity para pesquisa de temas
**Decisão:** Toda inteligência do sistema roda via Claude API. Perplexity não é usado.

**Por quê:**
- Claude com web search faz pesquisa de temas em alta com qualidade equivalente
- Elimina uma API e uma conta a gerenciar
- Mantém tudo na mesma plataforma — Anthropic
- Reduz custo mensal em ~$5

**O que foi descartado:** Perplexity Sonar, Perplexity Sonar-Pro

---

### LinkedIn API direta — não Buffer
**Decisão:** Publicação automática via LinkedIn API diretamente no código Python.

**Por quê:**
- Buffer custa $18/mês mínimo
- LinkedIn API é gratuita
- Com Python, a integração é direta e controlável
- Buffer seria uma dependência externa desnecessária dado que temos a API

**O que foi descartado:** Buffer, Hootsuite, Later

**Observação importante:** LinkedIn API para perfil pessoal requer criar um Developer App no LinkedIn. É gratuito mas exige aprovação. O app precisa ter permissões `w_member_social` para publicar posts.

---

### Airtable como banco central — gratuito
**Decisão:** Airtable é o banco de dados e painel de controle do sistema.

**Por quê:**
- Gratuito até 1.000 registros (suficiente para anos de operação neste volume)
- Interface visual — Davi consegue ver o estado do sistema sem código
- API REST bem documentada e fácil de integrar com Python
- Conecta nativamente com a interface HTML de aprovação

**Alternativas descartadas:** Supabase (mais complexo para esse volume), Google Sheets (API menos robusta), banco local SQLite (sem interface visual)

---

### Interface de aprovação em HTML local — não Lovable
**Decisão:** Arquivo `interface_aprovacao.html` que abre direto no navegador, sem servidor.

**Por quê:**
- Lovable é plataforma externa com custos e dependência
- HTML puro funciona offline, sem deploy, sem conta
- Conecta diretamente no Airtable via API Key no navegador
- Zero manutenção

---

## 2. DECISÕES OPERACIONAIS

### Ciclo quinzenal — não mensal nem semanal
**Decisão:** O pipeline roda a cada 15 dias.

**Por quê:**
- Mensal gera 12-15 posts de uma vez para revisar — volume alto, difícil avaliar com atenção
- Quinzenal gera 6-7 posts por lote — tamanho ideal para revisão cuidadosa
- Quinzenal permite reagir a temas em alta com mais agilidade do que mensal
- Semanal seria muito frequente para o volume atual (3-5 posts/semana)

---

### Volume: 3 a 5 posts por semana
**Decisão:** Mínimo de 3, pode escalar para 5 com automação rodando.

**Por quê:**
- 3 era o volume manual — com automação o esforço do Davi não aumenta ao subir para 5
- Mais volume = mais superfície de teste = aprende mais rápido o que funciona
- Posts humanos do Davi entram além dos automatizados — não substituem

---

### Posts humanos entram no mesmo pipeline
**Decisão:** Quando Davi tem uma ideia bruta, ela entra no Airtable como input. O Agente Redação completa o copy. Entra no mesmo lote de aprovação.

**Por quê:**
- Mantém um único fluxo de aprovação
- Davi não precisa escrever o post inteiro — só a ideia ou o ângulo
- O Agente Crítico avalia igual — sem tratamento especial para posts humanos

---

### Interação ativa é manual — nunca automatizada
**Decisão:** Comentários em posts alheios e conexões novas são feitos pelo Davi manualmente.

**Por quê:**
- LinkedIn detecta padrão de automação em comentários e suspende contas
- Comentário gerado por agente sem ler o post completo é fácil de perceber e destrói credibilidade
- A solução é: Davi manda o post alheio numa aba separada, o Agente Redação escreve o comentário no tom certo, Davi cola e publica

**Rotina definida:**
- 10 minutos por dia
- 5 perfis por semana para interagir
- 5 conexões novas por semana com mensagem personalizada de 2 linhas

---

### Agente Crítico como porteiro obrigatório
**Decisão:** Nenhum post chega ao Davi sem passar pelo Agente Crítico primeiro.

**Por quê:**
- Sem filtro, posts medíocres chegam para aprovação e o Davi perde tempo avaliando o que devia ter sido reprovado automaticamente
- O Crítico tem critérios objetivos: hook fraco = reprovação automática, "cara de IA" = reprovação automática
- Posts reprovados voltam para o Agente Redação com feedback específico — sem intervenção humana

---

## 3. DIAGNÓSTICO QUE MOTIVOU O PROJETO

**Situação em abril de 2026:**
- 191 seguidores após ~4 semanas de publicação
- Melhor post: 771 impressões (16/03)
- Última semana analisada: 357 impressões totais (queda severa)
- DMs comerciais gerados: zero
- Causa identificada: zero CTA em todos os posts + zero interação ativa

**Os textos completos dos posts publicados estão na conversa de origem.** São a referência real de tom e formato — não apenas as métricas.

**O que funcionou:**
- Hook contraintuitivo + observação de padrão = posts acima de 400 impressões
- Histórias reais com contexto específico (BabaSol, Flora Amazon) = acima de 150 impressões

**O que não funcionou:**
- Compartilhamento de notícia externa = 15-28 impressões (formato eliminado)
- Posts sem ponto de vista claro = abaixo de 30 impressões
- Posts sem CTA = zero conversão mesmo com impressões altas

---

## 4. CUSTO MENSAL DO SISTEMA

| Item | Custo |
|---|---|
| Claude API | ~$2-5/mês |
| Airtable | $0 (gratuito) |
| LinkedIn API | $0 |
| Python/servidor | $0 (roda local) |
| **Total** | **~$2-5/mês** |

---

## 5. CONEXÃO COM OUTROS PROJETOS

### Projeto X — Content OS (Twitter/X)
- Sistema automatizado rodando em inglês
- Persona: Builder Operador Contrarian
- Status: operacional, em fase de observação/validação
- **Conexão com LinkedIn:** post que performa no X pode virar post no LinkedIn com ângulo diferente — cross-pollination manual por agora

### Projeto 8 — AI Content Factory
- Fábrica de conteúdo para vídeo (Instagram/TikTok)
- Pipeline de 7 etapas com agentes especializados
- Status: arquitetura pronta, sem execução real end-to-end
- **Conexão com LinkedIn:** compartilha a lógica de agentes especializados — aprendizados de um retroalimentam o outro

---

## 6. O QUE NÃO CONSTRUIR

Para evitar escopo desnecessário:

- **Não automatizar comentários** — risco de suspensão de conta + destrói credibilidade
- **Não construir dashboard próprio** — Airtable já tem interface visual suficiente
- **Não usar banco de dados próprio** — Airtable é suficiente para esse volume
- **Não construir sistema de agendamento complexo** — APScheduler ou cron job simples resolve
- **Não integrar múltiplos canais por agora** — foco total no LinkedIn até o sistema estar validado
