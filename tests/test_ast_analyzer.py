from analyzer.ast_analyzer import analyze_ast


def test_bad_code_has_valid_syntax():
    report = analyze_ast("samples/bad_code.py")

    assert report["valid_syntax"] is True


def test_bad_code_function_structure():
    report = analyze_ast("samples/bad_code.py")

    assert report["structure"]["function_count"] == 1
    assert report["structure"]["class_count"] == 0

    assert len(report["functions"]) == 1

    function = report["functions"][0]

    assert function["name"] == "calculate"
    assert function["line"] == 6
    assert function["arguments"] == ["a", "b"]


def test_bad_code_control_flow_structure():
    report = analyze_ast("samples/bad_code.py")

    structure = report["structure"]

    assert structure["if_count"] == 3
    assert structure["for_count"] == 0
    assert structure["while_count"] == 0


def test_bad_code_import_and_return_counts():
    report = analyze_ast("samples/bad_code.py")

    structure = report["structure"]

    assert structure["import_count"] == 2
    assert structure["return_count"] == 1