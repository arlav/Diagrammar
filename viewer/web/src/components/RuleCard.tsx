import { useEffect, useRef } from "react";
import cytoscape, { type ElementDefinition } from "cytoscape";
import type { Card } from "../api";
import { ACCESS_COLOR, HILITE, typeColor } from "../theme";

// A rule drawn: the left-hand side as it is matched, the right-hand side as it leaves the graph.
// Variables are labelled var:type; what the rule removes is struck through on the left, what it
// creates is green on the right, what it relabels is amber. Conditions ("no such node") are dashed.

const REL_ACCESS: Record<string, string> = { supports: "none", above: "none", party: "none", door: "door", core_door: "door",
  bridge: "door", corridor: "open", open: "open", stair: "stair" };

const STYLE: cytoscape.StylesheetStyle[] = [
  { selector: "node", style: { "background-color": "data(color)", width: 24, height: 24, label: "data(label)", "font-size": 8,
      "font-family": "ui-monospace, Menlo, monospace", color: "#1f1e1b", "text-valign": "bottom", "text-margin-y": 3,
      "text-wrap": "wrap", "text-max-width": "70px", "border-width": 1.5, "border-color": "#ffffff" } },
  { selector: "node.nonterminal", style: { shape: "round-rectangle" } },
  { selector: "node.nac", style: { "border-color": HILITE.removed, "border-style": "dashed", "border-width": 2, "background-opacity": 0.25 } },
  { selector: "node.created", style: { "border-color": HILITE.added, "border-width": 3 } },
  { selector: "node.changed", style: { "border-color": HILITE.changed, "border-width": 3 } },
  { selector: "node.gone", style: { "background-opacity": 0.2, "border-color": HILITE.removed, "border-width": 2, "border-style": "double" } },
  { selector: "node.contracted", style: { "border-color": HILITE.added, "border-width": 3, width: 30, height: 30 } },
  { selector: "edge", style: { "line-color": "data(color)", width: 2.2, "curve-style": "bezier", label: "data(label)", "font-size": 7,
      color: "#55524a", "text-rotation": "autorotate", "text-background-color": "#fff", "text-background-opacity": 0.8, "text-background-padding": "1px" } },
  { selector: "edge.nac", style: { "line-style": "dashed", "line-color": HILITE.removed } },
  { selector: "edge.added", style: { "line-color": HILITE.added, width: 3 } },
  { selector: "edge.gone", style: { "line-style": "dotted", "line-color": HILITE.removed } },
];

function typeOf(cons: Record<string, unknown> | undefined): string {
  const t = cons?.type;
  return typeof t === "string" && !t.startsWith("=") ? t : "";
}

function label(v: string, cons: Record<string, unknown> | undefined, extra?: string) {
  const t = typeOf(cons);
  const more = Object.entries(cons ?? {}).filter(([k]) => k !== "type").map(([k, val]) => `${k}${String(val).startsWith("=") ? String(val) : "=" + String(val)}`);
  return [v + (t ? ":" + t : ""), ...more.slice(0, 2), extra ?? ""].filter(Boolean).join("\n");
}

