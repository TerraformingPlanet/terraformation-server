"""
test_phase74_contracts.py — Phase 7.4 : Contrats v1.

Tests couverts :
    - Roundtrip JSON ContractData (tous les champs)
    - can_propose_contract — validation crédit
    - can_bid_contract / can_accept_private — validation état
    - process_delivery_tick — livraison partielle auto
    - apply_completion — crédits transférés + knowledgeBonus ResearchPoints
    - apply_break — penaltyCredits déduites du breaker
    - check_bidding_expiry — expiry public contract

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


_models    = _load("models", "models.py")
_contracts = _load("logic.contracts", "logic/contracts.py")

ContractData       = _models.ContractData
ContractStatus     = _models.ContractStatus
ContractVisibility = _models.ContractVisibility
CorporationData    = _models.CorporationData
ResourceType       = _models.ResourceType

can_propose_contract   = _contracts.can_propose_contract
can_bid_contract       = _contracts.can_bid_contract
can_accept_private     = _contracts.can_accept_private
can_break_contract     = _contracts.can_break_contract
process_delivery_tick  = _contracts.process_delivery_tick
apply_completion       = _contracts.apply_completion
apply_break            = _contracts.apply_break
check_completion       = _contracts.check_completion
check_bidding_expiry   = _contracts.check_bidding_expiry


def _make_corp(corp_id: str, credits: float = 1000.0, food: float = 0.0) -> CorporationData:
    resources = {"Food": food} if food > 0 else {}
    return CorporationData(id=corp_id, name=corp_id, credits=credits, resources=resources)


def _make_contract(
    proposer_id: str = "corp1",
    visibility: int = 1,          # Private by default
    resource_amount: float = 50.0,
    reward: float = 100.0,
    penalty: float = 20.0,
    knowledge: float = 0.0,
    status: ContractStatus = ContractStatus.Proposed,
    acceptor_id: str = "",
    bidding_close: int = 10,
) -> ContractData:
    return ContractData(
        id="c1",
        status=status,
        visibility=ContractVisibility(visibility),
        proposerId=proposer_id,
        targetId="corp2" if visibility == 1 else "",
        acceptorId=acceptor_id,
        resourceType=ResourceType.Food,
        resourceAmount=resource_amount,
        deliveredAmount=0.0,
        rewardCredits=reward,
        penaltyCredits=penalty,
        knowledgeBonus=knowledge,
        durationTicks=0,
        startTick=0,
        biddingWindowTicks=5,
        biddingCloseTick=bidding_close,
        tickCreated=0,
    )


# ── Test 1 : Roundtrip JSON ───────────────────────────────────────────────────

def test_contract_data_roundtrip():
    contract = _make_contract(knowledge=15.0)
    data = json.loads(contract.model_dump_json())
    c2 = ContractData.model_validate(data)

    assert c2.id == "c1"
    assert c2.resourceAmount == 50.0
    assert c2.rewardCredits == 100.0
    assert c2.penaltyCredits == 20.0
    assert c2.knowledgeBonus == 15.0
    assert c2.status == ContractStatus.Proposed
    assert c2.visibility == ContractVisibility.Private
    print("✓ ContractData roundtrip OK")


# ── Test 2 : can_propose_contract ─────────────────────────────────────────────

def test_can_propose_contract_ok():
    corp = _make_corp("corp1", credits=500.0)
    ok, reason = can_propose_contract(corp, resource_amount=50.0, reward_credits=100.0)
    assert ok, reason
    print("✓ can_propose_contract OK with sufficient credits")


def test_can_propose_contract_rejects_insufficient_credits():
    corp = _make_corp("corp1", credits=50.0)
    ok, reason = can_propose_contract(corp, resource_amount=50.0, reward_credits=100.0)
    assert not ok
    assert "Insufficient" in reason
    print(f"✓ can_propose_contract rejected: {reason}")


# ── Test 3 : can_bid_contract ─────────────────────────────────────────────────

def test_can_bid_public_contract_ok():
    bidder   = _make_corp("corp2")
    contract = _make_contract(proposer_id="corp1", visibility=0, bidding_close=10)  # Public
    ok, reason = can_bid_contract(bidder, contract, current_tick=5)
    assert ok, reason
    print("✓ can_bid_contract (public) OK")


def test_can_bid_contract_rejects_past_deadline():
    bidder   = _make_corp("corp2")
    contract = _make_contract(proposer_id="corp1", visibility=0, bidding_close=5)  # Public
    ok, reason = can_bid_contract(bidder, contract, current_tick=6)
    assert not ok
    assert "Bidding window" in reason
    print(f"✓ can_bid_contract past deadline rejected: {reason}")


# ── Test 4 : can_accept_private ───────────────────────────────────────────────

def test_can_accept_private_contract_ok():
    acceptor = _make_corp("corp2")
    contract = _make_contract(proposer_id="corp1", visibility=1)
    ok, reason = can_accept_private(acceptor, contract)
    assert ok, reason
    print("✓ can_accept_private OK")


def test_can_accept_private_wrong_target():
    acceptor = _make_corp("corp3")  # Not the target
    contract = _make_contract(proposer_id="corp1", visibility=1)
    ok, reason = can_accept_private(acceptor, contract)
    assert not ok
    assert "not directed" in reason
    print(f"✓ can_accept_private wrong target rejected: {reason}")


# ── Test 5 : process_delivery_tick ────────────────────────────────────────────

def test_process_delivery_tick_delivers_partially():
    contract = _make_contract(resource_amount=50.0)
    contract = contract.model_copy(update={"status": ContractStatus.Active, "acceptorId": "corp2"})
    acceptor = _make_corp("corp2", food=30.0)  # Has 30 food, needs 50

    new_contract, new_acceptor = process_delivery_tick(contract, acceptor)

    assert new_contract.deliveredAmount == 30.0, f"Expected 30.0, got {new_contract.deliveredAmount}"
    assert new_acceptor.resources.get("Food", 0.0) == 0.0
    assert not check_completion(new_contract)
    print(f"✓ process_delivery_tick partial: delivered={new_contract.deliveredAmount}")


def test_process_delivery_tick_completes_contract():
    contract = _make_contract(resource_amount=50.0)
    contract = contract.model_copy(update={"status": ContractStatus.Active, "acceptorId": "corp2"})
    acceptor = _make_corp("corp2", food=100.0)  # More than enough

    new_contract, new_acceptor = process_delivery_tick(contract, acceptor)

    assert new_contract.deliveredAmount == 50.0
    assert check_completion(new_contract)
    assert new_acceptor.resources["Food"] == 50.0
    print(f"✓ process_delivery_tick completed: delivered={new_contract.deliveredAmount}")


# ── Test 6 : apply_completion ─────────────────────────────────────────────────

def test_apply_completion_transfers_credits_and_knowledge_bonus():
    contract = _make_contract(
        resource_amount=50.0, reward=200.0, knowledge=25.0
    )
    contract = contract.model_copy(update={
        "status": ContractStatus.Active,
        "acceptorId": "corp2",
        "deliveredAmount": 50.0,
    })
    proposer = _make_corp("corp1", credits=1000.0)
    acceptor = _make_corp("corp2", credits=200.0)

    new_contract, new_proposer, new_acceptor = apply_completion(contract, proposer, acceptor)

    assert new_contract.status == ContractStatus.Completed
    assert abs(new_proposer.credits - 800.0) < 0.01, f"Expected 800, got {new_proposer.credits}"
    assert abs(new_acceptor.credits - 400.0) < 0.01, f"Expected 400, got {new_acceptor.credits}"
    # Knowledge bonus → ResearchPoints
    rp = new_acceptor.resources.get("ResearchPoints", 0.0)
    assert abs(rp - 25.0) < 0.01, f"Expected ResearchPoints=25.0, got {rp}"
    print(f"✓ apply_completion: proposer={new_proposer.credits}, acceptor={new_acceptor.credits}, RP={rp}")


# ── Test 7 : apply_break ──────────────────────────────────────────────────────

def test_apply_break_deducts_penalty_from_breaker():
    contract = _make_contract(penalty=50.0)
    contract = contract.model_copy(update={
        "status": ContractStatus.Active,
        "acceptorId": "corp2",
    })
    breaker = _make_corp("corp2", credits=200.0)
    other   = _make_corp("corp1", credits=500.0)

    new_contract, new_breaker, new_other = apply_break(contract, breaker, other)

    assert new_contract.status == ContractStatus.Broken
    assert abs(new_breaker.credits - 150.0) < 0.01, f"Expected 150, got {new_breaker.credits}"
    assert abs(new_other.credits - 550.0) < 0.01, f"Expected 550, got {new_other.credits}"
    print(f"✓ apply_break: breaker={new_breaker.credits}, other={new_other.credits}")


# ── Test 8 : check_bidding_expiry ─────────────────────────────────────────────

def test_check_bidding_expiry_detects_expired_window():
    contract = _make_contract(proposer_id="corp1", visibility=0, bidding_close=5)  # Public
    assert check_bidding_expiry(contract, current_tick=6), "Should be expired at tick 6"
    assert not check_bidding_expiry(contract, current_tick=4), "Should not be expired at tick 4"
    print("✓ check_bidding_expiry OK")
