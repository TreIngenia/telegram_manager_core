"""
Modulo per la gestione delle sessioni client Telegram

Questo modulo fornisce funzionalità per gestire le sessioni Telethon
in modo centralizzato, evitando conflitti tra operazioni parallele.
"""

import os
import json
import shutil
import threading
import time
import random
from utils import log_error, log_info

class SessionManager:
    """
    Gestisce le sessioni Telegram per evitare conflitti
    
    Questa classe crea sessioni dedicate per ogni operazione,
    copiando i dati da una sessione principale quando disponibile.
    """
    
    def __init__(self):
        """Inizializza il gestore delle sessioni"""
        self.sessions = {}
        self.sessions_lock = threading.RLock()
    
    def create_session(self, nickname, operation_id=None):
        """
        Crea una nuova sessione dedicata per un'operazione
        
        Args:
            nickname: Nome utente per cui creare la sessione
            operation_id: ID operazione, se None usa una sessione standard
            
        Returns:
            (success, session_path): Flag di successo e percorso alla sessione
        """
        with self.sessions_lock:
            try:
                # Se non è specificato un operation_id, usa la sessione standard
                if not operation_id:
                    session_path = f'session_{nickname}'
                    return True, session_path
                
                # Genera un ID unico per la sessione
                session_id = f"{operation_id}_{int(time.time())}_{random.randint(1000, 9999)}"
                session_path = f'session_{nickname}_{session_id}'
                
                # Sessione originale
                original_session = f'session_{nickname}.session'
                
                # Se esiste la sessione originale, copiala per creare la sessione dedicata
                if os.path.exists(original_session):
                    try:
                        # Copia il file di sessione
                        shutil.copy2(original_session, f'{session_path}.session')
                        
                        # Copia anche eventuali file correlati
                        for ext in ['.session-journal']:
                            src = f'session_{nickname}{ext}'
                            if os.path.exists(src):
                                shutil.copy2(src, f'{session_path}{ext}')
                    except Exception as e:
                        log_error(f"Errore nella copia del file di sessione: {e}")
                
                # Registra la sessione
                self.sessions[session_path] = {
                    'nickname': nickname,
                    'operation_id': operation_id,
                    'created_at': time.time()
                }
                
                log_info(f"Sessione creata: {session_path}", "sessions.log")
                return True, session_path
                
            except Exception as e:
                log_error(f"Errore nella creazione della sessione per {nickname}: {e}")
                return False, None
    
    def release_session(self, operation_id, nickname=None):
        """
        Rilascia tutte le sessioni associate a un'operazione
        
        Args:
            operation_id: ID dell'operazione
            nickname: Se specificato, rilascia solo le sessioni di questo utente
            
        Returns:
            count: Numero di sessioni rilasciate
        """
        with self.sessions_lock:
            try:
                # Trova tutte le sessioni da rilasciare
                sessions_to_release = []
                
                for session_path, info in list(self.sessions.items()):
                    if info['operation_id'] == operation_id:
                        if nickname is None or info['nickname'] == nickname:
                            sessions_to_release.append(session_path)
                
                # Rilascia le sessioni
                count = 0
                for session_path in sessions_to_release:
                    self._cleanup_session_files(session_path)
                    if session_path in self.sessions:
                        del self.sessions[session_path]
                        count += 1
                
                if count > 0:
                    log_info(f"Rilasciate {count} sessioni per operazione {operation_id}", "sessions.log")
                
                return count
                
            except Exception as e:
                log_error(f"Errore nel rilascio delle sessioni per operazione {operation_id}: {e}")
                return 0
    
    def _cleanup_session_files(self, session_path):
        """
        Pulisce i file associati a una sessione in modo sicuro
        
        Args:
            session_path: Percorso base della sessione (senza estensione)
        """
        try:
            # Aggiungi un ritardo prima di tentare di eliminare il file
            time.sleep(1)
            
            # Ritenta diverse volte in caso di errore
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    # Rimuovi il file di sessione principale
                    if os.path.exists(f'{session_path}.session'):
                        os.remove(f'{session_path}.session')
                    
                    # Rimuovi eventuali file correlati
                    for ext in ['.session-journal']:
                        file_path = f'{session_path}{ext}'
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    
                    return  # Successo, esci dal ciclo
                except PermissionError as e:
                    if attempt < max_attempts - 1:
                        # Se il file è in uso, attendi e riprova
                        log_error(f"File di sessione in uso, attendo e riprovo ({attempt+1}/{max_attempts}): {e}")
                        time.sleep(2 * (attempt + 1))  # Attesa crescente
                    else:
                        # Registra l'errore ma non bloccare l'esecuzione
                        log_error(f"Impossibile eliminare il file di sessione dopo {max_attempts} tentativi: {e}")
        except Exception as e:
            log_error(f"Errore durante la pulizia dei file di sessione {session_path}: {e}")
            
    
    def cleanup_all(self):
        """
        Pulisce tutte le sessioni temporanee
        
        Returns:
            count: Numero di sessioni pulite
        """
        with self.sessions_lock:
            try:
                # Trova tutte le sessioni da pulire
                session_paths = list(self.sessions.keys())
                
                # Pulisci le sessioni
                count = 0
                for session_path in session_paths:
                    self._cleanup_session_files(session_path)
                    count += 1
                
                # Svuota il dizionario delle sessioni
                self.sessions.clear()
                
                if count > 0:
                    log_info(f"Pulite {count} sessioni", "sessions.log")
                
                # Pulizia aggiuntiva: cerca file di sessione orfani
                orphan_count = self._cleanup_orphan_sessions()
                
                return count + orphan_count
                
            except Exception as e:
                log_error(f"Errore durante la pulizia di tutte le sessioni: {e}")
                return 0
    
    def _cleanup_orphan_sessions(self):
        """
        Pulisce i file di sessione orfani (non registrati nel gestore)
        
        Returns:
            count: Numero di file di sessione orfani rimossi
        """
        try:
            count = 0
            
            # Cerca file di sessione che contengono underscore (sessioni temporanee)
            for file in os.listdir('.'):
                if (file.endswith('.session') and '_' in file) or file.endswith('.session-journal'):
                    session_path = file.replace('.session', '').replace('-journal', '')
                    
                    # Se non è registrato nel gestore, è un orfano
                    if session_path not in self.sessions:
                        try:
                            os.remove(file)
                            count += 1
                        except:
                            pass
            
            if count > 0:
                log_info(f"Rimossi {count} file di sessione orfani", "sessions.log")
            
            return count
            
        except Exception as e:
            log_error(f"Errore durante la pulizia dei file di sessione orfani: {e}")
            return 0
    
    def get_session_status(self):
        """
        Ottiene lo stato di tutte le sessioni
        
        Returns:
            sessions: Dictionary con lo stato delle sessioni
        """
        with self.sessions_lock:
            return self.sessions.copy()
        
    def handle_orphaned_sessions(self):
        """
        Gestisce le sessioni orfane rilevando i file .session lasciati da processi precedenti
        
        Returns:
            orphaned_sessions: Lista di sessioni orfane trovate
        """
        orphaned_sessions = []
        
        try:
            # Cerca file di sessione con pattern che indicano sessioni temporanee
            for file in os.listdir('.'):
                if file.endswith('.session') and '_' in file:
                    session_path = file.replace('.session', '')
                    
                    # Se non è registrato nel gestore, è una sessione orfana
                    if session_path not in self.sessions:
                        # Verifica se il file è utilizzato
                        try:
                            # Prova ad aprire il file in modalità scrittura esclusiva
                            with open(file, 'a+b') as f:
                                # Se siamo qui, il file non è bloccato
                                f.close()
                                
                                # Tenta di eliminare il file
                                try:
                                    os.remove(file)
                                    # Controlla anche il file journal
                                    journal_file = f"{file}-journal"
                                    if os.path.exists(journal_file):
                                        os.remove(journal_file)
                                    log_info(f"Sessione orfana rimossa: {file}", "sessions.log")
                                except Exception as e:
                                    log_error(f"Impossibile rimuovere la sessione orfana {file}: {e}")
                                    
                        except (IOError, PermissionError):
                            # File in uso
                            orphaned_sessions.append(session_path)
                            log_info(f"Sessione orfana in uso rilevata: {file}", "sessions.log")
            
            return orphaned_sessions
        except Exception as e:
            log_error(f"Errore durante la gestione delle sessioni orfane: {e}")
            return []

# Singleton globale del SessionManager
session_manager = SessionManager()
