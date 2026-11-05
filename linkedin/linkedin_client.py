"""
LinkedIn API client.

OAuth flow:
  Run `python main.py auth-linkedin` once to authorize.
  The access token is stored in the .env file automatically.

Publishing scope: w_member_social
Analytics scope: r_member_social (likes/comments only — impressions not available via API for personal profiles)
"""
import os
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs
import webbrowser
import requests
from config import (
    LINKEDIN_CLIENT_ID,
    LINKEDIN_CLIENT_SECRET,
    LINKEDIN_REDIRECT_URI,
    LINKEDIN_ACCESS_TOKEN,
    LINKEDIN_PERSON_URN,
)

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
API_BASE = "https://api.linkedin.com/v2"

SCOPES = "w_member_social"  # r_member_social removido — nao necessario para publicar


class LinkedInClient:
    def __init__(self):
        self.access_token = LINKEDIN_ACCESS_TOKEN
        self.person_urn = LINKEDIN_PERSON_URN
        self._headers = {
            "Authorization": f"Bearer {self.access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

    def _check_token(self):
        if not self.access_token:
            raise RuntimeError(
                "LinkedIn access token not set. Run: python main.py auth-linkedin"
            )

    def get_profile(self) -> dict:
        self._check_token()
        res = requests.get(f"{API_BASE}/me", headers=self._headers)
        res.raise_for_status()
        return res.json()

    def post_text(self, text: str) -> str:
        """Publish a text post. Returns the LinkedIn post URN."""
        self._check_token()
        if not self.person_urn:
            profile = self.get_profile()
            self.person_urn = f"urn:li:person:{profile['id']}"

        payload = {
            "author": self.person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }
        res = requests.post(f"{API_BASE}/ugcPosts", headers=self._headers, json=payload)
        res.raise_for_status()
        post_urn = res.headers.get("x-restli-id", "") or res.json().get("id", "")
        return post_urn

    def upload_image(self, image_path: str) -> str:
        """
        Faz upload de uma imagem para o LinkedIn.
        Retorna o asset URN (ex: 'urn:li:digitalmediaAsset:...')

        Fluxo: registerUpload -> PUT binario -> retorna URN
        """
        self._check_token()
        if not self.person_urn:
            profile = self.get_profile()
            self.person_urn = f"urn:li:person:{profile['id']}"

        # 1. Registrar upload
        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": self.person_urn,
                "serviceRelationships": [
                    {
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent",
                    }
                ],
            }
        }
        reg_res = requests.post(
            f"{API_BASE}/assets?action=registerUpload",
            headers=self._headers,
            json=register_payload,
        )
        reg_res.raise_for_status()
        reg_data = reg_res.json()

        upload_url  = reg_data["value"]["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]
        asset_urn = reg_data["value"]["asset"]

        # 2. Upload do binario
        with open(image_path, "rb") as f:
            img_bytes = f.read()

        upload_headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/octet-stream",
        }
        put_res = requests.put(upload_url, headers=upload_headers, data=img_bytes)
        put_res.raise_for_status()

        return asset_urn

    def post_with_image(self, text: str, image_path: str) -> str:
        """
        Publica post com imagem no LinkedIn.
        Retorna o URN do post.
        """
        self._check_token()
        if not self.person_urn:
            profile = self.get_profile()
            self.person_urn = f"urn:li:person:{profile['id']}"

        asset_urn = self.upload_image(image_path)

        payload = {
            "author": self.person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "IMAGE",
                    "media": [
                        {
                            "status": "READY",
                            "description": {"text": ""},
                            "media": asset_urn,
                            "title": {"text": ""},
                        }
                    ],
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }
        res = requests.post(f"{API_BASE}/ugcPosts", headers=self._headers, json=payload)
        res.raise_for_status()
        post_urn = res.headers.get("x-restli-id", "") or res.json().get("id", "")
        return post_urn

    def get_post_stats(self, post_urn: str) -> dict:
        """
        Returns available stats for a post.
        Impressions are NOT available via API for personal profiles — must be input manually.
        """
        self._check_token()
        encoded = requests.utils.quote(post_urn, safe="")
        res = requests.get(
            f"{API_BASE}/socialActions/{encoded}",
            headers=self._headers,
        )
        if res.status_code == 404:
            return {"curtidas": 0, "comentarios": 0, "compartilhamentos": 0}
        res.raise_for_status()
        data = res.json()
        return {
            "curtidas": data.get("likesSummary", {}).get("totalLikes", 0),
            "comentarios": data.get("commentsSummary", {}).get("totalFirstLevelComments", 0),
            "compartilhamentos": data.get("shareStatistics", {}).get("shareCount", 0),
        }


