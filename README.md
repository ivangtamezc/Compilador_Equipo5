# Compilador_Equipo5

**Materia:** Compiladores  
**Equipo 5:**  
- Ivan Gerardo Tamez Cavazos  
- Marco Antonio Lucio Sosa  

## Descripción
Compilador desarrollado en Python usando la librería Lark que implementa 
las 4 etapas clásicas de un compilador:

1. **Análisis Léxico y Sintáctico** — `lexer_parser.py` + `grammar.lark`
2. **Análisis Semántico** — `semantic.py`
3. **Generación de Código Intermedio** — `codegen.py` (cuádruplos)
4. **Evaluación** — `evaluator.py`

## Requisitos
- Python 3.8+
- Lark

Instalar dependencias:
```
pip install lark
```

## Uso
```
python main.py <archivo.txt>
```

Ejemplos:
```
python main.py tests/pruebaWhile.txt
python main.py tests/pruebaIf.txt
python main.py tests/pruebaFor.txt
python main.py tests/pruebaErrores.txt
```

## Estructura del proyecto
```
Compilador_Equipo5/
├── main.py              ← Punto de entrada
├── grammar.lark         ← Gramática formal del lenguaje
├── lexer_parser.py      ← Análisis léxico y sintáctico con Lark
├── semantic.py          ← Verificación de tipos y variables
├── codegen.py           ← Generación de cuádruplos
├── evaluator.py         ← Ejecución del código intermedio
└── tests/
    ├── pruebaWhile.txt  ← Factorial con while (resultado: 120)
    ├── pruebaIf.txt     ← Condicionales anidados
    ├── pruebaFor.txt    ← Factorial con for (resultado: 24)
    └── pruebaErrores.txt ← Error semántico intencional (and con int)
```

## Lenguaje soportado
- Tipos: `int`, `float`, `string`, `bool`
- Operadores aritméticos: `+` `-` `*` `/` `%`
- Operadores relacionales: `>` `<` `>=` `<=` `==` `!=`
- Operadores lógicos: `and` `or` `not`
- Estructuras de control: `if` / `if-else`
- Ciclos: `while`, `for` estilo C
- Incremento/decremento: `i++` / `i--`
- Salida: `write()`

## Salida del compilador
Para cada archivo el compilador muestra 4 secciones:

```
=== Árbol Sintáctico ===
(árbol generado por Lark)

=== Análisis Semántico ===
OK  ó  lista de errores encontrados

=== Código Intermedio (Cuádruplos) ===
[ 0]  ( write , "factorial while" , _ , _ )
[ 1]  ( :=    ,                 5 , _ , n )
...

=== Resultado ===
factorial while
120
```
