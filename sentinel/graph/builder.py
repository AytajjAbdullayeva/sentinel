"""Build the attack-path graph from real facts.

Inputs, all real:
  * Group 2 static facts (entry points, external/low-level/delegate calls, transfers, oracle reads);
  * Group 3 deployed context (holdings = asset nodes; authority facts = who controls what).

Every edge cites the fact id or on-chain read it came from. There is exactly one rule for the
attacker's reach: an ACTOR("anyone") CAN_CALL a function only if that function is an externally
callable entry point whose body does not check msg.sender (Slither `is_protected`). A protected entry
point is reachable only from the AUTHORITY that controls it. Nothing is connected to everything.
"""

from __future__ import annotations

from dataclasses import dataclass

from sentinel.graph.model import EdgeType, Graph, Node, NodeType
from sentinel.static.slither_analyzer import AnalysisResult

ANYONE = "actor:anyone"


@dataclass
class DeployedContext:
    """Optional real deployment info for one contract, keyed by contract name."""
    holdings: dict[str, list] = None       # contract name -> list of Holding (Group 3)
    authority: dict[str, list] = None      # contract name -> list of AuthorityFact (Group 3)
    price_dependency_names: tuple[str, ...] = ("getprice", "latestanswer", "latestrounddata",
                                               "getreserves", "consult", "price")

    def held(self, contract: str) -> list:
        return (self.holdings or {}).get(contract, [])

    def auth(self, contract: str) -> list:
        return (self.authority or {}).get(contract, [])


def _fn_id(contract: str, fn: str) -> str:
    return f"fn:{contract}.{fn}"


def _looks_like_price_read(dest: str, fn_name: str, price_names: tuple[str, ...]) -> bool:
    text = f"{dest} {fn_name}".lower()
    return any(p in text for p in price_names)


def build(result: AnalysisResult, ctx: DeployedContext | None = None) -> Graph:
    ctx = ctx or DeployedContext()
    g = Graph()
    g.add_node(Node(ANYONE, NodeType.ACTOR, "anyone"))

    entry_facts = [f for f in result.structure() if f.name == "entry_point"]
    contracts = {f.contract for f in result.structure() if f.contract}
    for c in contracts:
        g.add_node(Node(f"contract:{c}", NodeType.CONTRACT, c))

    # Contract -> its own entry-point functions; actor/authority -> callable entry points.
    entries_by_fn = {}
    for f in entry_facts:
        fid = _fn_id(f.contract, f.function)
        protected = bool(dict(_detail(f)).get("checks_msg_sender"))
        g.add_node(Node(fid, NodeType.FUNCTION, f"{f.contract}.{f.function}",
                        attrs=(("protected", protected), ("visibility", dict(_detail(f)).get("visibility")))))
        g.add_edge(f"contract:{f.contract}", fid, EdgeType.DECLARES, [f.id])
        entries_by_fn[(f.contract, f.function)] = (fid, protected, f.id)
        if not protected:
            g.add_edge(ANYONE, fid, EdgeType.CAN_CALL, [f.id])

    # Asset nodes from real holdings, and HOLDS edges.
    asset_ids: dict[str, str] = {}
    for c in contracts:
        for h in ctx.held(c):
            aid = f"asset:{h.asset}"
            asset_ids.setdefault(h.asset, aid)
            g.add_node(Node(aid, NodeType.ASSET, h.asset, attrs=(("token", h.token),)))
            g.add_edge(f"contract:{c}", aid, EdgeType.HOLDS,
                       [f"onchain:{h.amount.source.call}@{h.amount.source.address}"])

    # Function-level structural edges.
    for f in result.structure():
        if not f.contract or not f.function:
            continue
        fid = _fn_id(f.contract, f.function)
        if fid not in g.nodes:  # non-entry internal function that still moves value/calls out
            g.add_node(Node(fid, NodeType.FUNCTION, f"{f.contract}.{f.function}"))
            g.add_edge(f"contract:{f.contract}", fid, EdgeType.DECLARES, [f.id])
        d = dict(_detail(f))
        if f.name == "eth_transfer":
            _transfer_edges(g, fid, f, ctx.held(f.contract), asset_ids, native=True)
        elif f.name == "external_call":
            if d.get("sends_value"):
                _transfer_edges(g, fid, f, ctx.held(f.contract), asset_ids, native=False, dest=d.get("destination"))
            if _looks_like_price_read(str(d.get("destination")), str(d.get("function")), ctx.price_dependency_names):
                dep = f"contract:dep:{d.get('destination')}"
                g.add_node(Node(dep, NodeType.CONTRACT, f"oracle:{d.get('destination')}"))
                g.add_edge(fid, dep, EdgeType.DEPENDS_ON, [f.id], attrs=(("read", str(d.get("function"))),))
        elif f.name in ("low_level_call", "delegatecall"):
            etype = EdgeType.DELEGATES if f.name == "delegatecall" else EdgeType.CALLS
            dep = f"contract:dep:{d.get('destination')}"
            g.add_node(Node(dep, NodeType.CONTRACT, f"{f.name}:{d.get('destination')}"))
            g.add_edge(fid, dep, etype, [f.id])

    _authority_edges(g, result, ctx, entries_by_fn)
    return g


def _transfer_edges(g, fid, fact, holdings, asset_ids, native, dest=None):
    """Edge function -> asset it can move. Native ETH -> the contract's ETH holding(s);
    token call -> the specific token holding if the destination matches a held token."""
    targets = []
    for h in holdings:
        if native and h.token is None:
            targets.append(h.asset)
        elif not native and dest and h.token and dest.lower() in (h.token.lower(), h.asset.lower()):
            targets.append(h.asset)
    for asset in targets:
        g.add_edge(fid, asset_ids[asset], EdgeType.TRANSFERS, [fact.id])
    if not targets:  # value leaves but no matching held asset: record an abstract value sink
        aid = f"asset:value-out:{fid}"
        g.add_node(Node(aid, NodeType.ASSET, f"value out of {fid}", attrs=(("concrete", False),)))
        g.add_edge(fid, aid, EdgeType.TRANSFERS, [fact.id])


def _authority_edges(g, result, ctx, entries_by_fn):
    """AUTHORITY -> protected entry points it controls, from real authority facts + modifier evidence."""
    for f in [s for s in result.structure() if s.name == "entry_point"]:
        d = dict(_detail(f))
        fid, protected, prov = entries_by_fn[(f.contract, f.function)]
        if not protected:
            continue
        # A protected entry point is governed by the contract's authority. Prefer a concrete
        # authority fact (owner/multisig/role) read on-chain; else a generic authority node.
        facts = ctx.auth(f.contract)
        if facts:
            for af in facts:
                aid = f"auth:{af.kind}:{af.address}"
                g.add_node(Node(aid, NodeType.AUTHORITY, f"{af.kind}@{af.address}",
                                attrs=tuple(sorted((k, str(v)) for k, v in af.values.items()))))
                prov_read = af.reads[0].call if af.reads else af.kind
                g.add_edge(aid, fid, EdgeType.CONTROLS, [f"onchain:{prov_read}@{af.address}"],
                           attrs=(("modifiers", tuple(d.get("modifiers", []))),))
        else:
            aid = f"auth:modifier:{f.contract}"
            g.add_node(Node(aid, NodeType.AUTHORITY, f"privileged caller of {f.contract}",
                            attrs=(("modifiers", tuple(d.get("modifiers", []))),)))
            g.add_edge(aid, fid, EdgeType.CONTROLS, [prov])


def _detail(fact):
    return tuple(fact.detail.items())
