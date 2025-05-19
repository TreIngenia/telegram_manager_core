"""
Flask blueprint per implementare le API REST

Questo modulo implementa le route API Flask per Telegram Media Downloader
utilizzando blueprints per organizzare meglio il codice.
"""

from flask import Blueprint, request, jsonify, current_app, send_from_directory
import os
import time
import asyncio
import threading

from api_security import require_api_token, require_admin_role
from utils import load_json, save_json, log_error, log_info, get_instance_id
from websocket_manager import get_websocket_manager
from config import DOWNLOADS_DIR

# Importazioni per le funzionalità del backend
from user_management import verify_and_add_user
from group_management import get_all_user_groups, get_group_link
from media_handler import download_group_archive
from event_handler import start_monitoring, cleanup_session_files

# Crea un blueprint per le API
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Dizionario per le operazioni attive
active_operations = {}

# Dizionario per tenere traccia delle autenticazioni in corso
pending_authentications = {}

def run_authentication(nickname, phone, auth_id):
    """Esegue l'autenticazione in un thread separato e invia aggiornamenti via WebSocket"""
    from telethon import TelegramClient, errors
    from config import API_ID, API_HASH, PHONE_NUMBERS_FILE
    
    # Ottieni il gestore WebSocket
    socketio_manager = get_websocket_manager()
    
    # Inizializza le informazioni di autenticazione
    pending_authentications[auth_id] = {
        'nickname': nickname,
        'phone': phone,
        'status': 'waiting_for_code',
        'code_received': False,
        'code': None,
        'error': None
    }
    
    try:
        # Crea un client Telegram
        client = TelegramClient(f'session_{nickname}', API_ID, API_HASH)
        
        # Invia l'aggiornamento di stato
        if socketio_manager:
            socketio_manager.broadcast_event('auth_status', {
                'auth_id': auth_id,
                'status': 'waiting_for_code',
                'nickname': nickname,
                'message': 'In attesa del codice di verifica'
            })
        
        # Crea un nuovo loop di eventi asyncio per questo thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Definisci la funzione per l'autenticazione asincrona
        async def async_auth_process():
            try:
                # Avvia il client con callback per il telefono
                await client.connect()
                
                # Se non siamo già autorizzati, richiedi il codice
                if not await client.is_user_authorized():
                    # Invia il codice di verifica
                    sent_code = await client.send_code_request(phone)
                    
                    # Aggiorna lo stato
                    if socketio_manager:
                        socketio_manager.broadcast_event('auth_status', {
                            'auth_id': auth_id,
                            'status': 'code_sent',
                            'nickname': nickname,
                            'phone_code_hash': sent_code.phone_code_hash,
                            'message': 'Codice di verifica inviato al telefono'
                        })
                    
                    pending_authentications[auth_id]['status'] = 'code_sent'
                    pending_authentications[auth_id]['phone_code_hash'] = sent_code.phone_code_hash
                    
                    # Attendiamo che il codice venga inserito tramite l'API
                    timeout = 300  # 5 minuti di timeout
                    start_time = time.time()
                    
                    while not pending_authentications[auth_id]['code_received']:
                        # Timeout
                        if time.time() - start_time > timeout:
                            if socketio_manager:
                                socketio_manager.broadcast_event('auth_status', {
                                    'auth_id': auth_id,
                                    'status': 'timeout',
                                    'message': 'Timeout durante l\'attesa del codice di verifica'
                                })
                            
                            pending_authentications[auth_id]['status'] = 'timeout'
                            return False
                        
                        await asyncio.sleep(1)
                    
                    # Ottieni il codice
                    code = pending_authentications[auth_id]['code']
                    
                    # Invia l'aggiornamento di stato
                    if socketio_manager:
                        socketio_manager.broadcast_event('auth_status', {
                            'auth_id': auth_id,
                            'status': 'verifying_code',
                            'message': 'Verifica del codice in corso'
                        })
                    
                    # Aggiorna lo stato
                    pending_authentications[auth_id]['status'] = 'verifying_code'
                    
                    # Log di debug
                    print(f"[DEBUG] Tentativo di sign_in per {nickname} con codice: {code}")
                    print(f"[DEBUG] phone_code_hash: {sent_code.phone_code_hash}")
                    
                    # Completa l'autenticazione con il codice
                    try:
                        # Qui è dove potrebbe verificarsi l'errore
                        await client.sign_in(phone, code, phone_code_hash=sent_code.phone_code_hash)
                        print(f"[DEBUG] sign_in completato con successo per {nickname}")
                        pending_authentications[auth_id]['status'] = 'authenticated'
                    except errors.SessionPasswordNeededError:
                        # Gestione autenticazione 2FA
                        if socketio_manager:
                            socketio_manager.broadcast_event('auth_status', {
                                'auth_id': auth_id,
                                'status': 'password_required',
                                'message': 'È richiesta la password di autenticazione a due fattori'
                            })
                        
                        pending_authentications[auth_id]['status'] = 'password_required'
                        return False
                else:
                    # Già autenticato
                    if socketio_manager:
                        socketio_manager.broadcast_event('auth_status', {
                            'auth_id': auth_id,
                            'status': 'already_authenticated',
                            'message': 'Utente già autenticato'
                        })
                    
                    pending_authentications[auth_id]['status'] = 'already_authenticated'
                
                return True
            finally:
                # Assicurati che il client sia disconnesso
                if client.is_connected():
                    await client.disconnect()
        
        # Esegui la funzione asincrona nel loop
        success = loop.run_until_complete(async_auth_process())
        
        # Chiudi il loop
        loop.close()
        
        print(f"Autenticazione completata per {nickname}")
        
        # Se autenticato con successo, salva l'utente
        if pending_authentications[auth_id]['status'] in ['authenticated', 'already_authenticated']:
            # Invia l'aggiornamento di stato
            if socketio_manager:
                socketio_manager.broadcast_event('auth_status', {
                    'auth_id': auth_id,
                    'status': pending_authentications[auth_id]['status'],
                    'message': 'Autenticazione completata con successo'
                })
            
            # Salva l'utente nel file degli utenti
            phone_numbers = load_json(PHONE_NUMBERS_FILE)
            phone_numbers[nickname] = phone
            save_json(PHONE_NUMBERS_FILE, phone_numbers)
        
    except Exception as e:
        error_msg = str(e)
        log_error(f"Errore durante l'autenticazione di {nickname}: {error_msg}")
        
        # Invia l'aggiornamento di stato
        if socketio_manager:
            socketio_manager.broadcast_event('auth_status', {
                'auth_id': auth_id,
                'status': 'error',
                'error': error_msg,
                'message': 'Errore durante l\'autenticazione'
            })
        
        # Aggiorna lo stato
        pending_authentications[auth_id]['status'] = 'error'
        pending_authentications[auth_id]['error'] = error_msg
    
    finally:
        # Rimuovi l'autenticazione dopo un po' di tempo
        def cleanup_auth():
            time.sleep(600)  # 10 minuti
            if auth_id in pending_authentications:
                del pending_authentications[auth_id]
        
        cleanup_thread = threading.Thread(target=cleanup_auth)
        cleanup_thread.daemon = True
        cleanup_thread.start()
        
