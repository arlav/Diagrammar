import { useEffect, useRef } from "react";
import type { Check, Scene } from "../api";
import { useShown, useStore, type Tab } from "../store";
import { ACCESS_COLOR, ACCESS_LABEL, typeColor } from "../theme";
import { AccessDot, EdgeTally, NodeChip, NodeChips } from "./Chips";

const show = (v: unknown): string =>
  v === null || v === undefined ? "" : typeof v === "object" ? JSON.stringify(v) : String(v);

function Histogram({ data, color }: { data: Record<string, number>; color: (k: string) => string }) {
  const max = Math.max(1, ...Object.values(data));
  return (
    <div className="hist">
      {Object.entries(data).map(([k, n]) => (
        <div key={k} className="hist-row">
          <span className="k"><i className="dot" style={{ background: color(k) }} />{k}</span>
          <span className="bar"><i style={{ width: `${(n / max) * 100}%`, background: color(k) }} /></span>
          <span className="n">{n}</span>
        </div>
      ))}
    </div>
  );
}

function Overview({ scene }: { scene: Scene }) {
  const { full, access } = scene.invariants;
  if (full.nodes === 0) return <p className="muted pad">The state is empty. Apply an axiom from the rule list to begin.</p>;
  return (
    <div className="pad">
      <p className="muted">Select a node or a cell to read its dictionary.</p>
      <table className="kv">
        <thead><tr><th /><th>full graph</th><th>access graph</th></tr></thead>
        <tbody>
          <tr><th>nodes</th><td>{full.nodes}</td><td>{access.nodes}</td></tr>
          <tr><th>edges</th><td>{full.edges}</td><td>{access.edges}</td></tr>
          <tr><th>components</th><td>{full.components}</td><td>{access.components}</td></tr>
          <tr><th>max degree</th><td>{full.max_degree}</td><td>{access.max_degree}</td></tr>
        </tbody>
      </table>
      <h4>Nodes by type</h4>
      <Histogram data={full.nodes_by_type} color={typeColor} />
      <h4>Edges by access</h4>
      <Histogram data={full.edges_by_access} color={(k) => ACCESS_COLOR[k]} />
      <h4>Edges by relation</h4>
      <Histogram data={full.edges_by_rel} color={(k) => ACCESS_COLOR[scene.graph.edges.find((e) => e.rel === k)?.access ?? "none"]} />
    </div>
  );
}

