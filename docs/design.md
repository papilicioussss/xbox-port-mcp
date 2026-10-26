# Xbox Port MCP — diseño inicial

Decisión del usuario: MCP independiente, reutilizable, con perfiles por juego. Primera versión local stdio en Python 3.11+, SDK oficial MCP 2.3.0. Windows es el destino inicial de compilación/empaquetado; inspección y extracción funcionan también en Linux/macOS.

Herramientas: listar perfiles, inspeccionar ISO/XBE, crear un espacio de trabajo, extraer la ISO, preparar fuentes fijadas por perfil, aplicar correcciones conocidas, consultar requisitos, ejecutar configuración/compilación, generar arte e instalador, crear/verificar ISO y consultar trabajos. Los procesos largos retornan un identificador y un registro acotado. No existe una herramienta de shell arbitraria. La ejecución de compiladores requiere habilitación explícita al iniciar el servidor; las fuentes de un port son código ejecutable de confianza.

El único perfil inicial es The Sims Bustin Out USA. Referencias: abilliontokens/bustinout-recomp e37436806c5107ee0ed4cb4d5c7a62b4c72eb613 y SDK adc40ab688be14da932514bd9f6f59a29dab3c65. Se diferencian hashes conocidos del XBE, compilación y pruebas humanas. Otro título requiere un perfil y trabajo de adaptación. No se afirma conversión universal.

El repositorio incluye exclusivamente código original, perfiles, correcciones y documentación. No incluye ISOs, ejecutables del juego, recursos, capturas del juego, partidas, bibliotecas redistribuibles ni herramientas descargadas. Las herramientas externas se configuran localmente; los archivos de trabajo quedan fuera del repositorio. El SDK conserva su aviso MIT; el port se obtiene como dependencia externa por referencia.

Lecturas limitadas a raíces configuradas y escrituras limitadas a espacios de trabajo propios. La extracción valida nombres, colisiones, límites, ciclos y rangos antes de publicar archivos. Se rechazan symlinks y rutas que escapen del espacio. Las pruebas usan datos sintéticos y un cliente MCP real; la inspección real de esta copia se hace solo de lectura. Publicación únicamente de una selección auditada de archivos de código.