# def run_authentication(nickname, phone, auth_id):
#     """Esegue l'autenticazione in un thread separato e invia aggiornamenti via WebSocket"""
#     from telethon import TelegramClient, errors
#     from config import API_ID, API_HASH, PHONE_NUMBERS_FILE
#     import nest_asyncio  # Se questa importazione fallisce, installa con: pip install nest_asyncio
    
#     # Ottieni il gestore WebSocket
#     socketio_manager = get_websocket_manager()
    
#     # Inizializza le informazioni di autenticazione
#     pending_authentications[auth_id] = {
#         'nickname': nickname,
#         'phone': phone,
#         'status': 'waiting_for_code',
#         'code_received': False,
#         'code': None,
#         'error': None
#     }
    
#     try:
#         # Invia l'aggiornamento di stato
#         if socketio_manager:
#             socketio_manager.broadcast_event('auth_status', {
#                 'auth_id': auth_id,
#                 'status': 'waiting_for_code',
#                 'nickname': nickname,
#                 'message': 'In attesa del codice di verifica'
#             })
        
#         # Crea un nuovo loop di eventi
#         loop = asyncio.new_event_loop()
        
#         # Importante: imposta il loop come loop corrente per questo thread
#         asyncio.set_event_loop(loop)
        
#         # Patch del loop per supportare operazioni nidificate
#         nest_asyncio.apply(loop)
        
#         # Ora esegui le operazioni di autenticazione
#         client = TelegramClient(f'session_{nickname}', API_ID, API_HASH)
        
#         # Connetti il client
#         loop.run_until_complete(client.connect())
        
#         # Verifica se l'utente è già autorizzato
#         is_authorized = loop.run_until_complete(client.is_user_authorized())
        
#         if not is_authorized:
#             # Invia il codice di verifica
#             sent_code = loop.run_until_complete(client.send_code_request(phone))
            
#             # Aggiorna lo stato
#             if socketio_manager:
#                 socketio_manager.broadcast_event('auth_status', {
#                     'auth_id': auth_id,
#                     'status': 'code_sent',
#                     'nickname': nickname,
#                     'phone_code_hash': sent_code.phone_code_hash,
#                     'message': 'Codice di verifica inviato al telefono'
#                 })
            
#             pending_authentications[auth_id]['status'] = 'code_sent'
#             pending_authentications[auth_id]['phone_code_hash'] = sent_code.phone_code_hash
            
#             # Attendiamo che il codice venga inserito tramite l'API
#             timeout = 300  # 5 minuti di timeout
#             start_time = time.time()
            
#             while not pending_authentications[auth_id]['code_received']:
#                 # Timeout
#                 if time.time() - start_time > timeout:
#                     if socketio_manager:
#                         socketio_manager.broadcast_event('auth_status', {
#                             'auth_id': auth_id,
#                             'status': 'timeout',
#                             'message': 'Timeout durante l\'attesa del codice di verifica'
#                         })
                    
#                     pending_authentications[auth_id]['status'] = 'timeout'
#                     if client.is_connected():
#                         loop.run_until_complete(client.disconnect())
#                     loop.close()
#                     return False
                
