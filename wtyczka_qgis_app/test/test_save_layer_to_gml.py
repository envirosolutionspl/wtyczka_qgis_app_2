"""Unit test for saving a layer to GML through the plugin."""

import os
import pathlib
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from qgis.core import QgsVectorLayer, QgsProject, QgsApplication
from qgis.gui import QgsMapLayerComboBox

# Allow running this test directly without relying on the test package.
# As with ``test/__init__``, we need the parent of the plugin directory on
# ``sys.path`` so Python can resolve ``wtyczka_qgis_app``.
PLUGIN_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
PLUGIN_PARENT = os.path.dirname(PLUGIN_ROOT)
DATA_ROOT = pathlib.Path(__file__).parent / "data"
for path in (PLUGIN_PARENT, PLUGIN_ROOT, DATA_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)


def extract_jpt_from_pog(pog_gml: pathlib.Path) -> str:
    tree = ET.parse(str(pog_gml))
    ns = {
        "app": "https://www.gov.pl/static/zagospodarowanieprzestrzenne/schemas/app/2.0"
    }
    elem = tree.find(".//app:przestrzenNazw", ns)
    if elem is None or not elem.text:
        raise ValueError("przestrzenNazw not found")
    core = elem.text.split("/")[-1].split("-")[0]
    return core[:6]


def get_crs_from_jpt(jpt: str) -> str:
    from wtyczka_qgis_app.modules.dictionaries import przypisaniePowiatuDoEPSGukladuPL2000
    for epsg in przypisaniePowiatuDoEPSGukladuPL2000:
        if jpt in przypisaniePowiatuDoEPSGukladuPL2000[epsg]:
            return epsg


class SaveLayerToGmlTest(unittest.TestCase):
    def setUp(self):
        self.plugin_dir = os.path.dirname(os.path.dirname(__file__))
        self.data_root = pathlib.Path(self.plugin_dir) / 'test' / 'data'

    def load_layer_from_file(self, path):
        """
        Load a vector layer from file, assign target CRS from settings, and add to project.
        Layer name is always the file name without extension.
        Supports GML reprojection template logic.
        """
        src = pathlib.Path(path)
        name = src.stem

        if src.suffix.lower() == ".gml":
            template = pathlib.Path(__file__).resolve().parents[1] / "GFS" / "template.gfs"
            dest_gfs = src.with_suffix(".gfs")
            print("TEST ", dest_gfs, template.exists(), dest_gfs.exists())
            if template.exists() and not dest_gfs.exists():
                print("KOPIOWANIE: ", template, 'do: ', dest_gfs)
                shutil.copyfile(str(template), str(dest_gfs))
        layer = QgsVectorLayer(str(src), name, "ogr")
        if not layer.isValid():
            return layer

        return layer

    def test_save_layer_to_gml(self):
        from qgis.core import QgsProject, QgsSettings, QgsApplication
        if QgsApplication.instance() is None:
            try:
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

        tmpdir = tempfile.gettempdir()

        for case in sorted(DATA_ROOT.iterdir(), key=lambda p: p.name):
            pog_src = case / 'pog' / 'AktPlanowaniaPrzestrzennego.gml'
            strefy_dir = case / 'strefy'

            plugin = AppModule(iface)

            s = QgsSettings()
            s.setValue('qgis_app2/settings/defaultPath', tmpdir)
            app_gml = shutil.copy(pog_src, os.path.join(tmpdir, 'AktPlanowaniaPrzestrzennego.gml'))
            jpt_value = extract_jpt_from_pog(pathlib.Path(app_gml))
            s.setValue("qgis_app2/settings/jpt", jpt_value)
            s.setValue("qgis_app2/settings/strefaPL2000", get_crs_from_jpt(jpt_value[:4]))

            gfs_source = pathlib.Path(self.plugin_dir) / 'GFS' / 'template.gfs'
            gfs_target_dir = pathlib.Path(QgsApplication.qgisSettingsDirPath()) / 'python/plugins/wtyczka_qgis_app/GFS'
            gfs_target = gfs_target_dir / 'template.gfs'
            if gfs_source.resolve() != gfs_target.resolve():
                gfs_target_dir.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(gfs_source, gfs_target)

            templates_src = pathlib.Path(self.plugin_dir, 'modules', 'templates')
            templates_dst = pathlib.Path(
                QgsApplication.qgisSettingsDirPath()) / 'python/plugins/wtyczka_qgis_app/modules/templates'
            
            if templates_src.resolve() != templates_dst.resolve():
                shutil.copytree(templates_src, templates_dst, dirs_exist_ok=True)
            
            granice_src = pathlib.Path(self.plugin_dir, 'modules', 'app', 'A00_Granice_panstwa')
            granice_dst = pathlib.Path(
                QgsApplication.qgisSettingsDirPath()) / 'python/plugins/wtyczka_qgis_app/modules/app/A00_Granice_panstwa'
            
            if granice_src.resolve() != granice_dst.resolve():
                shutil.copytree(granice_src, granice_dst, dirs_exist_ok=True)

            app_layer = self.load_layer_from_file(app_gml)
            self.assertTrue(app_layer.isValid(), 'AktPlanowaniaPrzestrzennego layer failed to load')

            plugin.activeDlg = plugin.wektorInstrukcjaDialogPOG
            plugin.activeDlg.name = 'AktPlanowaniaPrzestrzennego'
            plugin.activeDlg.layers_comboBox = QgsMapLayerComboBox()
            add_lyr = plugin.loadFromGMLorGPKG(path=app_gml)
            plugin.activeDlg.layers_comboBox.setCurrentText(add_lyr.name())

            out_path = os.path.join(tmpdir, f'output_pog_{case.name}.gml')
            from qgis.PyQt import QtWidgets
            self._save_layer_to_gml(QtWidgets, out_path, plugin)

            for spl_src in strefy_dir.glob('*.gml'):
                with self.subTest(case=case.name, spl_src=spl_src.name):
                    try:
                        spl_gml = shutil.copy(str(spl_src), os.path.join(tmpdir, spl_src.name))
                        spl_layer = self.load_layer_from_file(spl_gml)
                        self.assertTrue(spl_layer.isValid(), 'SPL layer failed to load')

                        plugin.activeDlg = plugin.wektorInstrukcjaDialogSPL
                        plugin.activeDlg.name = 'StrefaPlanistyczna'
                        plugin.activeDlg.layers_comboBox = QgsMapLayerComboBox()
                        spl_lyr = plugin.loadFromGMLorGPKG(path=spl_gml)
                        plugin.activeDlg.layers_comboBox.setCurrentText(spl_lyr.name())

                        out_path = os.path.join(
                            tmpdir, f'output_spl_{case.name}_{spl_src.stem}.gml'
                        )
                        self._save_layer_to_gml(QtWidgets, out_path, plugin)
                    except Exception as e:
                        self.fail(f"{case.name}/{spl_src.name} failed: {e}")

    def _save_layer_to_gml(self, QtWidgets, out_path, plugin):
        result = QtWidgets.QFileDialog.getSaveFileName
        QtWidgets.QFileDialog.getSaveFileName = staticmethod(lambda directory=None, filter=None: (out_path, None))
        try:
            plugin.saveLayerToGML()
        finally:
            QtWidgets.QFileDialog.getSaveFileName = result

        self.assertTrue(os.path.exists(out_path), 'Output GML not created')

        return result


if __name__ == '__main__':
    unittest.main()
