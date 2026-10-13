# Continuar desde el fork

Este documento explica cómo seguir trabajando en **este** clon (el fork
`mamimeli/LucioTech-Service-Manager`) y cómo retomar la sesión después de cerrarla.

## Situación

| | |
|---|---|
| Carpeta de trabajo del fork | `C:\gh\LucioTech-Service-Manager-MamiMeli` |
| `origin` de este clon | `https://github.com/mamimeli/LucioTech-Service-Manager` |
| Repositorio original (upstream) | `https://github.com/wachin/LucioTech-Service-Manager` |
| Rama | `main` |

Este clon es un **fork**, así que el push a `origin` sí funciona aquí: la cuenta
`mamimeli` es la dueña de ese repositorio. El 403 que aparecía en el clon original
se debía a que intentaba escribir en el repo de `wachin`, donde no hay permiso.

## Estado heredado del repo original

Al crear el fork, quedaron por trasladar los cambios que se hicieron en el clon
anterior (`C:\gh\LucioTech-Service-Manager`). Lo que ya está aplicado aquí:

- `README.md` actualizado con la **guía completa de Windows** (instalación,
  ejecución, rutas `%APPDATA%` / `%LOCALAPPDATA%`, estado de pruebas y solución de
  problemas). Sustituye al README anterior, que no documentaba Windows.
- `.gitignore` con `.workbuddy-ai/` para no versionar la memoria local del asistente.

Lo que **no** se traslada porque no debe versionarse:

- La carpeta `.venv/` (entorno virtual). Hay que crearla de nuevo en este clon.
- Bases de datos SQLite y fotografías de prueba (viven en `%APPDATA%`, no en el repo).

## Puesta en marcha en este clon

Desde `C:\gh\LucioTech-Service-Manager-MamiMeli`:

```bat
:: 1. Crear el entorno virtual
py -3.13 -m venv .venv

:: 2. Activarlo (elige tu shell)
.\.venv\Scripts\Activate.ps1      :: PowerShell
.venv\Scripts\activate.bat        :: cmd.exe
source .venv/Scripts/activate     :: Git Bash

:: 3. Instalar dependencias y el paquete
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .

:: 4. Ejecutar la aplicación
python -m luciotech.main
```

> Si `PowerShell` bloquea la activación, ejecuta una vez:
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`
> o llama directamente a `.venv\Scripts\python.exe`.

## Guardar los cambios de este bloque

Revisa primero qué va a incluirse y luego confirma:

```bat
git status
git diff
```

Si todo es correcto:

```bat
git add README.md .gitignore
git commit -m "docs(readme): add verified Windows setup instructions"
git push origin main
```

El push aquí no debería dar 403, porque `origin` es tu propio fork.

## Mantener el fork al día con el repo original

Para traer cambios que se hagan en `wachin/LucioTech-Service-Manager`:

```bat
:: Se hace una sola vez: registrar el repo original como segundo remote
git remote add upstream https://github.com/wachin/LucioTech-Service-Manager.git

:: Cada vez que quieras actualizarte
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
```

Si `git remote -v` ya muestra un `upstream`, no lo vuelvas a añadir; salta directo
al `fetch`.

## Verificar que todo funciona

```bat
:: Suite completa (en Windows: 233 pasan, 1 falla por diferencia de plataforma)
python -m pytest
```

La única prueba que falla en Windows es
`tests/test_rich_text_editor.py::test_toolbar_rows_are_compact_and_only_grow_when_scrolling_is_needed`.
Es un detalle cosmético de la barra de herramientas y está explicado en el README,
sección **Windows test status**.

## Por qué se dejó el clon anterior

El clon `C:\gh\LucioTech-Service-Manager` apunta al repo de `wachin` y su push da
403. Puedes conservarlo como referencia de solo lectura, pero **a partir de ahora
trabaja en `C:\gh\LucioTech-Service-Manager-MamiMeli`** para evitar confundirte de
carpeta.

## Recordatorios del proyecto

- Trabaja siempre dentro del `.venv` y ejecuta las pruebas con
  `.venv/Scripts/python.exe -m pytest`.
- Las reglas de desarrollo están en `AGENTS.md` y la especificación en `ROADMAP.md`.
- No versiones datos reales de clientes ni secretos (ya están cubiertos por
  `.gitignore`).
