import { create } from "zustand";
import { api, ApiError, type ElementType, type Pack, type Scene } from "./api";

export interface ViewOptions {
  cells: boolean;
  graph: boolean;
  accessOnly: boolean;
  lift: number;        // metres the graph is raised above the model
  gap: number;         // 0..0.3, how far cells are shrunk apart
  opacity: number;
  cut: number;         // 0..1 along the block; 1 = no cut
  ortho: boolean;
  layout: "elevation" | "plan" | "force";
}

export type Tab = "inspect" | "checks" | "event" | "elements";

interface State {
  pack: Pack | null;
  elements: ElementType[];
  scene: Scene | null;
  preview: Scene | null;
  previewOf: { rule: string; site: string } | null;
  selected: string | null;
  hover: string[];
  busy: boolean;
  error: string | null;
  problems: string[];
  view: ViewOptions;
  fit: number;
  tab: Tab;
  element: string | null;
  axiomOpen: boolean;

  init: () => Promise<void>;
  start: (preset: string | null, parameters?: Record<string, unknown>) => Promise<boolean>;
  previewSite: (rule: string, site: string) => Promise<void>;
  cancelPreview: () => void;
  apply: (rule: string, site: string) => Promise<void>;
  goto: (step: number) => Promise<void>;
  undo: () => Promise<void>;
  run: (until: string | null) => Promise<void>;
  select: (id: string | null) => void;
  setHover: (ids: string[]) => void;
  setView: (v: Partial<ViewOptions>) => void;
  refit: () => void;
  dismiss: () => void;
  setTab: (t: Tab) => void;
  showElement: (symbol: string) => void;
  openAxiom: (open: boolean) => void;
}

export const useStore = create<State>((set, get) => {
  // every action answers with a scene; this is the one place a scene is received
  const act = async (fn: () => Promise<Scene>, after?: Partial<State>) => {
    set({ busy: true, error: null });
    try {
      const scene = await fn();
      const selected = get().selected;
      set({
        scene, preview: null, previewOf: null, busy: false, hover: [],
        selected: selected && scene.graph.nodes.some((n) => n.id === selected) ? selected : null,
        ...after,
      });
      return true;
    } catch (e) {
      const err = e as ApiError;
      if (err.status === 404 && get().scene) {
        // the server was restarted and lost the derivation: begin again with the same parameters
        const s = get().scene!;
        try {
          const scene = await api.start(s.preset, s.preset ? undefined : s.parameters);
          set({ scene, preview: null, previewOf: null, busy: false, selected: null,
                error: "The server was restarted, so the derivation began again from the start." });
        } catch (e2) {
          set({ busy: false, error: (e2 as Error).message });
        }
        return false;
      }
      set({ busy: false, error: err.message, problems: err.problems ?? [] });
      return false;
    }
  };

  return {
    pack: null, elements: [], scene: null, preview: null, previewOf: null, selected: null, hover: [],
    busy: false, error: null, problems: [], fit: 0, tab: "inspect", element: null, axiomOpen: false,
    view: { cells: true, graph: true, accessOnly: false, lift: 0, gap: 0.04, opacity: 0.32, cut: 1, ortho: true, layout: "elevation" },

    init: async () => {
      set({ busy: true });
      try {
        const [pack, el] = await Promise.all([api.pack(), api.elements()]);
        set({ pack, elements: el.elements });
        await get().start(Object.keys(pack.presets)[0]);
      } catch (e) {
        set({ busy: false, error: (e as Error).message });
      }
    },

    start: async (preset, parameters) => {
      set({ problems: [] });
      const ok = await act(() => api.start(preset, parameters), { selected: null });
      if (ok) set((s) => ({ fit: s.fit + 1 }));
      return ok;
    },

    previewSite: async (rule, site) => {
      const sid = get().scene?.session;
      if (!sid) return;
      set({ busy: true, error: null });
      try {
        const preview = await api.preview(sid, rule, site);
        set({ preview, previewOf: { rule, site }, busy: false });
      } catch (e) {
        set({ busy: false, error: (e as Error).message });
      }
    },
    cancelPreview: () => set({ preview: null, previewOf: null }),

    apply: async (rule, site) => { const sid = get().scene?.session; if (sid) await act(() => api.apply(sid, rule, site)); },
    goto: async (step) => { const sid = get().scene?.session; if (sid) await act(() => api.goto(sid, step)); },
    undo: async () => { const sid = get().scene?.session; if (sid) await act(() => api.undo(sid)); },
    run: async (until) => { const sid = get().scene?.session; if (sid) await act(() => api.run(sid, until)); },

    select: (id) => set((s) => ({ selected: id, tab: id && s.tab === "elements" ? "inspect" : s.tab })),
    setTab: (tab) => set({ tab }),
    showElement: (symbol) => set({ tab: "elements", element: symbol }),
    openAxiom: (axiomOpen) => set({ axiomOpen, problems: [], error: null }),
    setHover: (ids) => set({ hover: ids }),
    setView: (v) => set((s) => ({ view: { ...s.view, ...v } })),
    refit: () => set((s) => ({ fit: s.fit + 1 })),
    dismiss: () => set({ error: null }),
  };
});

// the scene the views draw: the preview while one is open, the head of the derivation otherwise
export const useShown = () => useStore((s) => s.preview ?? s.scene);
