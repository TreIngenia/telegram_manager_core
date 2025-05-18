"""
Classe di gestione delle sessioni WebSocket per il frontend

Questo modulo implementa una classe per gestire le sessioni Socket.IO,
facilitando la comunicazione in tempo reale tra backend e frontend.
"""

import os
import time
import asyncio
import threading
from flask_socketio import SocketIO
from utils import log_error, log_info

class WebSocketManager:
    """
    Gestore delle connessioni WebSocket per notifiche in tempo reale
    """
    
    def __init__(self, socketio_instance):
        """
        Inizializza il gestore WebSocket
        
        Args:
            socketio_instance: Istanza di Flask-SocketIO
        """
        self.socketio = socketio_instance
        self.connected_clients = {}
        self.active_sessions = {}
        self.lock = threading.RLock()
        
    def register_client(self, client_id, session_data=None):
        """
        Registra un nuovo client websocket
        
        Args:
            client_id: ID del client (sid del socket)
            session_data: Dati di sessione opzionali
        """
        with self.lock:
            self.connected_clients[client_id] = {
                'connected_at': time.time(),
                'last_activity': time.time(),
                'session_data': session_data or {}
            }
        
        # Log di connessione
        log_info(f"WebSocket: Nuovo client connesso (ID: {client_id})", "websocket.log")
        
        # Emetti evento di registrazione riuscita
        self.socketio.emit('registration_success', {
            'client_id': client_id, 
            'timestamp': time.time()
        }, room=client_id)
    
    def unregister_client(self, client_id):
        """
        Rimuove un client disconnesso
        
        Args:
            client_id: ID del client da rimuovere
        """
        with self.lock:
            if client_id in self.connected_clients:
                del self.connected_clients[client_id]
                log_info(f"WebSocket: Client disconnesso (ID: {client_id})", "websocket.log")
    
    def update_client_activity(self, client_id):
        """
        Aggiorna il timestamp dell'ultima attività di un client
        
        Args:
            client_id: ID del client
        """
        with self.lock:
            if client_id in self.connected_clients:
                self.connected_clients[client_id]['last_activity'] = time.time()
    
    def get_active_clients(self):
        """
        Restituisce la lista di tutti i client attivi
        
        Returns:
            Dictionary con client ID e metadati
        """
        with self.lock:
            return self.connected_clients.copy()
    
    def broadcast_event(self, event_name, data, exclude=None):
        """
        Invia un evento a tutti i client connessi
        
        Args:
            event_name: Nome dell'evento da inviare
            data: Dati dell'evento
            exclude: Lista di client ID da escludere
        """
        try:
            # Aggiungi timestamp all'evento
            if isinstance(data, dict):
                data['timestamp'] = time.time()
            
            if exclude:
                # Invia a tutti tranne i client specificati
                for client_id in self.connected_clients:
                    if client_id not in exclude:
                        self.socketio.emit(event_name, data, room=client_id)
            else:
                # Broadcast a tutti
                self.socketio.emit(event_name, data)
            
            return True
        except Exception as e:
            log_error(f"WebSocket: Errore durante il broadcast dell'evento {event_name}: {e}")
            return False
    
    def send_to_client(self, client_id, event_name, data):
        """
        Invia un evento a un client specifico
        
        Args:
            client_id: ID del client destinatario
            event_name: Nome dell'evento da inviare
            data: Dati dell'evento
        """
        try:
            with self.lock:
                if client_id not in self.connected_clients:
                    return False
            
            # Aggiungi timestamp all'evento
            if isinstance(data, dict):
                data['timestamp'] = time.time()
            
            self.socketio.emit(event_name, data, room=client_id)
            return True
        except Exception as e:
            log_error(f"WebSocket: Errore durante l'invio dell'evento {event_name} al client {client_id}: {e}")
            return False
    
    def start_monitoring_session(self, session_id, session_data=None):
        """
        Inizia una sessione di monitoraggio attiva
        
        Args:
            session_id: ID univoco della sessione di monitoraggio
            session_data: Metadati aggiuntivi sulla sessione
        """
        with self.lock:
            self.active_sessions[session_id] = {
                'type': 'monitoring',
                'start_time': time.time(),
                'status': 'active',
                'data': session_data or {}
            }
        
        # Notifica tutti i client della nuova sessione di monitoraggio
        self.broadcast_event('monitoring_started', {
            'session_id': session_id,
            'session_data': session_data
        })
        
        return True
    
    def end_monitoring_session(self, session_id, status='completed'):
        """
        Termina una sessione di monitoraggio attiva
        
        Args:
            session_id: ID della sessione di monitoraggio
            status: Stato finale della sessione (completed, error, stopped)
        """
        with self.lock:
            if session_id in self.active_sessions:
                session = self.active_sessions[session_id]
                session['status'] = status
                session['end_time'] = time.time()
                
                # Notifica tutti i client della fine del monitoraggio
                self.broadcast_event('monitoring_ended', {
                    'session_id': session_id,
                    'status': status,
                    'duration': session['end_time'] - session['start_time']
                })
                
                # Mantieni la sessione nel dizionario ma marcala come terminata
                return True
            
            return False
    
    def update_monitoring_status(self, session_id, status_update):
        """
        Aggiorna lo stato di una sessione di monitoraggio e notifica i client
        
        Args:
            session_id: ID della sessione
            status_update: Dizionario con aggiornamenti di stato
        """
        with self.lock:
            if session_id in self.active_sessions:
                # Aggiorna lo stato nella sessione
                for key, value in status_update.items():
                    if key not in ['start_time', 'type']:  # Non permettere modifiche a questi campi
                        self.active_sessions[session_id].setdefault('status_updates', []).append({
                            'timestamp': time.time(),
                            'update': {key: value}
                        })
                
                # Aggiungi session_id all'aggiornamento
                status_update['session_id'] = session_id
                
                # Notifica tutti i client dell'aggiornamento
                self.broadcast_event('monitoring_update', status_update)
                return True
        
        return False
    
    def get_active_sessions(self, session_type=None):
        """
        Ottiene tutte le sessioni attive, opzionalmente filtrate per tipo
        
        Args:
            session_type: Tipo di sessione da filtrare (es. 'monitoring')
            
        Returns:
            Dictionary con le sessioni attive
        """
        with self.lock:
            if session_type:
                return {sid: session for sid, session in self.active_sessions.items() 
                        if session['type'] == session_type}
            else:
                return self.active_sessions.copy()
    
    def setup_socketio_handlers(self):
        """
        Configura i gestori di eventi Socket.IO di base
        """
        @self.socketio.on('connect')
        def handle_connect():
            client_id = self.socketio.request.sid
            self.register_client(client_id)
            
            # Invia subito le sessioni attive al client appena connesso
            active_sessions = self.get_active_sessions()
            self.send_to_client(client_id, 'active_sessions', {
                'sessions': active_sessions
            })
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            client_id = self.socketio.request.sid
            self.unregister_client(client_id)
        
        @self.socketio.on('client_ping')
        def handle_ping(data):
            client_id = self.socketio.request.sid
            self.update_client_activity(client_id)
            # Rispondi con un pong
            self.send_to_client(client_id, 'server_pong', {
                'server_time': time.time(),
                'received_data': data
            })
        
        @self.socketio.on('request_active_sessions')
        def handle_request_active_sessions(data):
            client_id = self.socketio.request.sid
            session_type = data.get('type') if data else None
            active_sessions = self.get_active_sessions(session_type)
            
            self.send_to_client(client_id, 'active_sessions', {
                'sessions': active_sessions,
                'requested_type': session_type
            })
            
        @self.socketio.on('auth_status_request')
        def handle_auth_status_request(data):
            client_id = self.socketio.request.sid
            auth_id = data.get('auth_id')
            
            # Importa il dizionario delle autenticazioni in corso
            try:
                from api_routes import pending_authentications
                
                if auth_id in pending_authentications:
                    auth_status = pending_authentications[auth_id]
                    self.send_to_client(client_id, 'auth_status', {
                        'auth_id': auth_id,
                        'status': auth_status['status'],
                        'nickname': auth_status['nickname'],
                        'message': f"Stato autenticazione: {auth_status['status']}"
                    })
                else:
                    self.send_to_client(client_id, 'auth_status', {
                        'auth_id': auth_id,
                        'status': 'not_found',
                        'message': 'Processo di autenticazione non trovato'
                    })
            except ImportError:
                self.send_to_client(client_id, 'error', {
                    'message': 'Modulo api_routes non disponibile'
                })
            except Exception as e:
                self.send_to_client(client_id, 'error', {
                    'message': f'Errore: {str(e)}'
                })

# Crea un'istanza singola globale del WebSocketManager
# (da inizializzare con l'istanza di SocketIO nel modulo principale)
websocket_manager = None

def initialize_websocket_manager(socketio_instance):
    """
    Inizializza il gestore WebSocket globale
    
    Args:
        socketio_instance: Istanza di Flask-SocketIO
    """
    global websocket_manager
    
    if websocket_manager is None:
        websocket_manager = WebSocketManager(socketio_instance)
        websocket_manager.setup_socketio_handlers()
    
    return websocket_manager

def get_websocket_manager():
    """
    Ottiene l'istanza globale del gestore WebSocket
    
    Returns:
        Istanza del WebSocketManager
    """
    global websocket_manager
    return websocket_manager
