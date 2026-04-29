"""
Assertion script — p12-hud-p5 : DebugDrawer UXML migration + GameHUD.cs suppression
Critères de sortie :
  - DebugDrawer.uxml existe avec la bonne structure
  - DebugDrawer.uss existe
  - GameHUD.cs est supprimé
  - GameHUDController.cs a les nouveaux champs/méthodes
  - SceneSetupHelper.cs ne référence plus le type GameHUD
"""

import os
import re

WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
GAME_ASSETS = os.path.join(WORKSPACE, "Game", "Assets")
SCRIPTS     = os.path.join(GAME_ASSETS, "Scripts")
TEMPLATES   = os.path.join(GAME_ASSETS, "UI", "Templates")
STYLES      = os.path.join(GAME_ASSETS, "UI", "Styles")

UXML         = os.path.join(TEMPLATES, "DebugDrawer.uxml")
USS          = os.path.join(STYLES,    "DebugDrawer.uss")
GAMEHUD_CS   = os.path.join(SCRIPTS, "UI",      "GameHUD.cs")
CONTROLLER   = os.path.join(SCRIPTS, "UI",      "GameHUDController.cs")
DEBUG_CTRL   = os.path.join(SCRIPTS, "UI", "HUD", "DebugDrawerController.cs")
SCENE_HELPER = os.path.join(SCRIPTS, "Editor",  "SceneSetupHelper.cs")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


# ─── DebugDrawer.uxml ─────────────────────────────────────────────────────────

def test_debug_drawer_uxml_exists():
    assert os.path.isfile(UXML), f"DebugDrawer.uxml absent : {UXML}"


def test_debug_drawer_uxml_root_element():
    content = _read(UXML)
    assert 'name="debug-drawer"' in content, "Élément racine 'debug-drawer' manquant dans DebugDrawer.uxml"


def test_debug_drawer_uxml_btn_projection():
    content = _read(UXML)
    assert 'name="btn-debug-projection"' in content, "'btn-debug-projection' absent de DebugDrawer.uxml"


def test_debug_drawer_uxml_btn_ownership():
    content = _read(UXML)
    assert 'name="btn-refresh-ownership"' in content, "'btn-refresh-ownership' absent de DebugDrawer.uxml"


def test_debug_drawer_uxml_btn_corps():
    content = _read(UXML)
    assert 'name="btn-refresh-corps"' in content, "'btn-refresh-corps' absent de DebugDrawer.uxml"


def test_debug_drawer_uxml_status_label():
    content = _read(UXML)
    assert 'name="debug-status"' in content, "'debug-status' absent de DebugDrawer.uxml"


def test_debug_drawer_uxml_corp_list():
    content = _read(UXML)
    assert 'name="debug-corp-list"' in content, "'debug-corp-list' absent de DebugDrawer.uxml"


def test_debug_drawer_uxml_references_uss():
    content = _read(UXML)
    assert "DebugDrawer.uss" in content, "DebugDrawer.uxml ne référence pas DebugDrawer.uss"


# ─── DebugDrawer.uss ──────────────────────────────────────────────────────────

def test_debug_drawer_uss_exists():
    assert os.path.isfile(USS), f"DebugDrawer.uss absent : {USS}"


def test_debug_drawer_uss_main_class():
    content = _read(USS)
    assert ".debug-drawer {" in content, "Classe '.debug-drawer' absente de DebugDrawer.uss"


def test_debug_drawer_uss_corp_row():
    content = _read(USS)
    assert ".debug-drawer__corp-row" in content, "Classe '.debug-drawer__corp-row' absente de DebugDrawer.uss"


def test_debug_drawer_uss_scroll():
    content = _read(USS)
    assert ".debug-drawer__scroll" in content, "Classe '.debug-drawer__scroll' absente de DebugDrawer.uss"


# ─── GameHUD.cs supprimé ─────────────────────────────────────────────────────

def test_gamehud_cs_deleted():
    assert not os.path.isfile(GAMEHUD_CS), \
        f"GameHUD.cs doit être supprimé mais existe encore : {GAMEHUD_CS}"


# ─── GameHUDController.cs ─────────────────────────────────────────────────────

def test_controller_debugdrawer_template_field():
    # debugDrawerTemplate est dans DebugDrawerController (sous-controleur)
    content = _read(DEBUG_CTRL)
    assert "debugDrawerTemplate" in content, "'debugDrawerTemplate' absent de DebugDrawerController.cs"


def test_controller_debug_drawer_field():
    content = _read(DEBUG_CTRL)
    assert "_debugDrawer" in content, "'_debugDrawer' absent de DebugDrawerController.cs"


def test_controller_debug_status_field():
    content = _read(DEBUG_CTRL)
    assert "_debugStatus" in content, "'_debugStatus' absent de DebugDrawerController.cs"


def test_controller_debug_corp_list_field():
    content = _read(DEBUG_CTRL)
    assert "_debugCorpListContainer" in content, "'_debugCorpListContainer' absent de DebugDrawerController.cs"


def test_controller_build_debug_drawer_method():
    content = _read(DEBUG_CTRL)
    assert "BuildDebugDrawer()" in content or "BuildDebugDrawer(" in content, \
        "'BuildDebugDrawer' absent de DebugDrawerController.cs"


def test_controller_toggle_debug_drawer_method():
    content = _read(CONTROLLER)
    assert "ToggleDebugDrawer()" in content or "ToggleDebugDrawer(" in content, \
        "'ToggleDebugDrawer' absent de GameHUDController.cs"


def test_controller_refresh_corps_method():
    content = _read(DEBUG_CTRL)
    assert "RefreshCorpsForDebug" in content, "'RefreshCorpsForDebug' absent de DebugDrawerController.cs"


def test_controller_rebuild_corp_list_method():
    content = _read(DEBUG_CTRL)
    assert "RebuildDebugCorpList" in content, "'RebuildDebugCorpList' absent de DebugDrawerController.cs"


def test_controller_update_method():
    content = _read(CONTROLLER)
    assert "private void Update()" in content, "'Update()' absent de GameHUDController.cs"


def test_controller_f9_key():
    content = _read(CONTROLLER)
    assert "f9Key" in content, "f9Key (toggle debug drawer) absent de GameHUDController.cs"


def test_controller_f10_key():
    content = _read(CONTROLLER)
    assert "f10Key" in content, "f10Key (debug projection) absent de GameHUDController.cs"


def test_controller_input_system_using():
    content = _read(CONTROLLER)
    assert "using UnityEngine.InputSystem;" in content, \
        "'using UnityEngine.InputSystem;' absent de GameHUDController.cs"


# ─── SceneSetupHelper.cs ──────────────────────────────────────────────────────

def test_scene_setup_helper_no_gamehud_type():
    """SceneSetupHelper ne doit plus référencer le type GameHUD (ni AddComponent<GameHUD>)."""
    content = _read(SCENE_HELPER)
    assert "AddComponent<GameHUD>()" not in content, \
        "SceneSetupHelper.cs contient encore 'AddComponent<GameHUD>()'"
    assert "GetComponentsInChildren<GameHUD>" not in content, \
        "SceneSetupHelper.cs contient encore 'GetComponentsInChildren<GameHUD>'"


def test_scene_setup_helper_has_gamehudcontroller():
    content = _read(SCENE_HELPER)
    assert "AddGameHUDController" in content, \
        "'AddGameHUDController' absent de SceneSetupHelper.cs"
