import { useEffect, useState } from "react";
import { useStore } from "../store";

const text = (v: unknown) => (typeof v === "object" ? JSON.stringify(v).replace(/,/g, ", ") : String(v));

export default function AxiomDrawer() {
  const pack = useStore((s) => s.pack);
  const scene = useStore((s) => s.scene);
  const open = useStore((s) => s.axiomOpen);
  const setOpen = useStore((s) => s.openAxiom);
  const start = useStore((s) => s.start);
  const busy = useStore((s) => s.busy);
  const refused = useStore((s) => s.problems);
  const error = useStore((s) => s.error);

  const [preset, setPreset] = useState<string>("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [bad, setBad] = useState<Record<string, string>>({});
  const [checked, setChecked] = useState(false);      // the server has seen what is in the fields now

  const fill = (name: string) => {
    if (!pack) return;
    const p = { ...pack.parameters, ...(pack.presets[name]?.parameters ?? {}) };
    setPreset(name);
    setFields(Object.fromEntries(Object.entries(p).map(([k, v]) => [k, text(v)])));
    setBad({});
  };

  useEffect(() => {
    if (!open || !pack || !scene) return;
    if (scene.preset) fill(scene.preset);
    else { setPreset(""); setFields(Object.fromEntries(Object.entries(scene.parameters).map(([k, v]) => [k, text(v)]))); setBad({}); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open || !pack) return null;

  const base: Record<string, unknown> = { ...pack.parameters, ...(preset ? pack.presets[preset].parameters : {}) };
  const edited = Object.keys(fields).filter((k) => fields[k].replace(/\s/g, "") !== text(base[k]).replace(/\s/g, ""));

  const submit = async () => {
    const values: Record<string, unknown> = {};
    const wrong: Record<string, string> = {};
    for (const k of edited) {
      try { values[k] = JSON.parse(fields[k]); }
      catch { wrong[k] = typeof pack.parameters[k] === "number" ? "Enter a whole number." : 'Enter a list, such as [1, 4] or [[1, 2, 0, "K"]].'; }
    }
    setBad(wrong);
    setChecked(Object.keys(wrong).length === 0);
    if (Object.keys(wrong).length > 0) return;
    const ok = await start(preset || null, edited.length > 0 ? values : undefined);
    if (ok) setOpen(false);
  };

  const steps = scene?.timeline.length ?? 0;
  return (
    <div className="scrim" onMouseDown={(e) => { if (e.target === e.currentTarget) setOpen(false); }}>
      <div className="drawer" role="dialog" aria-label="Axiom">
        <header><h2>Axiom</h2><button className="x" onClick={() => setOpen(false)} aria-label="Close">×</button></header>
        <div className="drawer-body">
          <h4>Start from</h4>
          <div className="presets">
            {Object.entries(pack.presets).map(([k, p]) => (
              <button key={k} className={"preset" + (preset === k ? " on" : "")} onClick={() => fill(k)}>
                <b>{p.title}</b><span>{p.note}</span>
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
