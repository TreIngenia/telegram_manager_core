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

# Inizializzazione Flask e Socket.IO
app = Flask(__name__, 
            static_folder='static',  # Directory dei file statici
            static_url_path='/static')  # URL path per accedere ai file statici

# Configurazione per servire i file statici
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

# Abilita CORS per consentire richieste da domini diversi
CORS(app)

# Configura una chiave segreta per l'app
app.config['SECRET_KEY'] = secrets.token_hex(16)

# Inizializza Socket.IO
socketio = SocketIO(app, cors_allowed_origins="*")

# Classe per gestire eventi SocketIO
class SocketIOManager:
    def __init__(self, socketio_instance):
        self.socketio = socketio_instance
    
    def broadcast_event(self, event_name, data):
        try:
            self.socketio.emit(event_name, data)
            return True
        except Exception as e:
            print(f"Errore durante il broadcast dell'evento {event_name}: {e}")
            return False

# Gestore SocketIO globale
socketio_manager = None

# Funzione per ottenere il gestore WebSocket
def get_websocket_manager():
    global socketio_manager
    if socketio_manager is None:
        socketio_manager = SocketIOManager(socketio)
    return socketio_manager

# class SocketIOManager:
#     @staticmethod
#     def broadcast_event(event_name, data):
#         socketio.emit(event_name, data)

# # Funzione per ottenere il gestore WebSocket
# def get_websocket_manager():
#     return SocketIOManager()


# Eventi Socket.IO
@socketio.on('connect')
def handle_connect():
    emit('connected', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    pass

# Avvio del server
def run_api_server(host='0.0.0.0', port=5000, debug=False):
    global socketio_manager
    
    # Inizializza il gestore SocketIO
    socketio_manager = SocketIOManager(socketio)
    
    # Inizializza il sistema di sicurezza API
    try:
        from api_security import initialize_api_security
        admin_token = initialize_api_security()
        if admin_token:
            print(f"\n⚠️ TOKEN ADMIN GENERATO: {admin_token}")
            print("Salvare questo token in un luogo sicuro, non verrà mostrato di nuovo!")
    except Exception as e:
        print(f"⚠️ Errore durante l'inizializzazione del sistema di sicurezza API: {e}")
    
    try:
        # Implementa gli handler di base per SocketIO
        @socketio.on('connect')
        def handle_connect():
            from flask import request
            print(f"WebSocket: Client connesso (SID: {request.sid})")
            socketio.emit('connected', {'status': 'connected'}, room=request.sid)
        
        @socketio.on('disconnect')
        def handle_disconnect():
            from flask import request
            print(f"WebSocket: Client disconnesso (SID: {request.sid})")
        
        @socketio.on('client_ping')
        def handle_ping(data):
            from flask import request
            socketio.emit('server_pong', {'server_time': time.time()}, room=request.sid)
        
        # Importa e registra il blueprint delle rotte API
        from api_routes import register_api_routes
        success = register_api_routes(app)
        if not success:
            print("⚠️ Errore durante la registrazione delle route API")
    except Exception as e:
        print(f"⚠️ Errore durante l'inizializzazione del server: {e}")
    
    # Stampa tutte le route disponibili
    # print("\nRoute disponibili:")
    # for rule in app.url_map.iter_rules():
    #     print(f"{rule} [{', '.join(rule.methods)}]")
    
    # Avvia il server
    print(f"🚀 API Server in ascolto su {host}:{port}")
    socketio.run(app, host=host, port=port, debug=debug)

# def run_api_server(host='0.0.0.0', port=5000, debug=False):
#     # Inizializza il sistema di sicurezza API
#     from api_security import initialize_api_security
#     admin_token = initialize_api_security()
#     if admin_token:
#         print(f"\n⚠️ TOKEN ADMIN GENERATO: {admin_token}")
#         print("Salvare questo token in un luogo sicuro, non verrà mostrato di nuovo!")
    
#     # Importa e registra il blueprint delle rotte API
#     from api_routes import register_api_routes
#     register_api_routes(app)
    
#     # Inizializza il gestore WebSocket
#     from websocket_manager import initialize_websocket_manager
#     initialize_websocket_manager(socketio)
    
#     # Stampa tutte le route disponibili
#     print("\nRoute disponibili:")
#     for rule in app.url_map.iter_rules():
#         print(f"{rule} [{', '.join(rule.methods)}]")
    
#     # Avvia il server
#     print(f"🚀 API Server in ascolto su {host}:{port}")
#     socketio.run(app, host=host, port=port, debug=debug)

if __name__ == "__main__":
    # Se eseguito direttamente, avvia il server
    run_api_server()