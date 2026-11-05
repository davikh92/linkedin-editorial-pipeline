"""
diagnostico.py — checagem semanal de saude do pipeline.

Motivacao (pedido do Davi): antes, cada problema disparava seu proprio e-mail
(fila vazia, ciclo falhou, token vencendo). Virou ruido e ele parou de ler.
Agora e UM relatorio semanal: se esta tudo certo, diz OK e nao incomoda;
se ha problema, diz exatamente qual e o que fazer.

Uso:
    python main.py diagnostico            # relatorio legivel
    python main.py diagnostico --strict   # exit != 0 se precisa de acao humana
                                          # (o workflow usa --strict: e-mail so quando ha acao)

Niveis:
    OK     — nada a fazer
    AVISO  — merece atencao, mas nada quebrou
    ACAO   — precisa de intervencao humana (unico que gera e-mail)
"""
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

_BASE = Path(__file__).parent
_POSTS = _BASE / "data" / "posts.json"
_HEALTH = _BASE / "data" / "health.json"

OK, AVISO, ACAO = "OK", "AVISO", "ACAO"

_MIN_FILA = 2                 # abaixo disso a fila esta secando
_MAX_DIAS_SEM_PUBLICAR = 4    # cadencia e 4x/semana
_MAX_DIAS_SEM_GERAR = 3       # rotina local roda diariamente


def _carregar_posts() -> list[dict]:
    if not _POSTS.exists():
        return []
    with open(_POSTS, encoding="utf-8") as f:
        return json.load(f)


def _res(nome: str, nivel: str, detalhe: str, acao: str = "") -> dict:
    return {"nome": nome, "nivel": nivel, "detalhe": detalhe, "acao": acao}


# ─── checagens ────────────────────────────────────────────────────────────────

def checar_geracao_local() -> dict:
    """A rotina que gera os posts no PC rodou, e o login do CLI vale?"""
    nome = "Geracao local"
    if not _HEALTH.exists():
        return _res(nome, AVISO, "Sem registro de execucao local ainda.",
                    "Rode: python main.py fill-queue")

    try:
        with open(_HEALTH, encoding="utf-8") as f:
            h = json.load(f)
    except (json.JSONDecodeError, OSError):
        return _res(nome, AVISO, "Registro de execucao ilegivel.", "")

    quando = h.get("ultima_execucao", "")
    if not h.get("auth_ok", False):
        return _res(nome, ACAO,
                    f"Login do Claude CLI expirado (ultima tentativa: {quando[:16]}).",
                    "Abra um terminal, rode 'claude' e faca login. "
                    "Depois: python main.py fill-queue")

    try:
        dt = datetime.fromisoformat(quando.replace("Z", "+00:00"))
        dias = (datetime.now(timezone.utc) - dt).days
    except (ValueError, AttributeError):
        return _res(nome, OK, "Login OK.", "")

    if dias > _MAX_DIAS_SEM_GERAR:
        return _res(nome, AVISO, f"Nao roda ha {dias} dias (PC desligado?).",
                    "A fila tem folga, mas ligue o PC para reabastecer.")
    return _res(nome, OK, f"Rodou em {quando[:16]} — login OK.")


def checar_fila(posts: list[dict]) -> dict:
    """Ha posts suficientes agendados a frente?"""
    nome = "Fila de posts"
    hoje = date.today().isoformat()
    futuros = sorted(
        [p for p in posts
         if p.get("status") in ("Agendado", "Aprovado")
         and (p.get("data_agendada") or "") >= hoje],
        key=lambda p: p["data_agendada"],
    )

    if not futuros:
        return _res(nome, ACAO, "Fila VAZIA — nada para publicar.",
                    "Rode: python main.py fill-queue")
    if len(futuros) < _MIN_FILA:
        return _res(nome, AVISO,
                    f"So {len(futuros)} post(s) na fila (ate {futuros[-1]['data_agendada']}).",
                    "A rotina diaria deve reabastecer sozinha.")

    por_linha: dict[str, int] = {}
    for p in futuros:
        k = p.get("linha", "?")
        por_linha[k] = por_linha.get(k, 0) + 1
    resumo = ", ".join(f"{v} {k}" for k, v in sorted(por_linha.items()))
    return _res(nome, OK, f"{len(futuros)} posts ate {futuros[-1]['data_agendada']} ({resumo}).")


