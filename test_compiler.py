import unittest
import io
import sys
import os
from pathlib import Path

from lark import Tree
from lexer_parser import parse
from semantic import SemanticAnalyzer
from codegen import CodeGenerator
from evaluator import Evaluator

TESTS_DIR = Path(__file__).parent / "tests"

# Archivos que se espera que fallen (errores semánticos o de sintaxis intencionales)
EXPECTED_FAILURES = {"pruebaErrores.txt"}


def run_program(source: str):
    """Compila y ejecuta el código fuente. Retorna la salida capturada."""
    tree = parse(source)
    if not isinstance(tree, Tree):
        raise AssertionError(f"Error de parseo: {tree}")

    errors = SemanticAnalyzer(tree).analyze()
    if errors:
        raise AssertionError(f"Errores semánticos: {errors}")

    gen = CodeGenerator(tree)
    quads = gen.generate()

    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        Evaluator(quads, proc_table=gen.proc_table).run()
    finally:
        sys.stdout = old_stdout

    return captured.getvalue()


def _make_test(txt_path: Path, expect_failure: bool):
    def test(self):
        source = txt_path.read_text(encoding="utf-8")
        if expect_failure:
            with self.assertRaises(AssertionError):
                run_program(source)
        else:
            output = run_program(source)
            self.assertIsNotNone(output)

    test.__name__ = f"test_{txt_path.stem}"
    test.__doc__ = f"Prueba: {txt_path.name}"
    return test


class CompilerTests(unittest.TestCase):
    pass


for _txt in sorted(TESTS_DIR.glob("*.txt")):
    _expect_fail = _txt.name in EXPECTED_FAILURES
    _method = _make_test(_txt, _expect_fail)
    setattr(CompilerTests, _method.__name__, _method)


if __name__ == "__main__":
    unittest.main(verbosity=2)
