// The scene contract, as the server sends it (topogrammar/scene/build.py).

export type Access = "none" | "door" | "open" | "stair";

export interface Cell {
  id: string;
  category: string;
  type: string;
  block: string | null;
  level: number | null;
  symbol: string | null;
  positions: number[];
  indices: number[];
  lines: number[];
  centroid: [number, number, number];
  bounds: [[number, number, number], [number, number, number]];
  volume: number;
}

export interface GraphNode {
  id: string;
  pos: [number, number, number];
  type: string;
  label: string;
  occupiable: boolean;
  terminal: boolean;
  dictionary: Record<string, unknown>;
}

export interface GraphEdge {
  a: string;
  b: string;
  rel: string;
  access: Access;
  in_access_graph: boolean;
  mirror?: boolean;
}

export interface Site {
  key: string;
  label: string;
  nodes: string[];
  touched: string[];
  params: Record<string, unknown>;
  decisive: boolean;
  conflicts_with: string[];
  conflicts: number;
}

export interface SiteGroup {
  label: string;
  params: Record<string, unknown>;
  sites: Site[];
  competes_with: string[];
}

export interface RuleInfo {
  id: string;
  title: string;
  verb: string;
  grammar: string;
  description: string;
  symbols: string[];
  shape: { operation?: string };
  auto: boolean;
  identity: boolean;
  params: Record<string, unknown>;
  hash: string;
}

export interface Rule extends RuleInfo {
  enabled: boolean;
  site_count: number;
  groups: SiteGroup[];
}

export interface PatternView {
  nodes: Record<string, Record<string, unknown>>;
  edges: [string, string, string | null][];
  where: string[];
  flags: string[];
}

export interface Card {
  id: string;
  params: Record<string, unknown>;
  lhs: PatternView;
  nac: PatternView[];
  rhs: {
    delete?: string[];
    contract?: { into: string; nodes: string[] };
    create?: Record<string, Record<string, unknown>>;
    relabel?: Record<string, Record<string, unknown>>;
    unlink?: [string, string][];
    link?: [string, string, string][];
    set_edge?: [string, string, Record<string, unknown>][];
    flag?: string[];
  };
  touched: string[];
}

export interface TimelineStep {
  id: number;
  parent: number | null;
  rule: string | null;
  site: string | null;
  label: string;
  nodes: number;
  edges: number;
  applications: number;
  consequences: number;
  decisions: number;
  elapsed_ms: number;
  children: number[];
  on_path: boolean;
}

export interface Check {
  name: string;
  expected: unknown;
  actual: unknown;
  status: "ok" | "pending" | "fail";
}

export interface Metrics {
  nodes: number;
  edges: number;
  max_degree: number;
  components: number;
  edges_by_access: Record<string, number>;
  edges_by_rel: Record<string, number>;
  nodes_by_type: Record<string, number>;
}

export interface Oracle {
  against: string;
  method: string;
  nodes: [number, number];
  edges: [number, number];
  degree_sequences_equal: boolean;
  node_types_equal: boolean;
  isomorphic: boolean;
  isomorphic_typed: boolean;
}

export interface GraphEvent {
  rule?: string;
  operation?: string;
  shape_operation?: string;
  identity?: boolean;
  sites?: string[];
  params?: Record<string, unknown>;
  matched?: string[];
  consequences?: { rule: string; label: string }[];
  nodes_removed: string[];
  nodes_added: string[];
  nodes_changed: string[];
  edges_removed: GraphEdge[];
  edges_added: GraphEdge[];
  edges_changed: GraphEdge[];
}

export interface PathwayStep {
  step: number;
  rule: string;
  params: Record<string, unknown>;
  sites: string[][];
  consequences: number;
  nodes: number;
  edges: number;
  hash: string;
  label: string;
  decisions: number;
}

export interface Pathway {
  pack: string;
  lineage: { title: string; version: string; hash: string }[];
  preset: string | null;
  parameters: Record<string, unknown>;
  steps: PathwayStep[];
  hash: string;
}

export interface Strategy {
  id: string;
  title: string;
  steps: number;
  cursor: number;
  skipped: { index: number; rule: string }[];
  next: { rule: string; params?: Record<string, unknown>; select?: unknown; repeat?: boolean } | null;
}