#                 # Breve attesa - usa sleep sincrono perché siamo in un thread separato
#                 time.sleep(1)
            
#             # Ottieni il codice
#             code = pending_authentications[auth_id]['code']
            
#             # Invia l'aggiornamento di stato
#             if socketio_manager:
#                 socketio_manager.broadcast_event('auth_status', {
#                     'auth_id': auth_id,
#                     'status': 'verifying_code',
#                     'message': 'Verifica del codice in corso'
#                 })
            
#             # Aggiorna lo stato
#             pending_authentications[auth_id]['status'] = 'verifying_code'
            
#             # Completa l'autenticazione con il codice
#             try:
#                 # Importante: Assicurati che client.sign_in ritorni un awaitable
#                 sign_in_coroutine = client.sign_in(phone, code, phone_code_hash=sent_code.phone_code_hash)
#                 # Usa run_until_complete su questa coroutine
#                 loop.run_until_complete(sign_in_coroutine)
                
#                 # Se arriviamo qui, l'autenticazione è avvenuta con successo
#                 pending_authentications[auth_id]['status'] = 'authenticated'
                
#                 # Invia notifica di successo
#                 if socketio_manager:
#                     socketio_manager.broadcast_event('auth_status', {
#                         'auth_id': auth_id,
#                         'status': 'authenticated',
#                         'message': 'Autenticazione completata con successo'
#                     })
                
#                 # Debug
#                 print(f"Autenticazione completata per {nickname}")
                
#             except errors.SessionPasswordNeededError:
#                 # Gestione autenticazione 2FA
#                 if socketio_manager:
#                     socketio_manager.broadcast_event('auth_status', {
#                         'auth_id': auth_id,
#                         'status': 'password_required',
#                         'message': 'È richiesta la password di autenticazione a due fattori'
#                     })
                
#                 pending_authentications[auth_id]['status'] = 'password_required'
#             # try:
#             #     loop.run_until_complete(client.sign_in(phone, code, phone_code_hash=sent_code.phone_code_hash))
#             #     pending_authentications[auth_id]['status'] = 'authenticated'
#             # except errors.SessionPasswordNeededError:
#             #     # Gestione autenticazione 2FA
#             #     if socketio_manager:
#             #         socketio_manager.broadcast_event('auth_status', {
#             #             'auth_id': auth_id,
#             #             'status': 'password_required',
#             #             'message': 'È richiesta la password di autenticazione a due fattori'
#             #         })
                
#             #     pending_authentications[auth_id]['status'] = 'password_required'
#             #     if client.is_connected():
#             #         loop.run_until_complete(client.disconnect())
#             #     loop.close()
#             #     return False
#         else:
#             # Già autenticato
#             if socketio_manager:
#                 socketio_manager.broadcast_event('auth_status', {
#                     'auth_id': auth_id,
#                     'status': 'already_authenticated',
#                     'message': 'Utente già autenticato'
#                 })
            
#             pending_authentications[auth_id]['status'] = 'already_authenticated'
        
#         # Disconnetti il client
#         if client.is_connected():
#             loop.run_until_complete(client.disconnect())
        
#         # Chiudi il loop
#         loop.close()
        
#         # Se autenticato con successo, salva l'utente
#         if pending_authentications[auth_id]['status'] in ['authenticated', 'already_authenticated']:
#             # Invia l'aggiornamento di stato
#             if socketio_manager:
#                 socketio_manager.broadcast_event('auth_status', {
#                     'auth_id': auth_id,
#                     'status': pending_authentications[auth_id]['status'],
#                     'message': 'Autenticazione completata con successo'
#                 })
            
#             # Salva l'utente nel file degli utenti
#             phone_numbers = load_json(PHONE_NUMBERS_FILE)
#             phone_numbers[nickname] = phone
#             save_json(PHONE_NUMBERS_FILE, phone_numbers)
        
#     except Exception as e:
#         error_msg = str(e)
#         log_error(f"Errore durante l'autenticazione di {nickname}: {error_msg}")
        
#         # Invia l'aggiornamento di stato
#         if socketio_manager:
#             socketio_manager.broadcast_event('auth_status', {
#                 'auth_id': auth_id,
#                 'status': 'error',
#                 'error': error_msg,
#                 'message': 'Errore durante l\'autenticazione'
#             })
        
#         # Aggiorna lo stato
#         pending_authentications[auth_id]['status'] = 'error'
#         pending_authentications[auth_id]['error'] = error_msg
    
#     finally:
#         # Rimuovi l'autenticazione dopo un po' di tempo
#         def cleanup_auth():
#             time.sleep(600)  # 10 minuti
#             if auth_id in pending_authentications:
#                 del pending_authentications[auth_id]
        
#         cleanup_thread = threading.Thread(target=cleanup_auth)
#         cleanup_thread.daemon = True
#         cleanup_thread.start()

