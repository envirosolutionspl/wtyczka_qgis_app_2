import ast
from pathlib import Path
import unittest

# Resolve path to ``modules/app/wtyczka_app.py`` regardless of the
# current working directory used when running the tests. ``__file__``
# points to this test module located inside ``tests``. Going one level
# up gives the repository root.
FILE_PATH = (
    Path(__file__).resolve().parents[1]
    / "modules"
    / "app"
    / "wtyczka_app.py"
)


def _get_app_class():
    source = FILE_PATH.read_text(encoding='utf-8')
    module = ast.parse(source)
    cls = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == 'AppModule')
    return source, cls


def _get_method(name):
    src, cls = _get_app_class()
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name]
    method = methods[-1]
    return src, method


class TestWtyczkaAppAst(unittest.TestCase):
    def test_new_empty_layer_has_epsg_popup(self):
        src, method = _get_method('newEmptyLayer')
        found = False
        for node in ast.walk(method):
            if isinstance(node, ast.If):
                cond = ast.get_source_segment(src, node.test)
                if cond and cond.strip() == "epsg in (0, NULL, '')":
                    if any(
                        isinstance(child, ast.Call)
                        and (
                            (isinstance(child.func, ast.Name) and child.func.id == 'showPopup')
                            or (
                                isinstance(child.func, ast.Attribute)
                                and child.func.attr == 'showPopup'
                            )
                        )
                        for child in ast.walk(node)
                    ):
                        found = True
                        break
        self.assertTrue(found, 'Expected showPopup call when epsg is invalid')


    def test_save_layer_to_gml_has_invalid_layer_message(self):
        src, _ = _get_method('saveLayerToGML')
        self.assertIn('Niepoprawna nazwa warstwy', src)


if __name__ == '__main__':
    unittest.main()