# Domain

Esta carpeta define las estructuras de datos y modelos del dominio del negocio.

- `models.py` u objetos como `Patient`, `Session`, `Item`, y enums asociados (`DomainType`, `ItemCode`).
- Estos modelos se usan a través de toda la aplicación, manteniendo el código libre de dependencias a una base de datos específica o la interfaz de usuario.
