# Telegram Media Downloader API

Version: 1.0.0

API per la gestione di download e monitoraggio di media da Telegram

## Authentication

Type: Bearer Token

Header: `Authorization: Bearer YOUR_TOKEN`

## Endpoints

### GET /status

Ottiene lo stato del server API

#### Response

```json
{
  "status": "online",
  "version": "1.0.0",
  "time": "YYYY-MM-DD HH:MM:SS"
}
```

### GET /users

Ottiene la lista degli utenti configurati

**Authentication required**

#### Response

```json
{
  "users": [
    {
      "nickname": "example_user",
      "phone": "+1234567890"
    }
  ]
}
```

### POST /users

Aggiunge un nuovo utente

**Authentication required**

#### Parameters

| Name | Type | Required | Description | Location |
| ---- | ---- | -------- | ----------- | -------- |
| nickname | string | True | Nome utente per l'account Telegram | body |
| phone | string | True | Numero di telefono associato all'account Telegram | body |

#### Response

```json
{
  "status": "success",
  "message": "Utente example_user aggiunto con successo"
}
```

### DELETE /users/{nickname}

Rimuove un utente

**Authentication required**

#### Parameters

| Name | Type | Required | Description | Location |
| ---- | ---- | -------- | ----------- | -------- |
| nickname | string | True | Nome utente da rimuovere | path |

#### Response

```json
{
  "status": "success",
  "message": "Utente 'example_user' rimosso con successo"
}
```

### GET /groups

Ottiene la lista dei gruppi disponibili

**Authentication required**

#### Response

```json
{
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
```

### GET /groups/{group_id}/link

Ottiene il link di invito ad un gruppo

**Authentication required**

#### Parameters

| Name | Type | Required | Description | Location |
| ---- | ---- | -------- | ----------- | -------- |
| group_id | integer | True | ID del gruppo | path |

#### Response

```json
{
  "group_id": -1001234567890,
  "link": "https://t.me/example_group"
}
```

### POST /archives

Avvia il download dell'archivio di un gruppo

**Authentication required**

#### Parameters

| Name | Type | Required | Description | Location |
| ---- | ---- | -------- | ----------- | -------- |
| group_id | integer | True | ID del gruppo | body |
| user | string | True | Nome utente associato al gruppo | body |

#### Response

```json
{
  "status": "started",
  "operation_id": "archive_1234567890",
  "message": "Download archivio avviato per il gruppo Example Group"
}
```

### POST /monitoring

Avvia il monitoraggio dei gruppi

**Authentication required**

#### Response

```json
{
  "status": "started",
  "instance_id": "1234567890-12345",
  "message": "Monitoraggio avviato"
}
```

### DELETE /monitoring/{instance_id}

Ferma un'istanza di monitoraggio

**Authentication required**

#### Parameters

| Name | Type | Required | Description | Location |
| ---- | ---- | -------- | ----------- | -------- |
| instance_id | string | True | ID dell'istanza di monitoraggio | path |

#### Response

```json
{
  "status": "stopping",
  "instance_id": "1234567890-12345",
  "message": "Monitoraggio in fase di arresto"
}
```

### GET /monitoring

Ottiene lo stato delle istanze di monitoraggio attive

**Authentication required**

#### Response

```json
{
  "instances": {
    "1234567890-12345": {
      "type": "monitoring",
      "start_time": 1234567890,
      "status": "active"
    }
  }
}
```

### GET /media

Ottiene la lista dei file media

**Authentication required**

#### Parameters

| Name | Type | Required | Description | Location |
| ---- | ---- | -------- | ----------- | -------- |
| user | string | False | Filtra per utente | body |
| group | string | False | Filtra per gruppo | body |
| type | string | False | Filtra per tipo di media (images, videos, etc.) | body |

#### Response

```json
{
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
```

### GET /media/{file_path}

Ottiene un file media specifico

**Authentication required**

#### Parameters

| Name | Type | Required | Description | Location |
| ---- | ---- | -------- | ----------- | -------- |
| file_path | string | True | Percorso relativo del file | path |

#### Response

File binario

## WebSocket Events

### monitoring_status

Aggiornamenti sullo stato del monitoraggio

#### Data

```json
{
  "instance_id": "1234567890-12345",
  "status": "active",
  "time": "YYYY-MM-DD HH:MM:SS"
}
```

### monitoring_error

Errori durante il monitoraggio

#### Data

```json
{
  "instance_id": "1234567890-12345",
  "error": "Descrizione dell'errore",
  "time": "YYYY-MM-DD HH:MM:SS"
}
```

### archive_status

Aggiornamenti sullo stato del download archivio

#### Data

```json
{
  "operation_id": "archive_1234567890",
  "status": "downloading",
  "time": "YYYY-MM-DD HH:MM:SS"
}
```

