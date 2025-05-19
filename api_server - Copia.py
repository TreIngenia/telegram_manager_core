"""
API Server per Telegram Media Downloader

Questo modulo implementa un server API Flask con Socket.IO per esporre
le funzionalità del Telegram Media Downloader attraverso REST API e WebSocket.
"""

import os
import sys
import json
import time
import asyncio
import threading
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from functools import wraps
from flask import send_file
import secrets

# Importa i moduli necessari dal progetto principale
from config import API_ID, API_HASH, DOWNLOADS_DIR, TEMP_DIR, ARCHIVE_DIR, LOCK_FILE
from utils import load_json, save_json, log_error, log_info, get_instance_id, register_instance, unregister_instance
from user_management import add_new_user, remove_user, show_saved_users
from group_management import get_all_user_groups, get_group_link, select_group_for_action
from media_handler import download_group_archive
from event_handler import start_monitoring, cleanup_session_files

# Inizializzazione Flask e Socket.IO
# app = Flask(__name__, static_folder='static')
app = Flask(__name__, 
            static_folder='static',  # Directory dei file statici
            static_url_path='/static')  # URL path per accedere ai file statici

# Configurazione per servire i file statici

# Definisci il percorso assoluto alla directory static
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

@app.route('/static/<path:filename>')
def serve_static(filename):
    file_path = os.path.join(STATIC_DIR, filename)
    if os.path.exists(file_path):
        return send_file(file_path)
    else:
        return "File not found", 404
    
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Endpoint not found",
        "status_code": 404
    }), 404

@app.errorhandler(500)
def server_error(error):
    # Log dell'errore
    log_error(f"Server error: {error}")
    return jsonify({
        "error": "Internal server error",
        "status_code": 500
    }), 500

@app.errorhandler(Exception)
def handle_exception(e):
    # Log dell'errore
    log_error(f"Unhandled exception: {e}")
    return jsonify({
        "error": "An unexpected error occurred",
        "status_code": 500
    }), 500


CORS(app)  # Abilita CORS per consentire richieste da domini diversi

# Configura una chiave segreta per l'app
app.config['SECRET_KEY'] = secrets.token_hex(16)

# Inizializza Socket.IO
socketio = SocketIO(app, cors_allowed_origins="*")

# Dizionario per tenere traccia delle istanze attive create dall'API
active_api_instances = {}

# Gestione autenticazione API
API_TOKENS = {}

# Funzione per generare un token API casuale
def generate_api_token():
    return secrets.token_hex(24)

# Carica i token API esistenti o crea il file se non esiste
def load_api_tokens():
    global API_TOKENS
    tokens_file = "api_tokens.json"
    if os.path.exists(tokens_file):
        API_TOKENS = load_json(tokens_file)
    
    # Se non ci sono token, crea un token admin di default
    if not API_TOKENS:
        admin_token = generate_api_token()
        API_TOKENS = {
            "admin": {
                "token": admin_token,
                "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                "role": "admin"
            }
        }
        save_json(tokens_file, API_TOKENS)
        print(f"⚠️ Creato token API admin: {admin_token}")
        print("Usa questo token per autenticare le richieste API.")
    
    return API_TOKENS

# Decoratore per verificare il token API
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
# def require_api_token(f):
#     @wraps(f)
#     def decorated_function(*args, **kwargs):
#         token = request.headers.get('X-API-Token')
#         from api_server import API_TOKENS
#         # Prova a ottenerlo dall'header Authorization
#         auth_header = request.headers.get('Authorization')
#         if not token and auth_header and auth_header.startswith('Bearer '):
#             token = auth_header.split('Bearer ')[1].strip()
        
#         if not token:
#             return jsonify({"error": "Token API non valido o mancante"}), 401
        
#         # Usa la funzione validate_token da api_security
#         from api_security import validate_token
#         is_valid, username, role = validate_token(token)
        
