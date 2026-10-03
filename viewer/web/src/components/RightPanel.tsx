import { useEffect, useRef, useState } from "react";
import type { Check, Pathway, Scene } from "../api";
import { pack as packOf, useShown, useStore, type Tab } from "../store";
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
  const pack = useStore(packOf);
  const inv = scene.invariants;
  const preset = scene.preset ? pack?.presets[scene.preset] : null;
  const left = Object.entries(inv.unresolved);
  return (
    <div className="pad">
      <p className="muted">
        {preset ? <>Figures the preset <b>{preset.title}</b> must reach. </> : "These parameters are not a preset, so only the general checks apply. "}
        {!scene.complete && "While choices are still open, a figure not yet reached is pending."}
      </p>
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
          ? "Compared with the prototype's recorded access graph once nothing is left to apply."
          : "No recorded graph to compare with here. From P4 this compares the driven graph with the one rebuilt from shape provenance."}</p>
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

function PathwayView({ scene }: { scene: Scene }) {
  const goto = useStore((s) => s.goto);
  const replay = useStore((s) => s.replay);
  const busy = useStore((s) => s.busy);
  const p = scene.pathway;
  const [pasted, setPasted] = useState("");
  const [bad, setBad] = useState("");
  const text = JSON.stringify(p, null, 1);
  const decisions = p.steps.reduce((n, s) => n + s.decisions, 0);
  const load = () => {
    try {
      const obj = JSON.parse(pasted) as Pathway;
      if (!Array.isArray(obj.steps)) throw new Error("no steps");
      setBad("");
      replay(obj);
    } catch {
      setBad("That is not a pathway: paste the JSON exported from this panel.");
    }
  };
  return (
    <div className="pad">
      <p className="muted">The choices that led here, in order. The hash chains them to the pack, so the same choices on the same rules give the same hash, and a different choice anywhere gives a different one.</p>
      <table className="kv">
        <tbody>
          <tr><th>pack</th><td>{p.lineage.map((l) => `${l.title} ${l.hash}`).join(" → ")}</td></tr>
          <tr><th>pathway</th><td>{p.hash}</td></tr>
          <tr><th>choices</th><td>{p.steps.length}, of which {decisions} decided against another offer</td></tr>
        </tbody>
      </table>
      <h4>Steps</h4>
      <ol className="pathway">
        {p.steps.map((s, i) => (
          <li key={s.hash} className={s.decisions > 0 ? "decision" : ""}>
            <button className="plain" onClick={() => goto(s.step)} title={`Go to step ${s.step}`}>
              <b>{s.rule}</b>{Object.keys(s.params).length > 0 && <code>{Object.entries(s.params).map(([k, v]) => `${k}=${v}`).join(" ")}</code>}
              <span>{s.sites.length > 1 ? `${s.sites.length} sites` : s.label}</span>
              {s.decisions > 0 && <em title="This choice decided against other offers for the same nodes">decision</em>}
              {s.consequences > 0 && <span className="muted">+{s.consequences}</span>}
            </button>
            <span className="hash">{s.hash.slice(0, 8)}{i === p.steps.length - 1 ? "" : ""}</span>
          </li>
        ))}
      </ol>
      <h4>Export</h4>
      <textarea className="export" readOnly value={text} rows={5} onFocus={(e) => e.currentTarget.select()} />
      <h4>Replay a pathway here</h4>
      <p className="muted">Paste a pathway's JSON. It replaces this derivation and replays the choices on this pack's rules.</p>
      <textarea className="export" value={pasted} rows={3} onChange={(e) => setPasted(e.target.value)} placeholder='{"steps": [...]}' />
      {bad && <div className="notice bad">{bad}</div>}
      <button className="primary small" disabled={busy || !pasted.trim()} onClick={load}>Replay</button>
    </div>
  );
}

