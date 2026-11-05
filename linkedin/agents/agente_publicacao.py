"""
Agente Publicacao — publica posts aprovados no LinkedIn no horario programado.
Roda diariamente as 11h15 via GitHub Actions.

Garantias de robustez (sistema autonomo, publicacao irreversivel):
  - Nao perde post: pega data_agendada <= hoje (recupera atrasados se o
    scheduler falhar um dia), mas publica 1 por run para manter a cadencia.
  - Nao duplica: trava por linkedin_post_id + commit IMEDIATO apos cada
    publicacao (fecha a janela entre "foi ao LinkedIn" e "estado salvo").
  - Nao falha em silencio: erro grava no post e faz o run sair com codigo !=0
    para o GitHub Actions alertar por email.
"""
import os
import re
import subprocess
from pathlib import Path
from datetime import datetime, timezone
import storage as at
from linkedin_client import LinkedInClient
from config import STATUS_APROVADO, STATUS_PUBLICADO

# Raiz do repo — usado para resolver paths de imagem que podem ser absolutos Windows
# mas no GitHub Actions precisam ser relativos ao checkout do repo.
_REPO_ROOT = Path(__file__).parent.parent.parent   # agents/ -> linkedin/ -> repo raiz
_LI_IMAGES = _REPO_ROOT / "linkedin" / "data" / "images"


def _resolver_imagem(img_path_raw: str) -> Path | None:
    """
    Resolve o path da imagem independente de onde o código está rodando.

    Problema: paths salvos como 'C:\\Users\\davi_\\...\\images\\uuid.png'
    funcionam localmente mas nao existem no Linux do GitHub Actions.

    Solução: extrai o nome do arquivo e o busca em linkedin/data/images/,
    que é o diretório commitado no repo e disponível em qualquer ambiente.
    """
    if not img_path_raw:
        return None

    # Tenta o path original primeiro (funciona local)
    p = Path(img_path_raw)
    if p.exists():
        return p

    # Fallback: extrai só o nome do arquivo e busca no diretório do repo
    filename = Path(img_path_raw.replace("\\", "/")).name
    candidate = _LI_IMAGES / filename
    if candidate.exists():
        return candidate

    return None

REPO_ROOT = Path(__file__).parent.parent.parent  # agents/ -> linkedin/ -> repo


class PublicacaoError(Exception):
    """Sinaliza que houve falha de publicacao — usado para exit code != 0."""


