import type { Scene } from "./api";

// The extent of the site, from the parameters. It does not move as the derivation grows, so the
// views are framed once and a production is seen as a change in place.
export function siteExtent(scene: Scene): { min: [number, number, number]; max: [number, number, number] } {
  const d = scene.dimensions as Record<string, number> & { cb_origin: [number, number] };
  const p = scene.parameters as Record<string, number>;
  return {
    min: [Math.min(0, d.cb_origin[0]), Math.min(0, d.cb_origin[1]), 0],
    max: [p.bays * d.bay, d.depth, d.pilotis + (p.levels + 1) * d.storey],
  };
}