function EventView({ scene }: { scene: Scene }) {
  const e = scene.event;
  const pack = useStore(packOf);
  const rule = pack?.rules.find((r) => r.id === e.rule);
  if (!e.rule || !rule) return <p className="muted pad">No production has been applied yet.</p>;
  const by = new Map<string, number>();
  for (const c of e.consequences ?? []) by.set(c.rule, (by.get(c.rule) ?? 0) + 1);
  return (
    <div className="pad">
      <div className="node-head">
        <div><b>{rule.id} {rule.title}</b><span>{scene.preview ? "preview, not applied" : `step ${scene.step.id}, ${scene.step.elapsed_ms} ms`}</span></div>
      </div>
      <table className="kv">
        <tbody>
          <tr><th>graph</th><td>{rule.verb}</td></tr>
          <tr><th>shape</th><td>{e.shape_operation}</td></tr>
          {Object.keys(e.params ?? {}).length > 0 && <tr><th>parameters</th><td>{Object.entries(e.params!).map(([k, v]) => `${k} = ${v}`).join(", ")}</td></tr>}
          <tr><th>sites</th><td>{(e.sites ?? []).length > 4 ? `${e.sites!.length} sites` : (e.sites ?? []).join(", ")}</td></tr>
          {scene.step.decisions > 0 && <tr><th>decisions</th><td>{scene.step.decisions} of the sites had other offers competing for their nodes</td></tr>}
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
      <h4>Consequences ({(e.consequences ?? []).length})</h4>
      {by.size === 0 ? <span className="muted">none</span>
        : <span className="chips">{[...by.entries()].map(([r, n]) => <span key={r} className="chip flat">{r} ×{n}</span>)}</span>}
      <p className="muted foot">This is the graph's own record of the production. From P3 the ledger of shape provenance is shown beside it.</p>
    </div>
  );
}

function PackView() {
  const pack = useStore(packOf);
  const packs = useStore((s) => s.packs);
  if (!pack) return null;
  const d = pack.diff;
  const base = d ? packs.find((p) => p.title === d.base) : null;
  const byGrammar = new Map<string, number>();
  for (const r of pack.rules) byGrammar.set(r.grammar, (byGrammar.get(r.grammar) ?? 0) + 1);
  return (
    <div className="pad">
      <div className="node-head"><div><b>{pack.title}</b><span>{pack.model}</span></div></div>
      <table className="kv">
        <tbody>
          <tr><th>version</th><td>{pack.version}</td></tr>
          <tr><th>hash</th><td>{pack.hash}</td></tr>
          <tr><th>rules</th><td>{pack.rules.length}: {[...byGrammar.entries()].map(([g, n]) => `${n} in ${g}`).join(", ")}; {pack.rules.filter((r) => r.auto).length} consequences</td></tr>
          <tr><th>lineage</th><td>{pack.lineage.map((l) => `${l.title} (${l.hash})`).join(" → ")}</td></tr>
        </tbody>
      </table>
      {d && (
        <>
          <h4>Transformation of {d.base}</h4>
          <p className="muted">Knight (1983): a new language from an existing grammar by changing, adding and removing rules. The base pack's hash is {d.base_hash}{base && base.hash !== d.base_hash ? ", which no longer matches its current version" : ""}.</p>
          <table className="kv">
            <tbody>
              <tr><th>changed</th><td>{d.changed.join(", ") || "none"}</td></tr>
              <tr><th>added</th><td>{d.added.join(", ") || "none"}</td></tr>
              <tr><th>removed</th><td>{d.removed.join(", ") || "none"}</td></tr>
              {Object.entries(d.dimensions).map(([k, [a, b]]) => <tr key={k}><th>{k}</th><td>{show(a)} → {show(b)}</td></tr>)}
              {Object.entries(d.parameters).map(([k, [a, b]]) => <tr key={k}><th>{k}</th><td>{show(a)} → {show(b)}</td></tr>)}
            </tbody>
          </table>
        </>
      )}
      <h4>Dimensions</h4>
      <table className="kv"><tbody>{Object.entries(pack.dimensions).map(([k, v]) => <tr key={k}><th>{k}</th><td>{show(v)}</td></tr>)}</tbody></table>
      <h4>Rules</h4>
      <table className="kv rules-list">
        <tbody>
          {pack.rules.map((r) => (
            <tr key={r.id} className={r.auto ? "auto" : ""}><th>{r.id}</th><td>{r.title}<em>{r.verb}</em>{r.auto && <span className="tag">consequence</span>}</td></tr>
          ))}
        </tbody>
      </table>
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

const TABS: [Tab, string][] = [["inspect", "Inspect"], ["checks", "Checks"], ["pathway", "Pathway"], ["event", "Event"], ["pack", "Pack"], ["elements", "Elements"]];

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
          : tab === "pathway" ? <PathwayView scene={scene} /> : tab === "event" ? <EventView scene={scene} />
          : tab === "pack" ? <PackView /> : <Elements />}
      </div>
    </aside>
  );
}
