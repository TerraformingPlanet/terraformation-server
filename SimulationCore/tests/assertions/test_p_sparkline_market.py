"""
Assertion script — p_sparkline_market : SparklineElement vectorial market graph
Critères de sortie :
  - SparklineElement.cs existe dans UI/Components/
  - GenerateVisualContent avec MeshGenerationContext est présent
  - base.uss contient la classe .market-sparkline-curve
  - TileInspectorController.cs utilise SparklineElement dans RebuildBioMarketList et RebuildFinancialMarketList
  - TileInspectorController.cs ne contient plus de sparklines unicode (▁▂▃▄▅▆▇█)
"""

import os
import re

WORKSPACE   = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
GAME_ASSETS = os.path.join(WORKSPACE, "Game", "Assets")
SCRIPTS     = os.path.join(GAME_ASSETS, "Scripts")
STYLES      = os.path.join(GAME_ASSETS, "UI", "Styles")

SPARKLINE_CS    = os.path.join(SCRIPTS, "UI", "Components", "SparklineElement.cs")
TILE_CTRL_CS    = os.path.join(SCRIPTS, "UI", "HUD", "TileInspectorController.cs")
BASE_USS        = os.path.join(STYLES, "base.uss")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


# ─── SparklineElement.cs ──────────────────────────────────────────────────────

def test_sparkline_element_exists():
    assert os.path.isfile(SPARKLINE_CS), f"SparklineElement.cs absent : {SPARKLINE_CS}"


def test_sparkline_extends_visual_element():
    content = _read(SPARKLINE_CS)
    assert "VisualElement" in content, "SparklineElement doit hériter de VisualElement"


def test_sparkline_has_generate_visual_content():
    content = _read(SPARKLINE_CS)
    assert "generateVisualContent" in content, "generateVisualContent callback manquant"
    assert "MeshGenerationContext" in content, "MeshGenerationContext manquant"


def test_sparkline_has_set_data():
    content = _read(SPARKLINE_CS)
    assert "SetData" in content, "Méthode SetData() manquante"


def test_sparkline_uses_painter2d():
    content = _read(SPARKLINE_CS)
    assert "painter2D" in content, "painter2D (MeshGenerationContext) non utilisé"


def test_sparkline_has_uxml_factory():
    content = _read(SPARKLINE_CS)
    assert "UxmlFactory" in content, "UxmlFactory manquante (UXML instanciation)"


# ─── base.uss ─────────────────────────────────────────────────────────────────

def test_base_uss_has_sparkline_curve_class():
    content = _read(BASE_USS)
    assert ".market-sparkline-curve" in content, ".market-sparkline-curve absent de base.uss"


def test_base_uss_sparkline_curve_has_height():
    content = _read(BASE_USS)
    # Find the block
    match = re.search(r"\.market-sparkline-curve\s*\{([^}]+)\}", content)
    assert match, ".market-sparkline-curve block not found"
    block = match.group(1)
    assert "height" in block, ".market-sparkline-curve doit définir une height"


# ─── TileInspectorController.cs ──────────────────────────────────────────────

def test_tile_controller_uses_sparkline_in_bio():
    content = _read(TILE_CTRL_CS)
    assert "RebuildBioMarketList" in content, "RebuildBioMarketList() absent"
    # SparklineElement must be instantiated somewhere in or near that method
    assert "SparklineElement" in content, "SparklineElement non utilisé dans TileInspectorController"


def test_tile_controller_uses_sparkline_in_financial():
    content = _read(TILE_CTRL_CS)
    assert "RebuildFinancialMarketList" in content, "RebuildFinancialMarketList() absent"


def test_tile_controller_no_unicode_sparklines():
    content = _read(TILE_CTRL_CS)
    unicode_bars = "▁▂▃▄▅▆▇█"
    for char in unicode_bars:
        assert char not in content, \
            f"Caractère unicode sparkline '{char}' encore présent dans TileInspectorController.cs — remplacer par SparklineElement"


def test_tile_controller_has_refresh_market_coroutine():
    content = _read(TILE_CTRL_CS)
    assert "RefreshMarketData" in content, "Coroutine RefreshMarketData() absente"


def test_tile_controller_bio_market_dto():
    content = _read(TILE_CTRL_CS)
    assert "TileBioMarketStateDto" in content or "TileBioListingDto" in content, \
        "DTO bio-market absent dans TileInspectorController"


def test_tile_controller_local_market_dto():
    content = _read(TILE_CTRL_CS)
    assert "LocalMarketStateDto" in content or "ResourceListingDto" in content, \
        "DTO local market absent dans TileInspectorController"
