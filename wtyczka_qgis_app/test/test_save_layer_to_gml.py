"""Unit test for saving a layer to GML through the plugin."""

import os
import sys
import unittest
import pathlib
import shutil
import tempfile
import xml.etree.ElementTree as ET

from qgis._core import QgsVectorLayer, QgsProject
from qgis._gui import QgsMapLayerComboBox

przypisaniePowiatuDoEPSGukladuPL2000 = {
    "2176": ['0201','0203','0205','0206','0207','0209','0210','0211','0212','0216','0219','0221','0225','0226','0261','0262','0265','0801','0802','0803','0804',\
             '0805','0806','0807','0808','0809','0810','0811','0812','0861','0862','3002','3005','3014','3015','3024','3029','3201','3202','3203','3204','3205',\
             '3206','3207','3208','3209','3210','3211','3212','3214','3216','3217','3218','3261','3262','3263'],
    "2177": ['0202','0204','0208','0213','0214','0215','0217','0218','0220','0222','0223','0224','0264','0401','0402','0403','0404','0405','0406','0407','0408',\
             '0409','0410','0411','0412','0413','0414','0415','0416','0417','0418','0419','0461','0462','0463','0464','1001','1002','1003','1004','1008','1009',\
             '1011','1014','1017','1018','1019','1020','1061','1203','1213','1601','1602','1603','1604','1605','1606','1607','1608','1609','1610','1611','1661',\
             '2201','2202','2203','2204','2205','2206','2207','2208','2209','2210','2211','2212','2213','2214','2215','2216','2261','2262','2263','2264','2401',\
             '2402','2403','2404','2405','2406','2407','2408','2409','2410','2411','2412','2413','2414','2415','2417','2461','2462','2463','2464','2465','2466',\
             '2467','2468','2469','2470','2471','2472','2473','2474','2475','2476','2477','2478','2479','3001','3003','3004','3006','3007','3008','3009','3010',\
             '3011','3012','3013','3016','3017','3018','3019','3020','3021','3022','3023','3025','3026','3027','3028','3030','3031','3061','3062','3063','3064',\
             '3213','3215'],
    "2178": ['0605','0607','0611','0612','0614','0616','1005','1006','1007','1010','1012','1013','1015','1016','1021','1062','1063','1201','1202','1204','1205',\
             '1206','1207','1208','1209','1210','1211','1212','1214','1215','1216','1217','1218','1219','1261','1262','1263','1401','1402','1403','1404','1405',\
             '1406','1407','1408','1409','1411','1412','1413','1414','1415','1416','1417','1418','1419','1420','1421','1422','1423','1424','1425','1426','1427',\
             '1428','1429','1430','1432','1433','1434','1435','1436','1437','1438','1461','1462','1463','1464','1465','1802','1803','1805','1806','1807','1808',\
             '1810','1811','1812','1815','1816','1817','1818','1819','1820','1821','1861','1863','1864','2004','2006','2007','2014','2062','2416','2601','2602',\
             '2603','2604','2605','2606','2607','2608','2609','2610','2611','2612','2613','2661','2801','2802','2803','2804','2805','2806','2807','2808','2809',\
             '2810','2811','2812','2813','2814','2815','2816','2817','2818','2819','2861','2862'],
    "2179": ['0601','0602','0603','0604','0606','0608','0609','0610','0613','0615','0617','0618','0619','0620','0661','0662','0663','0664','1410','1801','1804',\
             '1809','1813','1814','1862','2001','2002','2003','2005','2008','2009','2010','2011','2012','2013','2061','2063']
    }


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
    for epsg in przypisaniePowiatuDoEPSGukladuPL2000:
        if jpt in przypisaniePowiatuDoEPSGukladuPL2000[epsg]:
            return epsg


