import { useEffect, useMemo } from "react";
import { Canvas, useThree, type ThreeEvent } from "@react-three/fiber";
import { Html, Line, OrbitControls, OrthographicCamera, PerspectiveCamera } from "@react-three/drei";
import * as THREE from "three";
import type { Cell, GraphEdge, GraphNode, Scene } from "../api";
import { useShown, useStore, type ViewOptions } from "../store";
import { useMarks, type Mark } from "../marks";
import { ACCESS_COLOR, HILITE, typeColor } from "../theme";
import { siteExtent } from "../extent";

type Box = { min: THREE.Vector3; max: THREE.Vector3 };

function siteBox(scene: Scene): Box {
  const e = siteExtent(scene);
  return { min: new THREE.Vector3(...e.min), max: new THREE.Vector3(...e.max) };
}

function CameraRig({ box, fit, ortho }: { box: Box; fit: number; ortho: boolean }) {
  const camera = useThree((s) => s.camera);
  const controls = useThree((s) => s.controls) as unknown as { target: THREE.Vector3; update: () => void } | null;
  const size = useThree((s) => s.size);
  useEffect(() => {
    if (!controls) return;
    const c = box.min.clone().add(box.max).multiplyScalar(0.5);
    const r = box.min.distanceTo(box.max) / 2;
    const dir = new THREE.Vector3(-0.5, -1, 0.6).normalize();
    camera.up.set(0, 0, 1);
    camera.position.copy(c).addScaledVector(dir, r * 2.6);
    camera.near = 0.1;
    camera.far = r * 30;
    if (camera instanceof THREE.OrthographicCamera) camera.zoom = Math.min(size.width, size.height * 1.9) / (r * 2.05);
    camera.updateProjectionMatrix();
    controls.target.copy(c);
    controls.update();
    // refit on request and when the projection changes, not when the viewport is resized
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fit, ortho, controls, camera]);
  return null;
}

function CellMesh({ cell, mark, view, planes, ghost }: {
  cell: Cell; mark?: Mark; view: ViewOptions; planes: THREE.Plane[]; ghost?: boolean;
}) {
  const select = useStore((s) => s.select);
  const [solid, outline] = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(cell.positions, 3));
    g.setIndex(cell.indices);
    g.computeVertexNormals();
    const l = new THREE.BufferGeometry();
    l.setAttribute("position", new THREE.Float32BufferAttribute(cell.lines, 3));
    return [g, l];
  }, [cell]);
  useEffect(() => () => { solid.dispose(); outline.dispose(); }, [solid, outline]);

  const s = 1 - view.gap;
  const c = cell.centroid;
  const nonterminal = cell.category === "Mass";
  const color = mark ? HILITE[mark] : typeColor(cell.type);
  const opacity = ghost ? 0.12 : mark ? Math.min(0.85, view.opacity + 0.4) : nonterminal ? view.opacity * 0.75 : view.opacity;

  const onClick = (e: ThreeEvent<MouseEvent>) => {
    if (ghost || e.delta > 4) return;
    // a graph node inside or behind this cell takes the click
    if (e.intersections.some((i) => i.object.userData.node)) return;
    e.stopPropagation();
    select(cell.id);
  };

  return (
    <group position={[c[0] * (1 - s), c[1] * (1 - s), c[2] * (1 - s)]} scale={s}>
      <mesh geometry={solid} onClick={onClick} renderOrder={mark ? 2 : 1}>
        <meshStandardMaterial color={color} transparent opacity={opacity} depthWrite={false}
          side={THREE.DoubleSide} clippingPlanes={planes} roughness={0.9} metalness={0} />
      </mesh>
      <lineSegments geometry={outline} raycast={() => null}>
        <lineBasicMaterial color={mark ? HILITE[mark] : "#2b2a27"} transparent
          opacity={ghost ? 0.9 : mark ? 1 : 0.45} clippingPlanes={planes} />
      </lineSegments>
    </group>
  );
}

function NodeMark({ node, mark, lift }: { node: GraphNode; mark?: Mark; lift: number }) {
  const select = useStore((s) => s.select);
  const r = node.type === "dwelling" || node.type === "hall" ? 0.5 : 0.36;
  const onClick = (e: ThreeEvent<MouseEvent>) => {
    if (e.delta > 4) return;
    e.stopPropagation();
    select(node.id);
  };
  return (
    <group position={[node.pos[0], node.pos[1], node.pos[2] + lift]}>
      <mesh onClick={onClick} userData={{ node: node.id }} renderOrder={3}>
        {node.terminal ? <sphereGeometry args={[r, 18, 12]} /> : <boxGeometry args={[r * 1.7, r * 1.7, r * 1.7]} />}
        <meshStandardMaterial color={typeColor(node.type)} roughness={0.6} />
      </mesh>
      {mark && (
        <mesh raycast={() => null} renderOrder={4}>
          <sphereGeometry args={[r * 1.75, 16, 10]} />
          <meshBasicMaterial color={HILITE[mark]} wireframe transparent opacity={0.9} />
        </mesh>
      )}
      {(mark === "selected" || mark === "site") && (
        <Html position={[0, 0, r * 2.2]} center className="tag3d" zIndexRange={[20, 10]}>{node.id}</Html>
      )}
    </group>
  );
}

