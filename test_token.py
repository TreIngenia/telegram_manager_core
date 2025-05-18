import os
import json
import sys
import hashlib
import time

# File dei token
API_TOKENS_FILE = "api_tokens.json"

def print_separator():
    print("\n" + "=" * 50 + "\n")

def generate_token_hash(token):
    """Genera un hash del token per confrontarlo con quello salvato"""
    return hashlib.sha256(token.encode()).hexdigest()

print_separator()
print("Script di diagnostica per i token API")
print_separator()

# Verifica se il file dei token esiste
if not os.path.exists(API_TOKENS_FILE):
    print(f"ERRORE: Il file {API_TOKENS_FILE} non esiste!")
    print("Devi generare un token admin prima di procedere.")
    print_separator()
    sys.exit(1)

# Leggi il file dei token
try:
    with open(API_TOKENS_FILE, 'r', encoding='utf-8') as f:
        tokens = json.load(f)
    
    print(f"File {API_TOKENS_FILE} trovato e caricato con successo.")
    print(f"Numero di token trovati: {len(tokens)}")
    print_separator()
    
    # Stampa informazioni sui token
    print("Token trovati:")
    for username, token_data in tokens.items():
        print(f"- Utente: {username}")
        print(f"  Ruolo: {token_data.get('role', 'N/A')}")
        print(f"  Creato: {token_data.get('created', 'N/A')}")
        print(f"  Scadenza: {token_data.get('expiration', 'Mai')}")
        print(f"  Ultimo utilizzo: {token_data.get('last_used', 'Mai')}")
        print()
    
    print_separator()
    
    # Chiedi all'utente di inserire un token da testare
    print("Inserisci il token API da testare:")
    token = input("> ").strip()
    
    if not token:
        print("Nessun token inserito. Uscita.")
        print_separator()
        sys.exit(0)
    
    # Calcola l'hash del token
    token_hash = generate_token_hash(token)
    print(f"Hash del token inserito: {token_hash}")
    print_separator()
    
    # Verifica se il token è valido
    valid = False
    for username, token_data in tokens.items():
        stored_hash = token_data.get('token_hash')
        if stored_hash == token_hash:
            valid = True
            print(f"TOKEN VALIDO per l'utente: {username}")
            print(f"Ruolo: {token_data.get('role', 'N/A')}")
            
            # Verifica la scadenza
            expiration = token_data.get('expiration')
            if expiration and time.time() > expiration:
                print("ATTENZIONE: Il token è scaduto!")
                valid = False
            
            break
    
    if not valid:
        print("TOKEN NON VALIDO!")
        print("Il token inserito non corrisponde a nessun token registrato.")
    
    print_separator()
    
    # Genera l'header corretto per il testing
    if valid:
        print("Usa questo header per le richieste API:")
        print(f'Authorization: Bearer {token}')
        print()
        print("In PowerShell:")
        print(f'Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/users" -Headers @{{ "Authorization" = "Bearer {token}" }}')
        print()
        print("Con curl.exe:")
        print(f'curl.exe -X GET "http://127.0.0.1:5000/api/users" -H "Authorization: Bearer {token}"')
    
    print_separator()
    
except Exception as e:
    print(f"ERRORE durante la lettura del file {API_TOKENS_FILE}: {e}")
    print("Contenuto del file:")
    try:
        with open(API_TOKENS_FILE, 'r', encoding='utf-8') as f:
            print(f.read())
    except:
        print("Impossibile leggere il file.")
    print_separator()