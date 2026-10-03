import { useEffect, useRef } from "react";
import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import type { GraphNode } from "../api";
import { useShown, useStore, type ViewOptions } from "../store";
import { useMarks } from "../marks";
import { ACCESS_COLOR, HILITE, typeColor } from "../theme";
import { siteExtent } from "../extent";

// Two drawings of the same graph, both read off the building: nodes stay where they are from one
// step to the next, so a production is seen as a change and not as a reshuffle.
function place(n: Pick<GraphNode, "pos">, layout: ViewOptions["layout"]) {
  const [x, y, z] = n.pos;
  if (layout === "plan") return { x: x * 15 + z * 2.2, y: -y * 15 - z * 4.2 };
  return { x: x * 15 + y * 4.2, y: -z * 17 - y * 5.5 };        // elevation, seen obliquely from the south
}

const STYLE: cytoscape.StylesheetStyle[] = [
  { selector: "node", style: {
      "background-color": "data(color)", width: "data(size)", height: "data(size)", shape: "ellipse",
      label: "data(id)", "font-size": 8, "min-zoomed-font-size": 7, color: "#3b3a36",
      "font-family": "ui-monospace, SFMono-Regular, Menlo, monospace",
      "text-valign": "bottom", "text-margin-y": 2, "border-width": 1, "border-color": "#ffffff" } },
  { selector: "node[?nonterminal]", style: { shape: "round-rectangle", "border-color": "#6b6759", "border-style": "dashed" } },
  { selector: "node.anchor", style: { opacity: 0, events: "no", label: "", width: 1, height: 1 } },
  { selector: "edge", style: { "line-color": "data(color)", width: "data(width)", "curve-style": "straight", opacity: 0.9 } },
  { selector: "edge[?mirror]", style: { "line-style": "dashed" } },
  { selector: "edge.added", style: { "line-color": HILITE.added, width: 4 } },
  ...(["changed", "added", "removed", "site", "selected"] as const).map((k) => ({
    selector: `node.${k}`,
    style: { "border-width": 3.5, "border-color": HILITE[k], "border-style": "solid" as const, "z-index": 10 },
  })),
];

export default function Graph2D() {
  const scene = useShown();
  const view = useStore((s) => s.view);
  const fit = useStore((s) => s.fit);
  const select = useStore((s) => s.select);
  const marks = useMarks();
  const box = useRef<HTMLDivElement>(null);
  const cy = useRef<Core | null>(null);
  const fitted = useRef("");

  useEffect(() => {
    const c = cytoscape({ container: box.current, style: STYLE, minZoom: 0.1, maxZoom: 6,
                          boxSelectionEnabled: false, autoungrabify: true });
    c.on("tap", "node", (e) => select(e.target.id()));
    c.on("tap", (e) => { if (e.target === c) select(null); });
    cy.current = c;
    return () => { c.destroy(); cy.current = null; };
  }, [select]);

  useEffect(() => {
    const c = cy.current;
    if (!c || !scene) return;
    const nodes = scene.graph.nodes.filter((n) => !view.accessOnly || n.occupiable);
    const shown = new Set(nodes.map((n) => n.id));
    const fresh = new Set(scene.event.edges_added.map((e) => (e.a < e.b ? `${e.a}|${e.b}` : `${e.b}|${e.a}`)));
    const els: ElementDefinition[] = nodes.map((n) => ({
      group: "nodes",
      data: { id: n.id, color: typeColor(n.type), nonterminal: !n.terminal,
              size: n.type === "dwelling" || n.type === "hall" ? 17 : 12 },
      position: place(n, view.layout),
    }));
    for (const e of scene.graph.edges) {
      if (!shown.has(e.a) || !shown.has(e.b) || (view.accessOnly && !e.in_access_graph)) continue;
      const id = e.a < e.b ? `${e.a}|${e.b}` : `${e.b}|${e.a}`;
      els.push({ group: "edges", classes: fresh.has(id) ? "added" : "",
                 data: { id, source: e.a, target: e.b, color: ACCESS_COLOR[e.access], mirror: !!e.mirror,
                         width: e.access === "none" ? 1 : 2.6 } });
    }
    const force = view.layout === "force";
    if (!force) {
      // two unseen nodes at the corners of the site: the drawing is framed on them
      const e = siteExtent(scene);
      const corners = [0, 1, 2, 3, 4, 5, 6, 7].map((i) =>
        place({ pos: [i & 1 ? e.max[0] : e.min[0], i & 2 ? e.max[1] : e.min[1], i & 4 ? e.max[2] : e.min[2]] }, view.layout));
      const xs = corners.map((q) => q.x), ys = corners.map((q) => q.y);
      els.push({ group: "nodes", classes: "anchor", data: { id: "__a", color: "#000", size: 1 }, position: { x: Math.min(...xs), y: Math.min(...ys) } },
               { group: "nodes", classes: "anchor", data: { id: "__b", color: "#000", size: 1 }, position: { x: Math.max(...xs), y: Math.max(...ys) } });
    }
    c.batch(() => { c.elements().remove(); c.add(els); });
    if (force) {
      c.layout({ name: "cose", animate: false, randomize: false, nodeRepulsion: () => 9000, idealEdgeLength: () => 40, fit: true, padding: 28 } as cytoscape.LayoutOptions).run();
      fitted.current = "";
      return;
    }
    // keep the reader's zoom and pan; refit only for a new derivation, a new layout or on request
    const key = `${scene.session}/${view.layout}/${fit}`;
    if (fitted.current !== key) { c.fit(c.$(".anchor"), 24); fitted.current = key; }
  }, [scene, view.layout, view.accessOnly, fit]);

  useEffect(() => {
    const c = cy.current;
    if (!c) return;
    c.batch(() => {
      c.nodes().removeClass("selected site added removed changed");
      marks.forEach((k, id) => c.getElementById(id).addClass(k));
    });
  }, [marks, scene, view.layout, view.accessOnly]);

  return <div ref={box} className="cy" />;
}
