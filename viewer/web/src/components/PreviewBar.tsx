import { useStore, pack as packOf } from "../store";
import { EdgeTally } from "./Chips";

export default function PreviewBar() {
  const preview = useStore((s) => s.preview);
  const of = useStore((s) => s.previewOf);
  const pack = useStore(packOf);
  const apply = useStore((s) => s.apply);
  const cancel = useStore((s) => s.cancelPreview);
  const busy = useStore((s) => s.busy);
  if (!preview || !of) return null;
  const rule = pack?.rules.find((r) => r.id === of.rule);
  const e = preview.event;
  const n = preview.step.applications;
  const auto = preview.step.consequences.length;
  return (
    <div className="preview-bar" role="dialog" aria-label="Preview of a production">
      <div className="what">
        <b>{rule?.id ?? of.rule} {rule?.title ?? ""}</b>
        <span>{n > 1 ? `at ${n} sites` : `at ${preview.step.label}`}{auto > 0 ? `, ${auto} consequence${auto > 1 ? "s" : ""}` : ""}</span>
      </div>
      <div className="effect">
        {e.identity
          ? <span>Changes nothing in the graph.</span>
          : <>
              <span><i className="sw removed" />{e.nodes_removed.length} removed</span>
              <span><i className="sw added" />{e.nodes_added.length} added</span>
              {e.nodes_changed.length > 0 && <span><i className="sw changed" />{e.nodes_changed.length} relabelled</span>}
              <span className="sep">edges</span>
              <span>+ <EdgeTally edges={e.edges_added} /></span>
              <span>− <EdgeTally edges={e.edges_removed} /></span>
            </>}
      </div>
      <div className="actions">
        <button onClick={cancel}>Cancel</button>
        <button className="primary" disabled={busy} onClick={() => apply(of.rule, of.select)}>Apply</button>
      </div>
    </div>
  );
}
