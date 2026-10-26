# Configuración

El servidor usa stdio: stdout queda reservado al protocolo y los diagnósticos usan stderr. El cliente inicia el proceso.

| Variable | Uso |
| --- | --- |
| XBOX_PORT_WORKSPACE_ROOT | Carpeta absoluta para espacios nuevos. Windows por defecto: XboxPorts dentro del directorio personal. Mantener fuera del repositorio. |
| XBOX_PORT_INPUT_ROOTS | Texto JSON con lista de carpetas absolutas existentes de entrada. Por defecto []. Los espacios propios también se pueden leer. |
| XBOX_PORT_ALLOW_EXECUTION | 1 habilita herramientas externas; por defecto desactivado. |
| XBOX_PORT_ALLOW_NETWORK | 1 permite preparar fuentes y obtener dependencias; por defecto desactivado. |
| XBOX_PORT_LLVM_BIN | Carpeta opcional con clang, clang++, lld-link, llvm-ar y llvm-ranlib. |
| XBOX_PORT_CRT_DIR | Redistribuibles MSVC x64 correspondientes a tu instalación/licencia: msvcp140.dll, vcruntime140.dll, vcruntime140_1.dll son obligatorias. |
| XBOX_PORT_GIT, XBOX_PORT_CMAKE, XBOX_PORT_NINJA | Rutas opcionales; de lo contrario PATH. Ninja debe estar además disponible para CMake en PATH. |
| XBOX_PORT_CLANG, XBOX_PORT_CLANG++, XBOX_PORT_FFMPEG, XBOX_PORT_ISCC, XBOX_PORT_POWERSHELL | Rutas opcionales para diagnóstico o herramientas correspondientes. Selecciona compiladores CMake mediante XBOX_PORT_LLVM_BIN. |

Para construir en Windows inicia el cliente/servidor desde un entorno de desarrollo Visual Studio **x64** que herede INCLUDE, LIB y PATH, con C++ y Windows SDK instalados. `doctor` informa de disponibilidad sin instalar nada. No se incluyen rutas de la máquina del autor.

La opción de red controla el flujo: sin ella se rechaza preparar y CMake recibe FETCHCONTENT_FULLY_DISCONNECTED=ON. **No es un cortafuegos**. Las herramientas y fuentes externas se ejecutan con permisos del usuario; revisa y confía en ellas antes de activarlas. La gestión de procesos para cancelación tampoco es aislamiento de seguridad.

Autoriza carpetas acotadas a tus juegos. Se rechazan rutas fuera de las raíces y enlaces que escapen de los espacios; no se pretende defender frente a otro programa local que manipule simultáneamente esos directorios.

## Resultados y recuperación

Consulta `get_job` hasta succeeded, failed o cancelled. Devuelve hasta 16 KiB de registro; el archivo local también se limita. Los identificadores son de la sesión y no se reanudan al reiniciar.

Extracción, arte y paquetes usan staging propio y rechazan destinos existentes. Una preparación interrumpida puede dejar fuentes parciales: usa otro espacio o revisa manualmente antes de continuar. No se hacen resets automáticos.

Los espacios contienen recursos, fuentes y resultados privados: **no los publiques**. El instalador solo toma recursos, ejecutable, DLL permitidas, atribuciones y configuración inicial; no recoge hdd de pruebas previas. Actualizar/desinstalar conserva hdd y configuración. Traslada partidas copiando hdd manualmente, con el juego cerrado y respaldo.

Las huellas admitidas están en el perfil. Un mismo título con otro XBE puede inspeccionarse pero no recibe correcciones específicas. La huella alternativa documentada por upstream aún no tiene prueba local de juego aquí.

Referencias: [MCP build server](https://modelcontextprotocol.io/docs/develop/build-server), [SDK Python](https://py.sdk.modelcontextprotocol.io/).

La creación de ISO inicia su proceso de PowerShell con `-ExecutionPolicy RemoteSigned` para ejecutar la plantilla local incluida. Solo afecta a ese proceso; no cambia la política guardada del equipo ni prevalece sobre políticas de grupo. [Referencia de Microsoft](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies?view=powershell-5.1).