#         if not is_valid:
#             return jsonify({"error": "Token API non valido o mancante"}), 401
        
#         return f(*args, **kwargs)
    
#     return decorated_function

# def require_api_token(f):
#     @wraps(f)
#     def decorated_function(*args, **kwargs):
#         token = request.headers.get('X-API-Token')
        
#         # Verifica il token
#         valid_token = False
#         for user, info in API_TOKENS.items():
#             # Controlla se il token è presente direttamente nella chiave 'token'
#             if info.get('token') == token:
#                 valid_token = True
#                 break
#             # Altrimenti controlla se è presente un hash del token
#             elif 'token_hash' in info:
#                 from api_security import generate_token_hash
#                 token_hash = generate_token_hash(token)
#                 if info['token_hash'] == token_hash:
#                     valid_token = True
#                     break
        
#         if not valid_token:
#             return jsonify({"error": "Token API non valido o mancante"}), 401
        
#         return f(*args, **kwargs)
    
#     return decorated_function

# Classe per gestire sessioni di monitoraggio tramite API
class ApiMonitoringSession:
    def __init__(self, instance_id, nickname=None):
        self.instance_id = instance_id
        self.nickname = nickname
        self.is_running = False
        self.start_time = None
        self.thread = None
        self.status = "initialized"
        self.error = None
    
    def start(self):
        if self.is_running:
            return False
        
        self.start_time = time.time()
        self.is_running = True
        self.status = "starting"
        
        # Crea un thread per eseguire il monitoraggio in background
        self.thread = threading.Thread(target=self._run_monitoring)
        self.thread.daemon = True
        self.thread.start()
        
        return True
    
    def _run_monitoring(self):
        try:
            # Configura un nuovo loop di eventi asyncio per questo thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            self.status = "running"
            socketio.emit('monitoring_status', {
                'instance_id': self.instance_id,
                'status': self.status,
                'time': time.strftime("%Y-%m-%d %H:%M:%S")
            })
            
            # Esegui il monitoraggio nel loop asyncio
            loop.run_until_complete(start_monitoring(self.instance_id))
            
            # Chiudi il loop
            loop.close()
        except Exception as e:
            self.error = str(e)
            self.status = "error"
            log_error(f"Errore nel monitoraggio API (Istanza {self.instance_id}): {e}")
            socketio.emit('monitoring_error', {
                'instance_id': self.instance_id,
                'error': str(e),
                'time': time.strftime("%Y-%m-%d %H:%M:%S")
            })
        finally:
            self.is_running = False
            self.status = "stopped"
            socketio.emit('monitoring_status', {
                'instance_id': self.instance_id,
                'status': self.status,
                'time': time.strftime("%Y-%m-%d %H:%M:%S")
            })
    
    def stop(self):
        if not self.is_running:
            return False
        
        self.is_running = False
        self.status = "stopping"
        
        # La sessione verrà terminata con la prossima interruzione nel loop asyncio
        # Pulizia dei file di sessione
        cleanup_session_files(self.instance_id)
        
        # Rimuovi questa istanza dal registro
        unregister_instance(self.instance_id, LOCK_FILE)
        
        return True

# Funzione per convertire i dati degli utenti in un formato JSON-friendly
def format_users_for_api():
    phone_numbers = load_json("phone_numbers.json")
    users_list = []
    
    for nickname, phone in phone_numbers.items():
        users_list.append({
            "nickname": nickname,
            "phone": phone
        })
    
    return users_list

# Funzione per convertire i dati dei gruppi in un formato JSON-friendly
def format_groups_for_api(user_groups):
    formatted_groups = []
    
    for nickname, groups in user_groups.items():
        for group in groups:
            formatted_groups.append({
                "id": group["id"],
                "name": group["name"],
                "username": group.get("link", ""),
                "members_count": group.get("members_count", 0),
                "user": nickname
            })
    
    return formatted_groups

