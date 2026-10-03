import { useStore } from "../store";
import { ACCESS_COLOR, typeColor } from "../theme";
import type { GraphEdge } from "../api";

export function NodeChip({ id, type }: { id: string; type?: string | null }) {
  const select = useStore((s) => s.select);
  const setHover = useStore((s) => s.setHover);
  const known = useStore((s) => (s.preview ?? s.scene)?.graph.nodes.find((n) => n.id === id));
  const t = type ?? known?.type;
  return (
    <button className="chip node" disabled={!known} title={known ? `${known.label} (${known.type})` : "not in this state"}
      onClick={() => select(id)} onMouseEnter={() => known && setHover([id])} onMouseLeave={() => setHover([])}>
      <i style={{ background: typeColor(t) }} />{id}
    </button>
  );
}

export function NodeChips({ ids, limit = 24 }: { ids: string[]; limit?: number }) {
  if (ids.length === 0) return <span className="muted">none</span>;
  return (
    <span className="chips">
      {ids.slice(0, limit).map((id) => <NodeChip key={id} id={id} />)}
      {ids.length > limit && <span className="muted"> and {ids.length - limit} more</span>}
    </span>
  );
}

export function AccessDot({ access }: { access: string }) {
  return <i className="dot" style={{ background: ACCESS_COLOR[access] ?? ACCESS_COLOR.none }} />;
}

export function EdgeTally({ edges }: { edges: GraphEdge[] }) {
  if (edges.length === 0) return <span className="muted">none</span>;
  const by = new Map<string, { n: number; access: string }>();
  for (const e of edges) by.set(e.rel, { n: (by.get(e.rel)?.n ?? 0) + 1, access: e.access });
  return (
    <span className="chips">
      {[...by.entries()].map(([rel, v]) => (
        <span key={rel} className="chip flat"><AccessDot access={v.access} />{v.n} {rel}</span>
      ))}
    </span>
  );
}

export function SymbolChip({ symbol }: { symbol: string }) {
  const show = useStore((s) => s.showElement);
  return <button className="chip symbol" onClick={() => show(symbol)} title="Show in the element dictionary">{symbol}</button>;
}