class SaveLayerToGmlTest(unittest.TestCase):
    def setUp(self):
        self.plugin_dir = os.path.dirname(os.path.dirname(__file__))
        self.app_gml = os.path.join(self.plugin_dir, 'test', 'data', '1', 'pog', 'AktPlanowaniaPrzestrzennego.gml')
        self.spl_gml = os.path.join(self.plugin_dir, 'test', 'data', '1', 'strefy', 'StrefaPlanistyczna.gml')

    def load_layer_from_file(self, path):
        """
        Load a vector layer from file, assign target CRS from settings, and add to project.
        Layer name is always the file name without extension.
        Supports GML reprojection template logic.
        """
        src = pathlib.Path(path)
        name = src.stem

        # For GML: copy template GFS if needed
        if src.suffix.lower() == ".gml":
            template = pathlib.Path(__file__).resolve().parents[1] / "GFS" / "template.gfs"
            dest_gfs = src.with_suffix(".gfs")
            if template.exists() and not dest_gfs.exists():
                shutil.copyfile(str(template), str(dest_gfs))
        layer = QgsVectorLayer(str(src), name, "ogr")
        if not layer.isValid():
            return layer
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
            app_gml = shutil.copy(self.app_gml, os.path.join(tmpdir, 'AktPlanowaniaPrzestrzennego.gml'))
            jpt_value = extract_jpt_from_pog(app_gml)
            s.setValue("qgis_app2/settings/jpt", jpt_value)
            s.setValue("qgis_app2/settings/strefaPL2000", get_crs_from_jpt(jpt_value[:4]))

            gfs_source = os.path.join(self.plugin_dir, 'GFS', 'template.gfs')
            gfs_target_dir = pathlib.Path(QgsApplication.qgisSettingsDirPath()) / 'python/plugins/wtyczka_qgis_app/GFS'
            gfs_target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(gfs_source, gfs_target_dir / 'template.gfs')

            templates_src = pathlib.Path(self.plugin_dir, 'modules', 'templates')
            templates_dst = pathlib.Path(QgsApplication.qgisSettingsDirPath()) / 'python/plugins/wtyczka_qgis_app/modules/templates'
            shutil.copytree(templates_src, templates_dst, dirs_exist_ok=True)
            granice_src = pathlib.Path(self.plugin_dir, 'modules', 'app', 'A00_Granice_panstwa')
            granice_dst = pathlib.Path(
                QgsApplication.qgisSettingsDirPath()) / 'python/plugins/wtyczka_qgis_app/modules/app/A00_Granice_panstwa'
            shutil.copytree(granice_src, granice_dst, dirs_exist_ok=True)

            app_layer = self.load_layer_from_file(app_gml)

            self.assertTrue(app_layer.isValid(), 'AktPlanowaniaPrzestrzennego layer failed to load')
            spl_gml = shutil.copy(self.spl_gml, os.path.join(tmpdir, 'StrefaPlanistyczna.gml'))
            spl_layer = self.load_layer_from_file(spl_gml)
            self.assertTrue(spl_layer.isValid(), 'SPL layer failed to load')


            plugin.activeDlg = plugin.wektorInstrukcjaDialogPOG
            plugin.activeDlg.name = 'AktPlanowaniaPrzestrzennego'
            plugin.activeDlg.layers_comboBox = QgsMapLayerComboBox()
            add_lyr = plugin.loadFromGMLorGPKG(False, app_gml)
            plugin.activeDlg.layers_comboBox.setCurrentText(add_lyr.name())
            out_path = os.path.join(tmpdir, 'output_pog.gml')

            from PyQt5 import QtWidgets
            original_save = self._save_layer_to_gml(
                QtWidgets, out_path, plugin
            )
            plugin.activeDlg = plugin.wektorInstrukcjaDialogSPL
            plugin.activeDlg.name = 'StrefaPlanistyczna'
            plugin.activeDlg.layers_comboBox = QgsMapLayerComboBox()
            spl_lyr = plugin.loadFromGMLorGPKG(False, spl_gml)
            plugin.activeDlg.layers_comboBox.setCurrentText(spl_lyr.name())

            out_path = os.path.join(tmpdir, 'output_spl.gml')

            from qgis.PyQt import QtWidgets
            original_save = self._save_layer_to_gml(
                QtWidgets, out_path, plugin
            )

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
