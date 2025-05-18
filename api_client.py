"""
Modulo client API per il frontend

Fornisce funzioni client per comunicare con il backend API di Telegram Media Downloader
"""

import requests
import json
import os
import time

class TelegramDownloaderClient:
    """
    Client API per interagire con il backend Telegram Media Downloader
    """
    
    def __init__(self, base_url='http://localhost:5000/api', api_token=None):
        """
        Inizializza il client API
        
        Args:
            base_url: URL base del server API
            api_token: Token di autenticazione API
        """
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.timeout = 30  # timeout in secondi
    
    def set_token(self, token):
        """Imposta il token API"""
        self.api_token = token
    
    def _get_headers(self):
        """Ottiene gli header per le richieste API"""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        if self.api_token:
            headers['Authorization'] = f'Bearer {self.api_token}'
        
        return headers
    
    def _request(self, method, endpoint, data=None, params=None, files=None):
        """
        Esegue una richiesta generica all'API
        
        Args:
            method: Metodo HTTP (GET, POST, PUT, DELETE)
            endpoint: Endpoint API (senza barra iniziale)
            data: Dati JSON per il corpo della richiesta
            params: Parametri query string
            files: File da caricare
            
        Returns:
            response: Risposta JSON dell'API
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._get_headers()
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
            elif method == 'POST':
                if files:
                    # Per upload file, non inviare JSON
                    headers.pop('Content-Type', None)
                    response = requests.post(url, headers=headers, data=data, files=files, timeout=self.timeout)
                else:
                    response = requests.post(url, headers=headers, json=data, params=params, timeout=self.timeout)
            elif method == 'PUT':
                response = requests.put(url, headers=headers, json=data, params=params, timeout=self.timeout)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, json=data, params=params, timeout=self.timeout)
            else:
                raise ValueError(f"Metodo HTTP non supportato: {method}")
            
            # Controlla errori HTTP
            response.raise_for_status()
            
            # Restituisci JSON se disponibile
            if response.content:
                return response.json()
            return {}
            
        except requests.exceptions.RequestException as e:
            # Gestisci gli errori di rete o API
            error_msg = str(e)
            
            # Prova ad estrarre il messaggio di errore dal corpo risposta
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    if 'error' in error_data:
                        error_msg = error_data['error']
                except:
                    pass
            
            raise Exception(f"Errore API: {error_msg}")
    
    # Metodi per la gestione degli utenti
    
    def get_users(self):
        """Ottiene la lista degli utenti configurati"""
        return self._request('GET', 'users')
    
    def add_user(self, nickname, phone):
        """Aggiunge un nuovo utente"""
        data = {
            'nickname': nickname,
            'phone': phone
        }
        return self._request('POST', 'users', data=data)
    
    def delete_user(self, nickname):
        """Rimuove un utente"""
        return self._request('DELETE', f'users/{nickname}')
    
    # Metodi per la gestione dei gruppi
    
    def get_groups(self):
        """Ottiene la lista dei gruppi disponibili"""
        return self._request('GET', 'groups')
    
    def get_group_link(self, group_id):
        """Ottiene il link di invito ad un gruppo"""
        return self._request('GET', f'groups/{group_id}/link')
    
    # Metodi per gli archivi
    
    def download_archive(self, group_id, user):
        """Avvia il download dell'archivio di un gruppo"""
        data = {
            'group_id': group_id,
            'user': user
        }
        return self._request('POST', 'archives', data=data)
    
    # Metodi per il monitoraggio
    
    def start_monitoring(self):
        """Avvia il monitoraggio dei gruppi"""
        return self._request('POST', 'monitoring')
    
    def stop_monitoring(self, instance_id):
        """Ferma un'istanza di monitoraggio"""
        return self._request('DELETE', f'monitoring/{instance_id}')
    
    def get_monitoring_status(self):
        """Ottiene lo stato delle istanze di monitoraggio attive"""
        return self._request('GET', 'monitoring')
    
    # Metodi per i file media
    
    def get_media_files(self, user=None, group=None, media_type=None):
        """
        Ottiene la lista dei file media
        
        Args:
            user: Filtra per utente
            group: Filtra per gruppo
            media_type: Filtra per tipo di media (images, videos, etc.)
        """
        params = {}
        if user:
            params['user'] = user
        if group:
            params['group'] = group
        if media_type:
            params['type'] = media_type
            
        return self._request('GET', 'media', params=params)
    
    def download_media_file(self, file_path, output_path=None):
        """
        Scarica un file media specifico
        
        Args:
            file_path: Percorso relativo del file
            output_path: Percorso locale dove salvare il file
            
        Returns:
            local_path: Percorso locale del file scaricato
        """
        url = f"{self.base_url}/media/{file_path}"
        headers = self._get_headers()
        
        try:
            # Ottieni il nome del file dalla path
            filename = os.path.basename(file_path)
            
            if not output_path:
                # Se non è specificato un percorso, usa la directory corrente
                output_path = os.path.join(os.getcwd(), filename)
            elif os.path.isdir(output_path):
                # Se è una directory, aggiungi il nome del file
                output_path = os.path.join(output_path, filename)
            
            # Effettua la richiesta con streaming per gestire file grandi
            with requests.get(url, headers=headers, stream=True, timeout=self.timeout) as response:
                response.raise_for_status()
                
                # Apri il file in modalità binaria e scrivi il contenuto
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            return output_path
            
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    if 'error' in error_data:
                        error_msg = error_data['error']
                except:
                    pass
            
            raise Exception(f"Errore nel download del file: {error_msg}")
    
    # Metodi per la gestione del server
    
    def get_server_status(self):
        """Ottiene lo stato del server API"""
        return self._request('GET', 'status')
    
    # Metodi per la gestione dei token
    
    def check_token_validity(self):
        """
        Verifica se il token API è valido
        
        Returns:
            bool: True se il token è valido
        """
        try:
            # Prova una richiesta semplice che richiede autenticazione
            self.get_server_status()
            return True
        except Exception:
            return False

# Esempio di utilizzo del client
if __name__ == "__main__":
    # Inizializza il client
    client = TelegramDownloaderClient(
        base_url="http://localhost:5000/api",
        api_token="your_api_token_here"
    )
    
    try:
        # Verifica lo stato del server
        status = client.get_server_status()
        print(f"Stato server: {status}")
        
        # Ottieni la lista degli utenti
        users = client.get_users()
        print(f"Utenti: {users}")
        
    except Exception as e:
        print(f"Errore: {e}")
