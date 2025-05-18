"""
Sistema di logging migliorato per Telegram Media Downloader API
"""

import os
import time
import logging
from logging.handlers import RotatingFileHandler
import traceback
import threading

# Directory per i log
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Configurazione logger
class LoggerSetup:
    def __init__(self):
        self.loggers = {}
        self.lock = threading.RLock()
    
    def get_logger(self, name="api", log_file=None):
        """
        Ottiene un logger configurato
        
        Args:
            name: Nome del logger
            log_file: File di log (default: {name}.log)
            
        Returns:
            Logger configurato
        """
        with self.lock:
            if name in self.loggers:
                return self.loggers[name]
            
            # Crea un nuovo logger
            logger = logging.getLogger(name)
            logger.setLevel(logging.DEBUG)
            
            # Formattatore per i log
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                '%Y-%m-%d %H:%M:%S'
            )
            
            # Handler per la console
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(formatter)
            
            # Handler per il file
            if log_file is None:
                log_file = f"{name}.log"
            
            file_handler = RotatingFileHandler(
                os.path.join(LOG_DIR, log_file),
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            
            # Aggiungi gli handler al logger
            logger.addHandler(console_handler)
            logger.addHandler(file_handler)
            
            # Memorizza il logger
            self.loggers[name] = logger
            
            return logger
    
    def log_error(self, error, logger_name="error"):
        """
        Registra un errore nel file di log
        
        Args:
            error: Messaggio di errore o eccezione
            logger_name: Nome del logger da utilizzare
        """
        logger = self.get_logger(logger_name, f"{logger_name}.log")
        
        if isinstance(error, Exception):
            logger.error(f"Exception: {error}")
            logger.error(traceback.format_exc())
        else:
            logger.error(error)
    
    def log_info(self, message, logger_name="info"):
        """
        Registra un'informazione nel file di log
        
        Args:
            message: Messaggio da registrare
            logger_name: Nome del logger da utilizzare
        """
        logger = self.get_logger(logger_name, f"{logger_name}.log")
        logger.info(message)
    
    def log_api_request(self, request, response_code, response_time, logger_name="api_requests"):
        """
        Registra una richiesta API nel file di log
        
        Args:
            request: Oggetto richiesta Flask
            response_code: Codice di risposta HTTP
            response_time: Tempo di risposta in millisecondi
            logger_name: Nome del logger da utilizzare
        """
        logger = self.get_logger(logger_name, f"{logger_name}.log")
        
        # Formato: timestamp - ip - metodo - url - status - tempo(ms)
        logger.info(
            f"{request.remote_addr} - {request.method} {request.path} - {response_code} - {response_time:.2f}ms"
        )

# Istanza globale del logger
logger_setup = LoggerSetup()

# Funzioni di supporto per la retrocompatibilità
def log_error(message):
    """Wrapper retrocompatibile per log_error"""
    logger_setup.log_error(message)

def log_info(message, file_name="info.log"):
    """Wrapper retrocompatibile per log_info"""
    logger_name = os.path.splitext(os.path.basename(file_name))[0]
    logger_setup.log_info(message, logger_name)