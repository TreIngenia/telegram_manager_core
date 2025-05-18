import os
import json
import secrets
import hashlib

# Funzione per generare un token sicuro
def generate_secure_token(length=32):
    return secrets.token_hex(length)

# Funzione per generare hash del token
def generate_token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()

# File dei token
API_TOKENS_FILE = "api_tokens.json"

# Elimina il file dei token esistente se presente
if os.path.exists(API_TOKENS_FILE):
    os.remove(API_TOKENS_FILE)

# Genera un nuovo token
admin_token = generate_secure_token()

# Crea il file dei token con il nuovo token admin
token_data = {
    "admin": {
        "token_hash": generate_token_hash(admin_token),
        "created": "2025-05-18 12:00:00",
        "role": "admin",
        "expiration": None,
        "last_used": None
    }
}

# Salva il file dei token
with open(API_TOKENS_FILE, "w", encoding="utf-8") as f:
    json.dump(token_data, f, indent=4)

# Mostra il token
print(f"\n=== NUOVO TOKEN ADMIN ===\n{admin_token}\n=======================")
print("Usa questo token per autenticare le richieste API.")