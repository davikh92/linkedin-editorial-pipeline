"""
agente_temporada.py — cria sozinho o roteiro da proxima temporada.

Antes, cada temporada era escrita a mao no TEMPORADAS de storyline.py. Agora o
sistema propoe a proxima quando o banco esvazia, e o Davi so supervisiona.

Dois passes:
  1. PESQUISA (web) — escolhe a pessoa, levanta os fatos com fonte e diz se ha
                      controversia relevante.
  2. ROTEIRO        — monta os 3 capitulos com esses fatos.

Houve uma versao com um terceiro passe de verificacao adversarial (conferir
fato a fato, classificar peso de fonte). Foi removida a pedido do Davi: pesada,
lenta e rigorosa demais para o ganho. A protecao que ficou e a essencial —
so fato com fonte entra, e controversia ativa veta a pessoa.
"""
import json
import re
import unicodedata
from datetime import date

from llm_local import call_claude

# Minimo de fatos para a temporada valer. Abaixo disso o roteiro seria
# preenchido com achismo sobre pessoa real, que e o que nao pode acontecer.
MIN_FATOS = 6

# Risco de controversia que veta a pessoa. Foi o criterio que barrou o Cacau
# Show na escolha manual (denuncias de franqueados em 2022+).
RISCO_VETADO = ("alto",)

TIMEOUT_PESQUISA = 1500
TIMEOUT_ROTEIRO = 600


def _tentar(rotulo: str, fn, *args, **kwargs):
    """
    Executa um passe e devolve None em vez de propagar erro de LLM.
    Em producao isto roda sem ninguem olhando: uma pesquisa lenta nao pode
    derrubar o fill-queue inteiro — a temporada apenas nao nasce hoje.
    """
    try:
        return fn(*args, **kwargs)
    except RuntimeError as e:
        print(f"[Temporada] {rotulo} falhou: {e}")
        return None


_PERFIL = """
O leitor e dono de negocio pequeno no Brasil: 5 a 20 funcionarios, comercio, servico
ou industria pequena. Ele nao e investidor nem executivo. O que prende esse leitor e
reconhecer o proprio problema — nao admirar um bilionario.

A pessoa da temporada tem que passar nos TRES criterios:
  1. ESCALA INICIAL RECONHECIVEL — comecou pequeno, com pouco dinheiro, fazendo com
     as proprias maos. Quem comecou com capital de familia ou heranca nao serve.
  2. ARCO QUE ATRAVESSA A TESE — o que virou o jogo foi definir o jeito de fazer e
     tirar da propria cabeca, nao trabalhar mais horas.
  3. FATOS PUBLICOS ABUNDANTES E SEM CONTROVERSIA ATIVA relevante.

PREFERENCIA FORTE POR BRASILEIROS. O leitor se reconhece em quem construiu aqui,
com as regras daqui. Estrangeiro so como excecao.

Alterne o nivel de fama: se as temporadas anteriores usaram nomes muito conhecidos,
escolha agora alguem que quem e do ramo conhece e o publico geral nao — mostra
conhecimento mais profundo. E vice-versa.
""".strip()


def _slug(texto: str) -> str:
    """Chave estavel a partir do nome da pessoa: 'Miguel Krigsner' -> 'miguel-krigsner'."""
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t[:40] or "temporada"


def _extrair_json(raw: str) -> dict | None:
    """Primeiro objeto JSON do texto. O CLI as vezes embrulha em cerca ou prosa."""
    if not raw:
        return None
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    candidato = m.group(1) if m else None
    if candidato is None:
        ini = raw.find("{")
        fim = raw.rfind("}")
        candidato = raw[ini:fim + 1] if ini != -1 and fim > ini else None
    if not candidato:
        return None
    try:
        return json.loads(candidato)
    except json.JSONDecodeError:
        return None


# ─── passo 1: pesquisa ────────────────────────────────────────────────────────