def run(max_por_run: int = 1) -> list[str]:
    """
    Publica posts pendentes ate hoje, do mais antigo, no maximo `max_por_run`.
    Levanta PublicacaoError se alguma publicacao falhar (para alertar no Actions).
    """
    print("[Agente Publicacao] Verificando posts para publicar...")

    posts = at.get_posts_due_for_publication()
    if not posts:
        print("[Agente Publicacao] Nenhum post pendente para hoje.")
        return []

    a_publicar = posts[:max_por_run]
    restantes  = len(posts) - len(a_publicar)
    hoje       = datetime.now(timezone.utc).date().isoformat()

    client     = LinkedInClient()
    publicados = []
    falhas     = []

    for post in a_publicar:
        record_id = post["id"]
        f         = post["fields"]
        copy      = f.get("Copy", "")
        titulo    = f.get("Título interno", f.get("Titulo interno", record_id))
        brief     = f.get("Image Brief", f.get("image_brief", ""))
        img_path  = f.get("Image Path", f.get("image_path", ""))
        data_ag   = f.get("Data agendada", f.get("data_agendada", ""))

        # Trava de idempotencia (dupla checagem — a query ja filtra, mas garante)
        if f.get("linkedin_post_id") or f.get("LinkedIn Post ID"):
            print(f"  [SKIP] {titulo[:55]} — ja tem URN (ja publicado).")
            continue

        if not copy.strip():
            print(f"  [SKIP] {titulo[:55]} — copy vazio.")
            continue

        if data_ag and data_ag < hoje:
            print(f"  [RECUPERANDO] {titulo[:50]} estava atrasado ({data_ag}).")

        # Carrossel: publica so o intro text (LinkedIn nao tem carrossel nativo via API)
        copy_pub = _extrair_copy_publicavel(copy)

        # Resolve o path da imagem (suporta path absoluto Windows e path relativo no Linux/Actions)
        img_file = _resolver_imagem(img_path)

        # Gera imagem se houver brief e nao foi encontrada
        if brief and not img_file:
            novo_path = _gerar_imagem(brief, record_id)
            if novo_path:
                img_file = Path(novo_path)
                at.update_post(record_id, {"Image Path": str(img_file)})

        try:
            if img_file:
                post_urn = client.post_with_image(copy_pub, str(img_file))
                print(f"  [OK] Publicado com imagem: {titulo[:55]}")
            else:
                post_urn = client.post_text(copy_pub)
                print(f"  [OK] Publicado (texto): {titulo[:55]}")

            if not post_urn:
                raise RuntimeError("LinkedIn nao retornou URN do post")

            # Persiste o estado ANTES de qualquer outra coisa
            at.update_post(record_id, {
                "Status":           STATUS_PUBLICADO,
                "LinkedIn Post ID": post_urn,
                "Data publicação":  hoje,
                "erro_publicacao":  "",  # limpa erro anterior se houver
            })
            print(f"       URN: {post_urn}")

            # Commit IMEDIATO — fecha a janela de duplicacao.
            # Se o processo morrer depois daqui, o estado ja esta duravel no GitHub.
            _commit_incremental(post_urn, titulo)

            publicados.append(record_id)

        except Exception as e:
            erro = f"{type(e).__name__}: {str(e)[:200]}"
            print(f"  [ERRO] {titulo[:55]}: {erro}")
            import traceback; traceback.print_exc()
            # Grava o erro no post para aparecer no painel
            at.update_post(record_id, {"erro_publicacao": f"[{hoje}] {erro}"})
            falhas.append((titulo, erro))

    if restantes:
        print(f"[Agente Publicacao] {restantes} post(s) ainda pendente(s) — proximo run.")

    print(f"[Agente Publicacao] {len(publicados)} publicado(s), {len(falhas)} falha(s).")

    if falhas:
        msg = "; ".join(f"{t[:30]} ({e[:40]})" for t, e in falhas)
        raise PublicacaoError(f"{len(falhas)} falha(s) de publicacao: {msg}")

    return publicados


def _commit_incremental(urn: str, titulo: str):
    """
    Commita e empurra o estado IMEDIATAMENTE apos publicar — so no GitHub Actions.
    Localmente (GITHUB_ACTIONS != true) nao faz nada: o usuario controla o git.

    Fecha a janela de idempotencia: sem isso, um crash entre a publicacao no
    LinkedIn e o commit final do workflow deixaria o post 'Agendado' no GitHub,
    causando republicacao (duplicata) num re-run.
    """
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    try:
        subprocess.run(["git", "add", "linkedin/data/posts.json", "linkedin/data/images"],
                       cwd=REPO_ROOT, check=True, capture_output=True)
        # Se nada mudou, git commit falha — tratamos como no-op
        r = subprocess.run(["git", "commit", "-m", f"data: publicado {titulo[:50]} ({urn[-12:]})"],
                           cwd=REPO_ROOT, capture_output=True, text=True)
        if r.returncode != 0 and "nothing to commit" not in (r.stdout + r.stderr).lower():
            print(f"  [git] aviso no commit: {r.stderr[:120]}")
        subprocess.run(["git", "push"], cwd=REPO_ROOT, check=True, capture_output=True)
        print(f"  [git] estado salvo no GitHub (commit imediato).")
    except subprocess.CalledProcessError as e:
        # Nao aborta a publicacao — o post ja foi ao LinkedIn. So avisa.
        err = (e.stderr or b"").decode("utf-8", "replace")[:200] if e.stderr else str(e)
        print(f"  [git] FALHA ao commitar estado: {err}")
        print(f"  [git] ATENCAO: post publicado mas estado pode nao ter sido salvo.")


