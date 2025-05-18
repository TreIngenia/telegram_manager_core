"""
CLI di avvio dell'API server per Telegram Media Downloader

Questo script avvia il server API per Telegram Media Downloader,
permettendo di controllare l'applicazione tramite REST API e WebSocket.
"""

import os
import sys
import argparse
import time
import threading
from api_server import run_api_server
from api_config import API_HOST, API_PORT, API_DEBUG
from utils import log_info, log_error

def parse_arguments():
    """Analizza gli argomenti della linea di comando."""
    parser = argparse.ArgumentParser(description="API Server per Telegram Media Downloader")
    
    parser.add_argument('--host', type=str, default=API_HOST,
                       help=f'Host su cui eseguire il server (default: {API_HOST})')
    
    parser.add_argument('--port', type=int, default=API_PORT,
                       help=f'Porta su cui eseguire il server (default: {API_PORT})')
    
    parser.add_argument('--debug', action='store_true', default=API_DEBUG,
                       help='Avvia in modalità debug')
    
    return parser.parse_args()

def main():
    """Funzione principale per l'avvio del server API."""
    args = parse_arguments()
    
    try:
        print("\n🚀 Avvio API Server Telegram Media Downloader")
        print(f"📡 Indirizzo: {args.host}:{args.port}")
        print(f"🔍 Modalità Debug: {'Attiva' if args.debug else 'Disattiva'}")
        
        # Gestisci eventuali sessioni orfane
        from session_manager import session_manager
        orphaned_sessions = session_manager.handle_orphaned_sessions()
        if orphaned_sessions:
            print(f"⚠️ Rilevate {len(orphaned_sessions)} sessioni orfane in uso. Alcune funzionalità potrebbero essere limitate.")
        
        # Registro l'avvio nei log
        log_info(f"API Server avviato su {args.host}:{args.port}", "api_server.log")
        
        # Avvia il server API
        run_api_server(host=args.host, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        print("\n🛑 Server interrotto manualmente.")
        log_info("API Server interrotto manualmente", "api_server.log")
    except Exception as e:
        error_msg = f"Errore durante l'avvio dell'API Server: {e}"
        log_error(error_msg)
        print(f"\n❌ {error_msg}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())