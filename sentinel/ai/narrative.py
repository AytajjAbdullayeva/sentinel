"""Grounded narrative: every claim carries the real evidence ids it rests on, and the verifier drops
any claim whose evidence is not in the analysis's real evidence set."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from sentinel.ai.client import LLMClient


@dataclass
class Claim:
    text: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class NarrativeContext:
    target: str
    pattern: str | None
    path_labels: list[str]
    path_provenance: list[str]                 # fact ids on the attack-path edges
    detector_facts: list[dict]                 # {name, impact, file, lines, id}
    sim: dict | None                           # {feasible, profit_wei, tx_hashes}
    score: dict | None                         # {status, score, components:{name:{value,origin}}}
    valid_evidence: set[str] = field(default_factory=set)


@dataclass
class Narrative:
    target: str
    prose: str
    claims: list[Claim]
    removed: list[Claim]

    def to_dict(self) -> dict:
        return {"target": self.target, "prose": self.prose,
                "claims": [asdict(c) for c in self.claims],
                "removed": [asdict(c) for c in self.removed]}


def build_claims(ctx: NarrativeContext) -> list[Claim]:
    claims: list[Claim] = []
    entry = next((lbl for lbl in ctx.path_labels if "(" in lbl), ctx.path_labels[0] if ctx.path_labels else "?")
    sink = ctx.path_labels[-1] if ctx.path_labels else "?"
    source = ctx.path_labels[0] if ctx.path_labels else "?"
    caller = "an external caller (anyone)" if source == "anyone" else f"'{source}'"
    if ctx.path_provenance:
        claims.append(Claim(f"Starting from {entry}, {caller} can reach {sink}.",
                            list(ctx.path_provenance)))
    for d in ctx.detector_facts:
        claims.append(Claim(
            f"{d['name']} ({d['impact']}) is reported at {d['file']}:{d['lines']} on the attack path.",
            [d["id"]]))
    if ctx.sim is not None:
        txs = ctx.sim.get("tx_hashes", [])
        if ctx.sim.get("feasible"):
            eth = ctx.sim["profit_wei"] / 10**18
            claims.append(Claim(
                f"Simulation on a local EVM executed the path and the attacker profited {eth:.4f} ETH.", txs))
        else:
            claims.append(Claim("Simulation on a local EVM executed the path and it was not profitable/feasible.", txs))
    if ctx.score is not None and ctx.score.get("status") == "scored":
        origins = [c["origin"] for c in ctx.score["components"].values()]
        claims.append(Claim(f"The risk score is {ctx.score['score']:.2f}, composed from "
                            f"{', '.join(ctx.score['components'])}.", origins))
    return claims


def ground(claims: list[Claim], valid_evidence: set[str]) -> tuple[list[Claim], list[Claim]]:
    kept, removed = [], []
    for c in claims:
        if c.evidence and set(c.evidence) <= valid_evidence:
            kept.append(c)
        else:
            removed.append(c)  # dropped entirely, not merely flagged
    return kept, removed


def render(claims: list[Claim]) -> str:
    return "\n".join(f"- {c.text} [evidence: {', '.join(c.evidence)}]" for c in claims)


def generate(ctx: NarrativeContext, client: LLMClient, extra_claims: list[Claim] | None = None) -> Narrative:
    """Build grounded claims (plus any extra claims, e.g. an LLM's own additions), strip the
    ungrounded ones, then let the client phrase only what survived."""
    all_claims = build_claims(ctx) + list(extra_claims or [])
    kept, removed = ground(all_claims, ctx.valid_evidence)
    prose = client.complete(render(kept))
    return Narrative(ctx.target, prose, kept, removed)
