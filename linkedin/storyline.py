"""
storyline.py — temporadas narrativas do LinkedIn (v2).

A storyline e a metade CURADA do conteudo (2 posts/semana, ter/qui). Diferente do
rolling automatico (pratico, commodity fresca), aqui a historia e definida por um
ROTEIRO — o Davi/Claude cura a espinha, o sistema escreve cada capitulo e o critico
garante o padrao. Cada temporada dura ~1 mes (8 capitulos, 2/semana).

Fluxo:
  python main.py storyline --dry-run          # gera a proxima temporada, mostra, nao agenda
  python main.py storyline                     # gera + agenda os capitulos nas datas ter/qui
  python main.py storyline --season a-maquina  # forca uma temporada especifica

Dias de publicacao da storyline: terca e quinta (o pratico ocupa seg e qua).
"""
import re
import time
import json
from pathlib import Path
from datetime import datetime, date, timedelta, timezone

import storage as at
from llm_local import call_claude
from agents.agente_redacao import _parse_output
from agents.agente_critico import _extrair_nota, _extrair_revisao
from config import STATUS_AGENDADO, FORMATO_TEXTO, FORMATO_IMAGEM, NOTA_MINIMA_APROVACAO
from prompts_v2 import (
    PROMPT_STORYLINE_SISTEMA, PROMPT_STORYLINE_PESSOA, PROMPT_CRITICO_V2,
    CRITICO_ADENDO_PESSOA, TIPO_STORYLINE,
)
from rolling import _limpar_copy, _primeira_linha, gerar_e_salvar_imagem
from agents.agente_imagem import brief_valido
from agents.agente_temporada import propor_temporada

# Banco persistido das temporadas geradas pelo agente. O TEMPORADAS abaixo e
# so a semente escrita a mao; tudo que o sistema cria sozinho vive aqui, para
# nao exigir commit de codigo a cada temporada nova.
BANCO_JSON = Path(__file__).parent / "data" / "temporadas.json"

# Dias de publicacao da storyline: 1=terca, 3=quinta
DIAS_STORYLINE = (1, 3)

# Marcador em posts.json (campo 'notas_davi') para saber quais temporadas ja rodaram
_SEASON_TAG = "storyline_season:"


# ─── BANCO DE TEMPORADAS ──────────────────────────────────────────────────────
# Cada temporada = premissa + 8 capitulos (angulo de cada). O sistema escreve a copy.
# Ordem do dict = ordem de execucao. Adicione novas temporadas ao fim.

