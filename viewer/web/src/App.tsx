import { useEffect } from "react";
import { pack as packOf, useStore } from "./store";
import { ACCESS_COLOR, ACCESS_LABEL } from "./theme";
import Viewport3D from "./components/Viewport3D";
import Graph2D from "./components/Graph2D";
import RulePalette from "./components/RulePalette";
import Timeline from "./components/Timeline";
import RightPanel from "./components/RightPanel";
import AxiomDrawer from "./components/AxiomDrawer";
import PreviewBar from "./components/PreviewBar";
import ViewBar, { CameraBar, GraphBar } from "./components/ViewBar";

export default function App() {
  const init = useStore((s) => s.init);
  const pack = useStore(packOf);
  const scene = useStore((s) => s.scene);
  const error = useStore((s) => s.error);
  const axiomOpen = useStore((s) => s.axiomOpen);
  const dismiss = useStore((s) => s.dismiss);
  const openAxiom = useStore((s) => s.openAxiom);
  const cancelPreview = useStore((s) => s.cancelPreview);

  useEffect(() => { init(); }, [init]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { cancelPreview(); openAxiom(false); } };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [cancelPreview, openAxiom]);

  const preset = scene?.preset ? pack?.presets[scene.preset] : null;
  const p = scene?.parameters as Record<string, unknown> | undefined;
  const strategy = scene?.strategy;

  return (
    <div className="app">
      <header className="top">
        <div className="brand"><b>topogrammar</b><span>{pack?.model ?? ""}</span></div>
        <button className="axiom" onClick={() => openAxiom(true)} disabled={!pack}>
          <b>{pack?.title ?? "…"}{preset ? ` · ${preset.title}` : scene ? " · custom parameters" : ""}</b>
          {p && <span>{String(p.bays)} bays, {String(p.levels)} levels{strategy ? `, pathway "${strategy.title}"` : ", free"}</span>}
          <em>Change</em>
        </button>
        <div className="legend">
          {Object.entries(ACCESS_LABEL).map(([k, label]) => (
            <span key={k}><i className={"ln" + (k === "none" ? " thin" : "")} style={{ background: ACCESS_COLOR[k] }} />{label}</span>
          ))}
        </div>
      </header>

      {error && !axiomOpen && (
        <div className="banner" role="alert"><span>{error}</span><button onClick={dismiss}>Dismiss</button></div>
      )}

      <aside className="left"><RulePalette /></aside>

      <main className="centre">
        <section className="view3d">
          <ViewBar />
          <div className="canvas"><Viewport3D /><CameraBar /><PreviewBar /></div>
        </section>
        <section className="view2d">
          <GraphBar />
          <div className="canvas"><Graph2D /></div>
        </section>
      </main>

      <RightPanel />
      <footer className="bottom"><Timeline /></footer>
      <AxiomDrawer />
    </div>
  );
}