def checar_publicacoes(posts: list[dict]) -> dict:
    """
    O pipeline publicou de verdade nos ultimos dias?

    A checagem decisiva e POST PRESO NO PASSADO: post agendado para uma data
    que ja passou e que nunca publicou. Isso e sintoma direto de publicacao
    quebrada (token vencido, API fora, workflow falhando) e aparece no mesmo
    dia — nao depende de esperar N dias de silencio para desconfiar.
    """
    nome = "Publicacoes"
    hoje = date.today().isoformat()

    presos = sorted(
        [p for p in posts
         if p.get("status") in ("Agendado", "Aprovado")
         and not p.get("linkedin_post_id")
         and (p.get("data_agendada") or "9999") < hoje],
        key=lambda p: p["data_agendada"],
    )
    if presos:
        datas = ", ".join(p["data_agendada"] for p in presos[:4])
        return _res(nome, ACAO,
                    f"{len(presos)} post(s) passaram da data sem publicar ({datas}).",
                    "Publicacao esta quebrada. Causa mais comum: token do LinkedIn vencido "
                    "(veja o item abaixo). Cheque tambem publish.yml no GitHub.")

    publicados = [p.get("data_agendada") for p in posts
                  if p.get("status") == "Publicado" and p.get("data_agendada")]
    if not publicados:
        return _res(nome, ACAO, "Nenhum post publicado ainda.",
                    "Verifique o workflow publish.yml no GitHub.")

    ultima = max(publicados)
    try:
        dias = (date.today() - date.fromisoformat(ultima)).days
    except ValueError:
        return _res(nome, AVISO, f"Data de publicacao invalida: {ultima}.")

    # Estritamente MAIOR que 4: a cadencia e seg-qui, entao o gap normal
    # qui -> seg e de exatamente 4 dias — e o diagnostico roda segunda de manha,
    # ANTES do publish do dia. Com >= 4, toda segunda-feira seria alarme falso.
    if dias > _MAX_DIAS_SEM_PUBLICAR:
        return _res(nome, ACAO, f"Ultima publicacao ha {dias} dias ({ultima}).",
                    "Verifique se ha posts na fila e se o publish.yml rodou no GitHub.")
    return _res(nome, OK, f"Ultima publicacao ha {dias} dia(s) ({ultima}).")


def checar_residuo(posts: list[dict]) -> dict:
    """Posts orfaos acumulando (sem data, ou 'Gerado' que nunca avancou)."""
    nome = "Residuo"
    sem_data = [p for p in posts
                if p.get("status") in ("Agendado", "Aprovado", "Gerado")
                and not p.get("data_agendada")]
    if len(sem_data) > 15:
        return _res(nome, AVISO, f"{len(sem_data)} posts sem data acumulados.",
                    "Nao atrapalha a publicacao, mas vale limpar o posts.json.")
    if sem_data:
        return _res(nome, OK, f"{len(sem_data)} post(s) sem data (residuo normal).")
    return _res(nome, OK, "Sem residuo.")


def checar_storyline(posts: list[dict]) -> dict:
    """A temporada em curso esta perto do fim? (precisa planejar a proxima)"""
    nome = "Temporada"
    hoje = date.today().isoformat()
    caps = sorted(
        [p for p in posts
         if p.get("linha") == "Storyline/Temporada"
         and p.get("status") in ("Agendado", "Aprovado")
         and (p.get("data_agendada") or "") >= hoje],
        key=lambda p: p["data_agendada"],
    )
    if not caps:
        return _res(nome, AVISO, "Nenhum capitulo futuro — temporada encerrada.",
                    "Escolha a proxima temporada e rode: python main.py storyline")
    if len(caps) <= 2:
        return _res(nome, AVISO,
                    f"So {len(caps)} capitulo(s) restante(s) (ate {caps[-1]['data_agendada']}).",
                    "Vale ja decidir a proxima temporada.")
    return _res(nome, OK, f"{len(caps)} capitulos ate {caps[-1]['data_agendada']}.")


