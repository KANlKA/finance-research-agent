"""
Calculator Tool - safe arithmetic evaluation (no `eval` on raw strings).
Walks a parsed AST and only allows numeric literals + basic operators.
"""
import ast
import operator as op

_OPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.Mod: op.mod,
    ast.USub: op.neg,
    ast.UAdd: op.pos,
}

TOOL_SPEC = {
    "name": "calculator",
    "description": "Evaluate a numeric arithmetic expression, e.g. portfolio percentage math.",
    "input_schema": {
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"],
    },
}


def _eval(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Only numeric constants are allowed.")
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


def run(expression: str) -> dict:
    tree = ast.parse(expression, mode="eval")
    result = _eval(tree.body)
    return {"expression": expression, "result": result}
