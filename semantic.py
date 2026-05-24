from lark import Tree, Token


class SemanticError:
    def __init__(self, message, line=None, column=None):
        self.message = message
        self.line = line
        self.column = column

    def __str__(self):
        if self.line is not None:
            return f"Error semántico [línea {self.line}, col {self.column}]: {self.message}"
        return f"Error semántico: {self.message}"


# representa la firma de un procedimiento declarado:
# - name:   nombre del procedimiento
# - params: lista de tuplas (nombre_param, tipo_param), en orden de declaración
class ProcSignature:
    def __init__(self, name, params):
        self.name = name
        # params: lista de tuplas (nombre, tipo, token_id) — token puede ser None
        self.params = params

    @property
    def param_types(self):
        return [p[1] for p in self.params]


# clase encargada de validar la semántica del programa:
# tipos en operaciones, declaraciones, scopes, llamadas a procedimientos, etc.
class SemanticAnalyzer:
    def __init__(self, tree):
        self.tree = tree
        self.errors = []
        # pila de scopes, cada scope es un dict {nombre: tipo}
        # scopes[0] = scope global (variables del programa)
        self.scopes = [{}]
        # tabla de procedimientos: {nombre: ProcSignature}
        self.proc_table = {}
        # nombre del procedimiento actual (None si estamos en main/begin)
        self.current_proc = None

    def analyze(self):
        self.errors.clear()
        self.scopes = [{}]
        self.proc_table.clear()
        self.current_proc = None
        self._visit(self.tree)
        return self.errors

    # ── manejo de scopes ────────────────────────────────────────────────────

    def _push_scope(self):
        self.scopes.append({})

    def _pop_scope(self):
        self.scopes.pop()

    def _declare(self, name, type_, tok=None):
        """Declara una variable en el scope actual. Reporta error si ya existe."""
        if name in self.scopes[-1]:
            self._add_error(f"Variable '{name}' declarada más de una vez", tok)
            return False
        self.scopes[-1][name] = type_
        return True

    def _lookup(self, name):
        """Busca una variable recorriendo la pila de scopes desde el más interno."""
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    # métodos principales

    # método principal de visiteo
    # recursivamente visita cada nodo del AST y a través de getattr realiza el análisis semántico
    # necesario específico para el nodo
    def _visit(self, node):
        # si no tenemos nada definido en la grámatica para ese token
        if isinstance(node, Token):
            return
        # getattr es un método de conveniencia para encontrar el método particular del nodo pasado
        # es decir, si el nodo es "program", handler se volverá una referencia al método _v_program
        # si no existe, devuelve None
        handler = getattr(self, f"_v_{node.data}", None)
        if handler:
            handler(node)
        else:
            # no hay handler para este tipo de nodo (típicamente nodos envoltorio
            # como stmt_block, stmt, block, etc.); recorremos sus hijos
            # recursivamente para llegar a nodos que sí tengan handler.
            for child in node.children:
                if isinstance(child, Tree):
                    self._visit(child)

    # método para inferir el resultado esperado de una expresión al ser ejecutada
    # permite métodos comparar el tipo de resultado obtenido con el tipo de resultado esperado
    def _infer(self, node):
        if isinstance(node, Token):
            return self._infer_token(node)
        # consigue la función infer en base al nombre del nodo
        handler = getattr(self, f"_infer_{node.data}", None)
        if handler:
            return handler(node)
        # si no tenemos un handler definido, revisamos a sus hijos
        for child in node.children:
            if isinstance(child, Tree):
                self._infer(child)
        return "unknown"

    # método de conveniencia para estandarizar errores
    def _add_error(self, msg, node=None):
        line = col = None
        if isinstance(node, Token):
            line, col = node.line, node.column
        elif isinstance(node, Tree):
            line = getattr(node.meta, "line", None)
            col = getattr(node.meta, "column", None)
        self.errors.append(SemanticError(msg, line, col))

    # utilidades de tipos 
    # para evitar reduncia al estar checando!!

    def _is_numeric(self, t):
        return t in ("int", "float")

    def _numeric_result(self, types):
        valid = [t for t in types if t != "unknown"]
        if not valid:
            return "unknown"
        return "float" if "float" in valid else "int"

    def _assign_compatible(self, decl_type, expr_type):
        if expr_type == "unknown":
            return True
        if decl_type in ("int", "float") and expr_type in ("int", "float"):
            return True
        return decl_type == expr_type


    def _resolve_type(self, type_node):
        # type_of tiene un único hijo Token (TYPE) con el valor del tipo
        for child in type_node.children:
            if isinstance(child, Token):
                return child.value
        return "unknown"

    # ── recorrido del programa ──────────────────────────────────────────────

    def _v_program(self, node):
        # paso 1: recopila todas las variables del programa, al menos en ese nivel
        for child in node.children:
            if isinstance(child, Tree) and child.data == "var_section":
                self._visit(child)

        # paso 2: recopilar las firmas de procedimientos (nombre del metodo y argumentos) antes de visitar sus cuerpos
        # esto permite que un procedimiento pueda llamar a otro definido más adelante
        for child in node.children:
            if isinstance(child, Tree) and child.data == "proc_section":
                self._collect_proc_signatures(child)

        # paso 3: recorrer el contenido de los procedimientos (ya con todas las firmas (métodos y sus atributos) conocidas)
        for child in node.children:
            if isinstance(child, Tree) and child.data == "proc_section":
                self._visit(child)

        # paso 4: visitar el bloque principal (begin...end) una vez que se tenga todo lo anterior
        for child in node.children:
            if isinstance(child, Tree) and child.data == "statement":
                self._visit(child)

    # método de conveniencia para recorrer y registar los procedures como firmas 
    def _collect_proc_signatures(self, proc_section_node):
        for child in proc_section_node.children:
            if isinstance(child, Tree) and child.data == "procedure":
                self._register_procedure(child)

    # método de conveniencia para registrar 
    def _register_procedure(self, proc_node):
        # children: Token(ID), [Tree(param_list)], Tree(stmt_block)
        id_tok = proc_node.children[0]
        name = str(id_tok)

        if name in self.proc_table:
            self._add_error(f"Procedimiento '{name}' declarado más de una vez", id_tok)
            return

        params = []  # tuplas (nombre, tipo, token_id) para preservar la posición
        for child in proc_node.children[1:]:
            if isinstance(child, Tree) and child.data == "param_list":
                for param_node in child.children:
                    if isinstance(param_node, Tree) and param_node.data == "param":
                        # param: Token(ID), Tree(type_of)
                        ptok = param_node.children[0]
                        pname = str(ptok)
                        ptype = self._resolve_type(param_node.children[1])
                        params.append((pname, ptype, ptok))

        self.proc_table[name] = ProcSignature(name, params)

    # ── declaraciones ───────────────────────────────────────────────────────

    def _v_var_decl(self, node):
        # children: ID+ ... type_of (último hijo)
        type_node = node.children[-1]
        type_name = self._resolve_type(type_node)
        for child in node.children[:-1]:
            if isinstance(child, Token):
                self._declare(str(child), type_name, child)

    def _v_procedure(self, node):
        # children: Token(ID), [Tree(param_list)], Tree(stmt_block)
        id_tok = node.children[0]
        name = str(id_tok)

        # abrimos un scope para el cuerpo del procedimiento
        self._push_scope()
        prev_proc = self.current_proc
        self.current_proc = name

        # declaramos los parámetros como variables locales
        # (ya tenemos la firma en proc_table, la reutilizamos)
        sig = self.proc_table.get(name)
        if sig is not None:
            for ptuple in sig.params:
                pname, ptype, ptok = ptuple
                self._declare(pname, ptype, ptok)

        # visitamos el cuerpo del procedimiento
        for child in node.children[1:]:
            if isinstance(child, Tree) and child.data == "stmt_block":
                self._visit(child)

        # cerramos el scope al salir
        self.current_proc = prev_proc
        self._pop_scope()

    # ── statements ──────────────────────────────────────────────────────────

    def _v_assignment(self, node):
        # children: Token(ID), Tree(expr)
        id_tok = node.children[0]
        expr_node = node.children[1]
        name = str(id_tok)
        decl_type = self._lookup(name)
        if decl_type is None:
            self._add_error(f"Variable '{name}' usada sin declarar", id_tok)
            self._infer(expr_node)
            return
        expr_type = self._infer(expr_node)
        if not self._assign_compatible(decl_type, expr_type):
            self._add_error(
                f"Asignación de tipo incorrecto a '{name}': "
                f"se esperaba '{decl_type}', se obtuvo '{expr_type}'",
                id_tok,
            )

    def _v_increment(self, node):
        # children: Token(ID), Token(INCR_OP)
        id_tok = node.children[0]
        name = str(id_tok)
        decl_type = self._lookup(name)
        if decl_type is None:
            self._add_error(f"Variable '{name}' usada sin declarar", id_tok)
            return
        if not self._is_numeric(decl_type):
            self._add_error(
                f"Incremento/decremento sobre variable no numérica '{name}' (tipo '{decl_type}')",
                id_tok,
            )

    def _v_if_stmt(self, node):
        cond = node.children[0]
        cond_type = self._infer(cond)
        if cond_type not in ("bool", "unknown"):
            self._add_error(
                f"La condición del 'if' debe ser booleana, se obtuvo '{cond_type}'",
                cond,
            )
        for child in node.children[1:]:
            if isinstance(child, Tree):
                self._visit(child)

    def _v_while_stmt(self, node):
        cond = node.children[0]
        cond_type = self._infer(cond)
        if cond_type not in ("bool", "unknown"):
            self._add_error(
                f"La condición del 'while' debe ser booleana, se obtuvo '{cond_type}'",
                cond,
            )
        for child in node.children[1:]:
            if isinstance(child, Tree):
                self._visit(child)

    def _v_for_stmt(self, node):
        self._visit(node.children[0])
        cond = node.children[1]
        cond_type = self._infer(cond)
        if cond_type not in ("bool", "unknown"):
            self._add_error(
                f"La condición del 'for' debe ser booleana, se obtuvo '{cond_type}'",
                cond,
            )
        self._visit(node.children[2])
        self._visit(node.children[3])

    def _v_for_init(self, node):
        id_tok = node.children[0]
        expr_node = node.children[1]
        name = str(id_tok)
        decl_type = self._lookup(name)
        if decl_type is None:
            self._add_error(f"Variable '{name}' usada sin declarar", id_tok)
            self._infer(expr_node)
            return
        expr_type = self._infer(expr_node)
        if not self._assign_compatible(decl_type, expr_type):
            self._add_error(
                f"Tipo incorrecto en inicialización del 'for' a '{name}': "
                f"se esperaba '{decl_type}', se obtuvo '{expr_type}'",
                id_tok,
            )

    def _v_write_stmt(self, node):
        for child in node.children:
            if isinstance(child, Tree):
                self._infer(child)

    def _v_return_stmt(self, node):
        # validamos la expresión y reportamos si se usa return fuera de un procedimiento
        if self.current_proc is None:
            self._add_error("Sentencia 'return' fuera de un procedimiento", node)
        for child in node.children:
            if isinstance(child, Tree):
                self._infer(child)

    def _v_proc_call(self, node):
        # children: Token(ID), [Tree(arg_list)]
        id_tok = node.children[0]
        name = str(id_tok)

        # capturamos los tipos de los argumentos (en orden)
        arg_types = []
        arg_nodes = []
        for child in node.children[1:]:
            if isinstance(child, Tree) and child.data == "arg_list":
                for arg in child.children:
                    if isinstance(arg, Tree) or isinstance(arg, Token):
                        arg_nodes.append(arg)
                        arg_types.append(self._infer(arg))

        # validamos que el procedimiento exista
        sig = self.proc_table.get(name)
        if sig is None:
            self._add_error(f"Procedimiento '{name}' no está declarado", id_tok)
            return

        # validamos número de argumentos
        if len(arg_types) != len(sig.params):
            self._add_error(
                f"Procedimiento '{name}' espera {len(sig.params)} argumento(s), "
                f"se recibió(eron) {len(arg_types)}",
                id_tok,
            )
            return

        # validamos tipos de argumentos uno por uno
        for i, (arg_type, ptuple) in enumerate(zip(arg_types, sig.params), start=1):
            pname, ptype, _ = ptuple
            if not self._assign_compatible(ptype, arg_type):
                self._add_error(
                    f"Argumento #{i} ('{pname}') de '{name}': "
                    f"se esperaba '{ptype}', se obtuvo '{arg_type}'",
                    id_tok,
                )

    # inferencia de tipos en expresiones particulares 

    def _infer_token(self, tok):
        if tok.type == "NUMBER":
            return "int"
        if tok.type == "FLOAT":
            return "float"
        if tok.type == "STRING":
            return "string"
        if tok.type == "ID":
            name = str(tok)
            decl_type = self._lookup(name)
            if decl_type is None:
                self._add_error(f"Variable '{name}' usada sin declarar", tok)
                return "unknown"
            return decl_type
        return "unknown"

    def _infer_expr_or(self, node):
        types = [self._infer(c) for c in node.children if isinstance(c, Tree)]
        if len(types) == 1:
            return types[0]
        for t in types:
            if t not in ("bool", "unknown"):
                self._add_error(
                    f"El operador 'or' requiere operandos booleanos, se obtuvo '{t}'",
                    node,
                )
        return "bool"

    def _infer_expr_and(self, node):
        types = [self._infer(c) for c in node.children if isinstance(c, Tree)]
        if len(types) == 1:
            return types[0]
        for t in types:
            if t not in ("bool", "unknown"):
                self._add_error(
                    f"El operador 'and' requiere operandos booleanos, se obtuvo '{t}'",
                    node,
                )
        return "bool"

    def _infer_expr_not(self, node):
        child = node.children[0]
        t = self._infer(child)
        if isinstance(child, Tree) and child.data == "expr_not":
            if t not in ("bool", "unknown"):
                self._add_error(
                    f"El operador 'not' requiere un operando booleano, se obtuvo '{t}'",
                    node,
                )
            return "bool"
        return t

    def _infer_expr_rel(self, node):
        # con '?' en la regla, si llegamos aquí siempre hay dos operandos
        trees = [c for c in node.children if isinstance(c, Tree)]
        left = self._infer(trees[0])
        right = self._infer(trees[1])
        if left != "unknown" and right != "unknown":
            if self._is_numeric(left) != self._is_numeric(right):
                self._add_error(
                    f"Tipos incompatibles en operación relacional: '{left}' vs '{right}'",
                    node,
                )
        return "bool"

    def _infer_expr_add(self, node):
        trees = [c for c in node.children if isinstance(c, Tree)]
        if len(trees) == 1:
            return self._infer(trees[0])
        types = [self._infer(t) for t in trees]
        for t in types:
            if t not in ("int", "float", "unknown"):
                self._add_error(
                    f"Operación aritmética (+/-) sobre tipo no numérico '{t}'", node
                )
        return self._numeric_result(types)

    def _infer_expr_mult(self, node):
        trees = [c for c in node.children if isinstance(c, Tree)]
        if len(trees) == 1:
            return self._infer(trees[0])
        types = [self._infer(t) for t in trees]
        for t in types:
            if t not in ("int", "float", "unknown"):
                self._add_error(
                    f"Operación aritmética (*//%) sobre tipo no numérico '{t}'", node
                )
        return self._numeric_result(types)

    def _infer_neg(self, node):
        # children: [Tree(factor)] -- el "-" es literal anónimo, se filtra
        t = self._infer(node.children[0])
        if t not in ("int", "float", "unknown"):
            self._add_error(
                f"Operador unario '-' sobre tipo no numérico '{t}'", node
            )
        return t if self._is_numeric(t) else "unknown"

    def _infer_factor(self, node):
        if not node.children:
            return "unknown"
        child = node.children[0]
        if isinstance(child, Token):
            if child.type == "BOOL_LIT":
                return "bool"
            return self._infer_token(child)
        if isinstance(child, Tree):
            if child.data == "proc_call":
                # validamos la llamada (existencia, # de args, tipos) y devolvemos
                # 'unknown' porque sin declaración de tipo de retorno no sabemos qué regresa
                self._v_proc_call(child)
                return "unknown"
            # cualquier sub-expresión (por paréntesis): delegamos
            return self._infer(child)
        return "unknown"