TEMPORADAS: dict[str, dict] = {
    "a-maquina": {
        "titulo": "A Máquina de Conteúdo",
        "premissa": (
            "Davi construiu, com IA, um sistema que pesquisa temas, escreve os posts, "
            "critica a si mesmo, gera as imagens, publica no LinkedIn e ainda comenta em "
            "outros perfis — sozinho, de graca, rodando no GitHub. Esta temporada abre a "
            "caixa-preta desse sistema, em linguagem que um dono de padaria entende. O heroi "
            "da historia e o Davi que construiu e dirige a maquina — a IA e a ferramenta, "
            "nao a estrela. Objetivo: provar que um dono de negocio pequeno pode usar IA como "
            "funcionario, nao como brinquedo."
        ),
        "capitulos": [
            {"angulo": "O gancho meta: este proprio post foi escrito por uma maquina de IA que o Davi "
                       "construiu. Revela o sistema pela primeira vez e para o scroll. Apresenta a serie."},
            {"angulo": "Por que construi: me recusei a postar todo dia na mao, virar escravo do LinkedIn. "
                       "Entao decidi montar um funcionario de IA que faz isso por mim. A frustracao que originou tudo."},
            {"angulo": "Como funciona por dentro, sem jargao: um robo pesquisa o que saiu de novo, outro escreve, "
                       "um terceiro critica e manda reescrever se estiver ruim, e ai publica. A linha de montagem."},
            {"angulo": "Quanto custa: praticamente R$0. Roda de graca no GitHub, usa versoes gratuitas das IAs. "
                       "O choque de custo — dono de negocio pequeno acha que isso custa fortuna e nao custa."},
            {"angulo": "O que deu MUITO errado: os primeiros posts sairam complexos, cheios de palavra dificil, "
                       "ninguem engajou. Tive que jogar tudo fora e reconstruir pensando no dono de padaria. A vulnerabilidade real."},
            {"angulo": "O robo que comenta por mim: alem de postar, o sistema comenta em posts de outras pessoas "
                       "pra aumentar o alcance. Como funciona e por que interagir importa mais que postar."},
            {"angulo": "O que a IA NAO consegue fazer: ela escreve, mas quem da a voz, o julgamento e as historias "
                       "reais sou eu. Onde o humano ainda manda — e por que isso nunca vai mudar. Preserva o fator humano."},
            {"angulo": "O que qualquer dono de negocio tira disso: voce nao precisa saber programar, mas o principio "
                       "de usar IA como funcionario vale pro seu negocio hoje. Fechamento + ponte comercial suave (diagnostico)."},
        ],
    },
    # Formato NOVO (decisao do Davi, 08/ago): temporadas sobre OUTRAS pessoas,
    # nao sobre ele. Motivo: "ninguem me conhece", biografia propria e pouco
    # relevante, e figuras conhecidas trazem atencao emprestada. A pessoa e a
    # PROVA; o assunto continua sendo o problema do leitor.
    #
    # PREFERENCIA POR BRASILEIROS (decisao do Davi, 08/ago): "a gente precisa
    # pensar um pouquinho mais no perfil do Brasil, vamos aproveitar mais
    # empresarios brasileiros". Referencia americana entra como excecao.
    #
    # TAMANHO: 3 capitulos por pessoa (decisao do Davi, 08/ago: "acho muito 6
    # capitulos sobre uma so"). Arco de tres: montagem, complicacao, resolucao.
    # ~1 semana e meia por pessoa (ter/qui), entao cara nova com frequencia.
    # Consequencia operacional: a agenda inicia a proxima temporada assim que
    # nao ha capitulo futuro — o banco esvazia em ~1,5 semana por pessoa.
    # Manter SEMPRE pelo menos duas pessoas nao usadas na fila.
    #
    # Criterio de escolha da pessoa — os tres tem que valer:
    #   1. escala inicial reconhecivel (comecou pequeno, com pouco dinheiro);
    #   2. arco que atravessa a tese do Davi (sistema > esforco);
    #   3. fatos publicos abundantes e SEM controversia ativa relevante.
    # Vetado por (3): Cacau Show / Alexandre Costa — historia de origem otima,
    # mas as denuncias de franqueados (2022+) transformariam a temporada em
    # briga nos comentarios, e o Davi levaria o passivo de reputacao.
    "krigsner": {
        "titulo": "O farmacêutico que virou rede",
        "pessoa": "Miguel Krigsner (O Boticário)",
        "premissa": (
            "Em 1977 Miguel Krigsner abriu uma farmacia de manipulacao numa rua secundaria "
            "de Curitiba (Saldanha Marinho) com cerca de US$ 3 mil emprestados de um tio. "
            "Chamou de O Boticario. Nao tinha o melhor produto do mercado nem dinheiro para "
            "anunciar — tinha um jeito de atender e, depois, um jeito de fazer que podia ser "
            "entregue a outra pessoa. Em 1980 abriu a primeira loja franqueada, em Brasilia, "
            "num pais que nem regulamentacao de franquia tinha. Essa e a tese do Davi contada "
            "por outra boca: o que faz um negocio crescer nao e o dono trabalhar mais, e o "
            "jeito de fazer existir fora da cabeca dele. Cada capitulo abre por uma dor "
            "concreta de quem tem negocio pequeno HOJE. Usar SOMENTE fatos publicos."
        ),
        "capitulos": [
            {"angulo": "SELO: Curitiba, 1977. DOR DO LEITOR: o cliente nao ve diferenca entre voce e o "
                       "concorrente do lado, entao decide por preco — e voce entra numa briga que nao ganha. "
                       "DECISAO: com pouco dinheiro, o caminho obvio era cobrar menos ou tentar ter o melhor "
                       "remedio; ele nao pegou nenhum dos dois. FATOS: rua Saldanha Marinho, centro de "
                       "Curitiba; farmacia de manipulacao pequena; cerca de US$ 3 mil emprestados de um tio; "
                       "formado em farmacia e bioquimica pela UFPR em 1975; batizou de O BOTICARIO, nome dos "
                       "antigos farmaceuticos que manipulavam a mao, numa epoca em que toda farmacia se "
                       "chamava 'Farmacia de Alguma Coisa'; ambiente aberto e o proprio Miguel Krigsner "
                       "atendendo no balcao. TRADUCAO: o unico diferencial que da pra montar sem dinheiro e "
                       "o que acontece no atendimento. PONTA SOLTA para o proximo capitulo: diferencial que "
                       "depende do dono no balcao para de existir quando ele sai dali."},
            {"angulo": "SELO: Brasilia, 1980. DOR DO LEITOR: 'ninguem faz do meu jeito' — voce ja tentou "
                       "passar tarefa pra frente e voltou pior, entao continua fazendo tudo. DECISAO: "
                       "entregar a loja pra um desconhecido, a 1.300 km de distancia, sem poder "
                       "supervisionar. FATOS: o produto ja saia de Curitiba na mala de quem passava pela "
                       "loja do aeroporto (aberta por volta de 1979) e a procura comecou a aparecer em "
                       "cidades onde ele nunca tinha pisado; em 1980 abriu a primeira loja franqueada de "
                       "O Boticario em Brasilia, num pais que nem regulamentacao de franquia tinha. "
                       "Franquear obriga a coisa mais dificil: escrever o jeito de fazer ANTES de entregar. "
                       "TRADUCAO: voce nao delega tarefa, delega processo — e so da pra delegar o que esta "
                       "escrito. PONTA SOLTA: deu certo rapido demais, e ai apareceu outro problema."},
            {"angulo": "SELO: anos 90. FECHO DA TEMPORADA. DOR DO LEITOR: cresceu e a qualidade caiu — cada "
                       "pessoa, cada turno, cada unidade entrega diferente. DECISAO: investir pesado em "
                       "padronizacao quando a rede JA era grande — em vez de seguir no improviso e deixar "
                       "para arrumar depois. ATENCAO FACTUAL: ele nao parou de crescer para padronizar; "
                       "padronizou enquanto crescia. Nao escreva 'ele parou'. FATOS: em cerca de cinco anos a rede "
                       "passou de centenas de lojas; nos anos 90 O Boticario investiu pesado em padronizacao "
                       "de produto e de loja — o que impediu a rede de virar centenas de negocios diferentes "
                       "com a mesma placa. TRADUCAO: padrao nao engessa, e o que permite crescer sem piorar; "
                       "e nao precisa virar rede pra usar isso num negocio de 5 pessoas. Amarra o fio dos "
                       "tres capitulos: em nenhum deles o que virou o jogo foi o dono trabalhar mais — foi "
                       "tirar o jeito de fazer da propria cabeca. Ponte comercial suave (diagnostico)."},
        ],
    },
    "ray-kroc": {
        "titulo": "O homem que não inventou nada",
        "pessoa": "Ray Kroc (McDonald's)",
        "premissa": (
            "Ray Kroc nao inventou o hamburguer, nem o restaurante, nem sequer o metodo — "
            "ele encontrou um sistema que funcionava e o transformou em algo replicavel. "
            "E a prova mais limpa da tese do Davi: o que separa um negocio que cresce de "
            "um que so trabalha mais nao e o produto, e o jeito de fazer. Cada capitulo abre "
            "por uma dor concreta de quem tem negocio pequeno HOJE; a historia do Kroc entra "
            "como evidencia de que aquilo tem solucao, e a traducao mostra o que fazer na "
            "escala de quem tem 5 funcionarios. Usar apenas fatos publicos e verificaveis."
        ),
        "capitulos": [
            {"angulo": "DOR DO LEITOR: o negocio para quando o dono sai — ferias, doenca, um dia fora "
                       "e tudo trava. PROVA: Kroc era vendedor de maquina de milkshake e encontrou, em "
                       "1954, um restaurante que ja rodava sem depender de talento individual. Ele nao "
                       "comprou a comida; comprou o jeito de fazer. TRADUCAO: o que num negocio pequeno "
                       "hoje so existe na cabeca do dono."},
            {"angulo": "DOR DO LEITOR: cada dia sai diferente — o mesmo servico, o mesmo prato, o mesmo "
                       "atendimento, com resultado que varia conforme quem esta na escala. PROVA: a "
                       "obsessao de Kroc por padrao operacional (o sistema de servico rapido dos irmaos "
                       "McDonald, medidas e tempos definidos). TRADUCAO: padronizar UMA coisa so, a mais "
                       "repetida do dia, e o comeco realista."},
            {"angulo": "DOR DO LEITOR: contratei pra aliviar e piorou — agora treino toda semana e "
                       "ninguem faz do meu jeito. PROVA: a criacao da Hamburger University (1961) — "
                       "treinar o METODO, nao a pessoa. TRADUCAO: sem o metodo escrito, cada contratacao "
                       "recomeca do zero; o dono vira professor em tempo integral."},
            {"angulo": "DOR DO LEITOR: o faturamento cresceu e o dinheiro nao apareceu na mesma "
                       "proporcao. PROVA: a virada financeira do McDonald's veio de onde ninguem "
                       "olhava — o modelo imobiliario desenhado por Harry Sonneborn. O negocio "
                       "aparente nao era onde estava a margem. TRADUCAO: onde o negocio do leitor "
                       "realmente ganha dinheiro pode nao ser o que ele passa o dia fazendo."},
            {"angulo": "DOR DO LEITOR: cresci e perdi o controle da qualidade — quanto mais gente e "
                       "mais clientes, mais coisa sai errada. PROVA: como o McDonald's manteve padrao "
                       "ao multiplicar unidades (exigencia sobre fornecedores e franqueados). "
                       "TRADUCAO: crescer sem padrao definido e multiplicar o erro, nao a receita."},
            {"angulo": "FECHO DA TEMPORADA. DOR DO LEITOR: 'entao preciso virar uma rede?' — nao. "
                       "O que se aproveita da historia num negocio de 5 pessoas: o sistema e o produto, "
                       "nao o esforco. Amarra os 5 capitulos e faz a ponte comercial suave (diagnostico)."},
        ],
    },
    # REMOVIDA em 08/ago: "tres-negocios" (Shake Dog / BabaSol / Flora Amazon).
    # Era biografia do proprio Davi, formato que ele encerrou: "nao estou muito
    # confortavel sobre a gente ficar gerando historias do meu passado".
    # As historias proprias continuam validas como UMA linha de leitura dentro
    # de um post — nunca como temporada inteira.
}


