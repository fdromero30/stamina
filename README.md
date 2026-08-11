# Stamina Trading App

Aplicación web de trading automatizado compuesta por varios servicios independientes:

- **`proxy`**: reverse proxy **Caddy** — único punto de entrada público (puertos 80/443) con SSL automático (Let's Encrypt).
- **`frontend-react`**: interfaz web en React + TypeScript (Vite) servida por Nginx.
- **`trading-core-python`**: core del bot de trading en Python (FastAPI).
- **`users-config-backend-java`**: backend Java (Spring Boot) para usuarios, API keys, estrategias y operaciones de trading.
- **`postgres`**: base de datos PostgreSQL para usuarios, configuraciones y estrategias.

> 🔒 **Seguridad en producción:** solo el servicio `proxy` (Caddy) se expone a internet. Los backends, la base de datos y el frontend viven en la red interna de Docker y **no publican puertos** al exterior.

---

## Requisitos previos

| Herramienta | Versión mínima |
|---|---|
| [Docker](https://docs.docker.com/get-docker/) | 24+ |
| [Docker Compose](https://docs.docker.com/compose/install/) | v2+ |

> **Opcional** (solo para desarrollo local sin Docker):
> - Node.js 22+
> - Python 3.12+
> - Java 21+ (JDK)
> - Maven 3.9+

---

## 🚀 Levantar el proyecto (Docker)

La forma más rápida de levantar toda la aplicación es con Docker Compose.

### 1. Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd stamina
```

> ⚠️ **Importante:** El proyecto completo (incluido `docker-compose.yml`) está dentro de la carpeta `stamina/`. Si ya estás dentro de un directorio llamado `stamina` pero no ves el archivo `docker-compose.yml`, entra a la subcarpeta:
>
> ```bash
> cd stamina
> ```
>
> Verifica que estás en el lugar correcto:
>
> ```bash
> ls docker-compose.yml
> ```
>
> Si el comando muestra el archivo, estás en el directorio correcto.

### 2. Configurar variables de entorno

```bash
cp .env.example .env
```

El archivo `.env` ya trae valores de desarrollo funcionales. Solo necesitas editarlo si quieres cambiar puertos, credenciales de la base de datos o configurar eToro.

### 3. Levantar los servicios

```bash
docker compose up --build
```

Este comando construye las imágenes y levanta los 4 servicios. La primera vez puede tardar varios minutos (descarga de imágenes base y compilación de dependencias).

Para levantar en segundo plano:

```bash
docker compose up --build -d
```

### 4. Verificar que todo está corriendo

```bash
docker compose ps
```

Todos los servicios deben aparecer con estado `Up` (o `healthy` en el caso de Postgres).

### 5. Acceder a la aplicación

| Servicio | URL |
|---|---|
| Frontend (React) | http://localhost (vía proxy Caddy) |
| Trading Core API (FastAPI) | http://localhost (vía proxy Caddy) |
| Users/Config Backend (Spring Boot) | http://localhost (vía proxy Caddy) |

> 🔒 **En producción con SSL**, la URL es `https://tu-dominio.com`.

> **Desarrollo local sin SSL:** el servicio `proxy` (Caddy) arranca con la configuración de tu `DOMAIN`. Si aún no has configurado el dominio, los backends no son accesibles desde el host (están solo en la red interna de Docker). Para desarrollo local, edita `.env` y usa `DOMAIN=localhost` (Caddy servirá por HTTP en `http://localhost` sin certificado).

### 6. Detener los servicios

```bash
docker compose down
```

Para detener y **eliminar los datos de la base de datos**:

```bash
docker compose down -v
```

---

## 🌍 Despliegue en producción (VPS)

La aplicación está preparada para desplegarse en un VPS (Hostinger, DigitalOcean, etc.) con **HTTPS automático**  con Caddy + Let's Encrypt.

### Arquitectura de seguridad

```
Internet ──▶ 80/443 (proxy Caddy) ──▶ frontend (nginx) ──▶ /api → users-config-backend
                                                            └─ /trading-core → trading-core
```

- **Solo el proxy (Caddy)** se expone a internet.
- Los backends, Postgres y el frontend **no publican puertos** — solo son accesibles en la red interna de Docker.
- Caddy genera y renueva certificados SSL automáticamente (Let's Encrypt, **gratis**) y redirige HTTP → HTTPS.

### Pasos

#### 1. Requisitos
- Un **dominio** (o subdominio, ej. `stamina.tudominio.com`) apuntando al IP del VPS (registro A en el DNS).
- Puertos **80** y **443** abiertos en el firewall del VPS (hPanel/ufw).

#### 2. Configurar variables de entorno

```bash
cp .env.example .env
nano .env
```

Valores obligatorios:

| Variable | Ejemplo |
|---|---|
| `DOMAIN` | `stamina.tudominio.com` |
| `ACME_EMAIL` | `tu@email.com` |
| `POSTGRES_PASSWORD` | `openssl rand -hex 24` |
| `CRYPTO_MASTER_KEY` | `openssl rand -hex 32` |
| `CORS_ALLOWED_ORIGINS` | `https://stamina.tudominio.com` |

#### 3. Levantar

```bash
docker compose up -d --build
```

Caddy detectará el dominio y obtendrá el certificado SSL automáticamente (los primeros segundos servirá HTTP mientras valida el dominio).

#### 4. Verificar

```bash
docker compose ps
curl -I https://tu-dominio.com
```

---

## ⚙️ Variables de entorno

Todas las variables están documentadas en [`.env.example`](.env.example):

| Variable | Descripción | Default |
|---|---|---|
| `POSTGRES_DB` | Nombre de la base de datos | `stamina` |
| `POSTGRES_USER` | Usuario de la base de datos | `stamina` |
| `POSTGRES_PASSWORD` | Contraseña de la base de datos | `stamina_dev_password` |
| `JAVA_BACKEND_PORT` | Puerto del backend Java | `8080` |
| `TRADING_CORE_PORT` | Puerto del trading core | `8000` |
| `FRONTEND_PORT` | Puerto del frontend | `5173` |
| `ETORO_API_BASE_URL` | URL base de la API de eToro | `https://public-api.etoro.com/api/v1` |
| `ETORO_API_KEY` | API key de eToro | `replace_me` |
| `ETORO_ACCOUNT_ID` | ID de cuenta eToro | `replace_me` |
| `CRYPTO_MASTER_KEY` | Clave AES-256 para cifrar API keys (**requerida**) | `a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6` |
| `VITE_USERS_CONFIG_API_URL` | URL del backend Java (solo dev local) | `http://localhost:8080` |
| `VITE_TRADING_CORE_URL` | URL del trading core (solo dev local) | `http://localhost:8000` |

> ⚠️ **`CRYPTO_MASTER_KEY` es obligatoria.** Debe tener exactamente 32 caracteres (AES-256). El valor incluido en `.env.example` es solo para desarrollo. En producción, genera una clave segura:
>
> ```bash
> openssl rand -hex 16
> ```

---

## 🛠️ Desarrollo local (sin Docker)

Si quieres trabajar en un servicio específico con hot-reload, puedes levantarlo individualmente.

### Frontend (React + Vite)

```bash
cd frontend-react
npm install
npm run dev
```

El servidor de desarrollo corre en `http://localhost:5174` y hace proxy de `/api` → `http://localhost:8080` y `/trading-core` → `http://localhost:8000`.

#### Nginx parametrizable (local vs Render)

El Dockerfile incluye dos templates seleccionados por `entrypoint.sh`:
- Local (sin RENDER): `nginx.local.conf` -> proxy HTTP a red interna
- Render (RENDER=true): `nginx.render.conf` -> proxy HTTPS con SNI

### Trading Core (Python + FastAPI)

```bash
cd trading-core-python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Users/Config Backend (Java + Spring Boot)

```bash
cd users-config-backend-java
./mvnw spring-boot:run
```

> **Nota:** Para desarrollo local necesitas una instancia de Postgres corriendo. Puedes levantarla solo con Docker:
>
> ```bash
> docker compose up postgres -d
> ```

---

## 🧪 Tests

### Frontend

```bash
cd frontend-react
npm test
```

### Trading Core

```bash
cd trading-core-python
pytest
```

### Users/Config Backend

```bash
cd users-config-backend-java
./mvnw test
```

---

## 📁 Estructura del proyecto

```text
stamina/
├── docker-compose.yml              # Orquestación de todos los servicios
├── .env.example                    # Plantilla de variables de entorno
├── frontend-react/                 # Frontend React + TypeScript (Vite)
│   ├── Dockerfile
│   ├── nginx.local.conf            # Template Nginx para entorno local
│   ├── nginx.render.conf           # Template Nginx para Render (SNI)
│   ├── entrypoint.sh               # Selecciona template según entorno
│   ├── package.json
│   └── src/
│       ├── components/             # Componentes reutilizables
│       ├── pages/                  # Páginas de la aplicación
│       ├── routing/                # Definición de rutas
│       ├── store/                  # Redux Toolkit (API slices)
│       └── test/                   # Tests unitarios
├── trading-core-python/            # Bot de trading (FastAPI)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                 # Endpoints de la API
│   │   ├── settings.py             # Configuración del bot
│   │   ├── bot/                    # Motor del bot y scheduler
│   │   └── integrations/           # Clientes de market data, órdenes y estrategias
│   └── tests/
└── users-config-backend-java/      # Backend de usuarios y config (Spring Boot)
    ├── Dockerfile
    ├── pom.xml
    └── src/main/java/com/stamina/usersconfig/
        ├── apikey/                 # Gestión de API keys (cifradas)
        ├── strategy/               # Configuración de estrategias
        ├── trading/                # Cliente eToro y operaciones
        ├── user/                   # Usuarios y autenticación
        └── config/                 # Seguridad, CORS, crypto, seeder
```

---

## 🔌 Endpoints principales

### Trading Core (`http://localhost:8000`)

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Estado del servicio |
| `POST` | `/bot/start` | Inicia el scheduler del bot |
| `POST` | `/bot/stop` | Detiene el scheduler del bot |
| `GET` | `/bot/status` | Estado actual del bot |
| `GET` | `/bot/cycles` | Historial de ciclos recientes y posiciones abiertas (persistido en SQLite) |
| `POST` | `/bot/cycle` | Ejecuta un ciclo de trading manualmente |
| `POST` | `/bot/evaluate/{strategy_id}` | Evalúa una estrategia sin ejecutar trades |
| `POST` | `/orders/market` | Envía una orden de mercado |

Documentación interactiva (Swagger): http://localhost:8000/docs

### Users/Config Backend (`http://localhost:8080`)

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Estado del servicio |
| `POST` | `/users` | Crear usuario |
| `POST` | `/users/login` | Iniciar sesión |
| `GET` | `/users` | Listar usuarios |
| `GET` | `/api-keys?userId={id}` | Listar API keys de un usuario |
| `POST` | `/api-keys` | Crear API key (se cifra con `CRYPTO_MASTER_KEY`) |
| `GET` | `/strategies?userId={id}` | Listar estrategias de un usuario |
| `POST` | `/strategies` | Crear estrategia |
| `PUT` | `/strategies/{id}` | Actualizar estrategia |
| `DELETE` | `/strategies/{id}` | Eliminar estrategia |

---

## 🐳 Comandos útiles de Docker

```bash
# Ver logs de un servicio específico
docker compose logs -f frontend

# Reconstruir un solo servicio
docker compose up --build trading-core

# Ver el estado de los contenedores
docker compose ps

# Ejecutar un comando dentro de un contenedor
docker compose exec postgres psql -U stamina -d stamina

# Detener todo y limpiar volúmenes (borra la BD)
docker compose down -v
```

---

## ⚠️ Nota sobre eToro

La integración con eToro queda aislada en `trading-core-python/app/integrations/` y en el cliente `EtoroClient` del backend Java.

Antes de operar con dinero real, confirma que tienes acceso a una API oficial/permitida por eToro para tu región, cuenta y caso de uso. **No uses scraping ni automatización no autorizada para trading real.**

---

## 💾 Persistencia del estado del bot

El trading core guarda el estado del bot en una base de datos SQLite local (`trading-core-python/data/bot_state.db`), de modo que el historial de ciclos, las posiciones abiertas y el contador de ciclos sobreviven a reinicios del servicio.

- **Archivo**: `trading-core-python/data/bot_state.db`
- **Volumen Docker**: `stamina_trading_data` (mapeado a `/app/data`)
- **Excluido de git**: los archivos `*.db` y el directorio `data/` están en `.gitignore`

### Datos persistidos

| Tabla | Contenido |
|---|---|
| `bot_state` | Estado general del bot (corriendo/detenido, conteo de ciclos, last/next run) |
| `cycle_history` | Historial de ciclos recientes con evaluations, trades y adjustments |
| `open_positions` | Posiciones abiertas con entry, stop loss, take profit y estado de breakeven |

## 🧰 Troubleshooting

### Conexión a Supabase falla (`jdbc connection problem` o `tenant not found`)

**Causa más común:** El hostname directo `db.ifbrxvkmeiburqagskjs.supabase.co` **no es accesible** desde algunos entornos (routing IPv4/IPv6). La solución es usar el **TRANSACTION POOLER**.

**Configuración verificada en DBeaver (funciona):**
| Variable | Valor |
|---|---|
| `SUPABASE_DB_HOST` | `aws-1-us-west-2.pooler.supabase.com` |
| `SUPABASE_DB_PORT` | `6543` (transaction pooler) |
| `SUPABASE_DB_USER` | `postgres.ifbrxvkmeiburqagskjs` |
| `SUPABASE_DB_PASSWORD` | password de Supabase |

Verificación rápida:
```bash
python3 db_diagnostic.py
cat stamina_db_check.txt
```
Debes ver `Auth code` o `tenant EXISTS`.

> ⚠️ **Nunca** incrustes la password en la JDBC URL (`jdbc:postgresql://...?password=...`). Caracteres como `*` rompen el parsing. Pásala por `SPRING_DATASOURCE_PASSWORD`.

### El puerto 5432 ya está en uso

Cambia el puerto de Postgres en tu `.env`:

```env
POSTGRES_PORT=5433
```

> Nota: `POSTGRES_PORT` no está definido por defecto en `docker-compose.yml`. Si necesitas cambiar el puerto de Postgres, edita la línea `"5432:5432"` en `docker-compose.yml` o agrega la variable al archivo compose.

### `CRYPTO_MASTER_KEY` no configurada

El backend Java fallará al arrancar si `CRYPTO_MASTER_KEY` está vacía. Asegúrate de que tu `.env` la incluya (el `.env.example` ya trae una de desarrollo).

### La primera compilación tarda mucho

Es normal: Docker descarga imágenes base (Node, Python, Maven, JRE) y compila las dependencias. Las siguientes ejecuciones usan caché y son mucho más rápidas.

### Quiero resetear todo

```bash
docker compose down -v
docker compose up --build
```
