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
}

export interface RuleInfo {
  id: string;
  name: string;
  grammar: string;
  stage: number;
  operation: string;
  shape_operation: string;
  description: string;
  identity: boolean;
  symbols: string[];
}

export interface Rule extends RuleInfo {
  enabled: boolean;
  reason: string;
  sites: Site[];
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
  matched?: string[];
  nodes_removed: string[];
  nodes_added: string[];
  nodes_changed: string[];
  edges_removed: GraphEdge[];
  edges_added: GraphEdge[];
  edges_changed: GraphEdge[];
}

export interface Scene {
  session: string;
  warnings: string[];
  preview: boolean;
  preset: string | null;
  parameters: Record<string, unknown>;
  dimensions: Record<string, unknown>;
  step: { id: number; parent: number | null; rule: string | null; site: string | null; label: string; note: string; applications: number; elapsed_ms: number };
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
}

export interface Preset {
  title: string;
  note: string;
  parameters: Record<string, unknown>;
  expect: Record<string, unknown>;
  prototype: { dwellings: number; note: string } | null;
}

export interface Pack {
  title: string;
  version: string;
  model: string;
  source: string;
  relations: Record<string, Access>;
  occupiable: string[];
  nonterminals: string[];
  parameters: Record<string, unknown>;
  parameter_notes: Record<string, string>;
  presets: Record<string, Preset>;
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
  pack: () => call<Pack>("/api/pack"),
  elements: () => call<{ elements: ElementType[] }>("/api/elements"),
  start: (preset: string | null, parameters?: Record<string, unknown>) =>
    call<Scene>("/api/session", { preset, parameters: parameters ?? null }),
  preview: (sid: string, rule: string, site: string) => call<Scene>(`/api/session/${sid}/preview`, { rule, site }),
  apply: (sid: string, rule: string, site: string) => call<Scene>(`/api/session/${sid}/apply`, { rule, site }),
  goto: (sid: string, step: number) => call<Scene>(`/api/session/${sid}/goto`, { step }),
  undo: (sid: string) => call<Scene>(`/api/session/${sid}/undo`, {}),
  run: (sid: string, until: string | null) => call<Scene>(`/api/session/${sid}/run`, { until }),
};