@api_bp.route('/users/authenticate', methods=['POST'])
@require_api_token
def start_user_authentication():
    """Avvia il processo di autenticazione per un utente"""
    data = request.json
    
    if not data or 'nickname' not in data or 'phone' not in data:
        return jsonify({"error": "Dati mancanti. Richiesti 'nickname' e 'phone'"}), 400
    
    # Ottieni il gestore WebSocket qui
    socketio_manager = get_websocket_manager()
    
    # Verifica se esiste già una sessione per questo utente
    session_file = f'session_{data["nickname"]}.session'
    if os.path.exists(session_file):
        # Verifica se la sessione è valida
        try:
            from telethon import TelegramClient
            from config import API_ID, API_HASH
            
            async def check_session():
                client = TelegramClient(f'session_{data["nickname"]}', API_ID, API_HASH)
                await client.connect()
                is_authorized = await client.is_user_authorized()
                await client.disconnect()
                return is_authorized
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            is_authorized = loop.run_until_complete(check_session())
            loop.close()
            
            if is_authorized:
                # Invia una notifica WebSocket qui
                if socketio_manager:
                    socketio_manager.broadcast_event('auth_status', {
                        'status': 'already_authenticated',
                        'nickname': data['nickname'],
                        'message': f"L'utente {data['nickname']} è già autenticato"
                    })
                
                return jsonify({
                    "status": "already_authenticated",
                    "message": f"L'utente {data['nickname']} è già autenticato"
                })
        except Exception as e:
            log_error(f"Errore durante la verifica della sessione: {e}")
            # Se c'è un errore, procediamo con una nuova autenticazione
    
    # Crea un ID univoco per questa operazione di autenticazione
    auth_id = f"auth_{int(time.time())}"
    
    # Invia una notifica WebSocket iniziale prima di avviare il thread
    if socketio_manager:
        socketio_manager.broadcast_event('auth_status', {
            'auth_id': auth_id,
            'status': 'starting',
            'nickname': data['nickname'],
            'message': f"Avvio processo di autenticazione per {data['nickname']}"
        })
        print(f"Inviato evento auth_status 'starting' per {data['nickname']}")
    
    # Avvia l'autenticazione in background
    auth_thread = threading.Thread(
        target=run_authentication,
        args=(data['nickname'], data['phone'], auth_id)
    )
    auth_thread.daemon = True
    auth_thread.start()
    
    return jsonify({
        "status": "pending",
        "auth_id": auth_id,
        "message": "Processo di autenticazione avviato. Monitorare gli eventi WebSocket per gli aggiornamenti."
    })

@api_bp.route('/users/authenticate/<auth_id>/code', methods=['POST'])
@require_api_token
def verify_authentication_code(auth_id):
    """Fornisce il codice di verifica per completare l'autenticazione"""
    data = request.json
    
    if not data or 'code' not in data:
        return jsonify({"error": "Codice di verifica mancante"}), 400
    
    # Verifica che l'auth_id esista
    if auth_id not in pending_authentications:
        return jsonify({"error": f"Processo di autenticazione {auth_id} non trovato"}), 404
    
    # Verifica lo stato dell'autenticazione
    auth_status = pending_authentications[auth_id]['status']
    if auth_status not in ['waiting_for_code', 'code_sent']:
        return jsonify({
            "error": f"Impossibile fornire il codice. Stato attuale: {auth_status}",
            "status": auth_status
        }), 400
    
    # Stampa di debug per monitorare il processo
    print(f"Ricevuto codice per auth_id {auth_id}, stato attuale: {auth_status}")
    
    # Salva il codice
    pending_authentications[auth_id]['code'] = data['code']
    pending_authentications[auth_id]['code_received'] = True
    
    # Ottieni il gestore WebSocket
    socketio_manager = get_websocket_manager()
    
    # Invia una notifica che il codice è stato ricevuto
    if socketio_manager:
        socketio_manager.broadcast_event('auth_status', {
            'auth_id': auth_id,
            'status': 'code_received',
            'message': 'Codice di verifica ricevuto e in elaborazione'
        })
    
    return jsonify({
        "status": "processing",
        "auth_id": auth_id,
        "message": "Codice di verifica ricevuto. Monitorare gli eventi WebSocket per gli aggiornamenti."
    })
# @api_bp.route('/users/authenticate/<auth_id>/code', methods=['POST'])
# @require_api_token
# def verify_authentication_code(auth_id):
#     """Fornisce il codice di verifica per completare l'autenticazione"""
#     data = request.json
    
#     if not data or 'code' not in data:
#         return jsonify({"error": "Codice di verifica mancante"}), 400
    
#     # Verifica che l'auth_id esista
#     if auth_id not in pending_authentications:
#         return jsonify({"error": f"Processo di autenticazione {auth_id} non trovato"}), 404
    
#     # Verifica lo stato dell'autenticazione
#     auth_status = pending_authentications[auth_id]['status']
#     if auth_status not in ['waiting_for_code', 'code_sent']:
#         return jsonify({
#             "error": f"Impossibile fornire il codice. Stato attuale: {auth_status}",
#             "status": auth_status
#         }), 400
    
#     # Salva il codice
#     pending_authentications[auth_id]['code'] = data['code']
#     pending_authentications[auth_id]['code_received'] = True
    
#     return jsonify({
#         "status": "processing",
#         "auth_id": auth_id,
#         "message": "Codice di verifica ricevuto. Monitorare gli eventi WebSocket per gli aggiornamenti."
#     })

