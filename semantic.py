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

# clase encargada de validar los tipos dentro de las operaciones
# revisa que no se hagan operaciones inválidas entre tipos, como la multiplación de una variable tipo string
class SemanticAnalyzer:
    def __init__(self, tree):
        self.tree = tree
        self.errors = []
        self.symbol_table = {}  # name -> type_str

    def analyze(self):
        self.errors.clear()
        self.symbol_table.clear()
        self._visit(self.tree)
        return self.errors

    # ── dispatch ────────────────────────────────────────────────────────────

    def _visit(self, node):
        if isinstance(node, Token):
            return
        handler = getattr(self, f"_v_{node.data}", None)
        if handler:
            handler(node)
        else:
            for child in node.children:
                if isinstance(child, Tree):
                    self._visit(child)

    def _infer(self, node):
        """Return the inferred type string of an expression node."""
        if isinstance(node, Token):
            return self._infer_token(node)
        handler = getattr(self, f"_infer_{node.data}", None)
        if handler:
            return handler(node)
        for child in node.children:
            if isinstance(child, Tree):
                self._infer(child)
        return "unknown"

    def _add_error(self, msg, node=None):
        line = col = None
        if isinstance(node, Token):
            line, col = node.line, node.column
        elif isinstance(node, Tree):
            line = getattr(node.meta, "line", None)
            col = getattr(node.meta, "column", None)
        self.errors.append(SemanticError(msg, line, col))

    # ── type utilities ──────────────────────────────────────────────────────

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

    # ── declarations ────────────────────────────────────────────────────────

    def _v_var_decl(self, node):
        # children: ID+ ... type_of (last child)
        type_node = node.children[-1]
        type_name = self._resolve_type(type_node)
        for child in node.children[:-1]:
            if isinstance(child, Token):
                name = str(child)
                if name in self.symbol_table:
                    self._add_error(f"Variable '{name}' declarada más de una vez", child)
                else:
                    self.symbol_table[name] = type_name

    def _resolve_type(self, type_node):
        # type_of has one TYPE token child (grammar uses named terminal TYPE)
        for child in type_node.children:
            if isinstance(child, Token):
                return child.value  # "int", "float", "string", "bool"
        return "unknown"

    # ── statements ──────────────────────────────────────────────────────────

    def _v_assignment(self, node):
        # children: Token(ID), Tree(expr)  — ":=" and ";" are filtered
        id_tok = node.children[0]
        expr_node = node.children[1]
        name = str(id_tok)
        if name not in self.symbol_table:
            self._add_error(f"Variable '{name}' usada sin declarar", id_tok)
            self._infer(expr_node)
            return
        expr_type = self._infer(expr_node)
        decl_type = self.symbol_table[name]
        if not self._assign_compatible(decl_type, expr_type):
            self._add_error(
                f"Asignación de tipo incorrecto a '{name}': "
                f"se esperaba '{decl_type}', se obtuvo '{expr_type}'",
                id_tok,
            )

    def _v_increment(self, node):
        # children: Token(ID)  — "++" / "--" filtered
        id_tok = node.children[0]
        name = str(id_tok)
        if name not in self.symbol_table:
            self._add_error(f"Variable '{name}' usada sin declarar", id_tok)
            return
        t = self.symbol_table[name]
        if not self._is_numeric(t):
            self._add_error(
                f"Incremento/decremento sobre variable no numérica '{name}' (tipo '{t}')",
                id_tok,
            )

    def _v_if_stmt(self, node):
        # children: Tree(expr), Tree(block) [, Tree(block)]
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
        # children: Tree(expr), Tree(block)
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
        # children: for_init, expr (condition), for_update, block
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
        # children: Token(ID), Tree(expr)
        id_tok = node.children[0]
        expr_node = node.children[1]
        name = str(id_tok)
        if name not in self.symbol_table:
            self._add_error(f"Variable '{name}' usada sin declarar", id_tok)
            self._infer(expr_node)
            return
        expr_type = self._infer(expr_node)
        decl_type = self.symbol_table[name]
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
        for child in node.children:
            if isinstance(child, Tree):
                self._infer(child)

    def _v_arg_list(self, node):
        for child in node.children:
            if isinstance(child, Tree):
                self._infer(child)

    # ── expression type inference ────────────────────────────────────────────

    def _infer_token(self, tok):
        if tok.type == "NUMBER":
            return "int"
        if tok.type == "FLOAT":
            return "float"
        if tok.type == "STRING":
            return "string"
        if tok.type == "ID":
            name = str(tok)
            if name not in self.symbol_table:
                self._add_error(f"Variable '{name}' usada sin declarar", tok)
                return "unknown"
            return self.symbol_table[name]
        return "unknown"

    def _infer_expr(self, node):
        return self._infer(node.children[0])

    def _infer_expr_or(self, node):
        # children: expr_and+  ("or" filtered)
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
        # children: expr_not+  ("and" filtered)
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
        # child is Tree(expr_not) → "not" was applied
        # child is Tree(expr_rel)  → passthrough
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
        # children: expr_add  OR  expr_add, op_rel, expr_add
        trees = [c for c in node.children if isinstance(c, Tree)]
        if len(trees) == 1:
            return self._infer(trees[0])
        # trees[0]=expr_add, trees[1]=op_rel, trees[2]=expr_add
        left = self._infer(trees[0])
        right = self._infer(trees[2])
        if left != "unknown" and right != "unknown":
            if self._is_numeric(left) != self._is_numeric(right):
                self._add_error(
                    f"Tipos incompatibles en operación relacional: '{left}' vs '{right}'",
                    node,
                )
        return "bool"

    def _infer_expr_add(self, node):
        # children: expr_mult+  ("+"/"-" filtered)
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
        # children: factor+  ("*"/"/"/"%"  filtered)
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

    def _infer_factor(self, node):
        if not node.children:
            return "bool"   # fallback (shouldn't occur with new grammar)
        child = node.children[0]
        if isinstance(child, Token):
            if child.type == "BOOL_LIT":
                return "bool"
            if child.type == "UMINUS":
                # grammar: UMINUS factor  →  children[1] is Tree(factor)
                t = self._infer(node.children[1])
                if t not in ("int", "float", "unknown"):
                    self._add_error(
                        f"Operador unario '-' sobre tipo no numérico '{t}'", node
                    )
                return t if self._is_numeric(t) else "unknown"
            return self._infer_token(child)   # NUMBER, FLOAT, STRING, ID
        if isinstance(child, Tree):
            if child.data == "expr":
                return self._infer(child)
            if child.data == "proc_call":
                self._visit(child)
                return "unknown"
        return "unknown"

    def _infer_proc_call(self, node):
        self._visit(node)
        return "unknown"
