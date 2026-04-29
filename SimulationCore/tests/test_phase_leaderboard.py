"""
test_phase_leaderboard.py — Phase Leaderboard : Classement corporations.

Tests couverts :
    - compute_scoreboard_score : formule credits + tiles×100 + rep×50
    - build_scoreboard_entry : populates correctly
    - ScoreboardEntry JSON roundtrip
    - Edge cases

Pas de Docker, pas de réseau. Durée < 1 s.
"""
import json
import sys
import importlib.util
from pathlib import Path

_SIM = Path(__file__).parent.parent / "terraformation_sim"


def _load(name: str, rel: str):
    p = _SIM / rel
    spec = importlib.util.spec_from_file_location(f"terraformation_sim.{name}", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"terraformation_sim.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod


_models = _load("models", "models.py")
_states = _load("logic.states", "logic/states.py")

CorporationData = _models.CorporationData
ScoreboardEntry = _models.ScoreboardEntry

compute_scoreboard_score = _states.compute_scoreboard_score
build_scoreboard_entry = _states.build_scoreboard_entry


def _make_corp(corp_id: str, name: str, credits: float, tiles: list[str], rep: float) -> CorporationData:
    """Helper to create a test corporation."""
    return CorporationData(
        id=corp_id,
        name=name,
        credits=credits,
        claimedTiles=[{"tileId": t, "corpId": corp_id} for t in tiles],
        globalReputation=rep,
    )


# ── Test 1 : Formule de score ─────────────────────────────────────────────────

def test_compute_scoreboard_score_formula():
    """Score = credits + tiles×100 + rep×50."""
    corp = _make_corp("c1", "Test", credits=1000.0, tiles=["t1", "t2"], rep=0.8)
    score = compute_scoreboard_score(corp)
    expected = 1000.0 + 2 * 100.0 + 0.8 * 50.0  # 1000 + 200 + 40 = 1240
    assert score == expected, f"Expected {expected}, got {score}"
    print(f"✓ Score formula: {score} == {expected}")


def test_compute_scoreboard_score_edge_cases():
    """Test with zero tiles, zero rep, negative credits."""
    # Zero tiles
    corp1 = _make_corp("c1", "ZeroTiles", 500.0, [], 0.5)
    assert compute_scoreboard_score(corp1) == 500.0 + 25.0  # 525

    # Zero rep
    corp2 = _make_corp("c2", "ZeroRep", 300.0, ["t1"], 0.0)
    assert compute_scoreboard_score(corp2) == 300.0 + 100.0  # 400

    # Negative credits
    corp3 = _make_corp("c3", "Negative", -200.0, ["t1", "t2", "t3"], 1.0)
    assert compute_scoreboard_score(corp3) == -200.0 + 300.0 + 50.0  # 150

    print("✓ Edge cases OK")


# ── Test 2 : build_scoreboard_entry ───────────────────────────────────────────

def test_build_scoreboard_entry():
    """build_scoreboard_entry populates all fields correctly."""
    corp = _make_corp("c1", "Alpha Corp", 2500.0, ["t1", "t2", "t3"], 0.6)
    entry = build_scoreboard_entry(corp)

    assert entry.corpId == "c1"
    assert entry.corpName == "Alpha Corp"
    assert entry.credits == 2500.0
    assert entry.tileCount == 3
    assert entry.globalReputation == 0.6
    assert entry.score == 2500.0 + 3*100.0 + 0.6*50.0  # 2500 + 300 + 30 = 2830

    print(f"✓ build_scoreboard_entry: score={entry.score}")


# ── Test 3 : build_scoreboard_entry ───────────────────────────────────────────

def test_build_scoreboard_entry():
    """build_scoreboard_entry populates all fields correctly."""
    corp = _make_corp("c1", "Alpha Corp", 2500.0, ["t1", "t2", "t3"], 0.6)
    entry = build_scoreboard_entry(corp)

    assert entry.corpId == "c1"
    assert entry.corpName == "Alpha Corp"
    assert entry.credits == 2500.0
    assert entry.tileCount == 3
    assert entry.globalReputation == 0.6
    assert entry.score == 2500.0 + 3*100.0 + 0.6*50.0  # 2500 + 300 + 30 = 2830

    print(f"✓ build_scoreboard_entry: score={entry.score}")


# ── Test 4 : ScoreboardEntry JSON roundtrip ───────────────────────────────────

def test_scoreboard_entry_json_roundtrip():
    """ScoreboardEntry survives JSON serialization."""
    entry = ScoreboardEntry(
        corpId="test-corp",
        corpName="Test Corporation",
        credits=1234.56,
        tileCount=42,
        globalReputation=0.75,
        score=9876.54,
    )

    json_str = entry.model_dump_json()
    data = json.loads(json_str)
    entry2 = ScoreboardEntry.model_validate(data)

    assert entry2.corpId == entry.corpId
    assert entry2.score == entry.score
    assert entry2.tileCount == entry.tileCount

    print("✓ ScoreboardEntry JSON roundtrip OK")