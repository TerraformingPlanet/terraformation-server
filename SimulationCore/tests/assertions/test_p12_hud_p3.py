"""
Script d'assertion pour la phase p12-hud-p3 : TileInspector UI Toolkit

Critères de sortie :
- TileInspector.uxml, BuildingCard.uxml, ConstructionCard.uxml
- sections Claim/Corp/Marché/Contrats/Nationalisation/Écologie
- conforme mockup paneau1.png
- remplace BuildRightPanel() + RebuildBuildingListUI() dans GameHUD.cs

Tests vérifient la présence des fichiers et structures UXML.
"""
import os
import pytest
import xml.etree.ElementTree as ET


# ── chemins des fichiers ──────────────────────────────────────────────────────

UNITY_ASSETS_PATH = "Game/Assets"
UI_TEMPLATES_PATH = f"{UNITY_ASSETS_PATH}/UI/Templates"
UI_COMPONENTS_PATH = f"{UNITY_ASSETS_PATH}/UI/Components"
SCRIPTS_PATH = f"{UNITY_ASSETS_PATH}/Scripts/UI"


# ── tests des fichiers UXML ───────────────────────────────────────────────────

def test_tile_inspector_uxml_exists():
    """Vérifie que TileInspector.uxml existe."""
    path = f"{UI_TEMPLATES_PATH}/TileInspector.uxml"
    assert os.path.exists(path), f"Fichier manquant : {path}"


def test_building_card_uxml_exists():
    """Vérifie que BuildingCard.uxml existe."""
    path = f"{UI_COMPONENTS_PATH}/BuildingCard.uxml"
    assert os.path.exists(path), f"Fichier manquant : {path}"


def test_construction_card_uxml_exists():
    """Vérifie que ConstructionCard.uxml existe (créé dans cette phase)."""
    path = f"{UI_COMPONENTS_PATH}/ConstructionCard.uxml"
    assert os.path.exists(path), f"Fichier manquant : {path}"


# ── tests de structure UXML ───────────────────────────────────────────────────

def test_tile_inspector_has_required_tabs():
    """Vérifie que TileInspector.uxml contient les 5 tabs requis."""
    path = f"{UI_TEMPLATES_PATH}/TileInspector.uxml"
    tree = ET.parse(path)
    root = tree.getroot()

    # Chercher les boutons de tab
    tab_buttons = []
    for elem in root.iter():
        if elem.tag.endswith("Button") and elem.get("name", "").startswith("tab-"):
            tab_buttons.append(elem.get("name"))

    expected_tabs = ["tab-resume", "tab-population", "tab-batiment", "tab-marche", "tab-contrats"]
    for tab in expected_tabs:
        assert tab in tab_buttons, f"Tab manquant dans TileInspector.uxml : {tab}"

    assert len(tab_buttons) >= 5, f"Nombre insuffisant de tabs : {len(tab_buttons)}"


def test_tile_inspector_has_required_sections():
    """Vérifie que TileInspector.uxml contient les sections requises."""
    path = f"{UI_TEMPLATES_PATH}/TileInspector.uxml"
    tree = ET.parse(path)
    root = tree.getroot()

    # Sections dans le tab résumé
    required_elements = [
        "corp-dropdown",
        "corp-list-container",
        "nationalisation-label", "btn-corrupt", "btn-cancel-nationalisation",
        "ecology-label"
    ]

    found_elements = []
    for elem in root.iter():
        name = elem.get("name")
        if name and name in required_elements:
            found_elements.append(name)

    for elem in required_elements:
        assert elem in found_elements, f"Élément manquant dans TileInspector.uxml : {elem}"


def test_tile_inspector_has_market_tab():
    """Vérifie que le tab marché contient market-list-container."""
    path = f"{UI_TEMPLATES_PATH}/TileInspector.uxml"
    tree = ET.parse(path)
    root = tree.getroot()

    market_container = None
    for elem in root.iter():
        if elem.get("name") == "market-bio-container":
            market_container = elem
            break

    assert market_container is not None, "market-bio-container manquant dans TileInspector.uxml"


def test_tile_inspector_has_contracts_tab():
    """Vérifie que le tab contrats contient les containers requis."""
    path = f"{UI_TEMPLATES_PATH}/TileInspector.uxml"
    tree = ET.parse(path)
    root = tree.getroot()

    public_container = None
    my_container = None
    for elem in root.iter():
        name = elem.get("name")
        if name == "public-contracts-container":
            public_container = elem
        elif name == "my-contracts-container":
            my_container = elem

    assert public_container is not None, "public-contracts-container manquant dans TileInspector.uxml"
    assert my_container is not None, "my-contracts-container manquant dans TileInspector.uxml"


# ── tests du script GameHUDController.cs ──────────────────────────────────────

def test_gamehud_controller_exists():
    """Vérifie que GameHUDController.cs existe."""
    path = f"{SCRIPTS_PATH}/GameHUDController.cs"
    assert os.path.exists(path), f"Fichier manquant : {path}"


def test_gamehud_controller_has_new_methods():
    """Vérifie que TileInspectorController.cs contient les méthodes de gestion de tuile."""
    path = f"{SCRIPTS_PATH}/HUD/TileInspectorController.cs"

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Méthodes de gestion des sections claim/corrupt/construct
    required_methods = [
        "OnCorruptClicked",
        "OnCancelNationalisationClicked",
        "RefreshStateRelationForTile",
        "OnConstructButtonClicked",
        "RebuildBuildingList",
    ]

    for method in required_methods:
        found = (f" {method}(" in content) or (f"\n    {method}(" in content)
        assert found, f"Méthode manquante dans TileInspectorController.cs : {method}"


def test_gamehud_controller_has_new_references():
    """Vérifie que TileInspectorController.cs contient les références d'éléments UI."""
    path = f"{SCRIPTS_PATH}/HUD/TileInspectorController.cs"

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Références d'éléments UI (déplacées dans TileInspectorController après refacto)
    required_refs = [
        "_corpListContainer",
        "_nationalisationLabel",
        "_btnCorrupt",
        "_btnCancelNationalisation",
        "_ecologyLabel",
        "_marketBioContainer",
        "_publicContractsContainer",
        "_myContractsContainer"
    ]

    for ref in required_refs:
        assert ref in content, f"Référence manquante dans TileInspectorController.cs : {ref}"