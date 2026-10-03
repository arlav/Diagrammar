import { useMemo } from "react";
import { useStore } from "./store";

export type Mark = "selected" | "site" | "removed" | "added" | "changed";

// Which nodes are picked out, and why. One node carries one mark; the first that applies wins.
export function useMarks(): Map<string, Mark> {
  const selected = useStore((s) => s.selected);
  const hover = useStore((s) => s.hover);
  const scene = useStore((s) => s.scene);
  const preview = useStore((s) => s.preview);
  return useMemo(() => {
    const m = new Map<string, Mark>();
    const ev = (preview ?? scene)?.event;
    ev?.nodes_changed.forEach((n) => m.set(n, "changed"));
    ev?.nodes_added.forEach((n) => m.set(n, "added"));
    if (preview) preview.event.nodes_removed.forEach((n) => m.set(n, "removed"));
    hover.forEach((n) => m.set(n, "site"));
    if (selected) m.set(selected, "selected");
    return m;
  }, [selected, hover, scene, preview]);
}
