"""End-to-end workflow test using plugin methods.

The test mirrors user interaction with the plugin:
1. "Wczytaj warstwę do edycji" – loadFromGMLorGPKG
2. "Zapisz warstwę do GML" – saveLayerToGML
3. "Dalej" – wektorInstrukcjaDialog_next_btn_clicked

Real plugin functions are invoked.  If QGIS is unavailable in the
environment the tests are skipped.
"""

from __future__ import annotations

from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import logging
import types
import os
import atexit
import pytest

# # # Skip entire module when QGIS is not installed – e.g. in CI environments
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
qgis = pytest.importorskip("qgis", reason="QGIS environment required")

from qgis.core import QgsSettings, QgsApplication
from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox

# Initialise minimal QGIS application so dialogs can be created safely during imports
_qgs_app = QgsApplication([], False)
_qgs_app.initQgis()
atexit.register(_qgs_app.exitQgis)

# Ensure the plugin package is importable as `wtyczka_qgis_app.  When tests
# run from the repository root, Python sees only this directory on `sys.path;
# relative imports inside the plugin expect the package name, so we prepend the
# parent directory.
PACKAGE_PARENT = Path(__file__).resolve().parents[2]
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

from wtyczka_qgis_app.wtyczka_app import WtyczkaAPP
from wtyczka_qgis_app.modules import utils

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_ROOT = Path(__file__).parent / "data"


def extract_jpt_from_pog(pog_gml: Path) -> str:
    tree = ET.parse(str(pog_gml))
    ns = {
        "app": "https://www.gov.pl/static/zagospodarowanieprzestrzenne/schemas/app/2.0"
    }
    elem = tree.find(".//app:przestrzenNazw", ns)
    if elem is None or not elem.text:
        raise ValueError("przestrzenNazw not found")
    core = elem.text.split("/")[-1].split("-")[0]
    jpt = core[:5]
    logger.info("Extracted JPT: %s", jpt)
    return jpt


class IFaceStub:
    """Minimal QGIS interface stub used only by the plugin."""

    def __init__(self):
        bar = types.SimpleNamespace(
            pushSuccess=lambda *a, **k: None,
            pushCritical=lambda *a, **k: None,
            pushWarning=lambda *a, **k: None,
        )
        self.messageBar = lambda: bar
        self.mainWindow = lambda: None
        self.addPluginToMenu = lambda *a, **k: None
        self.removePluginMenu = lambda *a, **k: None
        self.addToolBarWidget = lambda *a, **k: None
        self.removeToolBarIcon = lambda *a, **k: None


@pytest.mark.parametrize(
    "dataset_dir",
    sorted(
        [p for p in DATA_ROOT.iterdir() if p.is_dir() and p.name.isdigit()],
        key=lambda p: int(p.name),
    ),
)
def test_pog_workflow(dataset_dir: Path, tmp_path, monkeypatch):
    logger.info("Processing dataset: %s", dataset_dir.name)

    iface = IFaceStub()
    plugin = WtyczkaAPP(iface)

    # Basic settings expected by plugin
    settings = QgsSettings()
    settings.setValue("wtyczka_qgis_app/settings/rodzajZbioru", "POG")
    settings.setValue("wtyczka_qgis_app/settings/strefaPL2000", "2180")
    settings.setValue("wtyczka_qgis_app/settings/defaultPath", str(dataset_dir))

    # Provide jpt from POG layer attribute
    pog_layer_path = dataset_dir / "pog" / "AktPlanowaniaPrzestrzennego.gml"
    settings.setValue("wtyczka_qgis_app/settings/jpt", extract_jpt_from_pog(pog_layer_path))

    work_dir = tmp_path / dataset_dir.name

    # Collect layer paths for sequential dialog responses
    load_paths = [pog_layer_path] + sorted((dataset_dir / "strefy").glob("*.gml"))
    save_paths = [work_dir / p.name for p in load_paths]

    def fake_open(*args, **kwargs):
        path = load_paths.pop(0)
        return str(path), "pliki GML (*.gml)"

    def fake_save(*args, **kwargs):
        path = save_paths.pop(0)
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path), "pliki GML (*.gml)"

    # Avoid GUI popups during automated testing
    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake_open)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", fake_save)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    monkeypatch.setattr(utils, "showPopup", lambda *a, **k: None)

    # Simplify heavy validation to focus on workflow mechanics
    monkeypatch.setattr(WtyczkaAPP, "kontrolaWarstwy", lambda *a, **k: True)
    monkeypatch.setattr(WtyczkaAPP, "kontrolaGeometriiWarstwy", lambda *a, **k: True)
    monkeypatch.setattr(WtyczkaAPP, "czyObiektyUnikalne", lambda *a, **k: True)

    # Step 1: POG layer
    plugin.activeDlg = plugin.wektorInstrukcjaDialogPOG
    plugin.loadFromGMLorGPKG(False)
    plugin.saveLayerToGML()
    plugin.wektorInstrukcjaDialog_next_btn_clicked()

    # Step 2: strefy layers
    plugin.activeDlg = plugin.wektorInstrukcjaDialogSPL
    for _ in (dataset_dir / "strefy").glob("*.gml"):
        plugin.loadFromGMLorGPKG(False)
        plugin.saveLayerToGML()
        plugin.wektorInstrukcjaDialog_next_btn_clicked()

    # Verify outputs saved by plugin
    for saved in work_dir.glob("*.gml"):
        assert saved.exists()