function EdgeLines({ edges, at, lift, color, width, dashed }: {
  edges: GraphEdge[]; at: Map<string, GraphNode>; lift: number; color: string; width: number; dashed?: boolean;
}) {
  const points = useMemo(() => {
    const out: [number, number, number][] = [];
    for (const e of edges) {
      const a = at.get(e.a), b = at.get(e.b);
      if (a && b) out.push([a.pos[0], a.pos[1], a.pos[2] + lift], [b.pos[0], b.pos[1], b.pos[2] + lift]);
    }
    return out;
  }, [edges, at, lift]);
  if (points.length === 0) return null;
  return <Line points={points} segments color={color} lineWidth={width} dashed={dashed} dashSize={0.5} gapSize={0.35}
    transparent opacity={width < 2 ? 0.7 : 1} raycast={() => null} />;
}

function GraphOverlay({ scene, marks, view }: { scene: Scene; marks: Map<string, Mark>; view: ViewOptions }) {
  const nodes = useMemo(() => scene.graph.nodes.filter((n) => !view.accessOnly || n.occupiable), [scene, view.accessOnly]);
  const at = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
  const edges = useMemo(() => scene.graph.edges.filter((e) => !view.accessOnly || e.in_access_graph), [scene, view.accessOnly]);
  const key = (e: GraphEdge) => (e.a < e.b ? `${e.a}|${e.b}` : `${e.b}|${e.a}`);
  const fresh = useMemo(() => new Set(scene.event.edges_added.map(key)), [scene]);
  const by = (access: string) => edges.filter((e) => e.access === access && !fresh.has(key(e)));
  return (
    <group>
      <EdgeLines edges={by("none")} at={at} lift={view.lift} color={ACCESS_COLOR.none} width={1.2} />
      <EdgeLines edges={by("open")} at={at} lift={view.lift} color={ACCESS_COLOR.open} width={3.2} />
      <EdgeLines edges={by("door")} at={at} lift={view.lift} color={ACCESS_COLOR.door} width={3.2} />
      <EdgeLines edges={by("stair")} at={at} lift={view.lift} color={ACCESS_COLOR.stair} width={3.6} />
      <EdgeLines edges={edges.filter((e) => fresh.has(key(e)))} at={at} lift={view.lift} color={HILITE.added} width={4} />
      {nodes.map((n) => <NodeMark key={n.id} node={n} mark={marks.get(n.id)} lift={view.lift} />)}
    </group>
  );
}

export default function Viewport3D() {
  const scene = useShown();
  const head = useStore((s) => s.scene);
  const preview = useStore((s) => s.preview);
  const view = useStore((s) => s.view);
  const fit = useStore((s) => s.fit);
  const select = useStore((s) => s.select);
  const marks = useMarks();

  const box = useMemo(() => (scene ? siteBox(scene) : null), [scene?.session, scene?.parameters]);  // eslint-disable-line
  const planes = useMemo(() => {
    if (!box || view.cut >= 1) return [];
    const x = box.min.x + (box.max.x - box.min.x) * view.cut;
    return [new THREE.Plane(new THREE.Vector3(-1, 0, 0), x)];
  }, [box, view.cut]);

  // in a preview, what the production removes stays visible as a ghost of what is there now
  const ghosts = useMemo(() => {
    if (!preview || !head) return [];
    const gone = new Set(preview.event.nodes_removed);
    return head.cells.filter((c) => gone.has(c.id));
  }, [preview, head]);

  if (!scene || !box) return <div className="empty">Waiting for the server…</div>;
  const span = Math.max(box.max.x - box.min.x, box.max.y - box.min.y);

  return (
    <Canvas gl={{ antialias: true, localClippingEnabled: true }} dpr={[1, 2]} onPointerMissed={(e) => { if (e.type === "click") select(null); }}>
      <color attach="background" args={["#f4f2ec"]} />
      {view.ortho
        ? <OrthographicCamera makeDefault position={[-60, -120, 80]} zoom={8} near={0.1} far={4000} />
        : <PerspectiveCamera makeDefault position={[-60, -120, 80]} fov={32} near={0.1} far={4000} />}
      <OrbitControls makeDefault enableDamping dampingFactor={0.12} />
      <CameraRig box={box} fit={fit} ortho={view.ortho} />
      <ambientLight intensity={1.5} />
      <directionalLight position={[-40, -80, 120]} intensity={1.6} />
      <directionalLight position={[60, 40, 30]} intensity={0.5} />

      <gridHelper args={[Math.ceil(span / 10) * 20, Math.ceil(span / 10) * 4, "#cfcabd", "#e2ded3"]}
        rotation={[Math.PI / 2, 0, 0]} position={[(box.min.x + box.max.x) / 2, (box.min.y + box.max.y) / 2, -0.02]} />

      {view.cells && scene.cells.map((c) => <CellMesh key={c.id} cell={c} mark={marks.get(c.id)} view={view} planes={planes} />)}
      {ghosts.map((c) => <CellMesh key={"ghost-" + c.id} cell={c} mark="removed" view={view} planes={planes} ghost />)}
      {view.graph && <GraphOverlay scene={scene} marks={marks} view={view} />}
    </Canvas>
  );
}
