import { create } from "zustand";
import { api, ApiError, type Card, type ElementType, type Pack, type Pathway, type Scene, type Selection } from "./api";

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

export type Tab = "inspect" | "checks" | "pathway" | "event" | "pack" | "elements";

interface State {
  packs: Pack[];
  elements: ElementType[];
  scene: Scene | null;
  preview: Scene | null;
  previewOf: { rule: string; select: Selection | null; label: string } | null;
  cards: Record<string, Card>;
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
  start: (pack: string, preset: string | null, parameters?: Record<string, unknown>) => Promise<boolean>;
  previewSite: (rule: string, select: Selection | null, label: string) => Promise<void>;
  cancelPreview: () => void;
  apply: (rule: string, select: Selection | null) => Promise<void>;
  goto: (step: number) => Promise<void>;
  undo: () => Promise<void>;
  run: (mode: "next" | "continue" | "all") => Promise<void>;
  replay: (pathway: Pathway) => Promise<void>;
  loadCard: (rule: string, params?: Record<string, unknown>) => Promise<Card | null>;
  select: (id: string | null) => void;
  setHover: (ids: string[]) => void;
  setView: (v: Partial<ViewOptions>) => void;
  refit: () => void;
  dismiss: () => void;
  setTab: (t: Tab) => void;
  showElement: (symbol: string) => void;
  openAxiom: (open: boolean) => void;
}

export const pack = (s: State) => s.packs.find((p) => p.name === s.scene?.pack_name) ?? null;

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
          const scene = await api.start(s.pack_name, s.preset, s.preset ? undefined : s.parameters);
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
    packs: [], elements: [], scene: null, preview: null, previewOf: null, cards: {}, selected: null, hover: [],
    busy: false, error: null, problems: [], fit: 0, tab: "inspect", element: null, axiomOpen: false,
    view: { cells: true, graph: true, accessOnly: false, lift: 0, gap: 0.04, opacity: 0.32, cut: 1, ortho: true, layout: "elevation" },

    init: async () => {
      set({ busy: true });
      try {
        const [packs, el] = await Promise.all([api.packs(), api.elements()]);
        set({ packs, elements: el.elements });
        const first = packs[0];
        await get().start(first.name, Object.keys(first.presets)[0]);
      } catch (e) {
        set({ busy: false, error: (e as Error).message });
      }
    },

    start: async (packName, preset, parameters) => {
      set({ problems: [] });
      const ok = await act(() => api.start(packName, preset, parameters), { selected: null, cards: {} });
      if (ok) set((s) => ({ fit: s.fit + 1 }));
      return ok;
    },

    previewSite: async (rule, select, label) => {
      const sid = get().scene?.session;
      if (!sid) return;
      set({ busy: true, error: null });
      try {
        const preview = await api.preview(sid, rule, select);
        set({ preview, previewOf: { rule, select, label }, busy: false });
      } catch (e) {
        set({ busy: false, error: (e as Error).message });
      }
    },
    cancelPreview: () => set({ preview: null, previewOf: null }),

    apply: async (rule, select) => { const sid = get().scene?.session; if (sid) await act(() => api.apply(sid, rule, select)); },
    goto: async (step) => { const sid = get().scene?.session; if (sid) await act(() => api.goto(sid, step)); },
    undo: async () => { const sid = get().scene?.session; if (sid) await act(() => api.undo(sid)); },
    run: async (mode) => { const sid = get().scene?.session; if (sid) await act(() => api.run(sid, mode)); },
    replay: async (pathway) => { const sid = get().scene?.session; if (sid) await act(() => api.replay(sid, pathway)); },

    loadCard: async (rule, params) => {
      const s = get();
      const key = rule + JSON.stringify(params ?? {});
      if (s.cards[key]) return s.cards[key];
      const name = s.scene?.pack_name;
      if (!name) return null;
      try {
        const card = await api.card(name, rule, params);
        set((st) => ({ cards: { ...st.cards, [key]: card } }));
        return card;
      } catch (e) {
        set({ error: (e as Error).message });
        return null;
      }
    },

    select: (id) => set((s) => ({ selected: id, tab: id && (s.tab === "elements" || s.tab === "pack") ? "inspect" : s.tab })),
    setHover: (ids) => set({ hover: ids }),
    setView: (v) => set((s) => ({ view: { ...s.view, ...v } })),
    refit: () => set((s) => ({ fit: s.fit + 1 })),
    dismiss: () => set({ error: null }),
    setTab: (tab) => set({ tab }),
    showElement: (symbol) => set({ tab: "elements", element: symbol }),
    openAxiom: (axiomOpen) => set({ axiomOpen, problems: [], error: null }),
  };
});

// the scene the views draw: the preview while one is open, the head of the derivation otherwise
export const useShown = () => useStore((s) => s.preview ?? s.scene);
