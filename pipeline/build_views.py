"""Step 6 - Build the alignment views of the graph (MAP 2.0).

Reads out/whs.ttl (the core graph produced by build_graph.py) and writes:

  out/whs-entailed.nt  RDFS entailments of the core graph under the WHS element
                       set and the alignment axioms (rdfs:subPropertyOf /
                       rdfs:subClassOf closure only). Lets consumers that know
                       only DCMI Terms, CIDOC CRM or schema.org query the data
                       without running a reasoner.
  out/whs-crm.nt       CIDOC CRM-conformant view (../alignment/crm-view.rq).
  out/whs-all.trig     The three graphs as named graphs, ready to load into the
                       SPARQL endpoint:
                         <https://w3id.org/whs/graph/core>
                         <https://w3id.org/whs/graph/entailed>
                         <https://w3id.org/whs/graph/crm>
                         <https://w3id.org/whs/graph/removed>  (properties
                           removed from the List; URIs keep resolving)
                       plus the vocabulary, alignment and shapes in
                         <https://w3id.org/whs/graph/schema>
                       (element set, region scheme, alignment, shapes)

Only rdflib is needed (no OWL reasoner): the closure is computed directly.
"""
from pathlib import Path

from rdflib import Dataset, Graph, RDF, RDFS, URIRef

OUT = Path("out")
ROOT = Path("..")
G = "https://w3id.org/whs/graph/"


def schema_graph() -> Graph:
    g = Graph()
    g.parse(ROOT / "vocab" / "whs-terms.ttl", format="turtle")
    g.parse(ROOT / "alignment" / "whs-alignment.ttl", format="turtle")
    g.parse(ROOT / "vocab" / "whs-regions.ttl", format="turtle")
    return g


def closure(pairs: set[tuple]) -> dict:
    """Transitive closure of a sub-property / sub-class relation."""
    sup: dict = {}
    for a, b in pairs:
        sup.setdefault(a, set()).add(b)
    changed = True
    while changed:
        changed = False
        for a in list(sup):
            for b in list(sup[a]):
                for c in sup.get(b, ()):
                    if c not in sup[a] and c != a:
                        sup[a].add(c)
                        changed = True
    return sup


def entail(core: Graph, schema: Graph) -> Graph:
    sub_p = closure(set(schema.subject_objects(RDFS.subPropertyOf)))
    sub_c = closure(set(schema.subject_objects(RDFS.subClassOf)))
    inf = Graph()
    for s, p, o in core:
        for q in sub_p.get(p, ()):
            if (s, q, o) not in core:
                inf.add((s, q, o))
        if p == RDF.type:
            for c in sub_c.get(o, ()):
                if (s, RDF.type, c) not in core:
                    inf.add((s, RDF.type, c))
    return inf


def main() -> None:
    core = Graph().parse(OUT / "whs.ttl", format="turtle")
    removed = Graph()
    if (OUT / "whs-removed.ttl").exists():
        removed.parse(OUT / "whs-removed.ttl", format="turtle")
    schema = schema_graph()
    entailed = entail(core, schema)
    crm = core.query((ROOT / "alignment" / "crm-view.rq").read_text("utf-8")).graph

    entailed.serialize(OUT / "whs-entailed.nt", format="nt", encoding="utf-8")
    crm.serialize(OUT / "whs-crm.nt", format="nt", encoding="utf-8")

    shapes = Graph().parse("whs-shapes.ttl", format="turtle")
    ds = Dataset()
    for name, graph in [("core", core), ("entailed", entailed),
                        ("crm", crm), ("schema", schema + shapes),
                        ("removed", removed)]:
        target = ds.graph(URIRef(G + name))
        for t in graph:
            target.add(t)
    ds.serialize(OUT / "whs-all.trig", format="trig")

    print(f"core:     {len(core):,} triples")
    print(f"entailed: {len(entailed):,} triples")
    print(f"crm view: {len(crm):,} triples")
    print(f"written:  {OUT / 'whs-all.trig'}")


if __name__ == "__main__":
    main()
