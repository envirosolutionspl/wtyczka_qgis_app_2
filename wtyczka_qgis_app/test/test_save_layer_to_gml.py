"""Unit test for saving a layer to GML through the plugin."""

import os
import sys
import unittest
import pathlib
import shutil
import tempfile

# Allow running this test directly without relying on the tests package.
# As with ``tests/__init__``, we need the parent of the plugin directory on
# ``sys.path`` so Python can resolve ``wtyczka_qgis_app``.
PLUGIN_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
PLUGIN_PARENT = os.path.dirname(PLUGIN_ROOT)
for path in (PLUGIN_PARENT, PLUGIN_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)

class SaveLayerToGmlTest(unittest.TestCase):
    def setUp(self):
        self.plugin_dir = os.path.dirname(os.path.dirname(__file__))
        self.pog_gml = os.path.join(self.plugin_dir, 'test', 'data', 'AktPlanowaniaPrzestrzennego.gml')
        self.spl_gml = os.path.join(self.plugin_dir, 'test', 'data', 'StrefaPlanistyczna.gml')

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
            s.setValue('qgis_app2/settings/strefaPL2000', 4326)
            s.setValue('qgis_app2/settings/rodzajZbioru', 'POG')
            s.setValue('qgis_app2/settings/jpt', 'test')

            # Copy GML fixtures to a writable directory so QGIS can create
            # accompanying .gfs files without hitting permission errors.
            pog_gml = shutil.copy(self.pog_gml, os.path.join(tmpdir, 'granicaPOG.gml'))
            spl_gml = shutil.copy(self.spl_gml, os.path.join(tmpdir, 'strefaPlanistyczna.gml'))

            gfs_source = os.path.join(self.plugin_dir, 'GFS', 'template.gfs')
            gfs_target_dir = pathlib.Path(QgsApplication.qgisSettingsDirPath()) / 'python/plugins/wtyczka_qgis_app/GFS'
            gfs_target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(gfs_source, gfs_target_dir / 'template.gfs')

            from PyQt5 import QtWidgets
            original_open = QtWidgets.QFileDialog.getOpenFileName

            try:
                files_iter = iter([pog_gml, spl_gml])
                plugin.activeDlg = type('dlg', (), {'name': 'GranicaPOG'})()
                QtWidgets.QFileDialog.getOpenFileName = staticmethod(lambda *args, **kwargs: (next(files_iter), 'pliki GML (*.gml);'))
                plugin.loadFromGMLorGPKG(False)

                plugin.activeDlg = type('dlg', (), {'name': 'StrefaPlanistyczna'})()
                plugin.loadFromGMLorGPKG(False)
            finally:
                QtWidgets.QFileDialog.getOpenFileName = original_open

            project = QgsProject.instance()
            pog_layer = project.mapLayersByName('GranicaPOG')[0]
            spl_layer = project.mapLayersByName('StrefaPlanistyczna')[0]
            self.assertTrue(pog_layer.isValid(), 'POG layer failed to load')
            self.assertTrue(spl_layer.isValid(), 'SPL layer failed to load')

            plugin.wektorInstrukcjaDialogSPL = type('dlg', (), {
                'layers_comboBox': type('cmb', (), {'currentLayer': lambda self: spl_layer})()
            })()
            plugin.activeDlg = plugin.wektorInstrukcjaDialogSPL

            out_path = os.path.join(tmpdir, 'output.gml')

            original_save = QtWidgets.QFileDialog.getSaveFileName
            QtWidgets.QFileDialog.getSaveFileName = staticmethod(lambda directory=None, filter=None: (out_path, None))
            try:
                plugin.saveLayerToGML()
            finally:
                QtWidgets.QFileDialog.getSaveFileName = original_save

            self.assertTrue(os.path.exists(out_path), 'Output GML not created')

if __name__ == '__main__':
    unittest.main()
