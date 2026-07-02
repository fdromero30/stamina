# Stamina Trading App

Arquitectura inicial para una app web de trading separada en tres servicios:

- `frontend-react`: interfaz web en React.
- `trading-core-python`: core business del bot de trading en Python.
- `users-config-backend-java`: backend Java para usuarios y configuraciones.
- `postgres`: base de datos para usuarios, configuraciones y estrategias.

## Servicios

```text
stamina/
  frontend-react/
  trading-core-python/
  users-config-backend-java/
  docker-compose.yml
  .env.example
```

## Levantar en Docker

```bash
cp .env.example .env
docker compose up --build
```

URLs locales:

- Frontend: http://localhost:5173
- Trading core API: http://localhost:8000
- Users/config backend: http://localhost:8080
- Postgres: localhost:5432

## Nota sobre eToro

La integracion con eToro queda aislada en `trading-core-python/app/integrations/etoro_client.py`.
Antes de operar dinero real, confirma que tienes acceso a una API oficial/permitida por eToro para tu region, cuenta y caso de uso.
No uses scraping ni automatizacion no autorizada para trading real.

