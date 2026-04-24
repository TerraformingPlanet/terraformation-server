"""
Template de script d'assertion pour une phase de roadmap.

Copier ce fichier, renommer en test_<phase_id>.py (tirets → underscores),
puis remplir les tests selon les exit_criteria de la phase.

Convention de nommage :
  phase id  →  p10-economy
  fichier   →  test_p10_economy.py

Lien dans la phase :
  assertion_script = "SimulationCore/tests/assertions/test_p10_economy.py"
"""
import pytest

# ── imports nécessaires à la phase ────────────────────────────────────────────
# from terraformation_sim.models import ...
# from terraformation_sim.runtime import ...


# ── fixtures ──────────────────────────────────────────────────────────────────

# @pytest.fixture
# def world_state():
#     """Provide a minimal world state for testing."""
#     ...


# ── tests des critères de sortie ──────────────────────────────────────────────

def test_placeholder():
    """
    REMPLACER par les vrais tests des exit_criteria de la phase.

    Exemples :
    - test_economy_ticks_produce_resources()
    - test_market_price_bounded()
    - test_contract_lifecycle_complete()
    """
    # TODO: implement based on phase exit_criteria
    pass