# ─── OAuth flow ───────────────────────────────────────────────────────────────

_auth_code_holder: dict = {}


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        error = params.get("error", [None])[0]
        _auth_code_holder["code"] = code
        _auth_code_holder["error"] = error
        self.send_response(200)
        self.end_headers()
        msg = b"Autorizado! Pode fechar esta aba." if code else b"Erro na autorizacao."
        self.wfile.write(msg)

    def log_message(self, *args):
        pass


def authorize() -> str:
    """
    Opens browser for LinkedIn OAuth. Starts a local server to catch the callback.
    Returns the access token string and prints it for manual .env update.
    """
    if not LINKEDIN_CLIENT_ID or not LINKEDIN_CLIENT_SECRET:
        raise RuntimeError("Configure LINKEDIN_CLIENT_ID e LINKEDIN_CLIENT_SECRET no .env")

    port = int(urlparse(LINKEDIN_REDIRECT_URI).port or 8888)
    server = HTTPServer(("localhost", port), _CallbackHandler)

    params = urlencode({
        "response_type": "code",
        "client_id": LINKEDIN_CLIENT_ID,
        "redirect_uri": LINKEDIN_REDIRECT_URI,
        "scope": SCOPES,
    })
    url = f"{AUTH_URL}?{params}"
    print(f"\nAbrindo navegador para autorização LinkedIn...\n{url}\n")
    webbrowser.open(url)

    server.handle_request()
    server.server_close()

    code = _auth_code_holder.get("code")
    if not code:
        raise RuntimeError(f"Erro OAuth: {_auth_code_holder.get('error')}")

    res = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": LINKEDIN_REDIRECT_URI,
        "client_id": LINKEDIN_CLIENT_ID,
        "client_secret": LINKEDIN_CLIENT_SECRET,
    })
    res.raise_for_status()
    token_data = res.json()
    access_token   = token_data["access_token"]
    refresh_token  = token_data.get("refresh_token", "")

    # Salva tokens IMEDIATAMENTE — antes de qualquer chamada adicional que possa falhar
    _update_env("LINKEDIN_ACCESS_TOKEN", access_token)
    if refresh_token:
        _update_env("LINKEDIN_REFRESH_TOKEN", refresh_token)

    # Tenta buscar person_urn (requer scope de perfil — pode nao estar disponivel)
    person_urn = LINKEDIN_PERSON_URN  # usa o existente como fallback
    try:
        client = LinkedInClient.__new__(LinkedInClient)
        client.access_token = access_token
        client.person_urn = ""
        client._headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }
        profile = client.get_profile()
        person_urn = f"urn:li:person:{profile['id']}"
        _update_env("LINKEDIN_PERSON_URN", person_urn)
    except Exception:
        print(f"[aviso] Nao foi possivel buscar person_urn — usando o existente: {person_urn}")

    print(f"\nTokens salvos no .env (raiz do projeto).")
    print(f"LINKEDIN_ACCESS_TOKEN={access_token}")
    print(f"LINKEDIN_PERSON_URN={person_urn}")
    if refresh_token:
        print(f"LINKEDIN_REFRESH_TOKEN={refresh_token}")
        print("\n→ Adicione LINKEDIN_REFRESH_TOKEN aos secrets do GitHub:")
        print(f"  gh secret set LINKEDIN_REFRESH_TOKEN --body \"{refresh_token}\"")
    return access_token


def _update_env(key: str, value: str):
    # .env fica na raiz do monorepo (um nivel acima de linkedin/)
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if not os.path.exists(env_path):
        with open(env_path, "w") as f:
            f.write(f"{key}={value}\n")
        return
    with open(env_path, "r") as f:
        lines = f.readlines()
    updated = False
    new_lines = []
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(f"{key}={value}\n")
    with open(env_path, "w") as f:
        f.writelines(new_lines)
