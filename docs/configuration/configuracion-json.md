# Guía de uso de `configuracion_json`

**Proyecto:** Control Documental  
**Columna:** `configuracion_campos.configuracion_json`  
**Código de referencia:** `app/utils/dynamic_fields.py`, `app/views/gestor_view.py` y `app/views/admin_view.py`.

Esta guía documenta las opciones que aparecen en el código de la aplicación. La columna contiene un objeto JSON que modifica cómo se presenta y valida un campo dinámico. No reemplaza las columnas principales de `ConfiguracionCampos`, como `tipo_input`, `opciones_json`, `llave_jinja`, `tipo_persona` o `regla_validacion`.

## 1. Dónde se configura

En la administración de campos, revisa la columna **Configuración JSON** del campo correspondiente. El valor debe ser un objeto JSON válido: comienza con `{` y termina con `}`. Las claves y los textos deben usar comillas dobles.

Ejemplo mínimo:

```json
{
  "section": "Datos generales",
  "order": 10,
  "help": "Captura la información tal como aparece en el documento.",
  "required": true
}
```

Si no se necesita una opción, es preferible omitirla en lugar de guardar claves con `null`, salvo que exista una razón concreta para conservarlas.

## 2. Opciones generales de presentación y captura

| Clave | Tipo esperado | Función |
|---|---|---|
| `section` | Texto | Agrupa el campo bajo una sección en la interfaz. Si no se indica, el campo se agrupa en `General`. |
| `order` | Número entero recomendado | Ordena el campo dentro de la captura. Los valores menores aparecen antes. Si se omite, se usa el orden de respaldo definido por la aplicación. |
| `help` | Texto | Texto de ayuda que se muestra junto al campo. |
| `required` | Booleano (`true`/`false`) | Marca el campo como requerido para la validación del flujo de paquete. La compuerta del paquete considera los campos requeridos visibles; los valores deben guardarse antes de habilitar el flujo. |
| `default` | Valor compatible con el tipo del campo | Valor inicial de respaldo cuando no existe un valor previo guardado ni un valor en el estado de la sesión. No debe usarse para sobrescribir datos existentes. |

Ejemplo:

```json
{
  "section": "Identificación",
  "order": 20,
  "help": "Usa los datos del documento oficial.",
  "required": true,
  "default": ""
}
```

## 3. Opciones según el tipo de campo

### Texto

| Clave | Tipo | Regla |
|---|---|---|
| `placeholder` | Texto | Texto de ejemplo que aparece dentro del control cuando está vacío. |
| `max_chars` | Entero positivo | Longitud máxima admitida por el control de texto. Debe ser mayor que cero. |

Ejemplo:

```json
{
  "section": "Identificación",
  "order": 10,
  "placeholder": "Ej. ABCD123456...",
  "max_chars": 13
}
```

### Número

| Clave | Tipo | Regla |
|---|---|---|
| `min_value` | Número | Valor mínimo permitido por el control. |
| `max_value` | Número | Valor máximo permitido por el control. |
| `step` | Número positivo | Incremento del control; debe ser mayor que cero. |

Ejemplo:

```json
{
  "min_value": 0,
  "max_value": 100,
  "step": 1
}
```

Si se especifican ambos límites, `min_value` no puede ser mayor que `max_value`. No uses valores booleanos (`true` o `false`) como números.

### Selecciones

Las opciones base del campo se definen en `opciones_json`. Para variar las opciones disponibles según el valor de otro campo, usa `options_map` en `configuracion_json`.

Tipos de campo de selección admitidos por la lógica dinámica:
- `Opciones`
- `Selección única`
- `Selección múltiple`

Ejemplo de opciones dependientes:

```json
{
  "options_map": {
    "depends_on": "tipo_persona",
    "map": {
      "Fisica": ["CURP", "Identificación oficial"],
      "Moral": ["Acta constitutiva", "Poder notarial"]
    }
  }
}
```

Interpretación:
- `depends_on`: llave del campo del que depende la lista.
- `map`: objeto cuyas claves son los valores posibles del campo padre.
- Cada valor del mapa debe ser una lista de opciones escalares (por ejemplo, textos o números).
- Si el valor del campo padre no tiene una entrada en el mapa, la lista dependiente queda vacía.
- Al guardar, el servidor valida que la selección enviada pertenezca a las opciones permitidas para el valor actual del campo padre.
- `options_map` solo se admite en campos de selección, no en texto, fecha, número o casilla.

Asegúrate de que `depends_on` coincide exactamente con la `llave_jinja` del campo padre.

## 4. Visibilidad condicional con `visible_if`

Usa `visible_if` para mostrar un campo solo cuando otro campo tiene un valor determinado.

Ejemplo:

```json
{
  "visible_if": {
    "field": "nacionalidad",
    "equals": "Extranjera"
  }
}
```

- `field`: `llave_jinja` del campo que controla la visibilidad.
- `equals`: valor que debe tener el campo controlador.
- La comparación es por igualdad. Si el valor actual del campo controlador es una lista, la condición se cumple cuando contiene el valor esperado.
- La configuración debe incluir tanto `field` como `equals`.

Ejemplo combinado:

```json
{
  "section": "Datos adicionales",
  "order": 40,
  "help": "Solo se solicita para personas extranjeras.",
  "required": true,
  "visible_if": {
    "field": "nacionalidad",
    "equals": "Extranjera"
  }
}
```

**Importante:** ocultar un campo no debe borrar su valor guardado. La aplicación combina los valores enviados con los existentes para conservar los campos que no aparecen en el formulario visible. La compuerta del paquete también debe evaluar los campos requeridos según su visibilidad.

## 5. Diferencia entre configuración de campos y configuración de evidencias

No confundas estas dos columnas:

- `configuracion_campos.configuracion_json`: controla presentación, valores iniciales, restricciones de entrada, visibilidad y opciones dependientes de campos dinámicos.
- `configuracion_evidencias.configuracion_json`: contiene configuración de evidencias. El código de la vista Gestor lee la clave opcional `vigencia` y muestra su valor como días cuando es numérico.

Ejemplo de configuración de evidencia:

```json
{
  "vigencia": 30
}
```

**Límite conocido:** que la interfaz muestre `vigencia: 30` no demuestra por sí solo que exista una regla automática que bloquee documentos vencidos o calcule una fecha de expiración. No asumas esa capacidad sin verificar la implementación y sus pruebas.

## 6. Tipos de campo reconocidos

La lógica de configuración reconoce estos valores de `tipo_input`:

- `Texto`
- `Fecha`
- `Número`
- `Opciones`
- `Selección única`
- `Selección múltiple`
- `Casilla`

Los nombres deben coincidir exactamente con los valores que admite la aplicación. La configuración específica de texto se valida para `Texto`; `min_value`, `max_value` y `step` se validan para `Número`; `options_map` se limita a los tipos de selección.

## 7. Errores comunes

- Usar comillas simples en JSON: `{'required': True}` no es JSON válido.
- Escribir `True`/`False` en lugar de `true`/`false`.
- Usar una coma final después del último elemento.
- Configurar `max_chars` con cero, un número negativo, texto o un booleano.
- Configurar `step` en cero o negativo.
- Configurar `min_value` por encima de `max_value`.
- Usar `options_map` en un campo que no sea de selección.
- Omitir `field` o `equals` en `visible_if`.
- Referir en `visible_if.field` u `options_map.depends_on` un nombre que no coincide con la `llave_jinja` del campo controlador.
- Esperar que `default` reemplace un valor previamente capturado.
- Suponer que `required` por sí solo garantiza que el formulario no pueda guardarse vacío en cualquier ruta. En el flujo actual, la compuerta del paquete verifica los campos requeridos visibles; confirma el comportamiento concreto antes de cambiarlo.

## 8. Lista de comprobación

Antes de guardar una configuración:

1. Confirma que el JSON es válido y es un objeto.
2. Comprueba que cada clave es compatible con el tipo del campo.
3. Verifica las llaves de los campos controladores y que sus valores coincidan exactamente con las opciones reales.
4. Prueba tanto la condición verdadera como la falsa de `visible_if`.
5. Cambia el campo padre de un `options_map` y verifica que cambien las opciones disponibles.
6. Comprueba que el servidor rechace una opción dependiente que ya no esté permitida.
7. Guarda un valor, oculta el campo condicional y confirma que el valor previo se conserva.
8. Comprueba el flujo de campos requeridos visibles y que el paquete solo se habilite después de guardar los datos requeridos.
9. Revisa el documento generado para confirmar que refleja los valores guardados.
10. Ejecuta pruebas con datos de prueba, no con información productiva.

## 9. Referencias del repositorio

- `app/utils/dynamic_fields.py`: validación e interpretación de opciones JSON, visibilidad condicional, opciones dependientes y combinación de valores.
- `app/views/gestor_view.py`: agrupación y orden de campos, valores iniciales, ayuda, validación requerida y visualización de vigencia de evidencias.
- `app/views/admin_view.py`: administración y presentación de la configuración JSON.
- `scripts/seed_db.py`: ejemplos de configuración base.
- `scripts/seed_json_tests.py`: registros de prueba para variaciones JSON.
- `tests/test_dynamic_fields.py` y `tests/test_seed_json_tests.py`: pruebas automatizadas relacionadas.

Al modificar estas capacidades, consulta el código y las pruebas actuales. Esta guía explica el comportamiento documentado en el repositorio; no sustituye la verificación de una implementación nueva.


