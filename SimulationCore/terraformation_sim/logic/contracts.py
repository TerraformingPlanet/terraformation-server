"""
Contract logic — Phase 7.4 Contrats v1 (Corp ↔ Corp, ResourceDelivery only).

Pure functions: no side effects, no registry access, no `self`.
All state mutations happen in runtime.py via _process_contract_tick_locked().
"""
from __future__ import annotations

from ..models import (
    ContractData,
    ContractStatus,
    ContractVisibility,
    CorporationData,
)


# ── Validation helpers ────────────────────────────────────────────────────────

def can_propose_contract(
    proposer: CorporationData,
    resource_amount: float,
    reward_credits: float,
) -> tuple[bool, str]:
    """Check that the proposer has enough credits to back the reward."""
    if resource_amount <= 0:
        return False, "resourceAmount must be > 0"
    if reward_credits < 0:
        return False, "rewardCredits must be >= 0"
    if proposer.credits < reward_credits:
        return False, f"Insufficient credits: need {reward_credits}, have {proposer.credits:.2f}"
    return True, ""


def can_bid_contract(
    bidder: CorporationData,
    contract: ContractData,
    current_tick: int,
) -> tuple[bool, str]:
    """Check that a corp can place a bid on a public contract."""
    if contract.visibility != ContractVisibility.Public:
        return False, "Contract is not public"
    if contract.status != ContractStatus.Proposed:
        return False, f"Contract is not open for bids (status={contract.status.name})"
    if current_tick > contract.biddingCloseTick:
        return False, "Bidding window has closed"
    if bidder.id == contract.proposerId:
        return False, "Proposer cannot bid on their own contract"
    if bidder.id in contract.candidates:
        return False, "Already a candidate on this contract"
    return True, ""


def can_confirm_bidder(
    proposer: CorporationData,
    contract: ContractData,
    bidder_id: str,
) -> tuple[bool, str]:
    """Check that the proposer can confirm a candidate as acceptor."""
    if contract.proposerId != proposer.id:
        return False, "Only the proposer can confirm a bidder"
    if contract.status != ContractStatus.Proposed:
        return False, f"Contract is not in Proposed status (status={contract.status.name})"
    if bidder_id not in contract.candidates:
        return False, f"'{bidder_id}' is not a candidate on this contract"
    return True, ""


def can_accept_private(
    acceptor: CorporationData,
    contract: ContractData,
) -> tuple[bool, str]:
    """Check that a corp can accept a private contract directed at them."""
    if contract.visibility != ContractVisibility.Private:
        return False, "Use bid/confirm for public contracts"
    if contract.status != ContractStatus.Proposed:
        return False, f"Contract is not open for acceptance (status={contract.status.name})"
    if contract.targetId and contract.targetId != acceptor.id:
        return False, "This contract is not directed at your corporation"
    return True, ""


def can_break_contract(
    corp: CorporationData,
    contract: ContractData,
) -> tuple[bool, str]:
    """Check that a corp is a party to an active contract and can break it."""
    if contract.status != ContractStatus.Active:
        return False, f"Contract is not active (status={contract.status.name})"
    if corp.id not in (contract.proposerId, contract.acceptorId):
        return False, "Corporation is not a party to this contract"
    return True, ""


# ── Tick-time mutation ────────────────────────────────────────────────────────

def process_delivery_tick(
    contract: ContractData,
    acceptor: CorporationData,
) -> tuple[ContractData, CorporationData]:
    """Auto-deliver resources for one tick.

    Deducts min(available, remaining) from acceptor.resources and increments
    deliveredAmount. Returns updated (contract, acceptor) copies.
    """
    remaining = contract.resourceAmount - contract.deliveredAmount
    if remaining <= 0:
        return contract, acceptor

    resource_key = contract.resourceType
    available = acceptor.resources.get(resource_key, 0.0)
    delivered = min(available, remaining)

    if delivered <= 0:
        return contract, acceptor

    new_resources = dict(acceptor.resources)
    new_resources[resource_key] = max(0.0, available - delivered)
    new_acceptor = acceptor.model_copy(update={"resources": new_resources})
    new_contract = contract.model_copy(
        update={"deliveredAmount": contract.deliveredAmount + delivered}
    )
    return new_contract, new_acceptor


def check_completion(contract: ContractData) -> bool:
    """Return True if deliveredAmount has reached resourceAmount."""
    return contract.deliveredAmount >= contract.resourceAmount


def apply_completion(
    contract: ContractData,
    proposer: CorporationData,
    acceptor: CorporationData,
) -> tuple[ContractData, CorporationData, CorporationData]:
    """Finalise a completed contract.

    - Credits rewardCredits from proposer to acceptor.
    - Credits knowledgeBonus as ResearchPoints to acceptor.
    Returns updated (contract, proposer, acceptor).
    """
    new_contract  = contract.model_copy(update={"status": ContractStatus.Completed})

    new_proposer_credits  = proposer.credits  - contract.rewardCredits
    new_acceptor_credits  = acceptor.credits  + contract.rewardCredits

    # Knowledge bonus → ResearchPoints in acceptor.resources
    acceptor_resources = dict(acceptor.resources)
    if contract.knowledgeBonus > 0:
        rp_key = "ResearchPoints"
        acceptor_resources[rp_key] = acceptor_resources.get(rp_key, 0.0) + contract.knowledgeBonus

    new_proposer = proposer.model_copy(update={"credits": max(0.0, new_proposer_credits)})
    new_acceptor = acceptor.model_copy(update={
        "credits":   new_acceptor_credits,
        "resources": acceptor_resources,
    })
    return new_contract, new_proposer, new_acceptor


def apply_break(
    contract: ContractData,
    breaker: CorporationData,
    other: CorporationData,
) -> tuple[ContractData, CorporationData, CorporationData]:
    """Apply a contract break penalty.

    - Deducts penaltyCredits from breaker (can go negative — debt allowed).
    - Credits penaltyCredits to other party.
    Returns updated (contract, breaker, other).
    """
    new_contract = contract.model_copy(update={"status": ContractStatus.Broken})
    new_breaker  = breaker.model_copy(
        update={"credits": breaker.credits - contract.penaltyCredits}
    )
    new_other = other.model_copy(
        update={"credits": other.credits + contract.penaltyCredits}
    )
    return new_contract, new_breaker, new_other


def apply_expiry(contract: ContractData) -> ContractData:
    """Mark a contract as Expired (no penalty — it just ran out of time)."""
    return contract.model_copy(update={"status": ContractStatus.Expired})


def check_bidding_expiry(contract: ContractData, current_tick: int) -> bool:
    """Return True if the public bidding window has closed with no acceptor yet."""
    return (
        contract.visibility == ContractVisibility.Public
        and contract.status == ContractStatus.Proposed
        and current_tick > contract.biddingCloseTick
    )
