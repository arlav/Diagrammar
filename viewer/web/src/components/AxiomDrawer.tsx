import { useEffect, useState } from "react";
import { useStore } from "../store";

export default function AxiomDrawer() {
  const packs = useStore((s) => s.packs);
  const scene = useStore((s) => s.scene);
  const open = useStore((s) => s.axiomOpen);
  const setOpen = useStore((s) => s.openAxiom);
  const start = useStore((s) => s.start);
  const busy = useStore((s) => s.busy);
  const refused = useStore((s) => s.problems);
  const error = useStore((s) => s.error);

  const [packName, setPackName] = useState("");
  const [preset, setPreset] = useState<string>("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [bad, setBad] = useState<Record<string, string>>({});
  const [checked, setChecked] = useState(false);

  const pack = packs.find((p) => p.name === packName) ?? null;

  const fill = (name: string, presetName: string) => {
    const p = packs.find((x) => x.name === name);
    if (!p) return;
    const params = { ...p.parameters, ...(p.presets[presetName]?.parameters ?? {}) };
    setPackName(name);
    setPreset(presetName);
    setFields(Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])));
    setBad({});
    setChecked(false);
  };

  useEffect(() => {
    if (!open || !scene) return;
    if (scene.preset) fill(scene.pack_name, scene.preset);
    else {
      setPackName(scene.pack_name); setPreset("");
      setFields(Object.fromEntries(Object.entries(scene.parameters).map(([k, v]) => [k, String(v)])));
      setBad({}); setChecked(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open || !pack) return null;

  const base: Record<string, unknown> = { ...pack.parameters, ...(preset ? pack.presets[preset]?.parameters ?? {} : {}) };
  const edited = Object.keys(fields).filter((k) => fields[k].trim() !== String(base[k]));

  const submit = async () => {
    const values: Record<string, unknown> = {};
    const wrong: Record<string, string> = {};
    for (const k of edited) {
      const n = Number(fields[k]);
      if (!Number.isInteger(n)) wrong[k] = "Enter a whole number.";
      else values[k] = n;
    }
    setBad(wrong);
    setChecked(Object.keys(wrong).length === 0);
    if (Object.keys(wrong).length > 0) return;
    const ok = await start(packName, preset || null, edited.length > 0 ? values : undefined);
    if (ok) setOpen(false);
  };

  const steps = scene?.timeline.length ?? 0;
  const d = pack.diff;
  return (
    <div className="scrim" onMouseDown={(e) => { if (e.target === e.currentTarget) setOpen(false); }}>
      <div className="drawer" role="dialog" aria-label="Axiom">
        <header><h2>Axiom</h2><button className="x" onClick={() => setOpen(false)} aria-label="Close">×</button></header>
        <div className="drawer-body">
          <h4>Grammar</h4>
          <div className="presets">
            {packs.map((p) => (
              <button key={p.name} className={"preset" + (packName === p.name ? " on" : "")} onClick={() => fill(p.name, Object.keys(p.presets)[0])}>
                <b>{p.title}</b><span>{p.diff ? `a transformation of ${p.diff.base}: ${p.rules.length} rules` : `${p.rules.length} rules`}</span>
              </button>
            ))}
          </div>
          {d && (
            <p className="muted small">
              From {d.base}: changed {d.changed.join(", ") || "nothing"}; added {d.added.join(", ") || "nothing"}; removed {d.removed.length} rule{d.removed.length === 1 ? "" : "s"}.
            </p>
          )}
          <h4>Start from</h4>
          <div className="presets">
            {Object.entries(pack.presets).map(([k, p]) => (
              <button key={k} className={"preset" + (preset === k ? " on" : "")} onClick={() => fill(packName, k)}>
                <b>{p.title}</b><span>{p.note}</span>
                {p.strategy && <em>recorded pathway: {pack.strategies[p.strategy]?.steps ?? "?"} choices</em>}
              </button>
            ))}
          </div>
          <h4>Parameters</h4>
          {Object.keys(pack.parameters).map((k) => (
            <label key={k} className={"field" + (bad[k] ? " bad" : "")}>
              <span className="name">{k}{edited.includes(k) && <em>edited</em>}</span>
              <input value={fields[k] ?? ""} spellCheck={false} onChange={(e) => { setFields({ ...fields, [k]: e.target.value }); setChecked(false); }} />
              <span className="note">{bad[k] ?? pack.parameter_notes[k]}</span>
            </label>
          ))}
          {checked && refused.length > 0 && (
            <div className="notice bad">
              <b>{error}</b>
              <ul>{refused.map((p) => <li key={p}>{p}</li>)}</ul>
            </div>
          )}
        </div>
        <footer>
          <span className="muted">
            {edited.length > 0 && preset ? "Edited parameters are no longer the preset, so its figures will not be checked. " : ""}
            {steps > 1 ? `This discards the current derivation (${steps - 1} step${steps > 2 ? "s" : ""}).` : ""}
          </span>
          <button onClick={() => setOpen(false)}>Cancel</button>
          <button className="primary" disabled={busy} onClick={submit}>Start derivation</button>
        </footer>
      </div>
    </div>
  );
}
