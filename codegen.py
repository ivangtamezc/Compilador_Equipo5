from lark import Tree, Token


class CodeGenerator:
    def __init__(self, tree):
        self.tree = tree
        self._quads = []
        self._temp_count = 0
        self._label_count = 0
        # tabla de procedimientos: nombre -> {'label': L_func, 'params': [nombres]}
        # se usa para resolver llamadas y para que el evaluator pueda saltar al cuerpo
        self.proc_table = {}

    def generate(self):
        self._quads.clear()
        self._temp_count = 0
        self._label_count = 0
        self.proc_table.clear()
        self._gen_program(self.tree)
        return self._quads

    # ── helpers ─────────────────────────────────────────────────────────────

    def _new_temp(self):
        self._temp_count += 1
        return f"t{self._temp_count}"

    def _new_label(self):
        self._label_count += 1
        return f"L{self._label_count}"

    def _emit(self, op, arg1, arg2, result):
        self._quads.append((str(op), str(arg1), str(arg2), str(result)))

    # ── recorrido principal del programa ────────────────────────────────────

    def _gen_program(self, root):
        # root: start -> program; program: ID, var_section, proc_section, statement
        program = root.children[0]  # nodo 'program'

        proc_section = None
        statement = None
        for c in program.children:
            if isinstance(c, Tree):
                if c.data == "proc_section":
                    proc_section = c
                elif c.data == "statement":
                    statement = c
        # var_section no genera código (las variables se crean al asignarse)

        # 1) Saltamos por encima de los cuerpos de procedimientos para llegar al main
        l_main = self._new_label()
        self._emit("goto", "_", "_", l_main)

        # 2) Emitimos los cuerpos de los procedimientos
        if proc_section is not None:
            for child in proc_section.children:
                if isinstance(child, Tree) and child.data == "procedure":
                    self._gen_procedure(child)

        # 3) Etiqueta de inicio del main + cuerpo del main
        self._emit("label", l_main, "_", "_")
        if statement is not None:
            self._exec(statement)
        # marcamos el final con un halt explícito para el evaluator
        self._emit("halt", "_", "_", "_")

    def _gen_procedure(self, node):
        # node.children: Token(ID), [Tree(param_list)], Tree(stmt_block)
        name = str(node.children[0])
        l_func = self._new_label()
        params = []
        body = None
        for c in node.children[1:]:
            if isinstance(c, Tree):
                if c.data == "param_list":
                    for p in c.children:
                        if isinstance(p, Tree) and p.data == "param":
                            params.append(str(p.children[0]))
                elif c.data == "stmt_block":
                    body = c

        # registramos el procedimiento en la tabla
        self.proc_table[name] = {"label": l_func, "params": params}

        # emitimos la etiqueta de entrada al procedimiento
        self._emit("label", l_func, "_", "_")
        # los parámetros se reciben en orden inverso al pop de la pila
        # (cada call hace param p1, param p2, ..., y al entrar el callee los desempila)
        for p in params:
            self._emit("recv_param", "_", "_", p)
        # cuerpo del procedimiento
        if body is not None:
            self._exec(body)
        # si no hay return explícito, regresamos sin valor
        self._emit("return", "_", "_", "_")

    # ── dispatch de statements ──────────────────────────────────────────────

    def _exec(self, node):
        if isinstance(node, Token):
            return
        handler = getattr(self, f"_exec_{node.data}", None)
        if handler:
            handler(node)
        else:
            for child in node.children:
                if isinstance(child, Tree):
                    self._exec(child)

    # ── dispatch de expresiones (regresa nombre/valor del resultado) ────────

    def _gen(self, node):
        if isinstance(node, Token):
            return str(node)
        handler = getattr(self, f"_gen_{node.data}", None)
        if handler:
            return handler(node)
        last = "_"
        for child in node.children:
            if isinstance(child, Tree):
                last = self._gen(child)
        return last

    # ── statements ──────────────────────────────────────────────────────────

    def _exec_assignment(self, node):
        name = str(node.children[0])
        val = self._gen(node.children[1])
        self._emit(":=", val, "_", name)

    def _exec_increment(self, node):
        name = str(node.children[0])
        op = str(node.children[1])  # "++" o "--"
        self._emit(op, name, "_", name)

    def _exec_write_stmt(self, node):
        for child in node.children:
            if isinstance(child, Tree):
                val = self._gen(child)
                self._emit("write", val, "_", "_")

    def _exec_return_stmt(self, node):
        val = self._gen(node.children[0])
        self._emit("return", val, "_", "_")

    # las llamadas a procedimiento como statement se manejan emitiendo el call
    # y descartando el resultado (los temporales emitidos quedan disponibles si se quieren usar)
    def _exec_proc_call(self, node):
        self._gen_proc_call(node)

    def _exec_if_stmt(self, node):
        cond = self._gen(node.children[0])
        has_else = len(node.children) == 3

        l_false = self._new_label()
        self._emit("if_false", cond, "_", l_false)
        self._exec(node.children[1])

        if has_else:
            l_end = self._new_label()
            self._emit("goto", "_", "_", l_end)
            self._emit("label", l_false, "_", "_")
            self._exec(node.children[2])
            self._emit("label", l_end, "_", "_")
        else:
            self._emit("label", l_false, "_", "_")

    def _exec_while_stmt(self, node):
        l_start = self._new_label()
        l_end = self._new_label()
        self._emit("label", l_start, "_", "_")
        cond = self._gen(node.children[0])
        self._emit("if_false", cond, "_", l_end)
        self._exec(node.children[1])
        self._emit("goto", "_", "_", l_start)
        self._emit("label", l_end, "_", "_")

    def _exec_for_stmt(self, node):
        self._exec(node.children[0])  # for_init
        l_start = self._new_label()
        l_end = self._new_label()
        self._emit("label", l_start, "_", "_")
        cond = self._gen(node.children[1])
        self._emit("if_false", cond, "_", l_end)
        self._exec(node.children[3])  # body
        self._exec(node.children[2])  # update
        self._emit("goto", "_", "_", l_start)
        self._emit("label", l_end, "_", "_")

    def _exec_for_init(self, node):
        name = str(node.children[0])
        val = self._gen(node.children[1])
        self._emit(":=", val, "_", name)

    # ── generación de expresiones ───────────────────────────────────────────

    def _gen_expr_or(self, node):
        trees = [c for c in node.children if isinstance(c, Tree)]
        if len(trees) == 1:
            return self._gen(trees[0])
        result = self._gen(trees[0])
        for tree in trees[1:]:
            right = self._gen(tree)
            temp = self._new_temp()
            self._emit("or", result, right, temp)
            result = temp
        return result

    def _gen_expr_and(self, node):
        trees = [c for c in node.children if isinstance(c, Tree)]
        if len(trees) == 1:
            return self._gen(trees[0])
        result = self._gen(trees[0])
        for tree in trees[1:]:
            right = self._gen(tree)
            temp = self._new_temp()
            self._emit("and", result, right, temp)
            result = temp
        return result

    def _gen_expr_not(self, node):
        child = node.children[0]
        val = self._gen(child)
        if isinstance(child, Tree) and child.data == "expr_not":
            temp = self._new_temp()
            self._emit("not", val, "_", temp)
            return temp
        return val

    def _gen_expr_rel(self, node):
        # con '?' en la regla, si llegamos aquí siempre hay 2 operandos
        trees = [c for c in node.children if isinstance(c, Tree)]
        if len(trees) == 1:
            return self._gen(trees[0])
        left = self._gen(trees[0])
        # REL_OP es un Token y NO está en 'trees'; lo buscamos directo en children
        op = None
        for c in node.children:
            if isinstance(c, Token) and c.type == "REL_OP":
                op = str(c)
                break
        right = self._gen(trees[1])
        temp = self._new_temp()
        self._emit(op, left, right, temp)
        return temp

    def _gen_expr_add(self, node):
        result = None
        pending_op = None
        for child in node.children:
            if isinstance(child, Tree):
                val = self._gen(child)
                if result is None:
                    result = val
                else:
                    temp = self._new_temp()
                    self._emit(pending_op, result, val, temp)
                    result = temp
            elif isinstance(child, Token) and child.type == "ADD_OP":
                pending_op = str(child)
        return result or "_"

    def _gen_expr_mult(self, node):
        result = None
        pending_op = None
        for child in node.children:
            if isinstance(child, Tree):
                val = self._gen(child)
                if result is None:
                    result = val
                else:
                    temp = self._new_temp()
                    self._emit(pending_op, result, val, temp)
                    result = temp
            elif isinstance(child, Token) and child.type == "MUL_OP":
                pending_op = str(child)
        return result or "_"

    def _gen_factor(self, node):
        if not node.children:
            return "_"
        child = node.children[0]
        if isinstance(child, Token):
            # NUMBER, FLOAT, STRING, ID, BOOL_LIT
            return str(child)
        if isinstance(child, Tree):
            if child.data == "proc_call":
                return self._gen_proc_call(child)
            # cualquier sub-expresión: delegamos (paréntesis caen aquí)
            return self._gen(child)
        return "_"

    # handler para el menos unario (nodo 'neg' creado por "-" factor -> neg)
    def _gen_neg(self, node):
        inner = self._gen(node.children[0])
        temp = self._new_temp()
        self._emit("neg", inner, "_", temp)
        return temp

    def _gen_proc_call(self, node):
        # node.children: Token(ID), [Tree(arg_list)]
        func_name = str(node.children[0])
        args = []
        for child in node.children:
            if isinstance(child, Tree) and child.data == "arg_list":
                for expr in child.children:
                    if isinstance(expr, Tree) or isinstance(expr, Token):
                        args.append(self._gen(expr))
        # empujamos los argumentos en orden a la pila de parámetros
        for arg in args:
            self._emit("param", arg, "_", "_")
        # call con un temporal para recibir el valor de retorno (si hay)
        temp = self._new_temp()
        self._emit("call", func_name, str(len(args)), temp)
        return temp
