# Fvrever Analytics

Panel estático en un solo archivo `index.html`, listo para publicar en GitHub Pages o Vercel.

## Publicar
- Sube `index.html` a la raíz del repositorio.
- En Vercel, importa el repositorio y usa preset **Other**; deja Build Command vacío y Output Directory como `.`.
- En GitHub Pages, configura Deploy from a branch y selecciona la rama y carpeta raíz.

## Acceso y contraseñas
- Las contraseñas se verifican con PBKDF2-SHA-256 (310.000 iteraciones y salts independientes).
- El HTML no contiene las contraseñas en texto plano.
- Al cambiar la contraseña, se genera un salt nuevo y se guarda el hash en `localStorage` del navegador.

## Limitación importante
Esto es solamente una barrera de acceso del lado del navegador. No es autenticación real: cualquier visitante puede inspeccionar/modificar el JavaScript, borrar el almacenamiento local o saltarse la pantalla. El cambio de contraseña se aplica únicamente al navegador donde se realiza. La contraseña de respaldo tampoco puede proteger contra alguien que modifique el propio HTML.

No uses este método para proteger información sensible ni compartas secretos esperando seguridad real. Para un panel privado real, usa autenticación y verificación en servidor.

## Datos
Todas las estadísticas empiezan en cero. Este HTML no recopila telemetría ni está conectado a una base de datos o API.
