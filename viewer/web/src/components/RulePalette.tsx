import { useState } from "react";
import type { Rule, Site } from "../api";
import { useStore } from "../store";
import { SymbolChip } from "./Chips";

const NONE: Rule[] = [];
const GRAMMARS: Record<string, string> = { GA: "Grammar GA: block", GB: "Grammar GB: social condenser" };

function SiteRow({ rule, site }: { rule: Rule; site: Site }) {
  const previewSite = useStore((s) => s.previewSite);
  const setHover = useStore((s) => s.setHover);
  const active = useStore((s) => s.previewOf?.rule === rule.id && s.previewOf?.site === site.key);
  return (
    <button className={"site" + (active ? " active" : "")} onClick={() => previewSite(rule.id, site.key)}
      onMouseEnter={() => setHover(site.nodes)} onMouseLeave={() => setHover([])}>
      <span>{site.label}</span>
      <span className="muted">{site.nodes.length > 0 ? `${site.nodes.length} node${site.nodes.length > 1 ? "s" : ""}` : "new"}</span>
    </button>
  );
}

function RuleCard({ rule, open, toggle }: { rule: Rule; open: boolean; toggle: () => void }) {
  const previewSite = useStore((s) => s.previewSite);
  const setHover = useStore((s) => s.setHover);
  const allActive = useStore((s) => s.previewOf?.rule === rule.id && s.previewOf?.site === "*");
  const state = rule.enabled ? "enabled" : rule.sites.length > 0 ? "held" : "spent";
  return (
    <div className={`rule ${state}` + (open ? " open" : "")}>
      <button className="rule-head" onClick={toggle} aria-expanded={open}>
        <span className="rid">{rule.id}</span>
        <span className="rname">{rule.name}</span>
        {rule.identity && <span className="badge">identity</span>}
        <span className="count">{rule.enabled ? rule.sites.length : state === "held" ? "held" : ""}</span>
      </button>
      {open && (
        <div className="rule-body">
          <div className="ops">
            <span><b>graph</b> {rule.operation}</span>
            <span><b>shape</b> {rule.shape_operation}</span>
          </div>
          <p>{rule.description}</p>
          {rule.symbols.length > 0 && <div className="chips">{rule.symbols.map((s) => <SymbolChip key={s} symbol={s} />)}</div>}
          {!rule.enabled && <div className="reason">{rule.reason === "no site matches" ? "No site matches in this state." : `Held back: ${rule.reason}.`}</div>}
          {rule.enabled && (
            <div className="sites">
              {rule.sites.length > 1 && (
                <button className={"site all" + (allActive ? " active" : "")} onClick={() => previewSite(rule.id, "*")}
                  onMouseEnter={() => setHover(rule.sites.flatMap((s) => s.nodes))} onMouseLeave={() => setHover([])}>
                  <span>All {rule.sites.length} sites</span><span className="muted">one step</span>
                </button>
              )}
              {rule.sites.map((s) => <SiteRow key={s.key} rule={rule} site={s} />)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function RulePalette() {
  const scene = useStore((s) => s.scene);
  const rules = scene?.rules ?? NONE;
  const selected = useStore((s) => s.selected);
  const previewSite = useStore((s) => s.previewSite);
  const [open, setOpen] = useState<string | null>(null);

  // by default the first rule that can be applied is the one that is open
  const first = rules.find((r) => r.enabled)?.id ?? null;
  const shown = open && rules.some((r) => r.id === open) ? open : first;
  const here = selected
    ? rules.filter((r) => r.enabled).flatMap((r) => r.sites.filter((s) => s.nodes.includes(selected)).map((s) => ({ r, s })))
    : [];

  return (
    <div className="palette">
      {selected && (
        <section className="at-selection">
          <h3>At {selected}</h3>
          {here.length === 0
            ? <p className="muted">No rule can be applied at this node in this state.</p>
            : here.map(({ r, s }) => (
                <button key={r.id + s.key} className="site" onClick={() => previewSite(r.id, s.key)}>
                  <span><b>{r.id}</b> {r.name}</span><span className="muted">{s.label}</span>
                </button>
              ))}
        </section>
      )}
      {Object.entries(GRAMMARS).map(([g, title]) => (
        <section key={g}>
          <h3>{title}</h3>
          {rules.filter((r) => r.grammar === g).map((r) => (
            <RuleCard key={r.id} rule={r} open={shown === r.id} toggle={() => setOpen(shown === r.id ? "" : r.id)} />
          ))}
        </section>
      ))}
    </div>
  );
}