## 10. Plantillas de documentos: Jinja

La configuración JSON del campo y la plantilla Jinja cumplen funciones distintas:

- `configuracion_json` configura el formulario de captura.
- La plantilla Word o Excel usa expresiones Jinja para colocar los valores guardados en el documento.
- Para insertar un valor, utiliza su `llave_jinja`, respetando exactamente el nombre configurado en el campo.

Ejemplo:

```jinja
Nombre: {{ nombre_completo }}
RFC: {{ rfc }}
```

Las expresiones se evalúan con los valores del contexto de generación del documento. No inventes variables: confirma que la `llave_jinja` existe y que el campo ya tiene el valor que esperas imprimir.

### 10.1 Filtros Jinja integrados

La aplicación crea un entorno `jinja2.Environment()`, por lo que están disponibles los filtros estándar de Jinja2, además de los filtros personalizados descritos más adelante.

| Filtro | Ejemplo | Uso |
|---|---|---|
| `default` | `{{ segundo_nombre | default("", true) }}` | Sustituye un valor indefinido; con el segundo argumento `true`, también sustituye valores falsos o vacíos. |
| `upper` | `{{ nombre | upper }}` | Convierte el texto a mayúsculas. |
| `lower` | `{{ correo | lower }}` | Convierte el texto a minúsculas. |
| `title` | `{{ nombre | title }}` | Convierte el texto a formato de título. |
| `trim` | `{{ domicilio | trim }}` | Elimina espacios al inicio y al final. |
| `replace` | `{{ telefono | replace("-", "") }}` | Reemplaza una cadena por otra. |
| `length` | `{{ documentos | length }}` | Devuelve la longitud de una cadena o colección. |
| `join` | `{{ actividades | join(", ") }}` | Une elementos de una lista con un separador. |
| `round` | `{{ porcentaje | round(2) }}` | Redondea un número. |
| `int`, `float` | `{{ cantidad | int }}` | Convierte un valor numérico cuando sea válido. |

Ejemplo para un dato opcional:

```jinja
Segundo nombre: {{ segundo_nombre | default("No aplica", true) }}
```

Nota: `default` es un filtro integrado de Jinja2; no es la clave JSON `default` descrita en la sección 2. La clave JSON define un valor inicial de captura. El filtro Jinja define cómo representar un valor al generar el documento.

### 10.2 Filtros personalizados de la aplicación

La aplicación registra tres filtros personalizados: `mark`, `mark_not` y `prefix`. Están registrados tanto en el renderizador Word como en el renderizador Excel.

#### `mark`: marcar una coincidencia

Devuelve `X` si el valor coincide con el objetivo; si no coincide, devuelve una cadena vacía por defecto.

```jinja
Mexicana: {{ nacionalidad | mark("Mexicana") }}
Extranjera: {{ nacionalidad | mark("Extranjera") }}
```

Características:
- La comparación no distingue mayúsculas ni acentos: `"Sí"` coincide con `"si"`.
- Acepta listas o tuplas, por ejemplo, para una selección múltiple.
- Si se omite el objetivo, marca un valor verdadero, útil para una casilla booleana.
- Los valores ausentes o en blanco nunca generan una marca, incluso al invertir la comparación.

Parámetros opcionales:

```jinja
{{ estado_civil | mark("Casado/a", mark="✓", default="-") }}
```

- `mark`: símbolo de salida cuando se cumple la condición; por defecto, `"X"`.
- `default`: salida cuando no se cumple la condición; por defecto, `""`.

#### `mark_not` e inversión con `is_not`

`mark_not` es el filtro inverso por compatibilidad: marca cuando el valor no coincide con el objetivo. Para plantillas nuevas también puedes usar `mark(..., is_not=True)`.

```jinja
No mexicana: {{ nacionalidad | mark_not("Mexicana") }}
No mexicana (forma alternativa): {{ nacionalidad | mark("Mexicana", is_not=True) }}
```

Para valores en blanco o ausentes, ambos ejemplos dejan la salida vacía; no los interpretan como una respuesta negativa. `mark_not` admite explícitamente el argumento `is_not` por compatibilidad, pero normalmente no es necesario indicarlo.

Para excluir varias opciones:

```jinja
Otro estado civil: {{ estado_civil | mark_not(["Soltero/a", "Casado/a"]) }}
```

#### `prefix`: prefijo para datos opcionales

Añade un prefijo solo si el valor tiene contenido. Si el valor es ausente o está en blanco, devuelve una cadena vacía.

```jinja
{{ interior | prefix(", interior: ") }}
{{ codigo_postal | prefix("C.P. ") }}
{{ rfc | prefix("RFC: ") }}
```