def _extrair_copy_publicavel(raw: str) -> str:
    """
    Retorna APENAS o texto publicavel no LinkedIn — sem JSON, sem slides,
    sem separadores internos do agente (***, ---, ```, [BRIEF...], [TIPO...]).

    Separadores que o Gemini usa para marcar fim da copy:
      - [COPY DO POST] ... [BRIEF DA IMAGEM JSON]
      - *** (antes de bloco JSON ou slides)
      - --- (separador generico)
      - SLIDE 1: (carrossel)
      - ``` (bloco de codigo/JSON)
      - [LINHA: / [FORMATO: / [TIPO: etc. (metadados)
    """
    # 1) Se tem [COPY DO POST], pega so essa secao
    if "[COPY DO POST]" in raw:
        m = re.search(
            r"\[COPY DO POST\](.*?)(?:\[BRIEF|\[SLIDES\]|SLIDE\s+\d|\[TIPO|---|\*\*\*|```|\Z)",
            raw, re.DOTALL | re.IGNORECASE
        )
        if m:
            raw = m.group(1)

    # 2) Corta em qualquer separador de secao do agente
    separadores = [
        r"\n\s*\*{3,}\s*\n",          # *** em linha propria
        r"\n\s*-{3,}\s*\n",           # --- em linha propria
        r"\n\s*```",                   # inicio de bloco de codigo
        r"\n\s*SLIDE\s+1\s*:",        # slides de carrossel
        r"\n\s*\[BRIEF",              # brief de imagem
        r"\n\s*\[SLIDES\]",           # bloco de slides
    ]
    for sep in separadores:
        partes = re.split(sep, raw, maxsplit=1, flags=re.IGNORECASE)
        if len(partes) > 1:
            raw = partes[0]
            break

    # 3) Remove metadados finais [LINHA: x] [FORMATO: y] etc.
    raw = re.sub(
        r"\[(?:LINHA|FORMATO|CTA|FUNCAO|TIPO|PONTE|POSTURA|OFERTA|NOTA):[^\]]+\]",
        "", raw, flags=re.IGNORECASE
    )

    # 4) Remove qualquer bloco JSON solto que sobrou
    raw = re.sub(r"```[\s\S]*?```", "", raw)
    raw = re.sub(r"\{[\s\S]*?\}", "", raw)

    return raw.strip()


def _gerar_imagem(brief: str, post_id: str) -> str | None:
    """
    Gera a imagem do post. Retorna path ou None se falhar.

    Usa o v2 (fundo fotografico + overlay HTML + Puppeteer). Se o v2 falhar
    — sem GOOGLE_API_KEY, sem rede, node ausente — cai no v1 (Pillow), que
    nao depende de nada externo. Assim o post nunca fica sem imagem.
    """
    try:
        from agents.agente_imagem_v2 import gerar_imagem
        path = gerar_imagem(brief, post_id)
        if path:
            return path
        print(f"  [AVISO] Imagem v2 nao gerou para {post_id[:8]} — caindo no v1 (Pillow).")
    except Exception as e:
        print(f"  [AVISO] Imagem v2 falhou para {post_id[:8]}: {e} — caindo no v1.")

    try:
        from agents.agente_imagem import generate_image
        return generate_image(brief, post_id)
    except Exception as e:
        print(f"  [AVISO] Falha ao gerar imagem para {post_id[:8]}: {e}")
        return None


def schedule_posts(post_ids: list[str], dates: list[str]):
    """
    Agenda posts para datas especificas.
    dates: lista de strings no formato 'YYYY-MM-DD'
    """
    for post_id, date in zip(post_ids, dates):
        at.update_post(post_id, {"Data agendada": date, "Status": "Agendado"})
        print(f"  Agendado {post_id} para {date}")