export interface Scene {
  session: string;
  pack: string;
  pack_name: string;
  pack_hash: string;
  preview: boolean;
  preset: string | null;
  parameters: Record<string, unknown>;
  dimensions: Record<string, unknown>;
  step: { id: number; parent: number | null; rule: string | null; label: string; applications: number; decisions: number;
          consequences: { rule: string; label: string }[]; elapsed_ms: number; params: Record<string, unknown> };
  head: number;
  complete: boolean;
  event: GraphEvent;
  cells: Cell[];
  graph: { nodes: GraphNode[]; edges: GraphEdge[] };
  invariants: {
    checks: Check[];
    oracle: Oracle | null;
    reachability: { total: number; reachable: number; unreachable: string[]; valid: boolean };
    unresolved: Record<string, string[]>;
    access: Metrics;
    full: Metrics;
    conflicts: { node: string; neighbour: string; relations: string[]; kept: string }[];
  };
  rules: Rule[];
  timeline: TimelineStep[];
  pathway: Pathway;
  strategy: Strategy | null;
}

export interface Preset {
  title: string;
  note: string;
  parameters: Record<string, unknown>;
  strategy: string | null;
  expect: Record<string, unknown>;
}

export interface PackDiff {
  base: string;
  base_hash: string;
  added: string[];
  removed: string[];
  changed: string[];
  dimensions: Record<string, [unknown, unknown]>;
  parameters: Record<string, [unknown, unknown]>;
}

export interface Pack {
  name: string;
  title: string;
  version: string;
  model: string;
  hash: string;
  lineage: { title: string; version: string; hash: string }[];
  diff: PackDiff | null;
  source: string;
  relations: Record<string, Access>;
  occupiable: string[];
  nonterminals: string[];
  dimensions: Record<string, unknown>;
  parameters: Record<string, number>;
  parameter_notes: Record<string, string>;
  presets: Record<string, Preset>;
  strategies: Record<string, { id: string; title: string; note: string; steps: number }>;
  rules: RuleInfo[];
}

export interface ElementType {
  symbol: string;
  name: string;
  category: string;
  ifc: string;
  params: Record<string, unknown>;
  ports: { name: string; at: number[]; faces: number[] }[];
  occurrences: number | string;
  where: string;
  grammar_role: string;
}

export type Selection = string | string[] | { where?: string; params?: Record<string, unknown>; group?: string };

export class ApiError extends Error {
  problems: string[];
  status: number;
  constructor(status: number, message: string, problems: string[] = []) {
    super(message);
    this.status = status;
    this.problems = problems;
  }
}

async function call<T>(path: string, body?: unknown): Promise<T> {
  let r: Response;
  try {
    r = await fetch(path, body === undefined ? undefined : {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "The topogrammar server is not answering. Start it, then reload this page.");
  }
  if (!r.ok) {
    const detail = await r.json().then((j) => j.detail).catch(() => null);
    if (detail && typeof detail === "object" && "message" in detail)
      throw new ApiError(r.status, detail.message, detail.problems ?? []);
    if (r.status >= 500 && typeof detail !== "string")
      throw new ApiError(r.status, "The topogrammar server is not answering. Start it, then reload this page.");
    throw new ApiError(r.status, typeof detail === "string" ? detail : `The server answered ${r.status}.`);
  }
  return r.json();
}

export const api = {
  packs: () => call<Pack[]>("/api/packs"),
  card: (pack: string, rule: string, params?: Record<string, unknown>) =>
    call<Card>(`/api/pack/${pack}/card/${rule}` + (params ? `?params=${encodeURIComponent(JSON.stringify(params))}` : "")),
  elements: () => call<{ elements: ElementType[] }>("/api/elements"),
  start: (pack: string, preset: string | null, parameters?: Record<string, unknown>) =>
    call<Scene>("/api/session", { pack, preset, parameters: parameters ?? null }),
  preview: (sid: string, rule: string, select: Selection | null) => call<Scene>(`/api/session/${sid}/preview`, { rule, select }),
  apply: (sid: string, rule: string, select: Selection | null) => call<Scene>(`/api/session/${sid}/apply`, { rule, select }),
  goto: (sid: string, step: number) => call<Scene>(`/api/session/${sid}/goto`, { step }),
  undo: (sid: string) => call<Scene>(`/api/session/${sid}/undo`, {}),
  run: (sid: string, mode: "next" | "continue" | "all") => call<Scene>(`/api/session/${sid}/run`, { mode }),
  pathway: (sid: string) => call<Pathway>(`/api/session/${sid}/pathway`),
  replay: (sid: string, pathway: Pathway) => call<Scene>(`/api/session/${sid}/replay`, { pathway }),
};