def checar_token_linkedin() -> dict:
    """O token de publicacao do LinkedIn ainda vale?"""
    nome = "Token LinkedIn"
    token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
    if not token:
        # rodando local: o token esta no .env, nao no ambiente
        try:
            from dotenv import load_dotenv
            load_dotenv(_BASE.parent / ".env", encoding="utf-8")
            token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
        except ImportError:
            pass
    if not token:
        return _res(nome, AVISO, "Token nao visivel neste contexto.")

    cid = os.environ.get("LINKEDIN_CLIENT_ID", "")
    csec = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
    if not (cid and csec):
        return _res(nome, AVISO, "CLIENT_ID/SECRET ausentes — nao da para validar o token.")

    # introspectToken e o endpoint proprio para isso. Endpoints de perfil
    # (/v2/me, /v2/userinfo) NAO servem: nosso token tem escopo w_member_social
    # (so publicar), entao eles retornam 403 mesmo com o token perfeito — foi o
    # que fez esta checagem dar falso alarme antes.
    try:
        import requests
        r = requests.post("https://www.linkedin.com/oauth/v2/introspectToken",
                          data={"client_id": cid, "client_secret": csec, "token": token},
                          timeout=20)
    except Exception as e:
        return _res(nome, AVISO, f"Nao foi possivel verificar ({type(e).__name__}).")

    if r.status_code != 200:
        return _res(nome, AVISO, f"Introspeccao respondeu HTTP {r.status_code}.")

    d = r.json()
    if not d.get("active"):
        return _res(nome, ACAO, f"Token inativo (status: {d.get('status','?')}).",
                    "Rode 'cd linkedin && python main.py auth-linkedin', clique em Permitir, "
                    "e atualize o secret: gh secret set LINKEDIN_ACCESS_TOKEN")

    exp = d.get("expires_at")
    if exp:
        venc = datetime.fromtimestamp(exp, timezone.utc).date()
        dias = (venc - date.today()).days
        if dias <= 7:
            return _res(nome, ACAO, f"Token vence em {dias} dia(s) ({venc}).",
                        "Renove agora: 'cd linkedin && python main.py auth-linkedin', "
                        "clique em Permitir, depois 'gh secret set LINKEDIN_ACCESS_TOKEN'.")
        if dias <= 15:
            return _res(nome, AVISO, f"Token vence em {dias} dias ({venc}).",
                        "Vale renovar na proxima semana.")
        return _res(nome, OK, f"Token ativo, vence em {dias} dias ({venc}).")
    return _res(nome, OK, "Token ativo.")


# ─── relatorio ────────────────────────────────────────────────────────────────

def rodar() -> tuple[list[dict], bool]:
    """Roda todas as checagens. Retorna (resultados, precisa_acao)."""
    posts = _carregar_posts()
    resultados = [
        checar_geracao_local(),
        checar_fila(posts),
        checar_publicacoes(posts),
        checar_storyline(posts),
        checar_token_linkedin(),
        checar_residuo(posts),
    ]
    return resultados, any(r["nivel"] == ACAO for r in resultados)


def imprimir(resultados: list[dict], precisa_acao: bool) -> None:
    icone = {OK: "[ OK ]", AVISO: "[AVISO]", ACAO: "[ACAO]"}
    linha = "=" * 66
    print(linha)
    print(f"  DIAGNOSTICO DO PIPELINE — {date.today().isoformat()}")
    print(linha)
    for r in resultados:
        print(f"{icone[r['nivel']]} {r['nome']}: {r['detalhe']}")
        if r["acao"]:
            print(f"        -> {r['acao']}")
    print("-" * 66)
    if precisa_acao:
        print("RESUMO: precisa da sua atencao — veja os itens [ACAO] acima.")
    else:
        avisos = sum(1 for r in resultados if r["nivel"] == AVISO)
        extra = f" {avisos} aviso(s) sem urgencia." if avisos else ""
        print(f"RESUMO: tudo funcionando.{extra}")
    print(linha)


def registrar_execucao(auth_ok: bool, erro: str = "") -> None:
    """Chamado pela rotina local para deixar rastro do ultimo run."""
    _HEALTH.parent.mkdir(parents=True, exist_ok=True)
    with open(_HEALTH, "w", encoding="utf-8") as f:
        json.dump({
            "ultima_execucao": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "auth_ok": auth_ok,
            "erro": erro or None,
        }, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import sys
    resultados, precisa_acao = rodar()
    imprimir(resultados, precisa_acao)
    if "--strict" in sys.argv and precisa_acao:
        sys.exit(1)
