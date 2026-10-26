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
