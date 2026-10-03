import { useStore } from "../store";

function Slider({ label, value, min, max, step, onChange, show }: {
  label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void; show: string;
}) {
  return (
    <label className="slider">
      <span>{label}</span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
      <output>{show}</output>
    </label>
  );
}

export default function ViewBar() {
  const v = useStore((s) => s.view);
  const set = useStore((s) => s.setView);
  const Toggle = ({ k, label }: { k: "cells" | "graph" | "accessOnly"; label: string }) => (
    <button className={"toggle" + (v[k] ? " on" : "")} aria-pressed={v[k]} onClick={() => set({ [k]: !v[k] })}>{label}</button>
  );
  return (
    <div className="viewbar">
      <div className="group">
        <Toggle k="cells" label="Cells" />
        <Toggle k="graph" label="Graph" />
        <Toggle k="accessOnly" label="Access only" />
      </div>
      <div className="group">
        <Slider label="Opacity" value={v.opacity} min={0.05} max={0.9} step={0.05} onChange={(opacity) => set({ opacity })} show={`${Math.round(v.opacity * 100)}%`} />
        <Slider label="Gap" value={v.gap} min={0} max={0.3} step={0.01} onChange={(gap) => set({ gap })} show={`${Math.round(v.gap * 100)}%`} />
        <Slider label="Lift graph" value={v.lift} min={0} max={40} step={1} onChange={(lift) => set({ lift })} show={`${v.lift} m`} />
        <Slider label="Section" value={v.cut} min={0.02} max={1} step={0.01} onChange={(cut) => set({ cut })} show={v.cut >= 1 ? "off" : `${Math.round(v.cut * 100)}%`} />
      </div>
    </div>
  );
}

export function CameraBar() {
  const v = useStore((s) => s.view);
  const set = useStore((s) => s.setView);
  const refit = useStore((s) => s.refit);
  return (
    <div className="camerabar">
      <button className={"toggle" + (v.ortho ? " on" : "")} aria-pressed={v.ortho} onClick={() => set({ ortho: true })}>Axonometric</button>
      <button className={"toggle" + (!v.ortho ? " on" : "")} aria-pressed={!v.ortho} onClick={() => set({ ortho: false })}>Perspective</button>
      <button className="toggle" onClick={refit}>Fit</button>
    </div>
  );
}

export function GraphBar() {
  const v = useStore((s) => s.view);
  const set = useStore((s) => s.setView);
  const n = useStore((s) => (s.preview ?? s.scene)?.graph);
  const shownNodes = n ? n.nodes.filter((x) => !v.accessOnly || x.occupiable).length : 0;
  const shownEdges = n ? n.edges.filter((x) => !v.accessOnly || x.in_access_graph).length : 0;
  return (
    <div className="viewbar thin">
      <div className="group">
        <span className="title">{v.accessOnly ? "Access graph" : "Graph"}</span>
        <span className="muted">{shownNodes} nodes, {shownEdges} edges</span>
      </div>
      <div className="group">
        {(["elevation", "plan", "force"] as const).map((l) => (
          <button key={l} className={"toggle" + (v.layout === l ? " on" : "")} aria-pressed={v.layout === l} onClick={() => set({ layout: l })}>
            {l[0].toUpperCase() + l.slice(1)}
          </button>
        ))}
      </div>
    </div>
  );
}
