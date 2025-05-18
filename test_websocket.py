"""
Script per testare le connessioni WebSocket con il server API
"""

import socketio
import time
import sys

# Configurazione
SOCKET_URL = "http://127.0.0.1:5000"

# Crea un client Socket.IO
sio = socketio.Client()

# Eventi ricevuti
events_received = []

@sio.event
def connect():
    print("Connessione stabilita con il server WebSocket")

@sio.event
def disconnect():
    print("Disconnesso dal server WebSocket")

@sio.event
def monitoring_status(data):
    print("\nRicevuto evento monitoring_status:")
    print(data)
    events_received.append({"type": "monitoring_status", "data": data, "time": time.time()})

@sio.event
def archive_status(data):
    print("\nRicevuto evento archive_status:")
    print(data)
    events_received.append({"type": "archive_status", "data": data, "time": time.time()})

@sio.event
def server_pong(data):
    print("\nRicevuto pong dal server:")
    print(data)

def run_websocket_test(duration=60):
    """
    Esegue un test delle connessioni WebSocket
    
    Args:
        duration: Durata del test in secondi
    """
    print(f"Avvio del test WebSocket. Durata: {duration} secondi")
    print("In attesa di eventi dal server. Premi Ctrl+C per interrompere.")
    
    try:
        # Connessione al server
        sio.connect(SOCKET_URL)
        
        # Invia un ping ogni 10 secondi
        start_time = time.time()
        while time.time() - start_time < duration:
            sio.emit("client_ping", {"timestamp": time.time()})
            print(".", end="", flush=True)
            time.sleep(10)
        
        # Disconnessione
        sio.disconnect()
        
        # Stampa le statistiche
        print("\n\nStatistiche del test:")
        print(f"Eventi ricevuti: {len(events_received)}")
        for event_type in set(e["type"] for e in events_received):
            count = sum(1 for e in events_received if e["type"] == event_type)
            print(f"  - {event_type}: {count}")
            
    except KeyboardInterrupt:
        print("\nTest interrotto dall'utente")
        sio.disconnect()
    except Exception as e:
        print(f"\nErrore durante il test: {e}")
    
    print("Test WebSocket completato")

if __name__ == "__main__":
    # Durata del test (default: 60 secondi)
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    
    run_websocket_test(duration)