"""
Configurazione ottimizzata per il server API Telegram Media Downloader
"""

import os
from dotenv import load_dotenv

# Caricamento delle variabili d'ambiente
load_dotenv()

# Credenziali Telegram
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')

# Configurazioni API
API_HOST = os.getenv('API_HOST', '0.0.0.0')
API_PORT = int(os.getenv('API_PORT', 5000))
API_DEBUG = os.getenv('API_DEBUG', 'False').lower() == 'true'
API_SECRET_KEY = os.getenv('API_SECRET_KEY', os.urandom(24).hex())

# Configurazioni di performance
API_THREAD_POOL_SIZE = int(os.getenv('API_THREAD_POOL_SIZE', 10))
API_MAX_CONTENT_LENGTH = int(os.getenv('API_MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16 MB
API_RATE_LIMIT = os.getenv('API_RATE_LIMIT', '100 per minute')
API_TIMEOUT = int(os.getenv('API_TIMEOUT', 120))  # Timeout in secondi

# Directory
DOWNLOADS_DIR = "downloads"
TEMP_DIR = "private"
ARCHIVE_DIR = "archive"
STATIC_DIR = "static"
CACHE_DIR = "cache"  # Directory per la cache

# File di configurazione
USER_GROUPS_FILE = "user_groups.json"
PHONE_NUMBERS_FILE = "phone_numbers.json"
LOCK_FILE = "running_instances.lock"
API_TOKENS_FILE = "api_tokens.json"

# Configurazione Socket.IO
SOCKETIO_ASYNC_MODE = os.getenv('SOCKETIO_ASYNC_MODE', 'threading')
SOCKETIO_CORS_ALLOWED_ORIGINS = os.getenv('SOCKETIO_CORS_ALLOWED_ORIGINS', '*')
SOCKETIO_PING_TIMEOUT = int(os.getenv('SOCKETIO_PING_TIMEOUT', 60))
SOCKETIO_PING_INTERVAL = int(os.getenv('SOCKETIO_PING_INTERVAL', 25))

# Impostazioni cache
CACHE_TYPE = os.getenv('CACHE_TYPE', 'SimpleCache')
CACHE_DEFAULT_TIMEOUT = int(os.getenv('CACHE_DEFAULT_TIMEOUT', 300))  # 5 minuti

# Timeout per operazioni di download
DOWNLOAD_TIMEOUT = int(os.getenv('DOWNLOAD_TIMEOUT', 3600))  # 1 ora

# Creazione delle directory se non esistono
for directory in [DOWNLOADS_DIR, TEMP_DIR, ARCHIVE_DIR, STATIC_DIR, CACHE_DIR]:
    os.makedirs(directory, exist_ok=True)