def run_season(season_key: str = None, dry_run: bool = False) -> dict:
    """
    Gera e agenda todos os capitulos de uma temporada.
    season_key: chave em TEMPORADAS (default: proxima nao-usada).
    """
    if not season_key:
        season_key = _proxima_temporada()
        if not season_key:
            print("[Storyline] Todas as temporadas do banco ja foram usadas.")
            print("[Storyline] AVISO: adicione novas temporadas em storyline.py -> TEMPORADAS.")
            return {}

    temporada = _carregar_banco().get(season_key)
    if not temporada:
        print(f"[Storyline] Temporada '{season_key}' nao existe.")
        return {}

    caps = temporada["capitulos"]
    datas = _proximas_datas_storyline(len(caps))

    print(f"\n{'='*60}")
    print(f"  STORYLINE — {temporada['titulo']}")
    print(f"  {len(caps)} capitulos | {datas[0]} a {datas[-1]}")
    print(f"{'='*60}\n")

    resumo_anterior = ""
    resultados = []

    for i, cap in enumerate(caps):
        n = i + 1
        data = datas[i]
        print(f"[Storyline] Cap {n}/{len(caps)} → {data} ...")

        copy, brief = _redigir_capitulo(
            temporada, n, len(caps), cap["angulo"], resumo_anterior
        )
        copy = _limpar_copy(copy)

        nota, copy_rev, brief_rev = _criticar(copy, brief, pessoa=bool(temporada.get("pessoa")))
        if copy_rev:
            copy = _limpar_copy(copy_rev)
            # so troca o brief se o novo for valido — senao mantem o do redator
            if brief_rev is not None and brief_valido(brief_rev):
                brief = brief_rev
            print(f"           nota {nota:.0f}/10 — reescrito")
        else:
            print(f"           nota {nota:.0f}/10 — aprovado")

        # descarta brief invalido (LLM inventou campos) — post sai sem imagem, nunca quebrada
        if brief and not brief_valido(brief):
            brief = None

        titulo = _primeira_linha(copy)[:80] or f"{temporada['titulo']} — cap {n}"
        # O fecho anterior vai junto no contexto: sem isso os capitulos fechavam
        # com variacoes da mesma pergunta ("o que so funciona porque voce esta la?"),
        # que e o tipo de repeticao que faz o leitor parar de abrir a serie.
        resumo_anterior += (
            f"Cap {n}: {cap['angulo'][:100]}\n"
            f"  fecho ja usado (NAO repetir a ideia nem a forma): {_ultima_linha(copy)}\n"
        )

        if dry_run:
            print("\n" + "-" * 60)
            print(copy)
            if brief:
                print(f"\n[IMG] {json.dumps(brief, ensure_ascii=False)}")
            print("-" * 60 + "\n")
            resultados.append({"cap": n, "copy": copy, "data": data})
            continue

        formato = FORMATO_IMAGEM if brief else FORMATO_TEXTO
        record = at.create_post({
            "Titulo interno": titulo,
            "Copy":           copy,
            "Linha":          TIPO_STORYLINE,
            "Formato":        formato,
            "Tem CTA":        True,
            "Status":         STATUS_AGENDADO,
            "Data agendada":  data,
            "Origem":         "Storyline v2",
            "Notas Davi":     f"{_SEASON_TAG}{season_key} cap {n}/{len(caps)}",
            "Feedback Critico": f"[NOTA {nota:.0f}/10]",
            "Image Brief":    json.dumps(brief, ensure_ascii=False) if brief else "",
        })
        # Imagem gerada aqui (maquina local), nao na publicacao: o runner do
        # GitHub nao tem Node/Puppeteer. Ver gerar_e_salvar_imagem em rolling.py.
        gerar_e_salvar_imagem(record["id"], brief)

        resultados.append({"post_id": record["id"], "cap": n, "data": data})
        time.sleep(2)

    if dry_run:
        print(f"[Storyline] DRY RUN — {len(resultados)} capitulos gerados, nada salvo.")
    else:
        print(f"\n[Storyline] Temporada '{temporada['titulo']}' agendada: "
              f"{len(resultados)} capitulos ({datas[0]} a {datas[-1]}).")
    return {"season": season_key, "titulo": temporada["titulo"], "capitulos": resultados}


