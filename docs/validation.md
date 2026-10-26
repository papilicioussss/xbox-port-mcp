# Validación de 0.1.0

Comprobaciones locales del 26 de octubre de 2026, Windows x64:

- Suite: 33 pruebas aprobadas y 1 omitida por falta de privilegios para crear enlaces simbólicos.
- Cliente oficial MCP: inicialización, herramientas, errores, recurso y transporte stdio real.
- Lectores/extracción: datos sintéticos, rutas no portables, ciclos, colisiones, rangos inválidos, cancelación y límite de bytes.
- Procesos: salida fallida, registros acotados, exclusividad y cancelación después de cerrar stdout/stderr.
- Empaquetado: prueba real con Inno Setup 6.7.3 y Windows IMAPI, exclusivamente con archivos sintéticos. Instalador compilado, ISO de 3.473.408 bytes y hash del instalador interno verificado. No se ejecutó el falso juego sintético.
- Identificación adicional: XBE local de Sims reconocido como title ID 45410043 y SHA-1 cd46fd3bf40471823076ca795fec9b1feda4f984.
- Revisión independiente: cuatro hallazgos importantes reproducidos con pruebas fallidas y corregidos; suite completa aprobada después.
- Paquete wheel y fuente sdist construidos localmente. CI para Windows/Ubuntu configurada; aún no ejecutada en GitHub.

## Límites de esta evidencia

No se ha repetido un port completo a través de esta MCP. La prueba de empaquetado sintética no comprueba jugabilidad ni instalación interactiva del juego. La confirmación humana histórica del perfil corresponde al flujo manual anterior. La revisión upstream alternativa sigue sin probarse localmente.

Decisiones: recuperación de checkout parcial manual o con espacio nuevo, documentada para evitar resets; herramientas externas de confianza ejecutadas con permisos del usuario; red controlada por el flujo y no mediante aislamiento del sistema. No hay hallazgos menores diferidos de la revisión.

No se guardan aquí los archivos de juego ni registros con rutas personales.
