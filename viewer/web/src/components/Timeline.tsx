import { useEffect, useMemo, useRef } from "react";
import type { TimelineStep } from "../api";
import { useStore } from "../store";

const DX = 46, DY = 30, TOP = 30, LEFT = 28, CHART = 44;

// The derivation tree: depth runs to the right, each branch takes a lane of its own.
function lay(steps: TimelineStep[]) {
  const by = new Map(steps.map((s) => [s.id, s]));
  const at = new Map<number, { x: number; lane: number }>();
  let lanes = 0;
  const walk = (id: number, depth: number, lane: number) => {
    at.set(id, { x: depth, lane });
    by.get(id)!.children.forEach((c, i) => walk(c, depth + 1, i === 0 ? lane : ++lanes));
  };
  if (by.has(0)) walk(0, 0, 0);
  return { by, at, lanes: lanes + 1 };
}

export default function Timeline() {
  const scene = useStore((s) => s.scene);
  const goto = useStore((s) => s.goto);
  const undo = useStore((s) => s.undo);
  const run = useStore((s) => s.run);
  const start = useStore((s) => s.start);
  const busy = useStore((s) => s.busy);
  const previewing = useStore((s) => s.preview !== null);
  const scroller = useRef<HTMLDivElement>(null);

  const steps = scene?.timeline ?? [];
  const { by, at, lanes } = useMemo(() => lay(steps), [steps]);
  const path = steps.filter((s) => s.on_path).sort((a, b) => at.get(a.id)!.x - at.get(b.id)!.x);
  const depth = Math.max(0, ...[...at.values()].map((p) => p.x));
  const W = LEFT * 2 + depth * DX + 70, treeH = TOP + (lanes - 1) * DY + 22, H = treeH + CHART + 18;
  const top = Math.max(1, ...path.map((s) => s.edges));
  const px = (id: number) => LEFT + at.get(id)!.x * DX;
  const py = (id: number) => TOP + at.get(id)!.lane * DY;
  const cy = (v: number) => treeH + CHART - (v / top) * CHART;
  const last = path[path.length - 1];

  useEffect(() => {
    const el = scroller.current;
    if (!el || !scene) return;
    const x = px(scene.head);
    if (x < el.scrollLeft + 40 || x > el.scrollLeft + el.clientWidth - 40) el.scrollTo({ left: x - el.clientWidth / 2, behavior: "smooth" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scene?.head, steps.length]);

  if (!scene) return null;
  const next = scene.rules.find((r) => r.enabled);
  const head = by.get(scene.head);

  return (
    <div className="timeline">
      <div className="tl-controls">
        <div className="tl-title">
          <b>Derivation</b>
          <span className="muted">step {at.get(scene.head)?.x ?? 0} of {depth}{lanes > 1 ? `, ${lanes} branches` : ""}</span>
        </div>
        <button onClick={undo} disabled={busy || previewing || scene.head === 0}>Step back</button>
        <button onClick={() => next && run(next.id)} disabled={busy || previewing || !next}
          title={next ? `Apply ${next.id} ${next.name} at all its sites` : ""}>
          {next ? `Next stage: ${next.id}` : "Next stage"}
        </button>
        <button onClick={() => run(null)} disabled={busy || previewing || !next}>Derive to the end</button>
        <button onClick={() => start(scene.preset, scene.preset ? undefined : scene.parameters)} disabled={busy || steps.length < 2}
          title="Discard this derivation and begin again with the same parameters">Start again</button>
        <span className={"state " + (scene.complete ? "done" : "")}>{scene.complete ? "Derivation complete" : head?.rule ? "" : "Choose an axiom to begin"}</span>
      </div>
      <div className="tl-scroll" ref={scroller}>
        <svg width={Math.max(W, 300)} height={H} role="img" aria-label="Derivation tree">
          {steps.filter((s) => s.parent !== null).map((s) => {
            const x0 = px(s.parent!), y0 = py(s.parent!), x1 = px(s.id), y1 = py(s.id);
            return <path key={"e" + s.id} className={"tl-edge" + (s.on_path ? " on" : "")}
              d={y0 === y1 ? `M${x0},${y0}L${x1},${y1}` : `M${x0},${y0}C${x0 + DX / 2},${y0} ${x0 + DX / 2},${y1} ${x1},${y1}`} />;
          })}
          {path.length > 1 && <>
            <polyline className="tl-count edges" points={path.map((s) => `${px(s.id)},${cy(s.edges)}`).join(" ")} />
            <polyline className="tl-count nodes" points={path.map((s) => `${px(s.id)},${cy(s.nodes)}`).join(" ")} />
            <text className="tl-legend edges" x={px(last.id) + 10} y={Math.min(cy(last.edges), cy(last.nodes) - 12) + 3}>{last.edges} edges</text>
            <text className="tl-legend nodes" x={px(last.id) + 10} y={cy(last.nodes) + 3}>{last.nodes} nodes</text>
          </>}
          {steps.map((s) => {
            const isHead = s.id === scene.head;
            return (
              <g key={s.id} className={"tl-step" + (s.on_path ? " on" : "") + (isHead ? " head" : "") + (s.rule?.startsWith("GB") ? " gb" : "")}
                transform={`translate(${px(s.id)},${py(s.id)})`} onClick={() => !previewing && !busy && goto(s.id)}
                role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter" && !previewing && !busy) goto(s.id); }}>
                <title>{s.rule ? `${s.rule} at ${s.label}: ${s.nodes} nodes, ${s.edges} edges` : "The empty state"}</title>
                <rect className="hit" x={-DX / 2} y={-24} width={DX} height={DY + 18} />
                <circle r={isHead ? 8 : 5.5} />
                <text y={-13}>{s.rule ?? "start"}</text>
                {s.applications > 1 && <text className="times" y={20}>×{s.applications}</text>}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
