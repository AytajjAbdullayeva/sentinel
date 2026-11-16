"""Group 10: the stub never errors, claims are grounded, and ungrounded claims are REMOVED not flagged."""

import os

import pytest

from sentinel.ai import client as ai_client
from sentinel.ai.client import StubLLMClient, get_client
from sentinel.ai.narrative import Claim, NarrativeContext, generate, ground


def _ctx(valid):
    return NarrativeContext(
        target="demo", pattern="reentrancy",
        path_labels=["anyone", "Vault.withdraw()", "ETH"],
        path_provenance=["factA"], detector_facts=[{"name": "reentrancy-eth", "impact": "High",
                                                    "file": "Vault.sol", "lines": [17], "id": "factB"}],
        sim={"feasible": True, "profit_wei": 5 * 10**18, "tx_hashes": ["0xdead"]},
        score=None, valid_evidence=valid)


def test_stub_client_is_returned_without_key_and_never_errors(monkeypatch):
    monkeypatch.delenv("SENTINEL_LLM_API_KEY", raising=False)
    c = get_client()
    assert isinstance(c, StubLLMClient)
    assert c.complete("- something [evidence: x]")  # no network, returns text


def test_key_without_real_client_raises_not_fakes(monkeypatch):
    monkeypatch.setenv("SENTINEL_LLM_API_KEY", "sk-whatever")
    with pytest.raises(RuntimeError):
        get_client()


def test_grounding_removes_unsupported_claims():
    valid = {"factA", "factB", "0xdead"}
    claims = [Claim("supported", ["factA"]),
              Claim("hallucinated backdoor", ["fact-DOES-NOT-EXIST"]),
              Claim("no evidence at all", [])]
    kept, removed = ground(claims, valid)
    assert [c.text for c in kept] == ["supported"]
    assert {c.text for c in removed} == {"hallucinated backdoor", "no evidence at all"}


def test_generate_drops_injected_ungrounded_claim_from_output():
    ctx = _ctx(valid={"factA", "factB", "0xdead"})
    hallucination = Claim("The contract also mints unlimited tokens to the deployer.", ["fact-FAKE"])
    n = generate(ctx, StubLLMClient(), extra_claims=[hallucination])
    assert hallucination not in n.claims                      # not in the output
    assert any(c.text == hallucination.text for c in n.removed)  # explicitly removed
    assert "unlimited tokens" not in n.prose                  # and not in the prose
    for c in n.claims:                                        # every surviving claim is grounded
        assert c.evidence and set(c.evidence) <= ctx.valid_evidence


def test_every_claim_maps_to_a_real_evidence_id():
    ctx = _ctx(valid={"factA", "factB", "0xdead"})
    n = generate(ctx, StubLLMClient())
    assert n.claims
    for c in n.claims:
        for eid in c.evidence:
            assert eid in ctx.valid_evidence
