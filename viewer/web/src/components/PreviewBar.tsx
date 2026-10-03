import { useStore } from "../store";
import { EdgeTally } from "./Chips";

export default function PreviewBar() {
  const preview = useStore((s) => s.preview);
  const of = useStore((s) => s.previewOf);
  const rule = useStore((s) => s.scene?.rules.find((r) => r.id === s.previewOf?.rule));
  const apply = useStore((s) => s.apply);
  const cancel = useStore((s) => s.cancelPreview);
  const busy = useStore((s) => s.busy);
  if (!preview || !of || !rule) return null;
  const e = preview.event;
  const n = preview.step.applications;
  return (
    <div className="preview-bar" role="dialog" aria-label="Preview of a production">
      <div className="what">
        <b>{rule.id} {rule.name}</b>
        <span>{n > 1 ? `at ${n} sites` : `at ${preview.step.label}`}</span>
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
        <button className="primary" disabled={busy} onClick={() => apply(of.rule, of.site)}>Apply</button>
      </div>
    </div>
  );
}