# ─── geracao de capitulo ──────────────────────────────────────────────────────

def _redigir_capitulo(temporada, n, total, angulo, resumo_anterior):
    contexto_ant = (
        f"\nJA CONTADO nos capitulos anteriores (para dar continuidade, nao repetir):\n{resumo_anterior}"
        if resumo_anterior else "\n(Este e o primeiro capitulo — apresente a temporada.)"
    )
    user_msg = (
        f"TEMPORADA: {temporada['titulo']}\n"
        f"PREMISSA: {temporada['premissa']}\n\n"
        f"CAPITULO A ESCREVER: {n} de {total}\n"
        f"ANGULO DESTE CAPITULO: {angulo}\n"
        f"{contexto_ant}\n\n"
        f"Escreva o capitulo {n}."
        + (" Este e o ULTIMO capitulo — feche a historia e faca a ponte comercial suave." if n == total else "")
    )
    # Temporada sobre uma PESSOA usa o prompt que obriga abrir pelo leitor e
    # so admitir fato verificavel. As biograficas do Davi foram encerradas por
    # ele: "ninguem me conhece, e muito pouco relevante".
    if temporada.get("pessoa"):
        sistema = PROMPT_STORYLINE_PESSOA
        user_msg = f"PESSOA DA TEMPORADA: {temporada['pessoa']}\n" + user_msg
    else:
        sistema = PROMPT_STORYLINE_SISTEMA

    raw = call_claude(sistema, user_msg)
    copy, brief, _meta = _parse_output(raw, "")
    return copy, brief


