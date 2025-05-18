"""
Script per generare la documentazione dell'API di Telegram Media Downloader
"""

import os
import json
import time

# Configurazione
API_BASE_URL = "http://127.0.0.1:5000/api"
DOCS_DIR = "api_docs"
os.makedirs(DOCS_DIR, exist_ok=True)

# Struttura della documentazione
api_docs = {
    "title": "Telegram Media Downloader API",
    "version": "1.0.0",
    "base_url": API_BASE_URL,
    "description": "API per la gestione di download e monitoraggio di media da Telegram",
    "auth": {
        "type": "Bearer Token",
        "header": "Authorization: Bearer YOUR_TOKEN"
    },
    "endpoints": [
        {
            "path": "/status",
            "method": "GET",
            "description": "Ottiene lo stato del server API",
            "auth_required": False,
            "params": [],
            "response": {
                "status": "online",
                "version": "1.0.0",
                "time": "YYYY-MM-DD HH:MM:SS"
            }
        },
        {
            "path": "/users",
            "method": "GET",
            "description": "Ottiene la lista degli utenti configurati",
            "auth_required": True,
            "params": [],
            "response": {
                "users": [
                    {
                        "nickname": "example_user",
                        "phone": "+1234567890"
                    }
                ]
            }
        },
        {
            "path": "/users",
            "method": "POST",
            "description": "Aggiunge un nuovo utente",
            "auth_required": True,
            "params": [
                {
                    "name": "nickname",
                    "type": "string",
                    "required": True,
                    "description": "Nome utente per l'account Telegram"
                },
                {
                    "name": "phone",
                    "type": "string",
                    "required": True,
                    "description": "Numero di telefono associato all'account Telegram"
                }
            ],
            "response": {
                "status": "success",
                "message": "Utente example_user aggiunto con successo"
            }
        },
        {
            "path": "/users/{nickname}",
            "method": "DELETE",
            "description": "Rimuove un utente",
            "auth_required": True,
            "params": [
                {
                    "name": "nickname",
                    "type": "string",
                    "required": True,
                    "description": "Nome utente da rimuovere",
                    "in": "path"
                }
            ],
            "response": {
                "status": "success",
                "message": "Utente 'example_user' rimosso con successo"
            }
        },
        {
            "path": "/groups",
            "method": "GET",
            "description": "Ottiene la lista dei gruppi disponibili",
            "auth_required": True,
            "params": [],
            "response": {
                "groups": [
                    {
                        "id": -1001234567890,
                        "name": "Example Group",
                        "username": "@example_group",
                        "members_count": 100,
                        "user": "example_user"
                    }
                ]
            }
        },
        {
            "path": "/groups/{group_id}/link",
            "method": "GET",
            "description": "Ottiene il link di invito ad un gruppo",
            "auth_required": True,
            "params": [
                {
                    "name": "group_id",
                    "type": "integer",
                    "required": True,
                    "description": "ID del gruppo",
                    "in": "path"
                }
            ],
            "response": {
                "group_id": -1001234567890,
                "link": "https://t.me/example_group"
            }
        },
        {
            "path": "/archives",
            "method": "POST",
            "description": "Avvia il download dell'archivio di un gruppo",
            "auth_required": True,
            "params": [
                {
                    "name": "group_id",
                    "type": "integer",
                    "required": True,
                    "description": "ID del gruppo"
                },
                {
                    "name": "user",
                    "type": "string",
                    "required": True,
                    "description": "Nome utente associato al gruppo"
                }
            ],
            "response": {
                "status": "started",
                "operation_id": "archive_1234567890",
                "message": "Download archivio avviato per il gruppo Example Group"
            }
        },
        {
            "path": "/monitoring",
            "method": "POST",
            "description": "Avvia il monitoraggio dei gruppi",
            "auth_required": True,
            "params": [],
            "response": {
                "status": "started",
                "instance_id": "1234567890-12345",
                "message": "Monitoraggio avviato"
            }
        },
        {
            "path": "/monitoring/{instance_id}",
            "method": "DELETE",
            "description": "Ferma un'istanza di monitoraggio",
            "auth_required": True,
            "params": [
                {
                    "name": "instance_id",
                    "type": "string",
                    "required": True,
                    "description": "ID dell'istanza di monitoraggio",
                    "in": "path"
                }
            ],
            "response": {
                "status": "stopping",
                "instance_id": "1234567890-12345",
                "message": "Monitoraggio in fase di arresto"
            }
        },
        {
            "path": "/monitoring",
            "method": "GET",
            "description": "Ottiene lo stato delle istanze di monitoraggio attive",
            "auth_required": True,
            "params": [],
            "response": {
                "instances": {
                    "1234567890-12345": {
                        "type": "monitoring",
                        "start_time": 1234567890,
                        "status": "active"
                    }
                }
            }
        },
        {
            "path": "/media",
            "method": "GET",
            "description": "Ottiene la lista dei file media",
            "auth_required": True,
            "params": [
                {
                    "name": "user",
                    "type": "string",
                    "required": False,
                    "description": "Filtra per utente"
                },
                {
                    "name": "group",
                    "type": "string",
                    "required": False,
                    "description": "Filtra per gruppo"
                },
                {
                    "name": "type",
                    "type": "string",
                    "required": False,
                    "description": "Filtra per tipo di media (images, videos, etc.)"
                }
            ],
            "response": {
                "files": [
                    {
                        "name": "example_image.jpg",
                        "path": "example_user/Example_Group/images/example_image.jpg",
                        "size": 12345,
                        "type": "jpg",
                        "last_modified": "YYYY-MM-DD HH:MM:SS"
                    }
                ]
            }
        },
        {
            "path": "/media/{file_path}",
            "method": "GET",
            "description": "Ottiene un file media specifico",
            "auth_required": True,
            "params": [
                {
                    "name": "file_path",
                    "type": "string",
                    "required": True,
                    "description": "Percorso relativo del file",
                    "in": "path"
                }
            ],
            "response": "File binario"
        }
    ],
    "websocket_events": [
        {
            "event": "monitoring_status",
            "description": "Aggiornamenti sullo stato del monitoraggio",
            "data": {
                "instance_id": "1234567890-12345",
                "status": "active",
                "time": "YYYY-MM-DD HH:MM:SS"
            }
        },
        {
            "event": "monitoring_error",
            "description": "Errori durante il monitoraggio",
            "data": {
                "instance_id": "1234567890-12345",
                "error": "Descrizione dell'errore",
                "time": "YYYY-MM-DD HH:MM:SS"
            }
        },
        {
            "event": "archive_status",
            "description": "Aggiornamenti sullo stato del download archivio",
            "data": {
                "operation_id": "archive_1234567890",
                "status": "downloading",
                "time": "YYYY-MM-DD HH:MM:SS"
            }
        }
    ]
}

