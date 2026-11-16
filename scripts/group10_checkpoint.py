"""Group 10 checkpoint: grounded narratives for 3 different real attack paths, and a hallucination
that gets removed (not flagged). Uses the stub client (no API key)."""

import json
from decimal import Decimal
from pathlib import Path

from sentinel.ai import assemble as ai_assemble
from sentinel.ai.client import get_client
from sentinel.ai.narrative import Claim, generate
from sentinel.chain.anvil import Anvil
from sentinel.graph import attack, reconstruct
from sentinel.graph.builder import ANYONE, build
from sentinel.graph.paths import shortest_path
from sentinel.scoring import assemble as score_assemble, config as scfg
from sentinel.scoring.engine import score
from sentinel.sim import engine, exploits
from sentinel.value.model import Declared, Quantity

OUT = Path(__file__).resolve().parent.parent / "out"
PRICE = Quantity(Decimal(2500), "USD", Declared("checkpoint", "2026-09-25", "local ETH price"))


def _eth_path(g):
    for s in attack.asset_sinks(g):
        if g.nodes[s].label == "ETH" and (p := shortest_path(g, ANYONE, s)):
            return p
    return None


def main() -> None:
    OUT.mkdir(exist_ok=True)
    cfg = scfg.load()
    client = get_client()
    print(f"LLM client: {client.name}\n")
    report = {}
    with Anvil() as node:
        w3 = node.w3
        specs = [("reentrancy", reconstruct.reentrancy, exploits.reentrancy),
                 ("oracle_manipulation", reconstruct.oracle, exploits.oracle_manipulation),
                 ("governance", reconstruct.governance, None)]
        narratives = {}
        for name, recon, exploit in specs:
            r = recon(w3)
            g = build(r.analysis, r.context)
            pattern = next((h.pattern for h in attack.recognize(g, r.analysis)), None)
            if exploit is not None:
                path = _eth_path(g)
                sim = engine.run(w3, *(lambda s: (s.attacker_addresses, s.steps))(exploit(w3, patched=False)))
                sc = score(score_assemble.from_pipeline(name, g, path, sim, PRICE, "declared"), cfg)
            else:
                # governance: attacker can't reach the asset directly; narrate the authority path, no sim
                ap = attack.authority_paths(g)
                path = next(iter(ap.values()))[0]
                sim = sc = None
            ctx = ai_assemble.from_pipeline(name, r.analysis, g, path, pattern, sim, sc)
            n = generate(ctx, client)
            narratives[name] = n
            print(f"=== {name} ===")
            for c in n.claims:
                print(f"  - {c.text}\n      [evidence: {', '.join(c.evidence)}]")
            print()
            report[name] = n.to_dict()

        # Attempt to trick it: inject a fabricated claim into the reentrancy narrative.
        name = "reentrancy"
        r = reconstruct.reentrancy(w3)
        g = build(r.analysis, r.context)
        ctx = ai_assemble.from_pipeline(name, r.analysis, g, _eth_path(g), "reentrancy",
                                        engine.run(w3, *(lambda s: (s.attacker_addresses, s.steps))(
                                            exploits.reentrancy(w3, patched=False))))
        fake = Claim("The contract also contains a hidden owner backdoor that steals all deposits.",
                     ["fact-HALLUCINATED-0xDEADBEEF"])
        tricked = generate(ctx, client, extra_claims=[fake])
        print("=== hallucination attempt (reentrancy) ===")
        print(f"  injected claim: {fake.text}  [evidence: {fake.evidence}]")
        print(f"  in output claims? {any(c.text == fake.text for c in tricked.claims)}")
        print(f"  in removed?      {any(c.text == fake.text for c in tricked.removed)}")
        print(f"  in prose?        {'backdoor' in tricked.prose}")
        report["hallucination_test"] = {"injected": fake.text,
                                        "removed": any(c.text == fake.text for c in tricked.removed),
                                        "in_output": any(c.text == fake.text for c in tricked.claims),
                                        "in_prose": "backdoor" in tricked.prose}

        texts = {name: {c.text for c in n.claims} for name, n in narratives.items()}
        distinct = len({frozenset(v) for v in texts.values()}) == len(texts)
        print(f"\nthree narratives are mutually distinct: {distinct}")
        assert distinct
        assert report["hallucination_test"]["removed"] and not report["hallucination_test"]["in_output"]
        assert not report["hallucination_test"]["in_prose"]
        print("NARRATIVE OK: grounded, distinct, hallucination removed (not flagged).")
    (OUT / "group10.json").write_text(json.dumps(report, indent=2, default=str))
    print(f"wrote {OUT / 'group10.json'}")


if __name__ == "__main__":
    main()
