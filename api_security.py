"""
Modulo di sicurezza e autenticazione per API server

Implementa l'autenticazione token-based, la generazione di token sicuri
e la gestione degli accessi per il server API di Telegram Media Downloader.
"""

import os
import time
import json
import secrets
import hashlib
import threading
from functools import wraps
from flask import request, jsonify
from utils import load_json, save_json, log_error, log_info

# File per memorizzare i token API
API_TOKENS_FILE = "api_tokens.json"

# Lock per la sincronizzazione degli accessi al file dei token
token_lock = threading.RLock()

def generate_secure_token(length=32):
    """
    Genera un token API sicuro
    
    Args:
        length: Lunghezza del token in byte
        
    Returns:
        Token esadecimale
    """
    return secrets.token_hex(length)

def generate_token_hash(token):
    """
    Genera un hash del token per memorizzarlo in modo sicuro
    
    Args:
        token: Token da hashare
        
    Returns:
        Hash del token
    """
    return hashlib.sha256(token.encode()).hexdigest()

def create_user_token(username, role="user", expiration_days=None):
    """
    Crea un nuovo token API per un utente
    
    Args:
        username: Nome utente
        role: Ruolo dell'utente (admin, user)
        expiration_days: Giorni di validità del token (None = non scade mai)
        
    Returns:
        (token, token_data): Tupla con il token e i suoi metadati
    """
    with token_lock:
        tokens = load_json(API_TOKENS_FILE)
        
        # Genera un nuovo token
        token = generate_secure_token()
        token_hash = generate_token_hash(token)
        
        # Calcola la data di scadenza se specificata
        expiration = None
        if expiration_days:
            expiration = time.time() + (expiration_days * 86400)  # 86400 secondi = 1 giorno
        
        # Crea i dati del token
        token_data = {
            "token_hash": token_hash,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "role": role,
            "expiration": expiration,
            "last_used": None
        }
        
        # Salva il token nel file
        tokens[username] = token_data
        save_json(API_TOKENS_FILE, tokens)
        
        # Registra la creazione del token
        log_info(f"Creato nuovo token API per {username} (ruolo: {role})", "api_security.log")
        
        return token, token_data

def validate_token(token):
    """
    Verifica se un token API è valido
    
    Args:
        token: Token da verificare
        
    Returns:
        (is_valid, username, role): Tupla con validità, nome utente e ruolo
    """
    with token_lock:
        tokens = load_json(API_TOKENS_FILE)
        
        if not tokens:
            return False, None, None
        
        # Calcola l'hash del token per confrontarlo
        token_hash = generate_token_hash(token)
        
        # Cerca il token tra tutti gli utenti
        for username, token_data in tokens.items():
            # Verifica che l'hash corrisponda
            if token_data.get("token_hash") == token_hash:
                # Verifica la scadenza
                if token_data.get("expiration") and time.time() > token_data.get("expiration"):
                    return False, username, None
                
                # Aggiorna l'ultimo utilizzo
                token_data["last_used"] = time.strftime("%Y-%m-%d %H:%M:%S")
                tokens[username] = token_data
                save_json(API_TOKENS_FILE, tokens)
                
                return True, username, token_data.get("role")
        
        return False, None, None

def revoke_token(username):
    """
    Revoca il token API di un utente
    
    Args:
        username: Nome utente
        
    Returns:
        bool: True se il token è stato revocato, False altrimenti
    """
    with token_lock:
        tokens = load_json(API_TOKENS_FILE)
        
        if username in tokens:
            del tokens[username]
            save_json(API_TOKENS_FILE, tokens)
            
            # Registra la revoca del token
            log_info(f"Revocato token API per {username}", "api_security.log")
            
            return True
        
        return False

def require_api_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Inizializza token come None
        token = None
        
        # Prova prima a ottenere il token dall'header Authorization (metodo preferito)
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split('Bearer ')[1].strip()
        
        # Se non è stato trovato nell'header Authorization, prova X-API-Token (per retrocompatibilità)
        if not token:
            token = request.headers.get('X-API-Token')
        
        # Se non c'è alcun token, restituisci errore
        if not token:
            return jsonify({"error": "Token API mancante. Utilizzare l'header 'Authorization: Bearer TOKEN'"}), 401
        
        # Usa la funzione validate_token per verificare il token
        from api_security import validate_token
        is_valid, username, role = validate_token(token)
        
        # Se il token non è valido, restituisci errore
        if not is_valid:
            return jsonify({"error": "Token API non valido o scaduto"}), 401
        
        # Aggiungi le informazioni dell'utente alla richiesta per l'utilizzo in altri decoratori
        request.api_user = username
        request.api_role = role
        
        # Procedi con la funzione originale se il token è valido
        return f(*args, **kwargs)
    
    return decorated_function

def require_admin_role(f):
    """
    Decoratore per richiedere il ruolo di amministratore
    Deve essere utilizzato insieme a require_api_token
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(request, 'api_role') or request.api_role != 'admin':
            return jsonify({"error": "Questa operazione richiede privilegi di amministratore"}), 403
        
        return f(*args, **kwargs)
    
    return decorated_function

def initialize_api_security():
    """
    Inizializza il sistema di sicurezza API
    Crea un token admin predefinito se non esiste
    
    Returns:
        admin_token: Token admin predefinito (solo se appena creato)
    """
    with token_lock:
        if not os.path.exists(API_TOKENS_FILE):
            # Crea la directory se non esiste
            directory = os.path.dirname(API_TOKENS_FILE)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            
            # Inizializza il file dei token vuoto
            save_json(API_TOKENS_FILE, {})
        
        tokens = load_json(API_TOKENS_FILE)
        
        # Se non ci sono token admin, crea un token admin predefinito
        admin_exists = False
        for username, token_data in tokens.items():
            if token_data.get("role") == "admin":
                admin_exists = True
                break
        
        if not admin_exists:
            admin_token, _ = create_user_token("admin", role="admin")
            print(f"\n⚠️ TOKEN ADMIN GENERATO: {admin_token}")
            print("Salvare questo token in un luogo sicuro, non verrà mostrato di nuovo!")
            print("Utilizzare questo token per autenticare le richieste API come amministratore.")
            
            # Registra la creazione del token admin iniziale
            log_info("Creato token admin iniziale", "api_security.log")
            
            return admin_token
        
        return None
