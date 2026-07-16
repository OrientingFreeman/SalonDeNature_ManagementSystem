import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ApiSecurityContractTest(unittest.TestCase):
    def test_security_module_parses(self):
        ast.parse((ROOT / "api" / "security.py").read_text(encoding="utf-8"))

    def test_mutations_require_csrf_decorator(self):
        for relative in ("api/customer_routes.py", "api/admin_routes.py"):
            source = (ROOT / relative).read_text(encoding="utf-8")
            tree = ast.parse(source)
            for node in tree.body:
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                route_methods = []
                decorator_names = []
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                        route_methods.append(dec.func.attr)
                    elif isinstance(dec, ast.Name):
                        decorator_names.append(dec.id)
                    elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
                        decorator_names.append(dec.func.id)
                if "post" in route_methods or "patch" in route_methods:
                    self.assertIn("require_api_csrf", decorator_names, f"{relative}:{node.name}")
                    self.assertIn("rate_limit", decorator_names, f"{relative}:{node.name}")

    def test_operational_documentation_exists(self):
        self.assertTrue((ROOT / "API_OPERATIONS.md").exists())


if __name__ == "__main__":
    unittest.main()
