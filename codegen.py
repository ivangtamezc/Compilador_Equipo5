from lark import Tree, Token


class CodeGenerator:
    def __init__(self, tree):
        self.tree = tree
        self._quads = []
        self._temp_count = 0
        self._label_count = 0

    def generate(self):
        self._quads.clear()
        self._temp_count = 0
        self._label_count = 0
        self._exec(self.tree)
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

    # ── statement dispatch ───────────────────────────────────────────────────

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

    # ── expression dispatch — returns result name/value ─────────────────────

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
        # [Token(ID), Tree(expr)]
        name = str(node.children[0])
        val = self._gen(node.children[1])
        self._emit(":=", val, "_", name)

    def _exec_increment(self, node):
        # [Token(ID), Token(INCR_OP)]
        name = str(node.children[0])
        op = str(node.children[1])   # "++" or "--"
        self._emit(op, name, "_", name)

    def _exec_write_stmt(self, node):
        for child in node.children:
            if isinstance(child, Tree):
                val = self._gen(child)
                self._emit("write", val, "_", "_")

    def _exec_return_stmt(self, node):
        val = self._gen(node.children[0])
        self._emit("return", val, "_", "_")

    def _exec_if_stmt(self, node):
        # children: [expr, block_then] or [expr, block_then, block_else]
        cond = self._gen(node.children[0])
        has_else = len(node.children) == 3

        l_false = self._new_label()
        self._emit("if", cond, "_", l_false)
        self._exec(node.children[1])          # then block

        if has_else:
            l_end = self._new_label()
            self._emit("goto", "_", "_", l_end)
            self._emit("label", l_false, "_", "_")
            self._exec(node.children[2])      # else block
            self._emit("label", l_end, "_", "_")
        else:
            self._emit("label", l_false, "_", "_")

    def _exec_while_stmt(self, node):
        # children: [expr, block]
        l_start = self._new_label()
        l_end = self._new_label()
        self._emit("label", l_start, "_", "_")
        cond = self._gen(node.children[0])
        self._emit("if", cond, "_", l_end)
        self._exec(node.children[1])          # body
        self._emit("goto", "_", "_", l_start)
        self._emit("label", l_end, "_", "_")

    def _exec_for_stmt(self, node):
        # children: [for_init, expr (cond), for_update, block]
        self._exec(node.children[0])          # for_init → emits :=
        l_start = self._new_label()
        l_end = self._new_label()
        self._emit("label", l_start, "_", "_")
        cond = self._gen(node.children[1])    # condition expr
        self._emit("if", cond, "_", l_end)
        self._exec(node.children[3])          # body block
        self._exec(node.children[2])          # for_update (increment or assignment)
        self._emit("goto", "_", "_", l_start)
        self._emit("label", l_end, "_", "_")

    def _exec_for_init(self, node):
        # [Token(ID), Tree(expr)]
        name = str(node.children[0])
        val = self._gen(node.children[1])
        self._emit(":=", val, "_", name)

    # ── expression generation ────────────────────────────────────────────────

    def _gen_expr(self, node):
        return self._gen(node.children[0])

    def _gen_expr_or(self, node):
        # children: expr_and+  ("or" is anonymous, filtered)
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
        # children: expr_not+  ("and" is anonymous, filtered)
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
        # child is Tree(expr_not) → "not" was applied (keyword filtered)
        # child is Tree(expr_rel)  → passthrough
        child = node.children[0]
        val = self._gen(child)
        if isinstance(child, Tree) and child.data == "expr_not":
            temp = self._new_temp()
            self._emit("not", val, "_", temp)
            return temp
        return val

    def _gen_expr_rel(self, node):
        # children: [expr_add] or [expr_add, op_rel, expr_add]
        trees = [c for c in node.children if isinstance(c, Tree)]
        if len(trees) == 1:
            return self._gen(trees[0])
        left = self._gen(trees[0])
        op = str(trees[1].children[0])        # op_rel → Token(REL_OP)
        right = self._gen(trees[2])
        temp = self._new_temp()
        self._emit(op, left, right, temp)
        return temp

    def _gen_expr_add(self, node):
        # children alternate: Tree(expr_mult), Token(ADD_OP), Tree(expr_mult), ...
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
        # children alternate: Tree(factor), Token(MUL_OP), Tree(factor), ...
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
            return "_"          # fallback; BOOL_LIT keeps the token now
        child = node.children[0]
        if isinstance(child, Token):
            if child.type == "UMINUS":
                # unary minus: node.children[1] is Tree(factor)
                inner = self._gen(node.children[1])
                temp = self._new_temp()
                self._emit("neg", inner, "_", temp)
                return temp
            return str(child)   # NUMBER, FLOAT, STRING, ID, BOOL_LIT
        if isinstance(child, Tree):
            if child.data == "expr":
                return self._gen(child)
            if child.data == "proc_call":
                return self._gen_proc_call(child)
        return "_"

    def _gen_proc_call(self, node):
        func_name = str(node.children[0])
        args = []
        for child in node.children:
            if isinstance(child, Tree) and child.data == "arg_list":
                for expr in child.children:
                    if isinstance(expr, Tree):
                        args.append(self._gen(expr))
        for arg in args:
            self._emit("param", arg, "_", "_")
        temp = self._new_temp()
        self._emit("call", func_name, str(len(args)), temp)
        return temp