_SISTEMA_PESQUISA = f"""
Voce pesquisa a proxima temporada narrativa do LinkedIn de um consultor de
organizacao de negocios.

{_PERFIL}

Use WebSearch — nao responda de memoria, voce erra detalhe, e erro sobre pessoa
publica e vexame. Mas seja economico: no maximo 8 buscas no total. Decida a pessoa
nas duas primeiras e gaste o resto nos fatos dela. Nao compare candidatos: qualquer
um que passe nos tres criterios serve.

Levante 8 a 10 fatos verificaveis — datas, valores, lugares, decisoes documentadas —
cada um com a URL onde voce leu. Regra unica de honestidade: se voce nao achou o fato
numa fonte, nao inclua. Nada de "diz-se que" nem numero aproximado de cabeca.

Diga tambem se ha controversia relevante (processo, denuncia de funcionarios ou
franqueados, escandalo em curso). Uma temporada elogiosa sobre alguem com denuncia
ativa vira briga nos comentarios, e o passivo fica com quem postou.
  "baixo" — nada relevante | "medio" — polemica antiga ou pontual | "alto" — ativa e grave.

Responda SOMENTE com um objeto JSON, sem texto em volta:
{{
  "pessoa": "Nome Completo",
  "empresa": "Nome da empresa/marca",
  "por_que_serve": "2 linhas ligando o arco dela a tese: sistema vence esforco",
  "fatos": [
    {{"fato": "afirmacao curta e checavel", "ano": "1977", "fonte": "https://..."}}
  ],
  "risco_controversia": "baixo|medio|alto",
  "controversia": "1-2 linhas, ou vazio"
}}
""".strip()


def _pesquisar(usadas: list[str]) -> dict | None:
    ja = ", ".join(usadas) if usadas else "(nenhuma ainda)"
    user = (
        f"Pessoas ja usadas em temporadas anteriores (NAO repetir): {ja}\n\n"
        f"Escolha UMA pessoa nova e pesquise. Responda so o JSON."
    )
    raw = call_claude(_SISTEMA_PESQUISA, user, web_search=True, timeout=TIMEOUT_PESQUISA)
    return _extrair_json(raw)


# ─── passo 2: roteiro ─────────────────────────────────────────────────────────

_SISTEMA_ROTEIRO = f"""
Voce monta o ROTEIRO de uma temporada de 3 capitulos sobre uma pessoa real, para o
LinkedIn de um consultor de organizacao de negocios.

{_PERFIL}

Voce NAO escreve os posts — escreve o ANGULO de cada capitulo, que outro agente
transforma em texto. Um arco de tres: montagem, complicacao, resolucao.

Cada capitulo precisa de:
  - SELO: lugar + ano da cena (ex: "Curitiba, 1977"), que abre o post;
  - DOR DO LEITOR: um problema concreto de quem tem 5 a 20 funcionarios HOJE,
    escrito com as palavras que ele usaria;
  - DECISAO: UMA decisao da pessoa — inclusive o caminho obvio que ela NAO pegou;
  - FATOS: so os fatos que pertencem a ESTE capitulo (nao repita o mesmo fato em
    dois capitulos, e nao adiante fato de capitulo posterior);
  - TRADUCAO: o que isso significa no negocio do leitor, na escala dele;
  - PONTA SOLTA: o problema novo que essa solucao criou, e que abre o capitulo
    seguinte (no capitulo 3 nao ha ponta solta: ele fecha a temporada e faz a
    ponte comercial suave para um diagnostico).

Se algum fato tiver risco de ser mal interpretado, escreva no angulo uma linha
"ATENCAO FACTUAL: ..." dizendo o que NAO pode ser escrito.

Responda SOMENTE com JSON:
{{
  "titulo": "titulo curto da temporada, sem dois pontos",
  "premissa": "5 a 8 linhas: quem e, o que fez, e por que essa historia prova que
               o que faz um negocio crescer e o jeito de fazer existir fora da
               cabeca do dono. Terminar com: Usar SOMENTE fatos publicos.",
  "capitulos": [
    {{"angulo": "SELO: ... DOR DO LEITOR: ... DECISAO: ... FATOS: ... TRADUCAO: ... PONTA SOLTA: ..."}}
  ]
}}
Exatamente 3 capitulos.
""".strip()