# Endpoint di test per verificare che il server sia attivo
@app.route('/api/status', methods=['GET'])
def api_status():
    return jsonify({
        "status": "online",
        "version": "1.0.0",
        "time": time.strftime("%Y-%m-%d %H:%M:%S")
    })

# Endpoint protetti con autenticazione

# API per la gestione degli utenti
@app.route('/api/users', methods=['GET'])
@require_api_token
def get_users():
    users = format_users_for_api()
    return jsonify({"users": users})

@app.route('/api/users', methods=['POST'])
@require_api_token
def add_user():
    data = request.json
    
    if not data or 'nickname' not in data or 'phone' not in data:
        return jsonify({"error": "Dati mancanti. Richiesti 'nickname' e 'phone'"}), 400
    
    # Implementazione asincrona dell'aggiunta utente
    async def add_user_async():
        from user_management import verify_and_add_user
        success = await verify_and_add_user(data['nickname'], data['phone'])
        return success
    
    # Esegui in modo sincrono la funzione asincrona
    loop = asyncio.new_event_loop()
    try:
        success = loop.run_until_complete(add_user_async())
    finally:
        loop.close()
    
    if success:
        return jsonify({"status": "success", "message": f"Utente {data['nickname']} aggiunto con successo"})
    else:
        return jsonify({"error": "Impossibile aggiungere l'utente. Verifica le credenziali."}), 500

@app.route('/api/users/<nickname>', methods=['DELETE'])
@require_api_token
def delete_user(nickname):
    phone_numbers = load_json("phone_numbers.json")
    
    if nickname not in phone_numbers:
        return jsonify({"error": f"Utente '{nickname}' non trovato"}), 404
    
    # Rimuove l'utente dal file
    del phone_numbers[nickname]
    save_json("phone_numbers.json", phone_numbers)
    
    # Rimuove il file di sessione se esiste
    session_file = f'session_{nickname}.session'
    if os.path.exists(session_file):
        try:
            os.remove(session_file)
        except Exception as e:
            log_error(f"Impossibile rimuovere il file di sessione: {e}")
    
    return jsonify({"status": "success", "message": f"Utente '{nickname}' rimosso con successo"})