@api_bp.route('/users/authenticate/<auth_id>/status', methods=['GET'])
@require_api_token
def get_authentication_status(auth_id):
    """Ottiene lo stato del processo di autenticazione"""
    # Verifica che l'auth_id esista
    if auth_id not in pending_authentications:
        return jsonify({"error": f"Processo di autenticazione {auth_id} non trovato"}), 404
    
    # Ottieni lo stato
    auth_data = pending_authentications[auth_id]
    
    return jsonify({
        "status": auth_data['status'],
        "auth_id": auth_id,
        "nickname": auth_data['nickname'],
        "phone": auth_data['phone'],
        "error": auth_data.get('error')
    })        

# Endpoint di test
@api_bp.route('/status', methods=['GET'])
def api_status():
    """Endpoint per verificare lo stato dell'API"""
    return jsonify({
        "status": "online",
        "version": "1.0.0",
        "time": time.strftime("%Y-%m-%d %H:%M:%S")
    })

# API per la gestione degli utenti
@api_bp.route('/users', methods=['GET'])
@require_api_token
def get_users():
    """Ottiene la lista degli utenti configurati"""
    from config import PHONE_NUMBERS_FILE
    
    # Carica i dati degli utenti
    phone_numbers = load_json(PHONE_NUMBERS_FILE)
    users_list = []
    
    for nickname, phone in phone_numbers.items():
        users_list.append({
            "nickname": nickname,
            "phone": phone
        })
    
    return jsonify({"users": users_list})

