# Frontend

Este directorio contiene todo el código estático y dinámico utilizado para renderizar la interfaz gráfica de usuario. Al utilizar `pywebview`, el stack es de tecnologías web estándar.

## Archivos Principales

- `index.html`: La vista única principal de la aplicación con la estructura de layout semántico.
- `app.js`: La lógica central de UI. Maneja las ventanas, navegación por pestañas (`switchTab`), el *bucle* de dibujado del video al canvas local leyendo de `window.pywebview.api`, y las interacciones de los botones de la interfaz clínica.
- `index.css`: El sistema de diseño y hoja de estilos Vainilla CSS, respetando estéticas minimalistas pediátricas, un tema oscuro-elegante y diseños responsivos.
