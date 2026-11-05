"""
metricas.py — coleta e analise MENSAL de performance dos posts.

Decisao do Davi: mensal, nao semanal. Semana e ruido — 4 posts nao dizem nada
sobre o que funciona. No mes ha ~17 posts, o suficiente para comparar tipo de
conteudo (pratico vs storyline), formato e tema, e ajustar o mes seguinte.

O que a API do LinkedIn DA para perfil pessoal: likes e comentarios por post
(socialActions). O que ela NAO da: impressoes e alcance — esses continuam sendo
export manual do LinkedIn Analytics. Por isso o relatorio separa claramente o
que foi medido do que falta o Davi preencher.

Uso:
    python main.py metricas            # coleta + relatorio do mes passado
    python main.py metricas --mes 2026-08
"""
import json
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

_BASE = Path(__file__).parent
_POSTS = _BASE / "data" / "posts.json"
_METRICAS = _BASE / "data" / "metricas.json"


def _carregar_posts() -> list[dict]:
    if not _POSTS.exists():
        return []
    with open(_POSTS, encoding="utf-8") as f:
        return json.load(f)


def _mes_anterior() -> str:
    hoje = date.today()
    ano, mes = (hoje.year - 1, 12) if hoje.month == 1 else (hoje.year, hoje.month - 1)
    return f"{ano}-{mes:02d}"


def coletar(mes: str) -> list[dict]:
    """Busca likes/comentarios na API para cada post publicado no mes."""
    from linkedin_client import LinkedInClient

    posts = [p for p in _carregar_posts()
             if p.get("status") == "Publicado"
             and (p.get("data_agendada") or "").startswith(mes)
             and p.get("linkedin_post_id")]
    if not posts:
        return []

    client = LinkedInClient()
    coletados = []
    for p in posts:
        likes = comentarios = None
        try:
            stats = client.get_post_stats(p["linkedin_post_id"]) or {}
            # get_post_stats devolve as chaves em pt: curtidas/comentarios.
            # Ler "likes" deixava o valor None mesmo quando a API respondia.
            likes = stats.get("curtidas")
            comentarios = stats.get("comentarios")
        except Exception as e:
            detalhe = getattr(getattr(e, "response", None), "status_code", "") or type(e).__name__
            print(f"  [metricas] {p['data_agendada']}: falhou ({detalhe})")
        coletados.append({
            "id": p["id"],
            "data": p["data_agendada"],
            "titulo": (p.get("titulo") or "")[:70],
            "linha": p.get("linha", "?"),
            "formato": p.get("formato", "?"),
            "tem_imagem": bool(p.get("image_path")),
            "likes": likes,
            "comentarios": comentarios,
        })
    return coletados


def salvar(mes: str, dados: list[dict]) -> None:
    hist = {}
    if _METRICAS.exists():
        try:
            with open(_METRICAS, encoding="utf-8") as f:
                hist = json.load(f)
        except json.JSONDecodeError:
            hist = {}
    hist[mes] = {
        "coletado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "posts": dados,
    }
    _METRICAS.parent.mkdir(parents=True, exist_ok=True)
    with open(_METRICAS, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)


def _media(valores: list) -> str:
    nums = [v for v in valores if isinstance(v, (int, float))]
    return f"{sum(nums)/len(nums):.1f}" if nums else "sem dado"


def relatorio(mes: str, dados: list[dict]) -> None:
    linha = "=" * 68
    print(linha)
    print(f"  MEDICAO MENSAL — {mes}")
    print(linha)

    if not dados:
        print("Nenhum post publicado com ID do LinkedIn neste mes.")
        print(linha)
        return

    print(f"Posts publicados: {len(dados)}\n")

    # None = a API nao respondeu; 0 = respondeu e o post nao teve interacao.
    # Confundir os dois faz "nao consegui medir" virar "seu conteudo fracassou".
    medidos = [d for d in dados if d["likes"] is not None or d["comentarios"] is not None]
    if not medidos:
        print("!! NENHUM DADO COLETADO — a API recusou todas as chamadas.")
        print("   Isto NAO significa engajamento zero: significa medicao zero.")
        print("   Causa: o token tem escopo de escrita (w_member_social); ler")
        print("   socialActions devolve 403 ACCESS_DENIED.")
        print("   -> use o LinkedIn Analytics na mao e anote em PERFORMANCE.md")
        print(linha)
        return
    if len(medidos) < len(dados):
        print(f"AVISO: {len(dados) - len(medidos)} de {len(dados)} posts sem dado "
              f"(API recusou) — ficam fora das medias e do ranking.")
        dados = medidos

    # Por tipo de conteudo — a comparacao que decide o mix do mes seguinte
    por_linha = defaultdict(list)
    for d in dados:
        por_linha[d["linha"]].append(d)
    print("POR TIPO DE CONTEUDO")
    for nome, itens in sorted(por_linha.items()):
        print(f"  {nome:<22} {len(itens):>2} posts | "
              f"likes med {_media([i['likes'] for i in itens]):>9} | "
              f"comentarios med {_media([i['comentarios'] for i in itens]):>9}")

    com_img = [d for d in dados if d["tem_imagem"]]
    sem_img = [d for d in dados if not d["tem_imagem"]]
    if com_img and sem_img:
        print("\nCOM IMAGEM vs SEM IMAGEM")
        print(f"  com imagem  {len(com_img):>2} posts | likes med {_media([i['likes'] for i in com_img])}")
        print(f"  sem imagem  {len(sem_img):>2} posts | likes med {_media([i['likes'] for i in sem_img])}")

    ranq = sorted(dados, key=lambda d: (d["likes"] or 0) + 3 * (d["comentarios"] or 0),
                  reverse=True)
    print("\nRANKING (comentario pesa 3x — e o que o algoritmo premia)")
    for d in ranq[:5]:
        print(f"  {d['data']} L:{str(d['likes'] or 0):>3} C:{str(d['comentarios'] or 0):>2}  {d['titulo'][:44]}")
    if len(ranq) > 5:
        pior = ranq[-1]
        print("  ...")
        print(f"  {pior['data']} L:{str(pior['likes'] or 0):>3} C:{str(pior['comentarios'] or 0):>2}  {pior['titulo'][:44]}  <- pior")

    print("\n" + "-" * 68)
    print("FALTA MEDIR (a API nao entrega para perfil pessoal):")
    print("  impressoes, alcance e visitas ao perfil")
    print("  -> exporte do LinkedIn Analytics e anote em PERFORMANCE.md")
    print("\nPERGUNTAS PARA AJUSTAR O PROXIMO MES:")
    print("  1. Qual TIPO teve mais comentarios? Aumentar a fatia dele no mix.")
    print("  2. O melhor post tem o que em comum com o segundo? (tema, formato, hook)")
    print("  3. Os comentarios sao de dono de negocio pequeno, ou de colegas de area?")
    print("  4. Alguem comentou e ficou sem resposta? (isso derruba alcance)")
    print(linha)


def rodar(mes: str = None) -> dict:
    mes = mes or _mes_anterior()
    print(f"[metricas] Coletando {mes}...")
    dados = coletar(mes)
    salvar(mes, dados)
    relatorio(mes, dados)
    return {"mes": mes, "posts": len(dados)}


if __name__ == "__main__":
    import sys
    m = None
    if "--mes" in sys.argv:
        m = sys.argv[sys.argv.index("--mes") + 1]
    rodar(m)
