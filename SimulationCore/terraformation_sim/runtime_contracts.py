from __future__ import annotations

from uuid import uuid4

from .models import (
    ContractData,
    ContractStatus,
    ContractVisibility,
)
from .logic.contracts import (
    can_propose_contract,
    can_bid_contract,
    can_confirm_bidder,
    can_accept_private,
    can_break_contract,
    process_delivery_tick,
    check_completion,
    apply_completion,
    apply_break,
    apply_expiry,
    check_bidding_expiry,
)


class ContractsMixin:
    """Contract registry and contract lifecycle methods.

    State accessed via self:
        self._lock, self._contracts, self._corporations, self._tick_count, self._repo
    """

    # ── Contract registry (Phase 7.4) ─────────────────────────────────────────

    def propose_contract(
        self,
        proposer_id: str,
        resource_type: str,
        resource_amount: float,
        reward_credits: float,
        penalty_credits: float = 0.0,
        duration_ticks: int = 0,
        visibility: str = "Private",
        target_id: str = "",
        bidding_window_ticks: int = 5,
        knowledge_bonus: float = 0.0,
    ) -> ContractData:
        with self._lock:
            proposer = self._corporations.get(proposer_id)
            if proposer is None:
                raise KeyError(f"Corporation '{proposer_id}' not found")
            if target_id and target_id not in self._corporations:
                raise KeyError(f"Target corporation '{target_id}' not found")

            vis = ContractVisibility[visibility]
            rt  = resource_type  # already a string resource_id
            ok, reason = can_propose_contract(proposer, resource_amount, reward_credits)
            if not ok:
                raise ValueError(reason)

            contract_id = str(uuid4())
            close_tick  = self._tick_count + bidding_window_ticks
            expire_tick = (self._tick_count + duration_ticks) if duration_ticks > 0 else 0

            contract = ContractData(
                id=contract_id,
                status=ContractStatus.Proposed,
                visibility=vis,
                proposerId=proposer_id,
                targetId=target_id if vis == ContractVisibility.Private else "",
                resourceType=rt,
                resourceAmount=resource_amount,
                rewardCredits=reward_credits,
                penaltyCredits=penalty_credits,
                knowledgeBonus=knowledge_bonus,
                durationTicks=duration_ticks,
                expiresAtTick=expire_tick,
                biddingWindowTicks=bidding_window_ticks,
                biddingCloseTick=close_tick,
                tickCreated=self._tick_count,
            )
            self._contracts[contract_id] = contract
            self._repo.save_contract(contract)
            return contract

    def bid_on_contract(self, contract_id: str, bidder_id: str) -> ContractData:
        with self._lock:
            contract = self._contracts.get(contract_id)
            if contract is None:
                raise KeyError(f"Contract '{contract_id}' not found")
            bidder = self._corporations.get(bidder_id)
            if bidder is None:
                raise KeyError(f"Corporation '{bidder_id}' not found")
            ok, reason = can_bid_contract(bidder, contract, self._tick_count)
            if not ok:
                raise ValueError(reason)
            updated = contract.model_copy(
                update={"candidates": contract.candidates + [bidder_id]}
            )
            self._contracts[contract_id] = updated
            self._repo.save_contract(updated)
            return updated

    def confirm_bidder(
        self, contract_id: str, proposer_id: str, bidder_id: str
    ) -> ContractData:
        with self._lock:
            contract = self._contracts.get(contract_id)
            if contract is None:
                raise KeyError(f"Contract '{contract_id}' not found")
            proposer = self._corporations.get(proposer_id)
            if proposer is None:
                raise KeyError(f"Corporation '{proposer_id}' not found")
            ok, reason = can_confirm_bidder(proposer, contract, bidder_id)
            if not ok:
                raise ValueError(reason)
            updated = contract.model_copy(update={
                "status":     ContractStatus.Active,
                "acceptorId": bidder_id,
                "startTick":  self._tick_count,
                "expiresAtTick": (
                    self._tick_count + contract.durationTicks
                    if contract.durationTicks > 0 else 0
                ),
            })
            self._contracts[contract_id] = updated
            self._repo.save_contract(updated)
            return updated

    def accept_contract(self, contract_id: str, acceptor_id: str) -> ContractData:
        with self._lock:
            contract = self._contracts.get(contract_id)
            if contract is None:
                raise KeyError(f"Contract '{contract_id}' not found")
            acceptor = self._corporations.get(acceptor_id)
            if acceptor is None:
                raise KeyError(f"Corporation '{acceptor_id}' not found")
            ok, reason = can_accept_private(acceptor, contract)
            if not ok:
                raise ValueError(reason)
            updated = contract.model_copy(update={
                "status":     ContractStatus.Active,
                "acceptorId": acceptor_id,
                "startTick":  self._tick_count,
                "expiresAtTick": (
                    self._tick_count + contract.durationTicks
                    if contract.durationTicks > 0 else 0
                ),
            })
            self._contracts[contract_id] = updated
            self._repo.save_contract(updated)
            return updated

    def break_contract(self, contract_id: str, corp_id: str) -> ContractData:
        with self._lock:
            contract = self._contracts.get(contract_id)
            if contract is None:
                raise KeyError(f"Contract '{contract_id}' not found")
            corp = self._corporations.get(corp_id)
            if corp is None:
                raise KeyError(f"Corporation '{corp_id}' not found")
            ok, reason = can_break_contract(corp, contract)
            if not ok:
                raise ValueError(reason)

            other_id  = (
                contract.proposerId if corp_id == contract.acceptorId
                else contract.acceptorId
            )
            other = self._corporations.get(other_id)
            if other is None:
                raise KeyError(f"Other party '{other_id}' not found")

            new_contract, new_corp, new_other = apply_break(contract, corp, other)
            self._contracts[contract_id]   = new_contract
            self._corporations[corp_id]    = new_corp
            self._corporations[other_id]   = new_other
            self._repo.save_contract(new_contract)
            self._repo.save_corporation(new_corp)
            self._repo.save_corporation(new_other)
            return new_contract

    def get_contract(self, contract_id: str) -> ContractData | None:
        with self._lock:
            return self._contracts.get(contract_id)

    def list_contracts(self, corp_id: str | None = None) -> list[ContractData]:
        with self._lock:
            if corp_id is None:
                return list(self._contracts.values())
            return [
                c for c in self._contracts.values()
                if corp_id in (c.proposerId, c.acceptorId, c.targetId)
                or corp_id in c.candidates
            ]

    def list_public_contracts(self) -> list[ContractData]:
        with self._lock:
            return [
                c for c in self._contracts.values()
                if c.visibility == ContractVisibility.Public
                and c.status == ContractStatus.Proposed
            ]

    # ── Internal: contract tick processor ─────────────────────────────────────

    def _process_contract_tick_locked(self) -> None:
        """Auto-deliver resources for active contracts; handle expiry of proposed/active."""
        for contract_id, contract in list(self._contracts.items()):
            # 1. Expire public contracts whose bidding window has closed
            if check_bidding_expiry(contract, self._tick_count):
                self._contracts[contract_id] = apply_expiry(contract)
                continue

            if contract.status != ContractStatus.Active:
                continue

            acceptor = self._corporations.get(contract.acceptorId)
            proposer = self._corporations.get(contract.proposerId)
            if acceptor is None or proposer is None:
                continue

            # 2. Auto-deliver
            new_contract, new_acceptor = process_delivery_tick(contract, acceptor)
            self._corporations[contract.acceptorId] = new_acceptor

            # 3. Check completion
            if check_completion(new_contract):
                new_contract, new_proposer, new_acceptor = apply_completion(
                    new_contract, proposer, new_acceptor
                )
                self._corporations[contract.proposerId] = new_proposer
                self._corporations[contract.acceptorId] = new_acceptor
                self._contracts[contract_id] = new_contract
                continue

            # 4. Check fixed-duration expiry (penalty on acceptor for non-delivery)
            if new_contract.durationTicks > 0 and new_contract.expiresAtTick > 0:
                if self._tick_count >= new_contract.expiresAtTick:
                    expired, new_acceptor, new_proposer = apply_break(
                        new_contract, new_acceptor, proposer
                    )
                    self._corporations[contract.acceptorId] = new_acceptor
                    self._corporations[contract.proposerId] = new_proposer
                    self._contracts[contract_id] = expired
                    continue

            self._contracts[contract_id] = new_contract