@api_bp.route('/users', methods=['POST'])
@require_api_token
def add_user():
    """Aggiunge un nuovo utente"""
    data = request.json
    
    if not data or 'nickname' not in data or 'phone' not in data:
        return jsonify({"error": "Dati mancanti. Richiesti 'nickname' e 'phone'"}), 400
    
    # Implementazione asincrona dell'aggiunta utente
    loop = asyncio.new_event_loop()
    try:
        success = loop.run_until_complete(verify_and_add_user(data['nickname'], data['phone']))
    except Exception as e:
        log_error(f"Errore durante l'aggiunta dell'utente: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        loop.close()
    
    if success:
        return jsonify({
            "status": "success", 
            "message": f"Utente {data['nickname']} aggiunto con successo"
        })
    else:
        return jsonify({
            "error": "Impossibile aggiungere l'utente. Verifica le credenziali."
        }), 500

@api_bp.route('/users/<nickname>', methods=['DELETE'])
@require_api_token
def delete_user(nickname):
    """Rimuove un utente"""
    from config import PHONE_NUMBERS_FILE
    
    # Carica i dati degli utenti
    phone_numbers = load_json(PHONE_NUMBERS_FILE)
    
    if nickname not in phone_numbers:
        return jsonify({"error": f"Utente '{nickname}' non trovato"}), 404
    
    # Rimuove l'utente dal file
    del phone_numbers[nickname]
    save_json(PHONE_NUMBERS_FILE, phone_numbers)
    
    # Rimuove il file di sessione se esiste
    session_file = f'session_{nickname}.session'
    if os.path.exists(session_file):
        try:
            os.remove(session_file)
        except Exception as e:
            log_error(f"Impossibile rimuovere il file di sessione: {e}")
    
    return jsonify({
        "status": "success", 
        "message": f"Utente '{nickname}' rimosso con successo"
    })

# API per la gestione dei gruppi
@api_bp.route('/groups', methods=['GET'])
@require_api_token
def get_groups():
    """Ottiene la lista dei gruppi disponibili"""
    from config import USER_GROUPS_FILE, LOCK_FILE
    
    # Crea una nuova istanza per questa operazione
    instance_id = get_instance_id()
    
    # Esegui in modo sincrono la funzione asincrona
    loop = asyncio.new_event_loop()
    try:
        success = loop.run_until_complete(get_all_user_groups(instance_id))
        
        if success:
            # Carica i dati dei gruppi
            user_groups = load_json(USER_GROUPS_FILE)
            
            # Formatta i dati per l'API
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
            
            return jsonify({"groups": formatted_groups})
        else:
            return jsonify({"error": "Impossibile recuperare i gruppi"}), 500
    except Exception as e:
        log_error(f"Errore durante il recupero dei gruppi: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        loop.close()
        # Pulizia dei file di sessione
        cleanup_session_files(instance_id)

@api_bp.route('/groups/<int:group_id>/link', methods=['GET'])
@require_api_token
def get_group_link_api(group_id):
    """Ottiene il link di invito ad un gruppo"""
    from config import LOCK_FILE
    
    # Crea una nuova istanza per questa operazione
    instance_id = get_instance_id()
    
    # Esegui in modo sincrono la funzione asincrona
    loop = asyncio.new_event_loop()
    try:
        link = loop.run_until_complete(get_group_link(group_id, instance_id))
        
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
@api_bp.route('/archives', methods=['POST'])
@require_api_token
def start_archive_download():
    """Avvia il download dell'archivio di un gruppo"""
    from config import USER_GROUPS_FILE
    
    data = request.json
    
    if not data or 'group_id' not in data or 'user' not in data:
        return jsonify({"error": "Dati mancanti. Richiesti 'group_id' e 'user'"}), 400
    
    # Carica i dati dei gruppi
    user_groups = load_json(USER_GROUPS_FILE)
    
    # Verifica che l'utente esista
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
        return jsonify({
            "error": f"Gruppo con ID {data['group_id']} non trovato per l'utente {data['user']}"
        }), 404
    
    # Crea un ID per questa operazione
    operation_id = f"archive_{int(time.time())}"
    
    # Avvia il download in un thread separato
    download_thread = threading.Thread(
        target=run_archive_download,
        args=(selected_group, operation_id)
    )
    download_thread.daemon = True
    download_thread.start()
    
    # Registra l'operazione attiva
    active_operations[operation_id] = {
        "type": "archive",
        "start_time": time.time(),
        "status": "started",
        "group": selected_group["group"]["name"],
        "user": selected_group["user"]
    }
    
    return jsonify({
        "status": "started",
        "operation_id": operation_id,
        "message": f"Download archivio avviato per il gruppo {selected_group['group']['name']}"
    })

def run_archive_download(selected_group, operation_id):
    """Esegue il download dell'archivio in un thread separato e invia aggiornamenti via Socket.IO"""
    from config import LOCK_FILE
    
    # Ottieni il gestore WebSocket
    socketio_manager = get_websocket_manager()
    
    # Crea una nuova istanza per questa operazione
    instance_id = get_instance_id()
    
    try:
        # Invia notifica di inizio
        if socketio_manager:
            socketio_manager.broadcast_event('archive_status', {
                'operation_id': operation_id,
                'status': 'starting',
                'group_name': selected_group['group']['name'],
                'user': selected_group['user'],
                'time': time.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        # Aggiorna lo stato dell'operazione
        active_operations[operation_id]["status"] = "downloading"
        
        # Configura un nuovo loop di eventi asyncio per questo thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Invia notifica di download in corso
        if socketio_manager:
            socketio_manager.broadcast_event('archive_status', {
                'operation_id': operation_id,
                'status': 'downloading',
                'time': time.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        # Esegui il download
        result = loop.run_until_complete(
            download_group_archive(selected_group, instance_id, operation_id)
        )
        
        # Aggiorna lo stato finale dell'operazione
        if result:
            active_operations[operation_id]["status"] = "completed"
            active_operations[operation_id]["end_time"] = time.time()
            
            # Invia notifica di completamento
            if socketio_manager:
                socketio_manager.broadcast_event('archive_status', {
                    'operation_id': operation_id,
                    'status': 'completed',
                    'time': time.strftime("%Y-%m-%d %H:%M:%S")
                })
        else:
            active_operations[operation_id]["status"] = "failed"
            active_operations[operation_id]["end_time"] = time.time()
            
            # Invia notifica di errore
            if socketio_manager:
                socketio_manager.broadcast_event('archive_status', {
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
        
        # Aggiorna lo stato dell'operazione
        active_operations[operation_id]["status"] = "error"
        active_operations[operation_id]["error"] = error_msg
        active_operations[operation_id]["end_time"] = time.time()
        
        # Invia notifica di errore
        if socketio_manager:
            socketio_manager.broadcast_event('archive_status', {
                'operation_id': operation_id,
                'status': 'error',
                'error': error_msg,
                'time': time.strftime("%Y-%m-%d %H:%M:%S")
            })
    finally:
        # Pulizia dei file di sessione
        cleanup_session_files(instance_id)

# API per il monitoraggio
@api_bp.route('/monitoring', methods=['POST'])
@require_api_token
def start_monitoring_api():
    """Avvia il monitoraggio dei gruppi"""
    from config import LOCK_FILE
    
    # Crea un ID per questa istanza
    instance_id = get_instance_id()
    
    # Avvia il monitoraggio in un thread separato
    monitoring_thread = threading.Thread(
        target=run_monitoring,
        args=(instance_id,)
    )
    monitoring_thread.daemon = True
    monitoring_thread.start()
    
    # Registra l'operazione attiva
    active_operations[instance_id] = {
        "type": "monitoring",
        "start_time": time.time(),
        "status": "started"
    }
    
    return jsonify({
        "status": "started",
        "instance_id": instance_id,
        "message": "Monitoraggio avviato"
    })

def run_monitoring(instance_id):
    """Esegue il monitoraggio in un thread separato"""
    from config import LOCK_FILE
    
    # Ottieni il gestore WebSocket
    socketio_manager = get_websocket_manager()
    
    try:
        # Invia notifica di avvio
        if socketio_manager:
            socketio_manager.broadcast_event('monitoring_status', {
                'instance_id': instance_id,
                'status': 'starting',
                'time': time.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        # Configura un nuovo loop di eventi asyncio per questo thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Invia notifica di monitoraggio attivo
        if socketio_manager:
            socketio_manager.broadcast_event('monitoring_status', {
                'instance_id': instance_id,
                'status': 'active',
                'time': time.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        # Aggiorna lo stato dell'operazione
        active_operations[instance_id]["status"] = "active"
        
        # Esegui il monitoraggio
        loop.run_until_complete(start_monitoring(instance_id))
        
        # Aggiorna lo stato finale dell'operazione
        active_operations[instance_id]["status"] = "completed"
        active_operations[instance_id]["end_time"] = time.time()
        
        # Invia notifica di completamento
        if socketio_manager:
            socketio_manager.broadcast_event('monitoring_status', {
                'instance_id': instance_id,
                'status': 'completed',
                'time': time.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        # Chiudi il loop
        loop.close()
    except KeyboardInterrupt:
        # Aggiorna lo stato dell'operazione
        active_operations[instance_id]["status"] = "stopped"
        active_operations[instance_id]["end_time"] = time.time()
        
        # Invia notifica di interruzione
        if socketio_manager:
            socketio_manager.broadcast_event('monitoring_status', {
                'instance_id': instance_id,
                'status': 'stopped',
                'time': time.strftime("%Y-%m-%d %H:%M:%S")
            })
    except Exception as e:
        error_msg = str(e)
        log_error(f"Errore nel monitoraggio (Istanza {instance_id}): {error_msg}")
        
        # Aggiorna lo stato dell'operazione
        active_operations[instance_id]["status"] = "error"
        active_operations[instance_id]["error"] = error_msg
        active_operations[instance_id]["end_time"] = time.time()
        
        # Invia notifica di errore
        if socketio_manager:
            socketio_manager.broadcast_event('monitoring_error', {
                'instance_id': instance_id,
                'error': error_msg,
                'time': time.strftime("%Y-%m-%d %H:%M:%S")
            })
    finally:
        # Pulizia dei file di sessione
        cleanup_session_files(instance_id)

@api_bp.route('/monitoring/<instance_id>', methods=['DELETE'])
@require_api_token
def stop_monitoring_api(instance_id):
    """Ferma un'istanza di monitoraggio"""
    from config import LOCK_FILE
    from utils import unregister_instance, is_process_running
    
    # Verifica se l'istanza esiste
    if instance_id not in active_operations or active_operations[instance_id]["type"] != "monitoring":
        return jsonify({"error": f"Istanza di monitoraggio {instance_id} non trovata"}), 404
    
    # Verifica lo stato dell'istanza
    if active_operations[instance_id]["status"] not in ["active", "started"]:
        return jsonify({"error": f"L'istanza {instance_id} non è attiva"}), 400
    
    # Rimuovi l'istanza dal registro
    unregister_result = unregister_instance(instance_id, LOCK_FILE)
    
    # Aggiorna lo stato dell'operazione
    active_operations[instance_id]["status"] = "stopping"
    
    # Ottieni il gestore WebSocket
    socketio_manager = get_websocket_manager()
    
    # Invia notifica di interruzione
    if socketio_manager:
        socketio_manager.broadcast_event('monitoring_status', {
            'instance_id': instance_id,
            'status': 'stopping',
            'time': time.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    # Pulizia dei file di sessione
    cleanup_session_files(instance_id)
    
    return jsonify({
        "status": "stopping",
        "instance_id": instance_id,
        "message": "Monitoraggio in fase di arresto"
    })

@api_bp.route('/monitoring', methods=['GET'])
@require_api_token
def get_monitoring_status():
    """Ottiene lo stato delle istanze di monitoraggio attive"""
    monitoring_instances = {}
    
    # Filtra solo le istanze di monitoraggio
    for instance_id, data in active_operations.items():
        if data.get("type") == "monitoring":
            monitoring_instances[instance_id] = data
    
    return jsonify({"instances": monitoring_instances})

# API per i file media
@api_bp.route('/media', methods=['GET'])
@require_api_token
def get_media_files():
    """Ottiene la lista dei file media"""
    # Parametri opzionali per filtrare
    user = request.args.get('user')
    group = request.args.get('group')
    media_type = request.args.get('type')
    
    result = []
    
    # Funzione ricorsiva per scansionare le directory
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
                        "type": os.path.splitext(item)[1][1:] if os.path.splitext(item)[1] else "",
                        "last_modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(item_path)))
                    })
        except Exception as e:
            log_error(f"Errore durante la scansione della directory {full_path}: {e}")
        
        return items
    
    # Directory base per la ricerca dei media
    base_path = DOWNLOADS_DIR
    
    # Applica i filtri
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

@api_bp.route('/media/<path:file_path>', methods=['GET'])
@require_api_token
def get_media_file(file_path):
    """Ottiene un file media specifico"""
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

# API per le operazioni attive
@api_bp.route('/operations', methods=['GET'])
@require_api_token
def get_active_operations():
    """Ottiene la lista delle operazioni attive"""
    return jsonify({"operations": active_operations})

@api_bp.route('/operations/<operation_id>', methods=['GET'])
@require_api_token
def get_operation_status(operation_id):
    """Ottiene lo stato di un'operazione specifica"""
    if operation_id not in active_operations:
        return jsonify({"error": f"Operazione {operation_id} non trovata"}), 404
    
    return jsonify({"operation": active_operations[operation_id]})

# API per la gestione dei token
@api_bp.route('/tokens', methods=['POST'])
@require_api_token
@require_admin_role
def create_token():
    """Crea un nuovo token API"""
    from api_security import create_user_token
    
    data = request.json
    
    if not data or 'username' not in data:
        return jsonify({"error": "Dati mancanti. Richiesto 'username'"}), 400
    
    # Parametri opzionali
    role = data.get('role', 'user')
    expiration_days = data.get('expiration_days')
    
    # Crea il token
    token, token_data = create_user_token(data['username'], role, expiration_days)
    
    return jsonify({
        "status": "success",
        "username": data['username'],
        "token": token,
        "role": role,
        "expiration": token_data.get('expiration')
    })

@api_bp.route('/tokens/<username>', methods=['DELETE'])
@require_api_token
@require_admin_role
def revoke_token(username):
    """Revoca un token API"""
    from api_security import revoke_token as security_revoke_token
    
    # Verifica che non si stia tentando di revocare il proprio token
    if username == request.api_user:
        return jsonify({
            "error": "Non puoi revocare il tuo stesso token. Utilizza un altro account admin."
        }), 400
    
    # Revoca il token
    result = security_revoke_token(username)
    
    if result:
        return jsonify({
            "status": "success",
            "message": f"Token per l'utente {username} revocato con successo"
        })
    else:
        return jsonify({
            "error": f"Utente {username} non trovato o token già revocato"
        }), 404

# API per la gestione del server
@api_bp.route('/logs', methods=['GET'])
@require_api_token
@require_admin_role
def get_logs():
    """Ottiene i log del server"""
    # Parametri opzionali
    log_type = request.args.get('type', 'error')
    lines = request.args.get('lines', 100, type=int)
    
    # Mappa dei tipi di log
    log_files = {
        'error': os.path.join(DOWNLOADS_DIR, 'errors.txt'),
        'api': os.path.join(DOWNLOADS_DIR, 'api_server.log'),
        'websocket': os.path.join(DOWNLOADS_DIR, 'websocket.log'),
        'security': os.path.join(DOWNLOADS_DIR, 'api_security.log')
    }
    
    # Verifica che il tipo di log sia valido
    if log_type not in log_files:
        return jsonify({
            "error": f"Tipo di log non valido. Valori consentiti: {', '.join(log_files.keys())}"
        }), 400
    
    # Percorso al file di log
    log_file = log_files[log_type]
    
    # Verifica che il file esista
    if not os.path.exists(log_file):
        return jsonify({
            "error": f"File di log {log_type} non trovato"
        }), 404
    
    # Leggi le ultime N righe del file
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            # Leggi tutte le righe e prendi le ultime N
            all_lines = f.readlines()
            last_lines = all_lines[-lines:] if lines < len(all_lines) else all_lines
        
        return jsonify({
            "log_type": log_type,
            "lines": lines,
            "content": last_lines
        })
    except Exception as e:
        log_error(f"Errore durante la lettura del file di log {log_type}: {e}")
        return jsonify({
            "error": f"Errore durante la lettura del file di log: {str(e)}"
        }), 500

@api_bp.route('/debug/check-token', methods=['GET'])
def debug_check_token():
    """Endpoint per verificare il token API (solo per debug)"""
    from api_security import validate_token
    
    # Ottieni il token dall'header
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        token = request.headers.get('X-API-Token')
        if not token:
            return jsonify({
                "error": "Token mancante",
                "headers": dict(request.headers)
            }), 400
    else:
        token = auth_header.split('Bearer ')[1].strip()
    
    # Verifica il token
    is_valid, username, role = validate_token(token)
    
    return jsonify({
        "token_provided": token,
        "is_valid": is_valid,
        "username": username,
        "role": role,
        "headers": dict(request.headers)
    })

def register_api_routes(app):
    """Registra tutte le route API nell'app Flask"""
    try:
        # Prima di registrare il blueprint, stampa le sue route
        print("\nRoute nel blueprint prima della registrazione:")
        for func in api_bp.deferred_functions:
            print(f"  {func}")
        
        # Registra il blueprint
        app.register_blueprint(api_bp)
        
        # Stampa le route dopo la registrazione
        # print("\nRoute nell'app dopo la registrazione del blueprint:")
        # for rule in app.url_map.iter_rules():
        #     if rule.endpoint.startswith('api.'):
        #         print(f"  {rule}")
        
        # Log dell'inizializzazione
        try:
            # Prima verifica se log_info è disponibile
            from utils import log_info
            log_info("API Blueprint registrato con successo", "api_server.log")
        except (ImportError, NameError):
            # Versione di fallback se log_info non è disponibile
            try:
                import os
                import time
                from config import DOWNLOADS_DIR
                log_file = os.path.join(DOWNLOADS_DIR, "api_server.log")
                os.makedirs(os.path.dirname(log_file) if os.path.dirname(log_file) else '.', exist_ok=True)
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] API Blueprint registrato con successo\n")
                print(f"INFO: API Blueprint registrato con successo")
            except Exception as e:
                print(f"Impossibile scrivere nel file di log: {e}")
        
        return True
    
    except Exception as e:
        print(f"Errore durante la registrazione delle route API: {e}")
        return False

# # Funzione per registrare il blueprint nell'app Flask
# def register_api_routes(app):
#     """Registra tutte le route API nell'app Flask"""
#     app.register_blueprint(api_bp)
    
#     # Log dell'inizializzazione
#     log_info("API Blueprint registrato con successo", "api_server.log")
    
#     return True
