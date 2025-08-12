# -*- coding: utf-8 -*-

# GPLv3 license
# Copyright Lutra Consulting Limited


# import sys
# import unittest


# def _run_tests(test_suite, package_name):
#     count = test_suite.countTestCases()
#     print("########")
#     print("{} tests has been discovered in {}".format(count, package_name))
#     print("########")

#     unittest.TextTestRunner(verbosity=3, stream=sys.stdout).run(test_suite)


# def test_all(package="."):
#     test_loader = unittest.defaultTestLoader
#     test_suite = test_loader.discover(package)
#     _run_tests(test_suite, package)


# if __name__ == "__main__":
#     test_all()

import importlib.util
import pathlib
import sys
import unittest
import os

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname( __file__ ), os.pardir))# pathlib.Path(r"C:\Users\ms1\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\wtyczka_qgis_app")
TEST_PATH = os.path.join(PLUGIN_DIR, "test" , "test_save_layer_to_gml.py")

# Ensure the plugin root is importable so test module can resolve internal imports
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

spec = importlib.util.spec_from_file_location("test_save_layer_to_gml", TEST_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

suite = unittest.defaultTestLoader.loadTestsFromTestCase(module.SaveLayerToGmlTest)
unittest.TextTestRunner(verbosity=2).run(suite)