def _ultima_linha(copy: str) -> str:
    """Ultima linha nao-vazia do capitulo — normalmente o fecho/pergunta."""
    for linha in reversed((copy or "").strip().split("\n")):
        if linha.strip():
            return linha.strip()[:160]
    return ""


def _criticar(copy, brief, pessoa: bool = False):
    tem_imagem = "sim" if brief else "nao"
    # Temporada sobre pessoa: o adendo desliga o criterio da lente pessoal do
    # Davi — sem ele o critico reescrevia o capitulo injetando Shake Dog.
    adendo = f"{CRITICO_ADENDO_PESSOA}\n\n" if pessoa else ""
    user_msg = (
        f"{adendo}"
        f"Avalie este CAPITULO de storyline (tem imagem: {tem_imagem}). "
        f"Aplique os criterios de qualidade. Se nota < {NOTA_MINIMA_APROVACAO:.0f}, "
        f"reescreva na secao POST REVISADO.\n\n---\n{copy}\n---"
    )
    output = call_claude(PROMPT_CRITICO_V2, user_msg).strip()
    nota = _extrair_nota(output)
    copy_rev, brief_rev = _extrair_revisao(output, "")
    return nota, copy_rev, brief_rev


# ─── agenda e estado ──────────────────────────────────────────────────────────

