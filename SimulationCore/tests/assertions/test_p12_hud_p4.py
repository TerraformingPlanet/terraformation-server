"""
Assertions — Phase p12-hud-p4 : EventFeed + Tooltip + EventPopup

Exit criteria :
  - EventFeed.uxml présent dans Game/Assets/UI/Templates/
  - Tooltip.uxml présent dans Game/Assets/UI/Templates/
  - EventPopup.uxml présent dans Game/Assets/UI/Templates/
  - EventFeed.uxml contient les éléments : event-feed, event-feed-tabs,
    tab-events, tab-actions, event-feed-list, event-feed-actions
  - Tooltip.uxml contient : hud-tooltip, hud-tooltip-label
  - EventPopup.uxml contient : event-popup, event-popup-title, event-popup-body
  - GameHUDController.cs expose : eventFeedTemplate, tooltipTemplate,
    eventPopupTemplate, BuildEventFeed, BuildEventFeedProcedural,
    BuildTooltip, BuildEventPopup, ShowEventPopup, HideEventPopup
  - base.uss contient .event-popup et EventFeed positionné bottom/left
  - EventFeed.uxml référence base.uss
"""
import os
import pytest

GAME_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "Game")
)
TEMPLATES = os.path.join(GAME_ROOT, "Assets", "UI", "Templates")
STYLES    = os.path.join(GAME_ROOT, "Assets", "UI", "Styles")
SCRIPTS     = os.path.join(GAME_ROOT, "Assets", "Scripts", "UI")
HUD_SCRIPTS = os.path.join(GAME_ROOT, "Assets", "Scripts", "UI", "HUD")


# ── helpers ───────────────────────────────────────────────────────────────────

def _uxml(name: str) -> str:
    return os.path.join(TEMPLATES, name)

def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


# ── fichiers UXML ─────────────────────────────────────────────────────────────

def test_event_feed_uxml_exists():
    assert os.path.isfile(_uxml("EventFeed.uxml")), "EventFeed.uxml manquant"

def test_tooltip_uxml_exists():
    assert os.path.isfile(_uxml("Tooltip.uxml")), "Tooltip.uxml manquant"

def test_event_popup_uxml_exists():
    assert os.path.isfile(_uxml("EventPopup.uxml")), "EventPopup.uxml manquant"


# ── contenu EventFeed.uxml ────────────────────────────────────────────────────

def test_event_feed_uxml_structure():
    content = _read(_uxml("EventFeed.uxml"))
    for element in ("event-feed", "event-feed-tabs", "tab-events",
                    "tab-actions", "event-feed-list", "event-feed-actions"):
        assert element in content, f"EventFeed.uxml: élément '{element}' manquant"

def test_event_feed_uxml_references_base_uss():
    content = _read(_uxml("EventFeed.uxml"))
    assert "base.uss" in content, "EventFeed.uxml doit référencer base.uss"


# ── contenu Tooltip.uxml ─────────────────────────────────────────────────────

def test_tooltip_uxml_structure():
    content = _read(_uxml("Tooltip.uxml"))
    for element in ("hud-tooltip", "hud-tooltip-label"):
        assert element in content, f"Tooltip.uxml: élément '{element}' manquant"

def test_tooltip_picking_mode_ignore():
    content = _read(_uxml("Tooltip.uxml"))
    assert "picking-mode=\"Ignore\"" in content or "picking-mode='Ignore'" in content, \
        "Tooltip.uxml doit avoir picking-mode=Ignore"


# ── contenu EventPopup.uxml ───────────────────────────────────────────────────

def test_event_popup_uxml_structure():
    content = _read(_uxml("EventPopup.uxml"))
    for element in ("event-popup", "event-popup-title", "event-popup-body"):
        assert element in content, f"EventPopup.uxml: élément '{element}' manquant"

def test_event_popup_picking_mode_ignore():
    content = _read(_uxml("EventPopup.uxml"))
    assert "picking-mode=\"Ignore\"" in content or "picking-mode='Ignore'" in content, \
        "EventPopup.uxml doit avoir picking-mode=Ignore"


# ── base.uss ──────────────────────────────────────────────────────────────────

def test_base_uss_event_popup_style():
    content = _read(os.path.join(STYLES, "base.uss"))
    assert ".event-popup" in content, "base.uss doit contenir .event-popup"
    assert ".event-popup__title" in content, "base.uss doit contenir .event-popup__title"
    assert ".event-popup__body"  in content, "base.uss doit contenir .event-popup__body"

def test_base_uss_event_feed_bottom_left():
    content = _read(os.path.join(STYLES, "base.uss"))
    # EventFeed migré vers bas-gauche : doit avoir left: et bottom: (pas right:) dans .event-feed
    # Vérifier que left apparaît après .event-feed
    idx = content.find(".event-feed {")
    assert idx != -1, ".event-feed manquant dans base.uss"
    block = content[idx:idx + 200]
    assert "left:" in block, ".event-feed doit être positionné à gauche (left:)"


# ── GameHUDController.cs ──────────────────────────────────────────────────────

def test_controller_template_fields():
    # tooltipTemplate et eventPopupTemplate restent dans l'orchestrateur
    controller = _read(os.path.join(SCRIPTS, "GameHUDController.cs"))
    for field in ("tooltipTemplate", "eventPopupTemplate"):
        assert field in controller, f"GameHUDController.cs: champ '{field}' manquant"
    # eventFeedTemplate est dans le sous-controleur EventFeedController
    event_feed = _read(os.path.join(HUD_SCRIPTS, "EventFeedController.cs"))
    assert "eventFeedTemplate" in event_feed, "EventFeedController.cs: champ 'eventFeedTemplate' manquant"

def test_controller_build_methods():
    # BuildEventFeed et BuildEventFeedProcedural sont dans EventFeedController
    event_feed = _read(os.path.join(HUD_SCRIPTS, "EventFeedController.cs"))
    for method in ("BuildEventFeed(", "BuildEventFeedProcedural("):
        assert method in event_feed, f"EventFeedController.cs: methode '{method}' manquante"
    # BuildTooltip, BuildEventPopup, ShowEventPopup, HideEventPopup restent dans l'orchestrateur
    controller = _read(os.path.join(SCRIPTS, "GameHUDController.cs"))
    for method in ("BuildTooltip(", "BuildEventPopup(", "ShowEventPopup(", "HideEventPopup("):
        assert method in controller, f"GameHUDController.cs: methode '{method}' manquante"

def test_controller_event_popup_fields():
    content = _read(os.path.join(SCRIPTS, "GameHUDController.cs"))
    for field in ("_eventPopup", "_eventPopupTitle", "_eventPopupBody"):
        assert field in content, f"GameHUDController.cs: champ '{field}' manquant"
