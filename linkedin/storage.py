"""
storage.py — camada de persistência em JSON (repo GitHub como banco de dados).

Substitui notion_client.py. Interface idêntica: agents fazem `import storage as at`.

Arquivos em data/:
  ciclo_ativo.json  — ciclo atual (dict)
  posts.json        — lista de todos os posts
  temas.json        — lista de temas do ciclo atual
"""
import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

_CICLO  = DATA_DIR / "ciclo_ativo.json"
_POSTS  = DATA_DIR / "posts.json"
_TEMAS  = DATA_DIR / "temas.json"


# ─── helpers ─────────────────────────────────────────────────────────────────

def _load(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _dump(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _uid() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


# ─── CICLOS ──────────────────────────────────────────────────────────────────

def get_active_cycle() -> dict | None:
    c = _load(_CICLO, {})
    if not c or c.get("status") != "Ativo":
        return None
    return {"id": c["id"], "fields": c}


def create_cycle(nome: str, start: datetime, end: datetime) -> dict:
    c = {
        "id":        _uid(),
        "nome":      nome,
        "status":    "Ativo",
        "inicio":    start.date().isoformat(),
        "fim":       end.date().isoformat(),
        "criado_em": _now(),
    }
    _dump(_CICLO, c)
    return {"id": c["id"], "fields": c}


def close_cycle(cycle_id: str):
    c = _load(_CICLO, {})
    if c.get("id") == cycle_id:
        c["status"] = "Encerrado"
        _dump(_CICLO, c)


def update_cycle(cycle_id: str, fields: dict) -> dict:
    c = _load(_CICLO, {})
    if c.get("id") == cycle_id:
        c.update(fields)
        _dump(_CICLO, c)
    return {"id": c.get("id"), "fields": c}


def get_cycle(cycle_id: str) -> dict | None:
    c = _load(_CICLO, {})
    if c.get("id") == cycle_id:
        return {"id": c["id"], "fields": c}
    return None


# ─── POSTS ───────────────────────────────────────────────────────────────────

def _posts() -> list[dict]:
    return _load(_POSTS, [])


def get_post(post_id: str) -> dict | None:
    for p in _posts():
        if p["id"] == post_id:
            return {"id": p["id"], "fields": p}
    return None


def get_posts_by_status(status: str, cycle_id: str = None) -> list[dict]:
    result = []
    for p in _posts():
        if p.get("status") != status:
            continue
        if cycle_id and p.get("ciclo_id") != cycle_id:
            continue
        result.append({"id": p["id"], "fields": p})
    return result


def create_post(fields: dict) -> dict:
    all_posts = _posts()
    post = {"id": _uid(), "criado_em": _now()}
    post.update(_normalize_fields(fields))
    all_posts.append(post)
    _dump(_POSTS, all_posts)
    return {"id": post["id"], "fields": post}


def update_post(post_id: str, fields: dict) -> dict:
    all_posts = _posts()
    for p in all_posts:
        if p["id"] == post_id:
            p.update(_normalize_fields(fields))
            _dump(_POSTS, all_posts)
            return {"id": p["id"], "fields": p}
    return {}


# ─── TEMAS ───────────────────────────────────────────────────────────────────

def _temas() -> list[dict]:
    return _load(_TEMAS, [])


def _tema_wrap(t: dict) -> dict:
    """Devolve tema com chaves Notion-style para compatibilidade com agente_redacao."""
    return {"id": t["id"], "fields": {
        "Tema":            t.get("tema", ""),
        "Linha":           t.get("linha", ""),
        "Relevância":      t.get("relevancia", 0),
        "Ângulo sugerido": t.get("angulo", ""),
        "Status":          t.get("status", ""),
        "ciclo_id":        t.get("ciclo_id"),
    }}


def get_available_temas(cycle_id: str = None) -> list[dict]:
    result = []
    for t in _temas():
        if t.get("status") != "Disponível":
            continue
        if cycle_id and t.get("ciclo_id") != cycle_id:
            continue
        result.append(_tema_wrap(t))
    result.sort(key=lambda x: -x["fields"].get("Relevância", 0))
    return result


def save_tema(tema: str, linha: str, relevancia: int, notas: str, cycle_id: str) -> dict:
    all_temas = _temas()
    t = {
        "id":           _uid(),
        "tema":         tema,
        "linha":        linha,
        "relevancia":   relevancia,
        "angulo":       notas,
        "status":       "Disponível",
        "ciclo_id":     cycle_id,
        "data_pesquisa": _today(),
    }
    all_temas.append(t)
    _dump(_TEMAS, all_temas)
    return _tema_wrap(t)


def mark_tema_em_uso(tema_id: str):
    all_temas = _temas()
    for t in all_temas:
        if t["id"] == tema_id:
            t["status"] = "Em uso"
    _dump(_TEMAS, all_temas)


def mark_tema_usado(tema_id: str, post_id: str = None):
    all_temas = _temas()
    for t in all_temas:
        if t["id"] == tema_id:
            t["status"] = "Usado"
            if post_id:
                t["post_id"] = post_id
    _dump(_TEMAS, all_temas)


def get_used_topics(days: int = 30) -> list[str]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    return [
        t["tema"] for t in _temas()
        if t.get("status") == "Usado" and (t.get("data_pesquisa") or "") >= cutoff
    ]


# ─── field normalizer ─────────────────────────────────────────────────────────
# Aceita nomes Notion ("Título interno", "Copy"…) OU snake_case já limpo.
# Normaliza para snake_case internamente — mais simples de ler nos arquivos JSON.

_TO_SNAKE = {
    # posts
    "Título interno":   "titulo",
    "Copy":             "copy",
    "Linha":            "linha",
    "Formato":          "formato",
    "Função no Funil":  "funcao_funil",
    "Tem CTA":          "tem_cta",
    "Status":           "status",
    "Origem":           "origem",
    "Notas Davi":       "notas_davi",
    "Feedback Crítico": "feedback_critico",
    "Data agendada":    "data_agendada",
    "Data publicação":  "data_publicacao",
    "LinkedIn Post ID": "linkedin_post_id",
    "Image Brief":      "image_brief",
    "Image Path":       "image_path",
    "Titulo interno":   "titulo",   # alias sem acento
    # relações
    "Ciclo":            "ciclo_id",
    "Tema":             "tema_id",   # quando usado em posts (lista de IDs)
    # ciclos
    "Nome":             "nome",
    "Data início":      "inicio",
    "Data fim":         "fim",
}

# mapeamento inverso para leitura pelos agents
_FROM_SNAKE = {v: k for k, v in _TO_SNAKE.items()}


def _normalize_fields(fields: dict) -> dict:
    """Converte nomes Notion → snake_case. Listas de relação → primeiro elemento."""
    out = {}
    for k, v in fields.items():
        key = _TO_SNAKE.get(k, k)  # snake_case se tiver mapeamento, senão usa como está
        # Relações chegam como lista de IDs — guardar só o primeiro
        if isinstance(v, list) and key in ("ciclo_id", "tema_id"):
            out[key] = v[0] if v else None
        else:
            out[key] = v
    return out


def _fields_out(p: dict) -> dict:
    """Devolve o dict com as chaves originais (Notion-style) para os agents lerem."""
    result = {}
    for k, v in p.items():
        notion_key = _FROM_SNAKE.get(k, k)
        result[notion_key] = v
    return result


# Monkey-patch get_post / get_posts_* para devolver campos no formato Notion
# (assim agents fazem fields.get("Copy") e funciona)

def _wrap(p: dict) -> dict:
    """Envolve um post/tema retornando fields com nomes Notion."""
    return {"id": p["id"], "fields": _fields_out(p)}


# Redefine as funções públicas para usar _wrap:

def get_post(post_id: str) -> dict | None:  # noqa: F811
    for p in _posts():
        if p["id"] == post_id:
            return _wrap(p)
    return None


def get_posts_by_status(status: str, cycle_id: str = None) -> list[dict]:  # noqa: F811
    result = []
    for p in _posts():
        if p.get("status") != status:
            continue
        if cycle_id and p.get("ciclo_id") != cycle_id:
            continue
        result.append(_wrap(p))
    return result


# Janela de recuperacao: recupera posts atrasados ate N dias (cobre falha de
# scheduler + fim de semana). Posts mais velhos sao tratados como residuo/lixo
# e NAO publicam automatico — ficam para supervisao humana no painel.
JANELA_RECUPERACAO_DIAS = 3


def get_posts_due_for_publication() -> list[dict]:  # noqa: F811
    """
    Posts pendentes para publicar, ordenados do mais antigo.

    Resiliencia (sistema autonomo, publicacao irreversivel):
      - Janela [hoje-3d, hoje]: recupera atrasos de falha real (scheduler caiu,
        fim de semana) sem perder o post. Atraso > 3 dias = nao publica automatico
        (provavelmente residuo de teste/ciclo antigo) — evita postar conteudo
        velho em nome do Davi.
      - Exclui posts com linkedin_post_id: trava de idempotencia que sobrevive
        a um crash antes de o status ser salvo.

    Retorna Notion-style (_wrap). O agente publica 1/run para manter a cadencia.
    """
    hoje  = datetime.now(timezone.utc).date()
    today = hoje.isoformat()
    floor = (hoje - timedelta(days=JANELA_RECUPERACAO_DIAS)).isoformat()
    result = []
    for p in _posts():
        if p.get("status") not in ("Agendado", "Aprovado"):
            continue
        if p.get("linkedin_post_id"):          # ja publicado — nunca republicar
            continue
        data = p.get("data_agendada")
        if data and floor <= data <= today:
            result.append(p)
    result.sort(key=lambda p: p.get("data_agendada", ""))
    return [_wrap(p) for p in result]


def get_published_posts(cycle_id: str) -> list[dict]:  # noqa: F811
    return get_posts_by_status("Publicado", cycle_id=cycle_id)


def get_posts_for_cycle(cycle_id: str) -> list[dict]:  # noqa: F811
    return [_wrap(p) for p in _posts() if p.get("ciclo_id") == cycle_id]


def get_available_temas(cycle_id: str = None) -> list[dict]:  # noqa: F811
    result = []
    for t in _temas():
        if t.get("status") != "Disponível":
            continue
        if cycle_id and t.get("ciclo_id") != cycle_id:
            continue
        result.append({"id": t["id"], "fields": {
            "Tema":            t.get("tema", ""),
            "Linha":           t.get("linha", ""),
            "Relevância":      t.get("relevancia", 0),
            "Ângulo sugerido": t.get("angulo", ""),
            "Status":          t.get("status", ""),
            "ciclo_id":        t.get("ciclo_id"),
        }})
    result.sort(key=lambda x: -x["fields"].get("Relevância", 0))
    return result
