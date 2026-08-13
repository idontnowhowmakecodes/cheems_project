# Activities

Este módulo contiene la lógica específica que orquesta el flujo de actividades o ítems de los distintos protocolos de evaluación (ADOS-2, STAT).

## Estructura

- `session_manager.py`: (U otros archivos similares) Contienen la lógica para definir qué ítems se evaluarán secuencialmente y qué instrucciones o reglas se aplican a cada paso.
- Define qué dominios (Juego, Interacción, etc.) se activan en cada actividad, y cómo la sesión en su totalidad avanza ítem por ítem hasta finalizar.
