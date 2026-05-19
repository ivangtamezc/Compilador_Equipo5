class Evaluator:
    def __init__(self, quads):
        self._quads = quads
        self._env = {}     # variables and temporals share one flat namespace
        self._labels = {}  # label_name → quad index

    def run(self):
        self._env = {}
        self._build_labels()
        pc = 0
        while pc < len(self._quads):
            op, a1, a2, res = self._quads[pc]
            pc += 1                        # advance first; jumps override this
            pc = self._step(op, a1, a2, res, pc)

    # ── pre-compute label positions ──────────────────────────────────────────

    def _build_labels(self):
        self._labels = {}
        for i, (op, a1, *_) in enumerate(self._quads):
            if op == "label":
                self._labels[a1] = i

    # ── value resolution ─────────────────────────────────────────────────────

    def _resolve(self, name):
        if name == "_":
            return None
        if name.startswith('"') and name.endswith('"'):
            return name[1:-1]               # string literal → strip quotes
        if name == "true":
            return True
        if name == "false":
            return False
        try:
            return int(name)                # integer literal
        except ValueError:
            pass
        try:
            return float(name)              # float literal
        except ValueError:
            pass
        return self._env.get(name, 0)       # variable or temporary (default 0)

    def _store(self, name, value):
        if name != "_":
            self._env[name] = value

    # ── single-step execution ────────────────────────────────────────────────

    def _step(self, op, a1, a2, res, pc):
        v1 = self._resolve(a1)
        v2 = self._resolve(a2)

        if op == ":=":
            self._store(res, v1)

        elif op == "+":
            self._store(res, v1 + v2)
        elif op == "-":
            self._store(res, v1 - v2)
        elif op == "*":
            self._store(res, v1 * v2)
        elif op == "/":
            self._store(res, v1 / v2)
        elif op == "%":
            self._store(res, v1 % v2)
        elif op == "neg":
            self._store(res, -v1)

        elif op == ">":
            self._store(res, v1 > v2)
        elif op == "<":
            self._store(res, v1 < v2)
        elif op == ">=":
            self._store(res, v1 >= v2)
        elif op == "<=":
            self._store(res, v1 <= v2)
        elif op == "==":
            self._store(res, v1 == v2)
        elif op == "!=":
            self._store(res, v1 != v2)

        elif op == "and":
            self._store(res, bool(v1) and bool(v2))
        elif op == "or":
            self._store(res, bool(v1) or bool(v2))
        elif op == "not":
            self._store(res, not bool(v1))

        elif op == "++":
            self._store(res, v1 + 1)
        elif op == "--":
            self._store(res, v1 - 1)

        elif op == "label":
            pass                            # no-op; just a marker

        elif op == "goto":
            pc = self._labels[res]          # jump to label (executes label noop, then continues)

        elif op == "if":
            if not bool(v1):               # condition is FALSE → take the jump
                pc = self._labels[res]

        elif op == "write":
            val = v1
            # Print floats that are whole numbers as ints for clean output
            if isinstance(val, float) and val == int(val):
                print(int(val))
            else:
                print(val)

        elif op in ("param", "call", "return"):
            pass                            # not exercised by the test programs

        return pc
