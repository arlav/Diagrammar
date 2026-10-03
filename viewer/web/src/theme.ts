// One colour per node type and per kind of access, shared by every view.

export const TYPE_COLOR: Record<string, string> = {
  dwelling: "#d99a2b",
  corridor: "#2f7fc1",
  stairwell: "#b5482a",
  ground: "#6f8f5f",
  hall: "#8b4fa8",
  gallery: "#c08ad6",
  bridge: "#1f9d8f",
  interface: "#64748b",
  roof: "#7c8aa0",
  mass: "#a39c8c",
  storey: "#b3ac9c",
  bay: "#c4bdae",
};

export const ACCESS_COLOR: Record<string, string> = {
  none: "#9aa0a8",
  door: "#d9541e",
  open: "#2f7fc1",
  stair: "#a3162e",
};

export const ACCESS_LABEL: Record<string, string> = {
  none: "adjacent, no access",
  door: "door",
  open: "open",
  stair: "stair",
};

export const HILITE = { selected: "#111827", site: "#e11d8f", added: "#16a34a", removed: "#dc2626", changed: "#ca8a04" };

export const typeColor = (t: string | null | undefined) => TYPE_COLOR[t ?? ""] ?? "#94a3b8";