function side(card: Card, which: "lhs" | "rhs"): ElementDefinition[] {
  const els: ElementDefinition[] = [];
  const lhs = card.lhs;
  const rhs = card.rhs;
  const deleted = new Set(rhs.delete ?? []);
  const contracted = new Set(rhs.contract?.nodes ?? []);
  const relabelled = rhs.relabel ?? {};
  const key = (a: string, b: string) => (a < b ? `${a}|${b}` : `${b}|${a}`);
  if (which === "lhs") {
    for (const [v, cons] of Object.entries(lhs.nodes)) {
      const t = typeOf(cons);
      els.push({ data: { id: v, label: label(v, cons), color: t ? typeColor(t) : "#cfcabd" },
                 classes: [t && ["mass", "storey", "bay"].includes(t) ? "nonterminal" : "", deleted.has(v) || contracted.has(v) ? "gone" : ""].join(" ") });
    }
    for (const [a, b, rel] of lhs.edges)
      els.push({ data: { id: "e" + key(a, b) + rel, source: a, target: b, label: rel ?? "", color: ACCESS_COLOR[REL_ACCESS[rel ?? ""] ?? "none"] } });
    card.nac.forEach((n, i) => {
      for (const [v, cons] of Object.entries(n.nodes)) {
        if (v in lhs.nodes) continue;
        const t = typeOf(cons);
        els.push({ data: { id: `nac${i}_${v}`, label: label(v, cons, "(must not exist)"), color: t ? typeColor(t) : "#cfcabd" }, classes: "nac" });
      }
      for (const [a, b, rel] of n.edges) {
        const src = a in lhs.nodes ? a : `nac${i}_${a}`, dst = b in lhs.nodes ? b : `nac${i}_${b}`;
        els.push({ data: { id: `nac${i}e${key(src, dst)}${rel}`, source: src, target: dst, label: rel ? `no ${rel}` : "no edge", color: HILITE.removed }, classes: "nac" });
      }
    });
    return els;
  }
  // right-hand side: what survives, what is made
  const kept = Object.keys(lhs.nodes).filter((v) => !deleted.has(v) && !contracted.has(v));
  for (const v of kept) {
    const cons = { ...lhs.nodes[v], ...(relabelled[v] ?? {}) };
    const t = typeOf(cons);
    els.push({ data: { id: v, label: label(v, cons), color: t ? typeColor(t) : "#cfcabd" },
               classes: [t && ["mass", "storey", "bay"].includes(t) ? "nonterminal" : "", v in relabelled ? "changed" : ""].join(" ") });
  }
  for (const [v, spec] of Object.entries(rhs.create ?? {})) {
    const t = typeOf(spec);
    const isContract = rhs.contract?.into === v;
    els.push({ data: { id: v, label: label(v, spec, isContract ? `← ${rhs.contract!.nodes.join(", ")}` : "(new)"), color: t ? typeColor(t) : "#cfcabd" },
               classes: isContract ? "contracted" : "created" });
  }
  const present = new Set(els.map((e) => e.data.id as string));
  const unlinked = new Set((rhs.unlink ?? []).map(([a, b]) => key(a, b)));
  const linked = new Set((rhs.link ?? []).map(([a, b]) => key(a, b)));
  for (const [a, b, rel] of lhs.edges) {
    const a2 = contracted.has(a) ? rhs.contract!.into : a, b2 = contracted.has(b) ? rhs.contract!.into : b;
    if (a2 === b2 || !present.has(a2) || !present.has(b2) || linked.has(key(a2, b2))) continue;
    els.push({ data: { id: "e" + key(a2, b2) + rel, source: a2, target: b2, label: rel ?? "", color: ACCESS_COLOR[REL_ACCESS[rel ?? ""] ?? "none"] },
               classes: unlinked.has(key(a, b)) ? "gone" : "" });
  }
  for (const [a, b, rel] of rhs.link ?? []) {
    const a2 = contracted.has(a) ? rhs.contract!.into : a, b2 = contracted.has(b) ? rhs.contract!.into : b;
    if (!present.has(a2) || !present.has(b2)) continue;
    els.push({ data: { id: "l" + key(a2, b2) + rel, source: a2, target: b2, label: rel, color: ACCESS_COLOR[REL_ACCESS[rel] ?? "none"] }, classes: "added" });
  }
  return els;
}

function Side({ card, which }: { card: Card; which: "lhs" | "rhs" }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const els = side(card, which);
    const c = cytoscape({ container: box.current, style: STYLE, elements: els, userZoomingEnabled: false, userPanningEnabled: false,
                          boxSelectionEnabled: false, autoungrabify: true, autounselectify: true });
    const n = els.filter((e) => !e.data.source).length;
    c.layout(n <= 2 ? { name: "grid", rows: 1, fit: true, padding: 14 } : { name: "cose", animate: false, fit: true, padding: 14, nodeRepulsion: () => 40000, idealEdgeLength: () => 50 } as cytoscape.LayoutOptions).run();
    c.fit(undefined, 14);
    return () => c.destroy();
  }, [card, which]);
  return <div ref={box} className="card-side" />;
}

export default function RuleCard({ card }: { card: Card }) {
  const flags = card.rhs.flag ?? [];
  const empty = Object.keys(card.lhs.nodes).length === 0;
  return (
    <div className="card">
      <div className="card-sides">
        <div>
          <div className="card-title">LHS{card.lhs.where.length > 0 && <span title={card.lhs.where.join(" and ")}> · {card.lhs.where.length} condition{card.lhs.where.length > 1 ? "s" : ""}</span>}</div>
          {empty ? <div className="card-side empty-side">∅</div> : <Side card={card} which="lhs" />}
        </div>
        <div className="card-arrow">→</div>
        <div>
          <div className="card-title">RHS{flags.length > 0 && <span> · marks {flags.join(", ")}</span>}</div>
          <Side card={card} which="rhs" />
        </div>
      </div>
      {card.lhs.where.length > 0 && <div className="card-where">{card.lhs.where.map((w) => <code key={w}>{w}</code>)}</div>}
    </div>
  );
}
