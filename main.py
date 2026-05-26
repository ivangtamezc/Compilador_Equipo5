import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from lark import Tree
from lexer_parser import parse
from semantic import SemanticAnalyzer
from codegen import CodeGenerator
from evaluator import Evaluator


def print_quads(quads):
    if not quads:
        return
    w0 = max(len(q[0]) for q in quads)
    w1 = max(len(q[1]) for q in quads)
    w2 = max(len(q[2]) for q in quads)
    w3 = max(len(q[3]) for q in quads)
    for i, (op, a1, a2, res) in enumerate(quads):
        print(f"[{i:>2}]  ( {op:<{w0}} , {a1:>{w1}} , {a2:>{w2}} , {res:>{w3}} )")


def main():
    if len(sys.argv) < 2:
        print("Uso: python main.py <archivo.txt>")
        sys.exit(1)

    filename = sys.argv[1]
    try:
        with open(filename, "r", encoding="utf-8") as f:
            code = f.read()
    except FileNotFoundError:
        print(f"Error: no se encontró el archivo '{filename}'")
        sys.exit(1)

    result = parse(code)
    if not isinstance(result, Tree):
        print(result)
        sys.exit(1)

    print("Árbol sintáctico:")
    print(result.pretty())

    print("Análisis semántico:")
    errors = SemanticAnalyzer(result).analyze()
    if errors:
        for e in errors:
            print(f"  {e}")
        sys.exit(1)

    print("OK")
    print()

    quads = CodeGenerator(result)
    generated = quads.generate()
    print(f"Cuádruplos ({len(generated)}):")
    print()
    print_quads(generated)
    print()

    print("Salida:")
    Evaluator(generated, proc_table=quads.proc_table).run()


if __name__ == "__main__":
    main()
