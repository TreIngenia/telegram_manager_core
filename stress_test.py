"""
Script per testare la robustezza del server API con richieste simultanee
"""

import requests
import threading
import time
import random

# Configurazione
API_BASE_URL = "http://127.0.0.1:5000/api"
API_TOKEN = "224b4a19cfca33f76e005b6aa9eb1f63ae59f87f3d7f65571bd6efa318c95191"  # Sostituisci con il tuo token API
NUM_THREADS = 5
NUM_REQUESTS_PER_THREAD = 20

# Headers per le richieste
headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# Endpoint da testare
endpoints = [
    "status",
    "users",
    "groups",
    "monitoring",
    "media"
]

# Statistiche globali
lock = threading.Lock()
total_requests = 0
successful_requests = 0
failed_requests = 0
response_times = []

def make_request(thread_id):
    """Funzione eseguita da ogni thread per fare richieste all'API"""
    global total_requests, successful_requests, failed_requests, response_times
    
    for i in range(NUM_REQUESTS_PER_THREAD):
        # Scegli un endpoint casuale
        endpoint = random.choice(endpoints)
        url = f"{API_BASE_URL}/{endpoint}"
        
        try:
            # Misura il tempo di risposta
            start_time = time.time()
            response = requests.get(url, headers=headers)
            end_time = time.time()
            
            # Calcola il tempo di risposta in millisecondi
            response_time = (end_time - start_time) * 1000
            
            # Aggiorna le statistiche
            with lock:
                total_requests += 1
                if response.status_code == 200:
                    successful_requests += 1
                else:
                    failed_requests += 1
                response_times.append(response_time)
            
            print(f"Thread {thread_id}, Richiesta {i+1}: {endpoint} - Stato: {response.status_code}, Tempo: {response_time:.2f}ms")
            
            # Breve pausa per evitare di sovraccaricare il server
            time.sleep(0.1)
            
        except Exception as e:
            with lock:
                total_requests += 1
                failed_requests += 1
            
            print(f"Thread {thread_id}, Richiesta {i+1}: {endpoint} - ERRORE: {e}")
            time.sleep(0.5)  # Pausa più lunga in caso di errore

def print_results():
    """Stampa i risultati del test"""
    print("\n" + "=" * 50)
    print("RISULTATI DEL TEST DI STRESS")
    print("=" * 50)
    
    print(f"Numero di thread: {NUM_THREADS}")
    print(f"Richieste per thread: {NUM_REQUESTS_PER_THREAD}")
    print(f"Totale richieste: {total_requests}")
    print(f"Richieste riuscite: {successful_requests}")
    print(f"Richieste fallite: {failed_requests}")
    
    if response_times:
        avg_time = sum(response_times) / len(response_times)
        min_time = min(response_times)
        max_time = max(response_times)
        
        print(f"Tempo medio di risposta: {avg_time:.2f}ms")
        print(f"Tempo minimo di risposta: {min_time:.2f}ms")
        print(f"Tempo massimo di risposta: {max_time:.2f}ms")
    
    success_rate = (successful_requests / total_requests) * 100 if total_requests > 0 else 0
    print(f"Tasso di successo: {success_rate:.2f}%")
    
    print("=" * 50)

def run_stress_test():
    """Esegue il test di stress con più thread"""
    print("Avvio del test di stress...")
    
    # Crea e avvia i thread
    threads = []
    for i in range(NUM_THREADS):
        thread = threading.Thread(target=make_request, args=(i+1,))
        threads.append(thread)
        thread.start()
    
    # Attendi il completamento di tutti i thread
    for thread in threads:
        thread.join()
    
    # Stampa i risultati
    print_results()

if __name__ == "__main__":
    if API_TOKEN == "IL_TUO_TOKEN_QUI":
        print("ERRORE: Devi impostare il tuo token API nel file di test.")
        exit(1)
    
    run_stress_test()