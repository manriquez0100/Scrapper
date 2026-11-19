# Guía: Chrome con Remote Debugging para MercadoLibre Scraper

## Objetivo
Permitir que el scraper se **adjunte a tu Chrome habitual** (con tu sesión de MercadoLibre ya iniciada) en lugar de abrir una ventana nueva sin login.

---

## Paso a Paso

### 1. Cerrar Chrome completamente
- Cierra **todas** las ventanas de Chrome
- Verifica en Administrador de tareas que no quede ningún proceso `chrome.exe`

### 2. Crear acceso directo (recomendado) o ejecutar comando

#### Opción A: Acceso directo permanente (recomendado)
1. Click derecho en escritorio → **Nuevo** → **Acceso directo**
2. En "Ubicación del elemento", pegar:
   ```
   "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\Users\DATA-MESACNTL3\AppData\Local\Google\Chrome\User Data"
   ```
3. Nombre: `Chrome con Debugging`
4. Usar **este acceso directo** siempre que quieras scrapear

#### Opción B: Ejecutar desde terminal (una vez)
```cmd
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\Users\DATA-MESACNTL3\AppData\Local\Google\Chrome\User Data"
```

#### Opción C: Archivo `.bat` (guardar como `chrome_debug.bat`)
```bat
@echo off
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\Users\DATA-MESACNTL3\AppData\Local\Google\Chrome\User Data"
```

---

## Verificación

### 1. Comprobar que el puerto está activo
Abre una terminal (PowerShell/CMD) y ejecuta:
```cmd
curl http://127.0.0.1:9222/json/version
```
**Debe devolver JSON** similar a:
```json
{
  "Browser": "Chrome/120.0.6099.109",
  "Protocol-Version": "1.3",
  "User-Agent": "Mozilla/5.0...",
  "V8-Version": "12.0.267.8",
  "WebKit-Version": "537.36...",
  "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/browser/..."
}
```

### 2. Ver en navegador
Abre: `http://127.0.0.1:9222` → Debe mostrar la interfaz de DevTools con pestañas abiertas

---

## Uso Diario

### Flujo normal:
1. **Abrir Chrome** usando el acceso directo "Chrome con Debugging"
2. **Iniciar sesión** en MercadoLibre (si no lo está)
3. **Dejar Chrome abierto** (mínimizado si quieres)
4. **Ejecutar scraper** con flag `--attach`:
   ```bash
   python -m mercadolibre --usar-chrome-abierto --query "harry potter"
   ```
   O desde la app principal (ya pasa `debugger_address` automáticamente via env var)

### El scraper:
- Se **adjunta** a la ventana existente
- **No abre** nueva ventana
- **No cierra** Chrome al terminar
- Usa **tu sesión real** (cookies, login, preferencias)

---

## Variables de Entorno (`.env`)

```env
# Puerto debugging del Chrome adjunto
MELI_CHROME_DEBUGGER_ADDRESS=127.0.0.1:9222
```

El scraper lee esto automáticamente.

---

## Troubleshooting

| Problema | Causa | Solución |
|----------|-------|----------|
| `curl` falla / connection refused | Chrome no inició con `--remote-debugging-port` | Verificar acceso directo, cerrar todo Chrome y reabrir |
| `curl` devuelve HTML en vez de JSON | Puerto ocupado por otra app | Cambiar puerto (ej. 9223) en acceso directo Y en `.env` |
| "Chrome failed to start: crashed" | Perfil bloqueado (SingletonLock) | Cerrar TODOS los Chrome, borrar `SingletonLock` en User Data, reintentar |
| Scraper dice "no hay Chrome disponible" | Puerto/distinto o Chrome no corriendo | Verificar `curl`, asegurar que Chrome abierto es el del acceso directo |
| Múltiples Chrome abiertos | Solo el PRIMERO con el flag expone el puerto | Cerrar todos, abrir solo el del acceso directo |
| Login modal aparece | Sesión expirada o ML fuerza re-login | Iniciar sesión manualmente en ese Chrome, luego scrapear |

---

## Alternativa: Perfil Dedicado "Scraping" (si no quieres usar tu perfil principal)

Si prefieres no tocar tu perfil habitual:

1. **Crear perfil nuevo en Chrome:**
   - Chrome → Perfil (arriba a la derecha) → **Agregar**
   - Nombre: `MercadoLibre Scraper`
   - **NO** sincronizar con cuenta Google

2. **Iniciar sesión en MercadoLibre** en ese perfil

3. **Acceso directo para ese perfil:**
   ```
   "C:\Program Files\Google\Chrome\Application\chrome.exe" 
   --remote-debugging-port=9222 
   --user-data-dir="C:\Users\DATA-MESACNTL3\AppData\Local\Google\Chrome\User Data" 
   --profile-directory="Profile 1"
   ```
   *(Donde "Profile 1" es el nombre de carpeta que Chrome creó - verificar en `chrome://version` → "Profile Path")*

4. Usar mismo flujo: abrir acceso directo → login ML → scraper con `--attach`

---

## Comandos de Prueba Rápida

```bash
# 1. Verificar puerto
curl http://127.0.0.1:9222/json/version

# 2. Test diagnóstico selectores (adjunto)
python debug_ml_selectors.py --attach --query "harry potter"

# 3. Test búsqueda real via scraper
python -c "
import asyncio
from mercadolibre import search_mercadolibre
result = asyncio.run(search_mercadolibre('harry potter', max_results=3, debugger_address='127.0.0.1:9222'))
print(f'Resultados: {len(result[\"results\"])}')
for r in result['results']:
    print(f'  - {r[\"title\"]} | {r[\"price\"]} | {r[\"condition\"]}')
"

# 4. Test desde main.py (requiere backend corriendo)
# python main.py  (en otra terminal)
# Luego usar frontend terminal
```

---

## Notas Importantes

- **El scraper NUNCA cierra tu Chrome** cuando usa `--attach` (ver `_attached_browser` flag)
- **Solo una instancia** de Chrome puede tener el puerto 9222 abierto
- **Cookies y sesión** persisten entre reinicios del scraper
- **Headless NO funciona** con CDP attach (Chrome debe estar visible)
- Si cambias de usuario en ML, haz logout/login en ese Chrome, no en el scraper

---

## Archivos Relacionados

| Archivo | Función |
|---------|---------|
| `mercadolibre.py` | Scraper principal con soporte CDP (`_conectar_a_chrome_abierto`, `--usar-chrome-abierto`) |
| `debug_ml_selectors.py` | Diagnóstico de selectores (usa mismo mecanismo CDP) |
| `main.py` | Llama a `search_mercadolibre(debugger_address=...)` desde env var |
| `.env` | Define `MELI_CHROME_DEBUGGER_ADDRESS=127.0.0.1:9222` |