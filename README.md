# Xbox Port MCP

[English](README.en.md) · [Configuración](docs/configuration.md) · [Contribuir](CONTRIBUTING.md)

MCP independiente para inspeccionar juegos de Xbox original y coordinar ports para Windows mediante **perfiles específicos**. Automatiza pasos repetibles del trabajo realizado con Los Sims toman la calle. No convierte cualquier ISO en un juego nativo: necesita un proyecto de recompilación y correcciones para cada título y revisión.

## Estado 0.1.0: experimental

Un perfil incluido: `sims-bustin-out-usa`. Usa [bustinout-recomp](https://github.com/abilliontokens/bustinout-recomp) y [XboxXBERecomp](https://github.com/abilliontokens/XboxXBERecomp), fijados por commit.

El flujo manual original produjo un juego que su usuario confirmó jugable dentro de una casa, con guardado, textos originales en español e instalador funcional. **Esta MCP es una implementación nueva de ese flujo**: tiene pruebas de protocolo, lectores, rutas, trabajos y empaquetado. Todavía no se ha repetido una compilación completa del juego de principio a fin mediante esta MCP. La confirmación histórica se distingue de las pruebas de esta versión.

El perfil selecciona los recursos españoles presentes en el juego. La traducción del panel adicional de ajustes de PC no está incluida en esta receta. El instalador está en español. Los Sims conservan su idioma ficticio.

## Funciones

- Inspección ISO XDVDFS y XBE, identidad y huellas; extracción sin ejecutar el juego.
- Rechazo de revisiones desconocidas antes de aplicar correcciones de direcciones.
- Fuentes fijadas, correcciones de almacenamiento/idioma y configuración/compilación.
- Imágenes del instalador generadas desde vídeos de la copia local, instalador e ISO para Windows.
- Verificación del instalador dentro de la ISO y registro separado de observaciones humanas.

No incluye juegos, BIOS, claves, recursos comerciales, capturas, partidas ni ejecutables de juegos recompilados. Cada usuario aporta sus archivos localmente. REA puede ayudar a investigar perfiles nuevos; no es una dependencia obligatoria ni sustituye la implementación de un port.

## Instalar

Python 3.11 o posterior. Desde una copia del repositorio:

```console
python -m venv .venv
.venv\Scripts\python -m pip install .
```

En Linux/macOS usa `.venv/bin/python`. En esos sistemas solo se ofrece inspección/extracción; la receta de compilación y empaquetado actual está orientada a Windows x64.

Añade el servidor stdio a tu cliente MCP siguiendo [examples/mcp.json](examples/mcp.json). Sustituye las rutas por rutas absolutas reales. El comando es el Python de esa instalación y los argumentos son `-m xbox_port_mcp`.

Inspeccionar/extraer no requiere compiladores. Construir requiere Git, CMake, Ninja, LLVM compatible y entorno MSVC x64; empaquetar añade FFmpeg, Inno Setup, redistribuibles x64 y Windows PowerShell/IMAPI. La MCP no instala estas herramientas. Véase [configuración](docs/configuration.md).

## Flujo

1. Llama a `doctor`, `list_profiles` e `inspect_iso` y verifica la identidad exacta.
2. Usa `create_workspace` con `profile_id="sims-bustin-out-usa"` y `language="es"`.
3. Llama a `start_step` en orden: `extract` (con `input_path`), `prepare`, `configure`, `compile`. Preparar/configurar ya aplican `fixes`, también disponible por separado.
4. Consulta `get_job` hasta terminar cada trabajo. Detén pasos dependientes ante fallos; `cancel_job` cancela trabajos propios.
5. Prueba manualmente el ejecutable: menú, casa y guardar/cargar. `record_manual_observation` registra solo resultados comunicados por el usuario.
6. Continúa con `artwork`, `installer`, `iso`, `verify_iso`, y prueba instalar y abrir el resultado.

Son nueve herramientas, el recurso `xbox-port://profiles` y el prompt `port_workflow`. Ejecutar programas está desactivado por defecto. Un trabajo `succeeded` confirma ese paso, no la jugabilidad.

## Desarrollo

```console
python -m pip install ".[dev]"
python -m pytest -q
python -m pip wheel . --no-deps --wheel-dir dist
```

Las pruebas usan archivos sintéticos. La configuración CI incluye Windows y Ubuntu; eso no equivale a comprobar un juego completo. Código propio bajo [MIT](LICENSE); véase [atribuciones](THIRD_PARTY.md).
