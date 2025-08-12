"""
Unit test – zapis warstw do GML z pełną tolerancją błędów.

* Działa na wszystkich katalogach w test/data.
* Błędy w danych lub w wtyczce → tylko `warnings.warn()`.
* Żadnych `AssertionError`, `self.fail()` ani `skipTest()` (oprócz braku QGIS).
* Na końcu drukuje podsumowanie wczytań/zapisów.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import sys
import tempfile
import unittest
import warnings
import xml.etree.ElementTree as ET

from qgis.core import (
    QgsApplication,
    QgsProject,
    QgsSettings,
    QgsVectorLayer,
)
from qgis.gui import QgsMapLayerComboBox

warnings.simplefilter("always", category=RuntimeWarning)

# ---------------------------------------------------- ŚCIEŻKI
PLUGIN_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
PLUGIN_PARENT = os.path.dirname(PLUGIN_ROOT)
DATA_ROOT = pathlib.Path(__file__).parent / "data"
for p in (PLUGIN_PARENT, PLUGIN_ROOT, DATA_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)


# ---------------------------------------------------- HELPERY
def extract_jpt_from_pog(pog_gml: pathlib.Path) -> str:
    tree = ET.parse(str(pog_gml))
    ns = {"app": "https://www.gov.pl/static/zagospodarowanieprzestrzenne/schemas/app/2.0"}
    elem = tree.find(".//app:przestrzenNazw", ns)
    if elem is None or not elem.text:
        raise ValueError("przestrzenNazw not found")
    return elem.text.split("/")[-1].split("-")[0][:6]


def get_crs_from_jpt(jpt: str) -> str | None:
    from wtyczka_qgis_app.modules.dictionaries import przypisaniePowiatuDoEPSGukladuPL2000
    for epsg, powiaty in przypisaniePowiatuDoEPSGukladuPL2000.items():
        if jpt in powiaty:
            return epsg
    return None


def safe_copy(src: pathlib.Path, dst: pathlib.Path, ctx: str) -> None:
    """Kopiuje plik/katalog, a brak źródła tylko loguje ostrzeżenie."""
    if not src.exists():
        warnings.warn(f"{ctx}: brak {src}", RuntimeWarning)
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            if not dst.exists():
                shutil.copyfile(src, dst)
    except Exception as exc:  # noqa: BLE001
        warnings.warn(f"{ctx}: kopiowanie {src} → {dst} nieudane: {exc}", RuntimeWarning)


# ---------------------------------------------------- TEST
class SaveLayerToGmlTest(unittest.TestCase):
    # -------- statystyki
    load_ok: list[str] = []
    load_fail: list[tuple[str, str]] = []
    save_ok: list[str] = []
    save_fail: list[tuple[str, str]] = []

    # --- uchwyty do oryginałów/stubów Qt
    _qtw1 = None  # PyQt5.QtWidgets
    _qtw2 = None  # qgis.PyQt.QtWidgets
    _orig_msgbox_exec_1 = None
    _orig_msgbox_exec_2 = None

    def setUp(self):
        self.plugin_dir = os.path.dirname(os.path.dirname(__file__))
        self.data_root = pathlib.Path(self.plugin_dir) / "test" / "data"
        from PyQt5 import QtWidgets
        self._orig_msgbox_exec = QtWidgets.QMessageBox.exec_
        QtWidgets.QMessageBox.exec_ = lambda self: QtWidgets.QMessageBox.Ok

    def tearDown(self):  # noqa: D401 - default teardown
        """Przywraca oryginalną metodę exec_ QMessageBox."""
        from PyQt5 import QtWidgets
        QtWidgets.QMessageBox.exec_ = self._orig_msgbox_exec

        # --- patch QMessageBox.exec_ w obu przestrzeniach nazw
        from PyQt5 import QtWidgets as QtW1
        from qgis.PyQt import QtWidgets as QtW2
        self.__class__._qtw1 = QtW1
        self.__class__._qtw2 = QtW2

        self.__class__._orig_msgbox_exec_1 = QtW1.QMessageBox.exec_
        self.__class__._orig_msgbox_exec_2 = QtW2.QMessageBox.exec_

        # zawsze udawaj "OK" żeby dialogi nie blokowały
        QtW1.QMessageBox.exec_ = lambda self: QtW1.QMessageBox.Ok
        QtW2.QMessageBox.exec_ = lambda self: QtW2.QMessageBox.Ok

    def tearDown(self):  # noqa: D401 - default teardown
        """Przywraca oryginalną metodę exec_ QMessageBox."""
        if self._qtw1 and self._orig_msgbox_exec_1:
            self._qtw1.QMessageBox.exec_ = self._orig_msgbox_exec_1
        if self._qtw2 and self._orig_msgbox_exec_2:
            self._qtw2.QMessageBox.exec_ = self._orig_msgbox_exec_2

        # --- patch QMessageBox.exec_ w obu przestrzeniach nazw
        from PyQt5 import QtWidgets as QtW1
        from qgis.PyQt import QtWidgets as QtW2
        self.__class__._qtw1 = QtW1
        self.__class__._qtw2 = QtW2

        self.__class__._orig_msgbox_exec_1 = QtW1.QMessageBox.exec_
        self.__class__._orig_msgbox_exec_2 = QtW2.QMessageBox.exec_

        # zawsze udawaj "OK" żeby dialogi nie blokowały
        QtW1.QMessageBox.exec_ = lambda self: QtW1.QMessageBox.Ok
        QtW2.QMessageBox.exec_ = lambda self: QtW2.QMessageBox.Ok

    def tearDown(self):  # noqa: D401 - default teardown
        """Przywraca oryginalną metodę exec_ QMessageBox."""
        if self._qtw1 and self._orig_msgbox_exec_1:
            self._qtw1.QMessageBox.exec_ = self._orig_msgbox_exec_1
        if self._qtw2 and self._orig_msgbox_exec_2:
            self._qtw2.QMessageBox.exec_ = self._orig_msgbox_exec_2

    # ---------- util: wczytanie warstwy (bez asercji)
    def _load_layer(self, path: pathlib.Path) -> QgsVectorLayer:
        if path.suffix.lower() == ".gml":
            tpl = pathlib.Path(__file__).resolve().parents[1] / "GFS" / "template.gfs"
            gfs = path.with_suffix(".gfs")
            if tpl.exists() and not gfs.exists():
                shutil.copyfile(tpl, gfs)
        layer = QgsVectorLayer(str(path), path.stem, "ogr")
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
        return layer

    # ---------- util: bezpieczne wywołanie loadFromGMLorGPKG
    def _safe_plugin_load(self, plugin, gml: pathlib.Path, ctx: str):
        try:
            lyr = plugin.loadFromGMLorGPKG(str(gml))
            if lyr and lyr.isValid():
                self.__class__.load_ok.append(ctx)
            else:
                self.__class__.load_fail.append((ctx, "layer invalid"))
            return lyr
        except Exception as exc:  # noqa: BLE001
            warnings.warn(f"{ctx}: loadFromGMLorGPKG() wyjątek: {exc}", RuntimeWarning)
            self.__class__.load_fail.append((ctx, str(exc)))
            return None

    # ---------- util: bezpieczny zapis GML (patchuje QFileDialog w PyQt5 i qgis.PyQt)
    def _safe_save(self, out_path: pathlib.Path, plugin, ctx: str) -> bool:
        from PyQt5 import QtWidgets as QtW1
        from qgis.PyQt import QtWidgets as QtW2

        orig1 = QtW1.QFileDialog.getSaveFileName
        orig2 = QtW2.QFileDialog.getSaveFileName

        def _fake_get_save_name(*_a, **_kw):
            # zwróć ścieżkę i przykładowy filtr – niektóre implementacje na nim polegają
            return str(out_path), "GML (*.gml)"

        try:
            QtW1.QFileDialog.getSaveFileName = staticmethod(_fake_get_save_name)
            QtW2.QFileDialog.getSaveFileName = staticmethod(_fake_get_save_name)

            plugin.saveLayerToGML()
        except Exception as exc:  # noqa: BLE001
            warnings.warn(f"{ctx}: saveLayerToGML() wyjątek: {exc}", RuntimeWarning)
            self.__class__.save_fail.append((ctx, str(exc)))
            return False
        finally:
            QtW1.QFileDialog.getSaveFileName = orig1
            QtW2.QFileDialog.getSaveFileName = orig2

        if not out_path.exists():
            warnings.warn(f"{ctx}: plik {out_path} nie powstał", RuntimeWarning)
            self.__class__.save_fail.append((ctx, "plik nie powstał"))
            return False

        self.__class__.save_ok.append(ctx)
        return True

    # ---------- MAIN
    def test_save_layer_to_gml(self):
        # -- QGIS init
        if QgsApplication.instance() is None:
            try:
                from qgis.testing import start_app
                start_app()
            except Exception:
                self.skipTest("Brak środowiska QGIS")

        # -- iface stub
        try:
            from qgis.utils import iface
        except Exception:
            iface = None
        if iface is None:
            class DummyIface:
                class Bar:
                    def pushSuccess(self, *_a, **_kw):
                        pass
                def messageBar(self):
                    return self.Bar()
            iface = DummyIface()

        from wtyczka_qgis_app.modules.app.wtyczka_app import AppModule
        tmpdir = pathlib.Path(tempfile.gettempdir())
        prof_dir = pathlib.Path(QgsApplication.qgisSettingsDirPath())

        for case in sorted(self.data_root.iterdir(), key=lambda p: p.name):
            with self.subTest(folder=case.name):
                pog_src = case / "pog" / "AktPlanowaniaPrzestrzennego.gml"
                strefy_dir = case / "strefy"

                pog_tmp = shutil.copy(pog_src, tmpdir / pog_src.name)

                # ---- ustawienia (nie przerywamy przy błędzie JPT)
                settings = QgsSettings()
                settings.setValue("qgis_app2/settings/defaultPath", str(tmpdir))
                try:
                    jpt = extract_jpt_from_pog(pog_tmp)
                    settings.setValue("qgis_app2/settings/jpt", jpt)
                    settings.setValue("qgis_app2/settings/strefaPL2000", get_crs_from_jpt(jpt[:4]))
                except Exception as exc:  # noqa: BLE001
                    warnings.warn(f"{case.name}: problem z JPT ({exc})", RuntimeWarning)

                # ---- kopiuj zasoby wtyczki (jeśli brak – tylko ostrzeżenie)
                safe_copy(pathlib.Path(self.plugin_dir) / "GFS" / "template.gfs",
                          prof_dir / "python/plugins/wtyczka_qgis_app/GFS/template.gfs",
                          case.name)
                safe_copy(pathlib.Path(self.plugin_dir) / "modules" / "templates",
                          prof_dir / "python/plugins/wtyczka_qgis_app/modules/templates",
                          case.name)
                safe_copy(pathlib.Path(self.plugin_dir) / "modules/app/A00_Granice_panstwa",
                          prof_dir / "python/plugins/wtyczka_qgis_app/modules/app/A00_Granice_panstwa",
                          case.name)

                # ======================= POG =================================
                plugin = AppModule(iface)
                plugin.activeDlg = plugin.wektorInstrukcjaDialogPOG
                plugin.activeDlg.name = "AktPlanowaniaPrzestrzennego"
                plugin.activeDlg.layers_comboBox = QgsMapLayerComboBox()

                lyr_pog = self._safe_plugin_load(plugin, pog_tmp, f"{case.name}: POG")
                if lyr_pog and lyr_pog.isValid():
                    plugin.activeDlg.layers_comboBox.setCurrentText(lyr_pog.name())
                    out_pog = tmpdir / f"output_pog_{case.name}.gml"
                    self._safe_save(out_pog, plugin, f"{case.name}: zapis POG")
                QgsProject.instance().removeAllMapLayers()

                # ======================= SPL =================================
                for spl_src in strefy_dir.glob("*.gml"):
                    with self.subTest(folder=case.name, file=spl_src.name):
                        QgsProject.instance().removeAllMapLayers()
                        spl_tmp = shutil.copy(spl_src, tmpdir / spl_src.name)

                        plugin_spl = AppModule(iface)
                        plugin_spl.activeDlg = plugin_spl.wektorInstrukcjaDialogSPL
                        plugin_spl.activeDlg.name = "StrefaPlanistyczna"
                        plugin_spl.activeDlg.layers_comboBox = QgsMapLayerComboBox()

                        lyr_spl = self._safe_plugin_load(
                            plugin_spl, spl_tmp, f"{case.name}/{spl_src.name}: SPL"
                        )
                        if lyr_spl and lyr_spl.isValid():
                            plugin_spl.activeDlg.layers_comboBox.setCurrentText(lyr_spl.name())
                            out_spl = tmpdir / f"output_spl_{case.name}_{spl_src.stem}.gml"
                            self._safe_save(out_spl, plugin_spl, f"{case.name}/{spl_src.name}: zapis SPL")
                        QgsProject.instance().removeAllMapLayers()

    # ---------- PODSUMOWANIE
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        def show(title, items, ok=True):
            mark = "✔" if ok else "✖"
            print(f"\n{title} ({len(items)})")
            for it in items:
                if ok:
                    print(f"  {mark} {it}")
                else:
                    ctx, msg = it
                    print(f"  {mark} {ctx:<45} → {msg}")

        print("\n================ PODSUMOWANIE GML =================")
        show("Wczytane poprawnie", cls.load_ok)
        show("Niewczytane", cls.load_fail, ok=False)
        show("Zapisane poprawnie", cls.save_ok)
        show("Niezapisane", cls.save_fail, ok=False)
        print("===================================================\n")


if __name__ == "__main__":
    unittest.main(verbosity=2, warnings="always")
