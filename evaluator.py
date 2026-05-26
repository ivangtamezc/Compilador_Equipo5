class Evaluator:
    def __init__(self, quads, proc_table=None):
        self._quads = quads
        # tablita de procedimientos: {nombre: {'label': L_func, 'params': [nombres]}}
        self._proc_table = proc_table or {}

        # namespace único y plano: globales, parámetros y temporales viven aquí
        # no manejamos scopes locales
        self._env = {}
        # pila de direcciones de retorno (pc al que volver tras un return)
        self._return_stack = []
        # pila de "targets" del valor de retorno (nombre del temporal del call)
        self._return_target = []
        # pila de parámetros pendientes (se llenan con 'param', se consumen con 'recv_param')
        self._param_stack = []

        # índice de labels -> posición de quad
        self._labels = {}

    def run(self):
        self._env.clear()
        self._build_labels()
        pc = 0
        while pc < len(self._quads):
            op, a1, a2, res = self._quads[pc]
            pc += 1
            pc = self._step(op, a1, a2, res, pc)
            if pc is None:  # halt
                return

    def _build_labels(self):
        self._labels = {}
        for i, (op, a1, *_) in enumerate(self._quads):
            if op == "label":
                self._labels[a1] = i

    def _resolve(self, name):
        if name == "_":
            return None
        if name.startswith('"') and name.endswith('"'):
            return name[1:-1]
        if name == "true":
            return True
        if name == "false":
            return False
        try:
            return int(name)
        except ValueError:
            pass
        try:
            return float(name)
        except ValueError:
            pass
        # variable, parámetro o temporal: todos viven en el mismo namespace
        return self._env.get(name, 0)

    def _store(self, name, value):
        if name != "_":
            self._env[name] = value

    def _step(self, op, a1, a2, res, pc):

        if op == ":=":
            self._store(res, self._resolve(a1))

        elif op in ("+", "-", "*", "/", "%"):
            v1 = self._resolve(a1)
            v2 = self._resolve(a2)
            if op == "+": self._store(res, v1 + v2)
            elif op == "-": self._store(res, v1 - v2)
            elif op == "*": self._store(res, v1 * v2)
            elif op == "/": self._store(res, v1 / v2)
            elif op == "%": self._store(res, v1 % v2)

        elif op == "neg":
            self._store(res, -self._resolve(a1))

        elif op in (">", "<", ">=", "<=", "==", "!="):
            v1 = self._resolve(a1)
            v2 = self._resolve(a2)
            if op == ">": self._store(res, v1 > v2)
            elif op == "<": self._store(res, v1 < v2)
            elif op == ">=": self._store(res, v1 >= v2)
            elif op == "<=": self._store(res, v1 <= v2)
            elif op == "==": self._store(res, v1 == v2)
            elif op == "!=": self._store(res, v1 != v2)

        elif op == "and":
            self._store(res, bool(self._resolve(a1)) and bool(self._resolve(a2)))
        elif op == "or":
            self._store(res, bool(self._resolve(a1)) or bool(self._resolve(a2)))
        elif op == "not":
            self._store(res, not bool(self._resolve(a1)))

        elif op == "++":
            self._store(res, self._resolve(a1) + 1)
        elif op == "--":
            self._store(res, self._resolve(a1) - 1)

        elif op == "label":
            pass

        elif op == "goto":
            pc = self._labels[res]

        elif op == "if_false":
            if not bool(self._resolve(a1)):
                pc = self._labels[res]
        elif op == "if":
            if not bool(self._resolve(a1)):
                pc = self._labels[res]

        elif op == "write":
            val = self._resolve(a1)
            if isinstance(val, float) and val == int(val):
                print(int(val))
            else:
                print(val)

        elif op == "param":
            # apilamos el valor del argumento para que el callee lo desempile
            self._param_stack.append(self._resolve(a1))

        elif op == "call":
            # a1: nombre del proc, a2: # de args, res: temporal para el valor de retorno
            proc = self._proc_table.get(a1)
            if proc is None:
                return pc
            self._return_stack.append(pc)
            self._return_target.append(res)
            pc = self._labels[proc["label"]]

        elif op == "recv_param":
            # el callee desempila los parámetros en el orden en que llegaron
            self._store(res, self._param_stack.pop())

        elif op == "return":
            ret_val = self._resolve(a1) if a1 != "_" else None
            if self._return_stack:
                pc = self._return_stack.pop()
                target = self._return_target.pop()
                if ret_val is not None:
                    self._store(target, ret_val)

        elif op == "halt":
            return None

        return pc