def _montar_roteiro(pesquisa: dict) -> dict | None:
    user = (
        f"PESSOA: {pesquisa.get('pessoa')} ({pesquisa.get('empresa')})\n"
        f"POR QUE SERVE: {pesquisa.get('por_que_serve', '')}\n\n"
        f"FATOS (use apenas estes):\n"
        f"{json.dumps(pesquisa.get('fatos', []), ensure_ascii=False, indent=2)}\n\n"
        f"Monte o roteiro dos 3 capitulos. Responda so o JSON."
    )
    raw = call_claude(_SISTEMA_ROTEIRO, user, timeout=TIMEOUT_ROTEIRO)
    return _extrair_json(raw)


# ─── orquestracao ─────────────────────────────────────────────────────────────

def propor_temporada(usadas: list[str] | None = None) -> tuple[str, dict] | None:
    """
    Propoe a proxima temporada. Retorna (chave, temporada) ou None se nada passou
    nos criterios — nesse caso o chamador decide (tentar de novo, ou seguir sem).
    A temporada retornada tem o mesmo schema do TEMPORADAS de storyline.py.
    """
    usadas = usadas or []

    print("[Temporada] 1/2 pesquisando candidato...")
    pesquisa = _tentar("pesquisa", _pesquisar, usadas)
    if not pesquisa or not pesquisa.get("pessoa"):
        print("[Temporada] Pesquisa nao retornou candidato valido.")
        return None

    pessoa = pesquisa["pessoa"]
    fatos = [f for f in pesquisa.get("fatos", []) if f.get("fato") and f.get("fonte")]
    risco = str(pesquisa.get("risco_controversia", "alto")).strip().lower()
    print(f"[Temporada]     {pessoa} ({pesquisa.get('empresa', '?')}) — "
          f"{len(fatos)} fatos com fonte, risco '{risco}'.")

    if pessoa.strip().lower() in {u.strip().lower() for u in usadas}:
        print(f"[Temporada] '{pessoa}' ja foi usada — descartada.")
        return None

    if risco in RISCO_VETADO:
        print(f"[Temporada] VETADA ({pessoa}): {pesquisa.get('controversia', 'controversia ativa')}")
        return None

    if len(fatos) < MIN_FATOS:
        print(f"[Temporada] Poucos fatos com fonte ({len(fatos)} < {MIN_FATOS}) — descartada.")
        return None

    print("[Temporada] 2/2 montando roteiro dos 3 capitulos...")
    roteiro = _tentar("roteiro", _montar_roteiro, pesquisa)
    if not roteiro or len(roteiro.get("capitulos", [])) != 3:
        print("[Temporada] Roteiro invalido (esperado 3 capitulos) — descartada.")
        return None

    # A empresa as vezes vem com o nome por extenso entre parenteses ("CVC Brasil
    # (Corporacao de Viagens e Cruzeiros)"), o que aninhava parenteses no rotulo.
    empresa = re.sub(r"\s*\(.*?\)\s*", "", (pesquisa.get("empresa") or "")).strip()
    temporada = {
        "titulo":    roteiro["titulo"],
        "pessoa":    f"{pessoa} ({empresa})" if empresa else pessoa,
        "premissa":  roteiro["premissa"],
        "capitulos": roteiro["capitulos"],
        # rastro para supervisao humana: da pra conferir cada fato na fonte
        "fontes":    [{"fato": f.get("fato"), "fonte": f.get("fonte")} for f in fatos],
        "risco_controversia": risco,
        "controversia": (pesquisa.get("controversia") or "").strip(),
        "gerada_em": date.today().isoformat(),
        "origem":    "agente_temporada",
    }
    return _slug(pessoa), temporada
