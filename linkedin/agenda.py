"""
agenda.py — mantem a fila de posts cheia (buffer). Roda no PC do Davi (Task Scheduler).

A geracao agora e LOCAL (Claude CLI, plano — custo zero). Como depende do PC ligar,
geramos com FOLGA: cada execucao garante ~N semanas de posts agendados a frente.
Se ja esta cheio, nao faz nada (idempotente). Isso desacopla "ligar o PC" de
"publicar todo dia" — o GitHub Actions publica da fila mesmo com o PC dias desligado.

Fila alvo por semana: seg + qua = pratico (rolling) | ter + qui = capitulo de storyline.
"""
from datetime import datetime, timedelta, timezone

import storage as at
import rolling
import storyline
from prompts_v2 import TIPO_STORYLINE

DIAS_PRATICO = (0, 2)  # seg, qua
MAX_PRATICOS_POR_RUN = 4  # trava de seguranca: nao gerar demais numa so execucao


class AuthExpiradaError(RuntimeError):
    """Login do Claude CLI expirou — nada pode ser gerado ate reautenticar."""


def _checar_auth() -> None:
    """
    Sonda barata antes de gerar qualquer coisa.

    Sem isso, um token expirado faz cada post falhar so depois de ~7min de
    timeout, deixando processos orfaos e um log que parece 'apenas nao gerou'.
    Falhar aqui, rapido e explicito, e o que torna o problema visivel.
    """
    from llm_local import call_claude
    try:
        call_claude("Responda apenas com a palavra pedida.", "Responda: OK", timeout=90)
    except Exception as e:
        msg = str(e).lower()
        if "401" in msg or "expired" in msg or "authenticate" in msg:
            raise AuthExpiradaError(
                "LOGIN DO CLAUDE CLI EXPIRADO — nenhum post pode ser gerado.\n"
                "  Acao: abra um terminal, rode 'claude' e faca login novamente.\n"
                "  Depois rode: python main.py fill-queue"
            ) from e
        raise


def fill_queue(semanas: int = 1) -> dict:
    """
    Enche a fila para cobrir ~`semanas` a frente. Idempotente.

    Janela de 1 semana (nao 2) porque pratico e conteudo perecivel: com buffer
    de 2 semanas os posts nasciam 11-14 dias antes de publicar e chegavam ao
    feed como noticia velha — exatamente o que a arquitetura rolling existia
    para evitar. A storyline nao sofre disso (narrativa curada) e continua
    sendo gerada por temporada inteira, em run_season.
    """
    hoje = datetime.now(timezone.utc).date()
    print(f"\n{'='*60}\n  AGENDA — enchendo fila ({semanas} semana(s) a frente)\n{'='*60}\n")

    # Registra o resultado da sonda de auth para o diagnostico semanal ler.
    # Sem esse rastro, o diagnostico (que roda na nuvem) nao teria como saber
    # que a geracao local parou por login expirado.
    from diagnostico import registrar_execucao

    print("[Agenda] Verificando login do Claude CLI...")
    try:
        _checar_auth()
    except AuthExpiradaError as e:
        registrar_execucao(auth_ok=False, erro=str(e))
        raise
    registrar_execucao(auth_ok=True)
    print("[Agenda] Login OK.\n")

    # 1. Storyline: se nao ha capitulo futuro agendado, inicia a proxima temporada
    if _tem_storyline_futura(hoje):
        print("[Agenda] Storyline: ja ha capitulos futuros agendados — ok.")
    else:
        print("[Agenda] Storyline: sem capitulos futuros — iniciando proxima temporada...")
        try:
            storyline.run_season()
        except Exception as e:
            print(f"[Agenda] AVISO: falha ao gerar storyline ({e}). Praticos seguem.")

    # 2. Praticos: enche seg/qua das proximas `semanas` semanas
    alvo = hoje + timedelta(weeks=semanas)
    d = hoje + timedelta(days=1)
    gerados = 0
    while d <= alvo and gerados < MAX_PRATICOS_POR_RUN:
        if d.weekday() in DIAS_PRATICO and not _ja_agendado(d.isoformat()):
            print(f"[Agenda] Pratico para {d.isoformat()} ({_nome_dia(d)})...")
            try:
                rolling.run_next_post(target_date=d.isoformat())
                gerados += 1
            except Exception as e:
                print(f"[Agenda] AVISO: falha ao gerar pratico {d.isoformat()} ({e}).")
        d += timedelta(days=1)

    print(f"\n[Agenda] {gerados} pratico(s) gerado(s) nesta execucao.")
    return {"praticos_gerados": gerados, "cobertura_ate": alvo.isoformat()}


def _ja_agendado(data_iso: str) -> bool:
    for s in ("Agendado", "Aprovado"):
        for p in at.get_posts_by_status(s):
            if p["fields"].get("Data agendada") == data_iso:
                return True
    return False


def _tem_storyline_futura(hoje) -> bool:
    hoje_iso = hoje.isoformat()
    for s in ("Agendado", "Aprovado"):
        for p in at.get_posts_by_status(s):
            f = p["fields"]
            if f.get("Linha") == TIPO_STORYLINE and (f.get("Data agendada") or "") > hoje_iso:
                return True
    return False


def _nome_dia(d) -> str:
    return ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"][d.weekday()]
