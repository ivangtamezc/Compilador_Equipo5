import os
from lark import Lark
from lark.exceptions import UnexpectedCharacters, UnexpectedToken, UnexpectedInput

_grammar_path = os.path.join(os.path.dirname(__file__), "grammar.lark")

with open(_grammar_path, "r", encoding="utf-8") as _f:
    _grammar = _f.read()

_parser = Lark(_grammar, parser="earley", propagate_positions=True)


def parse(code: str):
    try:
        return _parser.parse(code)
    except UnexpectedCharacters as e:
        return (
            f"Error léxico en línea {e.line}, columna {e.column}: "
            f"carácter inesperado '{e.char}'\n"
            f"  Se esperaba: {e.allowed}"
        )
    except UnexpectedToken as e:
        return (
            f"Error sintáctico en línea {e.line}, columna {e.column}: "
            f"token inesperado '{e.token}'\n"
            f"  Se esperaba uno de: {e.expected}"
        )
    except UnexpectedInput as e:
        return (
            f"Error en línea {e.line}, columna {e.column}: "
            f"entrada inesperada"
        )
    except Exception as e:
        return f"Error: {e}"