function Inspector({ scene }: { scene: Scene }) {
  const selected = useStore((s) => s.selected);
  const node = scene.graph.nodes.find((n) => n.id === selected);
  if (!node) return <Overview scene={scene} />;
  const cell = scene.cells.find((c) => c.id === node.id);
  const edges = scene.graph.edges.filter((e) => e.a === node.id || e.b === node.id);
  const skip = new Set(["id", "label", "type"]);
  return (
    <div className="pad">
      <div className="node-head">
        <i className="swatch" style={{ background: typeColor(node.type) }} />
        <div><b>{node.id}</b><span>{node.label}</span></div>
      </div>
      <div className="tags">
        <span className="tag">{node.type}</span>
        <span className="tag">{node.terminal ? "terminal" : "non-terminal"}</span>
        {node.occupiable && <span className="tag">in the access graph</span>}
      </div>
      <h4>Dictionary</h4>
      <table className="kv">
        <tbody>
          {Object.entries(node.dictionary).filter(([k]) => !skip.has(k)).map(([k, v]) => <tr key={k}><th>{k}</th><td>{show(v)}</td></tr>)}
          <tr><th>position</th><td>{node.pos.map((v) => v.toFixed(2)).join(", ")}</td></tr>
          {cell && <tr><th>volume</th><td>{cell.volume.toLocaleString()} m³</td></tr>}
        </tbody>
      </table>
      <h4>Edges ({edges.length})</h4>
      {edges.length === 0 ? <p className="muted">This node has no edges.</p> : (
        <table className="edges">
          <tbody>
            {edges.map((e) => {
              const other = e.a === node.id ? e.b : e.a;
              return (
                <tr key={other}>
                  <td><NodeChip id={other} /></td>
                  <td>{e.rel}{e.mirror ? " (mirror pair)" : ""}</td>
                  <td><AccessDot access={e.access} />{ACCESS_LABEL[e.access]}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

const MARK: Record<Check["status"], string> = { ok: "✓", pending: "…", fail: "✕" };

function Checks({ scene }: { scene: Scene }) {
  const pack = useStore((s) => s.pack);
  const inv = scene.invariants;
  const preset = scene.preset ? pack?.presets[scene.preset] : null;
  const left = Object.entries(inv.unresolved);
  return (
    <div className="pad">
      <p className="muted">
        {preset ? <>Figures the preset <b>{preset.title}</b> must reach. </> : "These parameters are not a preset, so only the general checks apply. "}
        {!scene.complete && "Until the derivation is complete, a figure not yet reached is pending."}
      </p>
      {scene.warnings.map((w) => <div key={w} className="notice warn">{w}</div>)}
      <table className="checks">
        <thead><tr><th /><th>check</th><th>expected</th><th>now</th></tr></thead>
        <tbody>
          {inv.checks.map((c) => (
            <tr key={c.name} className={c.status}>
              <td className="mark" aria-label={c.status}>{MARK[c.status]}</td>
              <td>{c.name}</td>
              <td>{typeof c.expected === "object" ? "recorded" : show(c.expected)}</td>
              <td>{typeof c.actual === "object" ? (c.status === "ok" ? "equal" : "differs") : show(c.actual)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h4>Lockstep</h4>
      {inv.oracle ? (
        <div className={"notice " + (inv.oracle.isomorphic_typed ? "good" : "bad")}>
          <b>{inv.oracle.isomorphic_typed ? "Isomorphic, type-preserving" : inv.oracle.isomorphic ? "Isomorphic, but node types differ" : "Not isomorphic"}</b>
          <span>against {inv.oracle.against} ({inv.oracle.method}): {inv.oracle.nodes[0]} / {inv.oracle.edges[0]} here,
            {" "}{inv.oracle.nodes[1]} / {inv.oracle.edges[1]} recorded.</span>
        </div>
      ) : (
        <p className="muted">{preset && "access" in (preset.expect as object)
          ? "Compared with the prototype's recorded access graph once the derivation is complete."
          : "No recorded graph to compare with for these parameters. From P4 this compares the driven graph with the one rebuilt from shape provenance."}</p>
      )}
      {preset?.prototype && (
        <div className="notice">
          <b>The prototype recorded {preset.prototype.dwellings} dwellings here.</b>
          <span>{preset.prototype.note} Here they are separate dwellings.</span>
        </div>
      )}

      <h4>Reachability</h4>
      <p>{inv.reachability.total === 0 ? <span className="muted">No dwellings yet.</span>
        : <>{inv.reachability.reachable} of {inv.reachability.total} dwellings can be reached on foot from {pack?.source}.</>}</p>
      {inv.reachability.unreachable.length > 0 && <NodeChips ids={inv.reachability.unreachable} />}

      <h4>Unresolved non-terminals</h4>
      {left.length === 0 ? <p className="muted">None.</p> : left.map(([t, ids]) => (
        <div key={t} className="unresolved"><span className="tag">{ids.length} {t}</span><NodeChips ids={ids} limit={12} /></div>
      ))}

      {inv.conflicts.length > 0 && <>
        <h4>Merge conflicts</h4>
        {inv.conflicts.map((c) => (
          <div key={c.node + c.neighbour} className="notice bad">
            <span><b>{c.node}</b> reaches {c.neighbour} by {c.relations.join(" and ")}; kept {c.kept}.</span>
          </div>
        ))}
      </>}
    </div>
  );
}

function EventView({ scene }: { scene: Scene }) {
  const e = scene.event;
  const rule = useStore((s) => s.pack?.rules.find((r) => r.id === e.rule));
  if (!e.rule || !rule) return <p className="muted pad">No production has been applied yet.</p>;
  return (
    <div className="pad">
      <div className="node-head">
        <div><b>{rule.id} {rule.name}</b><span>{scene.preview ? "preview, not applied" : `step ${scene.step.id}, ${scene.step.elapsed_ms} ms`}</span></div>
      </div>
      <table className="kv">
        <tbody>
          <tr><th>graph</th><td>{e.operation}</td></tr>
          <tr><th>shape</th><td>{e.shape_operation}</td></tr>
          <tr><th>sites</th><td>{(e.sites ?? []).length > 6 ? `${e.sites!.length} sites` : (e.sites ?? []).join(", ")}</td></tr>
        </tbody>
      </table>
      {e.identity && <div className="notice">An identity production: the shape changes, the graph does not.</div>}
      <h4>Matched</h4><NodeChips ids={e.matched ?? []} />
      <h4>Nodes removed ({e.nodes_removed.length})</h4>
      {e.nodes_removed.length === 0 ? <span className="muted">none</span>
        : <span className="chips">{e.nodes_removed.slice(0, 24).map((n) => <span key={n} className="chip flat gone">{n}</span>)}
            {e.nodes_removed.length > 24 && <span className="muted"> and {e.nodes_removed.length - 24} more</span>}</span>}
      <h4>Nodes added ({e.nodes_added.length})</h4><NodeChips ids={e.nodes_added} />
      <h4>Nodes relabelled ({e.nodes_changed.length})</h4><NodeChips ids={e.nodes_changed} />
      <h4>Edges added ({e.edges_added.length})</h4><EdgeTally edges={e.edges_added} />
      <h4>Edges removed ({e.edges_removed.length})</h4><EdgeTally edges={e.edges_removed} />
      <p className="muted foot">This is the graph's own record of the production. From P3 the ledger of shape provenance is shown beside it.</p>
    </div>
  );
}

function Elements() {
  const elements = useStore((s) => s.elements);
  const focus = useStore((s) => s.element);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (focus) ref.current?.querySelector(`[data-symbol="${focus}"]`)?.scrollIntoView({ block: "center" });
  }, [focus]);
  const cats = [...new Set(elements.map((e) => e.category))];
  return (
    <div className="pad" ref={ref}>
      <p className="muted">The {elements.length} element types of the prototype dictionary. Rules name the ones they produce.</p>
      {cats.map((c) => (
        <section key={c}>
          <h4>{c}</h4>
          {elements.filter((e) => e.category === c).map((e) => (
            <details key={e.symbol} data-symbol={e.symbol} className={"element" + (focus === e.symbol ? " focus" : "")} open={focus === e.symbol}>
              <summary><code>{e.symbol}</code><span>{e.name}</span></summary>
              <table className="kv">
                <tbody>
                  <tr><th>IFC class</th><td>{e.ifc}</td></tr>
                  {Object.entries(e.params).map(([k, v]) => <tr key={k}><th>{k}</th><td>{show(v)}</td></tr>)}
                  <tr><th>ports</th><td>{e.ports.map((p) => p.name).join(", ")}</td></tr>
                  <tr><th>occurs</th><td>{show(e.occurrences)}, {e.where}</td></tr>
                </tbody>
              </table>
              <p>{e.grammar_role}</p>
            </details>
          ))}
        </section>
      ))}
    </div>
  );
}

const TABS: [Tab, string][] = [["inspect", "Inspect"], ["checks", "Checks"], ["event", "Event"], ["elements", "Elements"]];

export default function RightPanel() {
  const scene = useShown();
  const tab = useStore((s) => s.tab);
  const setTab = useStore((s) => s.setTab);
  const failing = scene?.invariants.checks.filter((c) => c.status === "fail").length ?? 0;
  return (
    <aside className="right">
      <div className="tabs" role="tablist">
        {TABS.map(([t, label]) => (
          <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>
            {label}{t === "checks" && failing > 0 && <span className="pill">{failing}</span>}
          </button>
        ))}
      </div>
      <div className="tab-body">
        {!scene ? null : tab === "inspect" ? <Inspector scene={scene} /> : tab === "checks" ? <Checks scene={scene} />
          : tab === "event" ? <EventView scene={scene} /> : <Elements />}
      </div>
    </aside>
  );
}