def _proximas_datas_storyline(quantas: int) -> list[str]:
    """Proximas N datas ter/qui a partir de amanha, pulando datas ja ocupadas."""
    ocupadas = set()
    for status in ("Agendado", "Aprovado"):
        for p in at.get_posts_by_status(status):
            d = p["fields"].get("Data agendada")
            if d:
                ocupadas.add(d)

    datas = []
    d = datetime.now(timezone.utc).date() + timedelta(days=1)
    while len(datas) < quantas:
        if d.weekday() in DIAS_STORYLINE and d.isoformat() not in ocupadas:
            datas.append(d.isoformat())
        d += timedelta(days=1)
    return datas


def _carregar_banco() -> dict:
    """Semente escrita a mao + temporadas geradas pelo agente. A semente vence
    em caso de chave repetida, para o arquivo gerado nunca sobrescrever curadoria."""
    gerado = {}
    if BANCO_JSON.exists():
        try:
            gerado = json.loads(BANCO_JSON.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"[Storyline] AVISO: banco gerado ilegivel ({e}). Usando so a semente.")
    return {**gerado, **TEMPORADAS}


def _salvar_temporada(key: str, temporada: dict) -> bool:
    """Grava a temporada. Recusa sobrescrever chave existente — uma temporada ja
    aprovada nao pode ser trocada em silencio por outra versao da mesma pessoa."""
    banco = {}
    if BANCO_JSON.exists():
        try:
            banco = json.loads(BANCO_JSON.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            banco = {}
    if key in banco:
        print(f"[Storyline] AVISO: '{key}' ja existe no banco — nada foi sobrescrito.")
        return False
    banco[key] = temporada
    BANCO_JSON.parent.mkdir(parents=True, exist_ok=True)
    BANCO_JSON.write_text(json.dumps(banco, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Storyline] Temporada '{key}' salva em {BANCO_JSON.name}.")
    return True


def _pessoas_no_banco() -> list[str]:
    """
    Todas as pessoas ja no banco — publicadas E na fila.
    Antes so as publicadas eram enviadas ao agente como "nao repetir", e ele
    reescolheu alguem que ja estava na fila, sobrescrevendo a temporada.
    """
    banco = _carregar_banco()
    return [t["pessoa"] for t in banco.values() if t.get("pessoa")]


def _chaves_usadas() -> set[str]:
    usadas = set()
    for p in at._posts():
        notas = p.get("notas_davi", "") or ""
        m = re.search(rf"{_SEASON_TAG}(\S+)", notas)
        if m:
            usadas.add(m.group(1))
    return usadas


def _proxima_temporada() -> str | None:
    """
    Primeira temporada do banco que ainda nao foi usada. Se o banco acabou, pede
    uma nova ao agente e salva — e isso que faz a storyline girar sem intervencao.
    """
    usadas = _chaves_usadas()
    banco = _carregar_banco()
    for key in banco:
        if key not in usadas:
            return key

    print("[Storyline] Banco de temporadas vazio — gerando a proxima...")
    # O agente precisa dos NOMES ja no banco (publicados E na fila), nao das
    # chaves: e o nome que ele tem que evitar repetir na pesquisa.
    proposta = propor_temporada(_pessoas_no_banco())
    if not proposta:
        print("[Storyline] AVISO: o agente nao aprovou nenhum candidato desta vez.")
        return None
    key, temporada = proposta
    if key in usadas:
        print(f"[Storyline] AVISO: '{key}' ja foi usada — descartada.")
        return None
    _salvar_temporada(key, temporada)
    return key