# Genera la documentazione in JSON
with open(os.path.join(DOCS_DIR, "api_docs.json"), "w", encoding="utf-8") as f:
    json.dump(api_docs, f, indent=2)

# Genera la documentazione in Markdown
with open(os.path.join(DOCS_DIR, "api_docs.md"), "w", encoding="utf-8") as f:
    f.write(f"# {api_docs['title']}\n\n")
    f.write(f"Version: {api_docs['version']}\n\n")
    f.write(f"{api_docs['description']}\n\n")
    
    f.write("## Authentication\n\n")
    f.write(f"Type: {api_docs['auth']['type']}\n\n")
    f.write(f"Header: `{api_docs['auth']['header']}`\n\n")
    
    f.write("## Endpoints\n\n")
    
    for endpoint in api_docs["endpoints"]:
        f.write(f"### {endpoint['method']} {endpoint['path']}\n\n")
        f.write(f"{endpoint['description']}\n\n")
        
        if endpoint["auth_required"]:
            f.write("**Authentication required**\n\n")
        
        if endpoint["params"]:
            f.write("#### Parameters\n\n")
            f.write("| Name | Type | Required | Description | Location |\n")
            f.write("| ---- | ---- | -------- | ----------- | -------- |\n")
            
            for param in endpoint["params"]:
                location = param.get("in", "body")
                f.write(f"| {param['name']} | {param['type']} | {param['required']} | {param['description']} | {location} |\n")
            
            f.write("\n")
        
        f.write("#### Response\n\n")
        
        if isinstance(endpoint["response"], str):
            f.write(f"{endpoint['response']}\n\n")
        else:
            f.write("```json\n")
            f.write(json.dumps(endpoint["response"], indent=2))
            f.write("\n```\n\n")
    
    f.write("## WebSocket Events\n\n")
    
    for event in api_docs["websocket_events"]:
        f.write(f"### {event['event']}\n\n")
        f.write(f"{event['description']}\n\n")
        
        f.write("#### Data\n\n")
        f.write("```json\n")
        f.write(json.dumps(event["data"], indent=2))
        f.write("\n```\n\n")

print(f"Documentazione API generata in {DOCS_DIR}")