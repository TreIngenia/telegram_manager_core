"""
Configurazione dell'API per l'integrazione web di Telegram Media Downloader

Questo modulo estende il file di configurazione originale con impostazioni
aggiuntive per la gestione API e WebSocket.
"""

import os
from dotenv import load_dotenv

# Caricamento delle variabili d'ambiente
load_dotenv()

# Credenziali Telegram
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')

# Configurazioni API
API_HOST = os.getenv('API_HOST', '127.0.0.1')
API_PORT = int(os.getenv('API_PORT', 5000))
API_DEBUG = os.getenv('API_DEBUG', 'False').lower() == 'true'
API_SECRET_KEY = os.getenv('API_SECRET_KEY', '7dfb94af7de547e09e83ce29ec99aacd')

# Directory
DOWNLOADS_DIR = "downloads"
TEMP_DIR = "private"
ARCHIVE_DIR = "archive"  # Directory per gli archivi completi dei gruppi

# Directory per i file frontend statici
STATIC_DIR = "static"  

# File di configurazione
USER_GROUPS_FILE = "user_groups.json"
PHONE_NUMBERS_FILE = "phone_numbers.json"
LOCK_FILE = "running_instances.lock"  # File per gestire istanze multiple
API_TOKENS_FILE = "api_tokens.json"   # File per gestire i token API

# Impostazioni
VERBOSE = True
MAX_DOWNLOAD_RETRIES = 3
DOWNLOAD_RETRY_DELAY = 2  # secondi

# Configurazione Socket.IO
SOCKETIO_ASYNC_MODE = "threading"  # Modalità asincrona per Socket.IO (threading, eventlet, gevent)
SOCKETIO_CORS_ALLOWED_ORIGINS = "*"  # Origini CORS consentite per Socket.IO

# Creazione delle directory se non esistono
for directory in [DOWNLOADS_DIR, TEMP_DIR, ARCHIVE_DIR, STATIC_DIR]:
    os.makedirs(directory, exist_ok=True)
