"""
Renova o token do LinkedIn usando o refresh_token (válido 365 dias).
Salva os novos tokens em /tmp/ para o workflow fazer gh secret set.
"""
import os
import sys
import requests

REFRESH_TOKEN  = os.environ.get("LINKEDIN_REFRESH_TOKEN", "")
CLIENT_ID      = os.environ.get("LINKEDIN_CLIENT_ID", "")
CLIENT_SECRET  = os.environ.get("LINKEDIN_CLIENT_SECRET", "")

if not all([REFRESH_TOKEN, CLIENT_ID, CLIENT_SECRET]):
    print("ERRO: LINKEDIN_REFRESH_TOKEN, LINKEDIN_CLIENT_ID ou LINKEDIN_CLIENT_SECRET não configurados.")
    sys.exit(1)

print("Renovando token LinkedIn...")

res = requests.post(
    "https://www.linkedin.com/oauth/v2/accessToken",
    data={
        "grant_type":    "refresh_token",
        "refresh_token": REFRESH_TOKEN,
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    },
)

if res.status_code != 200:
    print(f"ERRO {res.status_code}: {res.text}")
    sys.exit(1)

data = res.json()
new_access  = data.get("access_token", "")
new_refresh = data.get("refresh_token", REFRESH_TOKEN)  # LinkedIn pode ou não rotacionar
expires_in  = data.get("expires_in", 0)

if not new_access:
    print("ERRO: resposta não contém access_token.")
    print(data)
    sys.exit(1)

# Salva em /tmp para o workflow ler
with open("/tmp/new_access_token.txt",  "w") as f:
    f.write(new_access)
with open("/tmp/new_refresh_token.txt", "w") as f:
    f.write(new_refresh)

days = expires_in // 86400
print(f"Token renovado com sucesso. Válido por {days} dias.")
