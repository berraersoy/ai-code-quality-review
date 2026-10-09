import ast


def analyze_ast(file_path):
    """
    Analyze the structural properties of a Python file using AST.
    """

    with open(file_path, "r", encoding="utf-8") as file:
        code = file.read()

    try:
        tree = ast.parse(code)

    except SyntaxError as error:
        return {
            "valid_syntax": False,
            "error": str(error)
        }

    functions = []
    classes = []

    if_count = 0
    for_count = 0
    while_count = 0
    import_count = 0
    return_count = 0

    for node in ast.walk(tree):

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append({
                "name": node.name,
                "line": node.lineno,
                "arguments": [
                    argument.arg
                    for argument in node.args.args
                ]
            })

        elif isinstance(node, ast.ClassDef):
            classes.append({
                "name": node.name,
                "line": node.lineno
            })

        elif isinstance(node, ast.If):
            if_count += 1

        elif isinstance(node, ast.For):
            for_count += 1

        elif isinstance(node, ast.While):
            while_count += 1

        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            import_count += 1

        elif isinstance(node, ast.Return):
            return_count += 1

    return {
        "valid_syntax": True,

        "functions": functions,

        "classes": classes,

        "structure": {
            "function_count": len(functions),
            "class_count": len(classes),
            "if_count": if_count,
            "for_count": for_count,
            "while_count": while_count,
            "import_count": import_count,
            "return_count": return_count
        }
    }


if __name__ == "__main__":
    result = analyze_ast("samples/bad_code.py")
    print(result)