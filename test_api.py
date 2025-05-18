"""
Script di test completo per il backend API Telegram Media Downloader
"""

import requests
import json
import time
import os
import sys
from pprint import pprint

# Configurazione
API_BASE_URL = "http://127.0.0.1:5000/api"
API_TOKEN = "224b4a19cfca33f76e005b6aa9eb1f63ae59f87f3d7f65571bd6efa318c95191"  # Sostituisci con il tuo token API

# Headers per le richieste
headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

def print_separator(title=None):
    """Stampa un separatore con titolo opzionale"""
    print("\n" + "=" * 80)
    if title:
        print(f"  {title}")
        print("=" * 80)
    print()

def api_request(method, endpoint, data=None, params=None, print_response=True):
    """Esegue una richiesta API e gestisce gli errori"""
    url = f"{API_BASE_URL}/{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, params=params)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data, params=params)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, json=data, params=params)
        else:
            print(f"Metodo {method} non supportato")
            return None
        
        # Verifica il codice di stato
        if response.status_code >= 400:
            print(f"ERRORE {response.status_code}: {response.text}")
            return None
        
        # Converti la risposta in JSON
        json_response = response.json()
        
        # Stampa la risposta se richiesto
        if print_response:
            print("Risposta:")
            pprint(json_response)
        
        return json_response
    
    except Exception as e:
        print(f"ERRORE nella richiesta a {url}: {e}")
        return None

def test_server_status():
    """Test dello stato del server"""
    print_separator("TEST: Stato del Server")
    return api_request("GET", "status")

def test_users():
    """Test delle operazioni sugli utenti"""
    print_separator("TEST: Gestione Utenti")
    
    # Ottieni utenti
    print("Ottenendo la lista degli utenti...")
    users = api_request("GET", "users")
    
    # Aggiungi un utente di test (se non esiste già)
    test_user = "test_user"
    test_phone = "+1234567890"  # Usa un numero di telefono valido per i test
    
    existing_users = users.get("users", []) if users else []
    user_exists = any(user["nickname"] == test_user for user in existing_users)
    
    if not user_exists:
        print(f"\nAggiungendo l'utente di test {test_user}...")
        user_data = {
            "nickname": test_user,
            "phone": test_phone
        }
        add_result = api_request("POST", "users", data=user_data)
        
        # Verifica che l'utente sia stato aggiunto
        if add_result and add_result.get("status") == "success":
            print(f"Utente {test_user} aggiunto con successo")
        else:
            print(f"ERRORE: Impossibile aggiungere l'utente {test_user}")
    else:
        print(f"\nL'utente {test_user} esiste già")
    
    # Ottieni la lista aggiornata degli utenti
    print("\nOttenendo la lista aggiornata degli utenti...")
    updated_users = api_request("GET", "users")
    
    return updated_users

def test_groups():
    """Test delle operazioni sui gruppi"""
    print_separator("TEST: Gestione Gruppi")
    
    # Ottieni gruppi
    print("Ottenendo la lista dei gruppi...")
    groups = api_request("GET", "groups")
    
    # Se ci sono gruppi, testa l'ottenimento del link di un gruppo
    if groups and groups.get("groups"):
        first_group = groups["groups"][0]
        group_id = first_group["id"]
        
        print(f"\nOttenendo il link per il gruppo {group_id}...")
        link = api_request("GET", f"groups/{group_id}/link")
    
    return groups

def test_monitoring():
    """Test delle operazioni di monitoraggio"""
    print_separator("TEST: Monitoraggio")
    
    # Ottieni stato del monitoraggio
    print("Ottenendo lo stato del monitoraggio...")
    monitoring_status = api_request("GET", "monitoring")
    
    # Avvia un monitoraggio di test
    print("\nAvviando un monitoraggio di test...")
    start_result = api_request("POST", "monitoring")
    
    if start_result and start_result.get("instance_id"):
        instance_id = start_result["instance_id"]
        print(f"Monitoraggio avviato con ID: {instance_id}")
        
        # Attendi un po' e controlla lo stato
        print("\nAttendendo 5 secondi...")
        time.sleep(5)
        
        print("Ottenendo lo stato aggiornato del monitoraggio...")
        updated_status = api_request("GET", "monitoring")
        
        # Ferma il monitoraggio
        print(f"\nFermando il monitoraggio {instance_id}...")
        stop_result = api_request("DELETE", f"monitoring/{instance_id}")
    
    return start_result

def test_media():
    """Test delle operazioni sui media"""
    print_separator("TEST: Media")
    
    # Ottieni la lista dei media
    print("Ottenendo la lista dei media...")
    media = api_request("GET", "media")
    
    return media

def run_all_tests():
    """Esegue tutti i test in sequenza"""
    print_separator("INIZIO DEI TEST API")
    
    # Test dello stato del server
    server_status = test_server_status()
    if not server_status:
        print("ERRORE: Il server non risponde. Interrompo i test.")
        return False
    
    # Test degli utenti
    test_users()
    
    # Test dei gruppi
    test_groups()
    
    # Test del monitoraggio
    test_monitoring()
    
    # Test dei media
    test_media()
    
    print_separator("TEST COMPLETATI")
    return True

if __name__ == "__main__":
    # Verifica che il token sia impostato
    if API_TOKEN == "IL_TUO_TOKEN_QUI":
        print("ERRORE: Devi impostare il tuo token API nel file di test.")
        print("Modifica la variabile API_TOKEN all'inizio del file.")
        sys.exit(1)
    
    run_all_tests()