# API per la gestione dei gruppi
@app.route('/api/groups', methods=['GET'])
@require_api_token
def get_groups():
    # Crea una nuova istanza per questa operazione
    instance_id = get_instance_id()
    
    # Esegui in modo sincrono la funzione asincrona
    async def get_groups_async():
        return await get_all_user_groups(instance_id)
    
    loop = asyncio.new_event_loop()
    try:
        success = loop.run_until_complete(get_groups_async())
        
        if success:
            user_groups = load_json("user_groups.json")
            groups = format_groups_for_api(user_groups)
            return jsonify({"groups": groups})
        else:
            return jsonify({"error": "Impossibile recuperare i gruppi"}), 500
    except Exception as e:
        log_error(f"Errore durante il recupero dei gruppi: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        loop.close()
        # Pulizia dei file di sessione
        cleanup_session_files(instance_id)

@app.route('/api/groups/<int:group_id>/link', methods=['GET'])
@require_api_token
def get_group_link_api(group_id):
    # Crea una nuova istanza per questa operazione
    instance_id = get_instance_id()
    
    # Esegui in modo sincrono la funzione asincrona
    async def get_link_async():
        return await get_group_link(group_id, instance_id)
    
    loop = asyncio.new_event_loop()
    try:
        link = loop.run_until_complete(get_link_async())
        
        if link:
            return jsonify({"group_id": group_id, "link": link})
        else:
            return jsonify({"error": "Impossibile recuperare il link del gruppo"}), 404
    except Exception as e:
        log_error(f"Errore durante il recupero del link del gruppo: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        loop.close()
        # Pulizia dei file di sessione
        cleanup_session_files(instance_id)

# API per il download degli archivi
@app.route('/api/archives', methods=['POST'])
@require_api_token
def start_archive_download():
    data = request.json
    
    if not data or 'group_id' not in data or 'user' not in data:
        return jsonify({"error": "Dati mancanti. Richiesti 'group_id' e 'user'"}), 400
    
    # Prepara i dati del gruppo
    user_groups = load_json("user_groups.json")
    if data['user'] not in user_groups:
        return jsonify({"error": f"Utente '{data['user']}' non trovato nei gruppi disponibili"}), 404
    
    # Trova il gruppo specifico
    selected_group = None
    for group in user_groups[data['user']]:
        if str(group['id']) == str(data['group_id']):
            # Crea un oggetto nel formato atteso dalla funzione
            selected_group = {
                "user": data['user'],
                "group": group
            }
            break
    
    if not selected_group:
        return jsonify({"error": f"Gruppo con ID {data['group_id']} non trovato per l'utente {data['user']}"}), 404
    
    # Crea un ID per questa operazione
    operation_id = f"archive_{int(time.time())}"
    
    # Avvia il download in un thread separato
    download_thread = threading.Thread(
        target=run_archive_download,
        args=(selected_group, operation_id)
    )
    download_thread.daemon = True
    download_thread.start()
    
    return jsonify({
        "status": "started",
        "operation_id": operation_id,
        "message": f"Download archivio avviato per il gruppo {selected_group['group']['name']}"
    })

def run_archive_download(selected_group, operation_id):
    """Esegue il download dell'archivio in un thread separato e invia aggiornamenti via Socket.IO."""
    instance_id = get_instance_id()
    
    try:
        # Invia notifica di inizio
        socketio.emit('archive_status', {
            'operation_id': operation_id,
            'status': 'starting',
            'group_name': selected_group['group']['name'],
            'user': selected_group['user'],
            'time': time.strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # Configura un nuovo loop di eventi asyncio per questo thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Esegui il download
        socketio.emit('archive_status', {
            'operation_id': operation_id,
            'status': 'downloading',
            'time': time.strftime("%Y-%m-%d %H:%M:%S")
        })
        
        result = loop.run_until_complete(
            download_group_archive(selected_group, instance_id, operation_id)
        )
        
        # Invia notifica di completamento
        if result:
            socketio.emit('archive_status', {
                'operation_id': operation_id,
                'status': 'completed',
                'time': time.strftime("%Y-%m-%d %H:%M:%S")
            })
        else:
            socketio.emit('archive_status', {
                'operation_id': operation_id,
                'status': 'failed',
                'error': 'Download non riuscito',
                'time': time.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        # Chiudi il loop
        loop.close()
    except Exception as e:
        error_msg = str(e)
        log_error(f"Errore nel download archivio (Op {operation_id}): {error_msg}")
        
        # Invia notifica di errore
        socketio.emit('archive_status', {
            'operation_id': operation_id,
            'status': 'error',
            'error': error_msg,
            'time': time.strftime("%Y-%m-%d %H:%M:%S")
        })
    finally:
        # Pulizia dei file di sessione
        cleanup_session_files(instance_id)

# API per il monitoraggio
@app.route('/api/monitoring', methods=['POST'])
@require_api_token
def start_monitoring_api():
    # Crea un ID per questa istanza
    instance_id = get_instance_id()
    
    # Registra l'istanza
    if not register_instance(instance_id, LOCK_FILE):
        return jsonify({"error": "Impossibile registrare l'istanza"}), 500
    
    # Crea una sessione di monitoraggio
    monitoring_session = ApiMonitoringSession(instance_id)
    active_api_instances[instance_id] = monitoring_session
    
    # Avvia il monitoraggio
    monitoring_session.start()
    
    return jsonify({
        "status": "started",
        "instance_id": instance_id,
        "message": "Monitoraggio avviato"
    })

@app.route('/api/monitoring/<instance_id>', methods=['DELETE'])
@require_api_token
def stop_monitoring_api(instance_id):
    if instance_id not in active_api_instances:
        return jsonify({"error": f"Istanza {instance_id} non trovata"}), 404
    
    # Ferma il monitoraggio
    monitoring_session = active_api_instances[instance_id]
    monitoring_session.stop()
    
    # Rimuovi la sessione
    del active_api_instances[instance_id]
    
    return jsonify({
        "status": "stopped",
        "instance_id": instance_id,
        "message": "Monitoraggio fermato"
    })

@app.route('/api/monitoring', methods=['GET'])
@require_api_token
def get_monitoring_status():
    instances = []
    
    for instance_id, session in active_api_instances.items():
        instances.append({
            "instance_id": instance_id,
            "status": session.status,
            "start_time": session.start_time,
            "error": session.error
        })
    
    return jsonify({"instances": instances})

# API per i file di media
@app.route('/api/media', methods=['GET'])
@require_api_token
def get_media_files():
    # Opzionalmente filtra per utente, gruppo e tipo
    user = request.args.get('user')
    group = request.args.get('group')
    media_type = request.args.get('type')
    
    result = []
    
    # Funzione per scansionare ricorsivamente le directory
    def scan_directory(base_dir, current_path=None):
        if current_path:
            full_path = os.path.join(base_dir, current_path)
        else:
            full_path = base_dir
            current_path = ""
        
        items = []
        
        try:
            for item in os.listdir(full_path):
                item_path = os.path.join(full_path, item)
                rel_path = os.path.join(current_path, item) if current_path else item
                
                if os.path.isdir(item_path):
                    # È una directory, scansiona ricorsivamente
                    sub_items = scan_directory(base_dir, rel_path)
                    items.extend(sub_items)
                else:
                    # È un file, aggiungilo alla lista
                    items.append({
                        "name": item,
                        "path": rel_path,
                        "size": os.path.getsize(item_path),
                        "type": os.path.splitext(item)[1][1:] if os.path.splitext(item)[1] else ""
                    })
        except Exception as e:
            log_error(f"Errore durante la scansione della directory {full_path}: {e}")
        
        return items
    
    # Base path per la ricerca dei media
    base_path = DOWNLOADS_DIR
    
    # Costruisci il percorso in base ai filtri
    if user:
        base_path = os.path.join(base_path, user)
        if group:
            base_path = os.path.join(base_path, group)
            if media_type:
                base_path = os.path.join(base_path, media_type)
    
    # Verifica che la directory esista
    if os.path.exists(base_path) and os.path.isdir(base_path):
        result = scan_directory(base_path)
    
    return jsonify({"files": result})

@app.route('/api/media/<path:file_path>', methods=['GET'])
@require_api_token
def get_media_file(file_path):
    # Assicurati che il percorso non contenga ".." per evitare accessi non autorizzati
    if '..' in file_path:
        return jsonify({"error": "Percorso non valido"}), 400
    
    # Percorso completo al file
    full_path = os.path.join(DOWNLOADS_DIR, file_path)
    
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        return jsonify({"error": "File non trovato"}), 404
    
    # Ottieni la directory e il nome del file
    directory = os.path.dirname(full_path)
    filename = os.path.basename(full_path)
    
    # Invia il file al client
    return send_from_directory(directory, filename)

# Eventi Socket.IO
@socketio.on('connect')
def handle_connect():
    emit('connected', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    pass

# Avvio del server
def run_api_server(host='0.0.0.0', port=5000, debug=False):
    load_api_tokens()

    # Stampa tutte le route disponibili
    # print("\nRoute disponibili:")
    # for rule in app.url_map.iter_rules():
    #     print(f"{rule} [{', '.join(rule.methods)}]")

    # Carica i token API
    
    
    # Avvia il server
    print(f"🚀 API Server in ascolto su {host}:{port}")
    socketio.run(app, host=host, port=port, debug=debug)

if __name__ == "__main__":
    # Se eseguito direttamente, avvia il server
    run_api_server()
