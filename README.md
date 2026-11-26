# FVREVER Analytics — Backend Vercel + Supabase

Este paquete agrega API real al panel existente. Conserva el diseño del `index.html` y reemplaza el acceso local por una sesión firmada en servidor.

## 1. Variables de entorno en Vercel

En **Project → Settings → Environment Variables**, agrega (Production, Preview y Development):

- `SUPABASE_URL` = URL del proyecto Supabase.
- `SUPABASE_SERVICE_ROLE_KEY` = clave `service_role` (secreta; nunca ponerla en HTML ni compartirla).
- `DASHBOARD_PASSWORD` = contraseña fuerte para entrar al panel.
- `SESSION_SECRET` = secreto aleatorio largo (mínimo 32 caracteres).

Para generar `SESSION_SECRET` en Windows PowerShell:
```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
Copia el resultado en Vercel. No lo publiques en GitHub.

## 2. Supabase

Usa las tablas `public.installations` y `public.analytics_events` creadas con el SQL anterior. La API usa la clave de servidor; no expone esa clave al navegador ni al launcher.

## 3. Archivos

- `index.html`: panel web, autenticación y lectura de estadísticas.
- `api/auth.py`: login, validación de sesión y logout.
- `api/telemetry.py`: endpoint público `POST /api/telemetry`.
- `api/dashboard.py`: endpoint privado `GET /api/dashboard`.
- `vercel.json`: configuración de funciones Python.

## 4. Despliegue

Sube todos los archivos manteniendo la estructura a la raíz del repositorio y espera el despliegue `Ready`.

Prueba:
- `https://TU-DOMINIO/api/auth` debe responder `401` sin sesión (normal).
- El panel inicia sesión usando `DASHBOARD_PASSWORD`.
- `POST /api/telemetry` recibe JSON con `installation_id` (UUID), `launcher_version` y `optional_consent` (boolean).

## 5. Privacidad

Siempre se registra un UUID aleatorio, versión del launcher, país aproximado cuando Vercel lo proporciona, y fechas de primera/última actividad. La dirección IP no se guarda ni se envía como campo de telemetría. Los eventos de uso solo se guardan si `optional_consent` es `true`.

La detección del país usa el encabezado de geolocalización de Vercel (`x-vercel-ip-country`). No se acepta un país enviado por el cliente.

## 6. Límites de esta entrega

Esta API queda lista, pero el launcher de escritorio todavía debe apuntar a `https://fvrever-client-analytics.vercel.app/api/telemetry` para que empiecen a registrarse instalaciones. La integración del launcher se realiza aparte en el proyecto FVREVER Client.

El dashboard muestra hasta 5.000 registros recientes por consulta. Los eventos visibles representan solo los eventos opcionales consentidos.