Este filtro es útil para evitar etiquetas o separadores sin dato, por ejemplo, que aparezca `", interior: "` cuando no se capturó interior.

### 10.3 Condiciones en plantillas Word

En documentos `.docx`, el renderizador usa `docxtpl`. Puedes incluir o excluir texto o párrafos según el valor de un campo. Los controles especiales `{%p ... %}` deben colocarse en párrafos separados; el párrafo que contiene la etiqueta de control se elimina durante el renderizado.

Ejemplo: incluir una aclaración solo para personas extranjeras:

```jinja
{%p if nacionalidad == "Extranjera" %}
La persona presenta documentación migratoria complementaria.
{%p endif %}
```

Ejemplo: mostrar una cláusula solo cuando se capturó una fecha:

```jinja
{%p if fecha_vencimiento %}
La fecha de vencimiento declarada es {{ fecha_vencimiento }}.
{%p endif %}
```

Casos útiles:
- Incluir una cláusula adicional cuando un campo tenga un valor específico.
- Omitir una sección opcional cuando no se capturó información.
- Mostrar una explicación distinta según el tipo de persona, nacionalidad o régimen.
- Condicionar un párrafo a una casilla booleana verdadera.

Usa los valores reales del contexto y las comparaciones que correspondan a su tipo. No uses una condición como sustituto de la validación del formulario: la plantilla decide qué imprime, no si el dato es correcto.

### 10.4 Bucles en plantillas Word

Los bucles sirven cuando el contexto contiene una lista iterable. Un caso habitual es una selección múltiple, cuyo valor puede ser una lista de opciones seleccionadas. No asumas que existen listas de objetos, filas de expedientes u otras colecciones si el contexto de generación no las proporciona.

Para recorrer una lista en un párrafo, coloca las etiquetas de control en párrafos separados:

```jinja
{%p for opcion in actividades %}
- {{ opcion }}
{%p endfor %}
```

Para repetir una fila de una tabla Word, usa las etiquetas especiales `{%tr ... %}` en una fila dedicada:

```jinja
Fila de control: {%tr for opcion in actividades %}
Fila repetida:  {{ opcion }}
Fila de control: {%tr endfor %}
```

En Word, cada etiqueta `{%tr ... %}` debe ir en su propia fila de control; esas filas se eliminan durante el renderizado. La fila intermedia contiene `{{ opcion }}` y se repite por cada elemento. Ajusta la tabla en Word y valida el documento generado, porque el diseño de las filas determina el resultado visual.

Casos útiles:
- Enumerar las opciones seleccionadas en un campo de selección múltiple.
- Repetir una fila por cada elemento de una lista que efectivamente esté presente en el contexto.
- Generar una lista de actividades o documentos cuando la aplicación entregue esos elementos como colección.

### 10.5 Límites del renderizador Excel

El renderizador Excel actual procesa expresiones Jinja dentro de celdas de texto que contienen `{{ ... }}`. Registra los filtros `mark`, `mark_not` y `prefix`, por lo que las expresiones y los filtros anteriores pueden usarse en celdas.

No se debe asumir que Excel admite las mismas estructuras de control que Word: la implementación actual no renderiza el libro completo con `docxtpl` ni procesa bloques `{% if %}` o `{% for %}` para agregar, eliminar o repetir filas. Para Excel, limita la plantilla a expresiones dentro de celdas y verifica que las fórmulas y el formato del libro se conserven.

## 11. Lista de comprobación para plantillas

1. Confirma que cada variable Jinja coincide con una `llave_jinja` existente.
2. Comprueba la salida con un valor normal, un valor vacío y una variable ausente.
3. Prueba `mark` con coincidencia, no coincidencia, diferencias de mayúsculas/acentos y listas cuando corresponda.
4. Comprueba que `mark_not` no marque valores vacíos.
5. Prueba `prefix` con valores presentes y vacíos.
6. Para controles y bucles Word, revisa que las etiquetas `{%p ... %}` y `{%tr ... %}` estén en párrafos o filas separados según corresponda.
7. Genera el documento real y revisa el diseño final; no basta con que la expresión Jinja sea válida.
8. Para Excel, no uses bloques de control ni bucles como si el renderizador Word también se aplicara al libro.
9. Ejecuta las pruebas con datos de prueba, no con información productiva.

## 12. Referencias de implementación Jinja

- `app/utils/template_filters.py`: comportamiento exacto de `mark`, `mark_not` y `prefix`.
- `app/utils/documentos.py`: registro de filtros y diferencias entre los renderizadores Word y Excel.
- `tests/test_template_filters.py`: pruebas de filtros personalizados.
- `tests/test_excel_template_rendering.py`: pruebas de expresiones y filtros en Excel.
- `tests/fixtures/plantilla_pruebas_json.txt`: ejemplos de prueba de campos dinámicos y filtros.
