"""Unit test for saving a layer to GML through the plugin."""

import os
import sys
import unittest
import pathlib
import shutil
import tempfile

from qgis._core import QgsVectorLayer, QgsProject

# Allow running this test directly without relying on the test package.
# As with ``test/__init__``, we need the parent of the plugin directory on
# ``sys.path`` so Python can resolve ``wtyczka_qgis_app``.
PLUGIN_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
PLUGIN_PARENT = os.path.dirname(PLUGIN_ROOT)
for path in (PLUGIN_PARENT, PLUGIN_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)

class SaveLayerToGmlTest(unittest.TestCase):
    def setUp(self):
        self.plugin_dir = os.path.dirname(os.path.dirname(__file__))
        self.app_gml = os.path.join(self.plugin_dir, 'test', 'data', 'AktPlanowaniaPrzestrzennego.gml')
        self.spl_gml = os.path.join(self.plugin_dir, 'test', 'data', 'StrefaPlanistyczna.gml')

    def load_layer_from_file(self, path, name=None):
        src = pathlib.Path(path)
        if name is None:
            name = src.stem
        if src.suffix.lower() == ".gml":
            template = pathlib.Path(__file__).resolve().parents[1] / "GFS" / "template.gfs"
            dest_gfs = src.with_suffix(".gfs")
            if template.exists() and not dest_gfs.exists():
                shutil.copyfile(str(template), str(dest_gfs))

        layer = QgsVectorLayer(str(src), name, "ogr")
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
        return layer

    def test_save_layer_to_gml(self):
        try:
            from qgis.core import QgsProject, QgsSettings, QgsApplication
            from qgis.testing import start_app
            start_app()
        except Exception:
            self.skipTest('QGIS environment is not available')

        from wtyczka_qgis_app.modules.app.wtyczka_app import AppModule
        try:
            from qgis.utils import iface
        except Exception:
            iface = None
        if iface is None:
            class DummyIface:
                class DummyMessageBar:
                    def pushSuccess(self, *args, **kwargs):
                        pass

                def messageBar(self):
                    return self.DummyMessageBar()

            iface = DummyIface()

        plugin = AppModule(iface)

        with tempfile.TemporaryDirectory() as tmpdir:
            s = QgsSettings()
            s.setValue('qgis_app2/settings/defaultPath', tmpdir)
            s.setValue('qgis_app2/settings/strefaPL2000', 2178)
            s.setValue('qgis_app2/settings/rodzajZbioru', 'POG')
            s.setValue('qgis_app2/settings/jpt', 'test')

            # Copy GML fixtures to a writable directory so QGIS can create
            # accompanying .gfs files without hitting permission errors.
            app_gml = shutil.copy(self.app_gml, os.path.join(tmpdir, 'AktPlanowaniaPrzestrzennego.gml'))
            spl_gml = shutil.copy(self.spl_gml, os.path.join(tmpdir, 'StrefaPlanistyczna.gml'))

            gfs_source = os.path.join(self.plugin_dir, 'GFS', 'template.gfs')
            gfs_target_dir = pathlib.Path(QgsApplication.qgisSettingsDirPath()) / 'python/plugins/wtyczka_qgis_app/GFS'
            gfs_target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(gfs_source, gfs_target_dir / 'template.gfs')

            templates_src = pathlib.Path(self.plugin_dir, 'modules', 'templates')
            templates_dst = pathlib.Path(QgsApplication.qgisSettingsDirPath()) / 'python/plugins/wtyczka_qgis_app/modules/templates'
            shutil.copytree(templates_src, templates_dst, dirs_exist_ok=True)

            app_layer = self.load_layer_from_file(app_gml)
            spl_layer = self.load_layer_from_file(spl_gml)

            self.assertTrue(app_layer.isValid(), 'AktPlanowaniaPrzestrzennego layer failed to load')
            self.assertTrue(spl_layer.isValid(), 'SPL layer failed to load')

            plugin.wektorInstrukcjaDialogSPL = type('dlg', (), {
                'layers_comboBox': type('cmb', (), {'currentLayer': lambda self: spl_layer})()
            })()
            plugin.activeDlg = plugin.wektorInstrukcjaDialogSPL

            out_path = os.path.join(tmpdir, 'output.gml')

            from PyQt5 import QtWidgets
            original_save = QtWidgets.QFileDialog.getSaveFileName
            QtWidgets.QFileDialog.getSaveFileName = staticmethod(lambda directory=None, filter=None: (out_path, None))
            try:
                plugin.saveLayerToGML()
            finally:
                QtWidgets.QFileDialog.getSaveFileName = original_save

            self.assertTrue(os.path.exists(out_path), 'Output GML not created')

if __name__ == '__main__':
    unittest.main()