import { useEffect, useState } from "react";
import type { Card, Rule, Site, SiteGroup } from "../api";
import { pack as packOf, useStore } from "../store";
import RuleCard from "./RuleCard";
import { SymbolChip } from "./Chips";

const NONE: Rule[] = [];
const GRAMMARS: Record<string, string> = { GA: "Grammar GA: block", GB: "Grammar GB: social condenser" };

function Competes({ ids }: { ids: string[] }) {
  if (ids.length === 0) return <span className="muted">no other rule wants these nodes</span>;
  return <span className="competes" title="Other rules that would rewrite the same nodes: choosing here decides against them">competes with {ids.join(", ")}</span>;
}

function SiteRow({ rule, site }: { rule: Rule; site: Site }) {
  const previewSite = useStore((s) => s.previewSite);
  const setHover = useStore((s) => s.setHover);
  const active = useStore((s) => s.previewOf?.rule === rule.id && s.previewOf?.select === site.key);
  return (
    <button className={"site" + (active ? " active" : "") + (site.decisive ? " decisive" : "")}
      onClick={() => previewSite(rule.id, site.key, site.label)}
      onMouseEnter={() => setHover(site.nodes)} onMouseLeave={() => setHover([])}
      title={site.decisive ? `A decision: ${site.conflicts} other offers want these nodes (${site.conflicts_with.join(", ")})` : "Independent of every other offer"}>
      <span>{site.label}</span>
      <span className="muted">{site.decisive ? "decision" : ""}</span>
    </button>
  );
}

function Group({ rule, group }: { rule: Rule; group: SiteGroup }) {
  const previewSite = useStore((s) => s.previewSite);
  const setHover = useStore((s) => s.setHover);
  const [open, setOpen] = useState(false);
  const active = useStore((s) => s.previewOf?.rule === rule.id && typeof s.previewOf?.select === "object"
    && s.previewOf?.select !== null && !Array.isArray(s.previewOf.select) && s.previewOf.select.group === group.label);
  const all = () => previewSite(rule.id, { group: group.label, params: group.params }, `${group.label}, all ${group.sites.length} sites`);
  return (
    <div className={"sgroup" + (open ? " open" : "")}>
      <div className="sgroup-head">
        <button className="sgroup-name" onClick={() => setOpen(!open)} aria-expanded={open}>
          <span className="caret">{open ? "▾" : "▸"}</span>
          <span>{group.label}</span>
          <span className="muted">{group.sites.length} site{group.sites.length > 1 ? "s" : ""}</span>
        </button>
        <button className={"site all" + (active ? " active" : "")} onClick={all}
          onMouseEnter={() => setHover(group.sites.flatMap((s) => s.nodes))} onMouseLeave={() => setHover([])}>
          {group.sites.length > 1 ? "All" : "Apply"}
        </button>
      </div>
      <div className="sgroup-note"><Competes ids={group.competes_with} /></div>
      {open && <div className="sites">{group.sites.map((s) => <SiteRow key={s.key} rule={rule} site={s} />)}</div>}
    </div>
  );
}

function RuleEntry({ rule, open, toggle }: { rule: Rule; open: boolean; toggle: () => void }) {
  const loadCard = useStore((s) => s.loadCard);
  const [card, setCard] = useState<Card | null>(null);
  const params = rule.groups[0]?.params;
  useEffect(() => {
    if (!open) return;
    let live = true;
    loadCard(rule.id, params && Object.keys(params).length ? params : undefined).then((c) => { if (live) setCard(c); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, rule.id, JSON.stringify(params)]);
  const state = rule.enabled ? "enabled" : "spent";
  return (
    <div className={`rule ${state}` + (open ? " open" : "")}>
      <button className="rule-head" onClick={toggle} aria-expanded={open}>
        <span className="rid">{rule.id}</span>
        <span className="rname">{rule.title}<em>{rule.verb}</em></span>
        {rule.identity && <span className="badge">identity</span>}
        <span className="count">{rule.enabled ? rule.site_count : ""}</span>
      </button>
      {open && (
        <div className="rule-body">
          {card ? <RuleCard card={card} /> : <div className="card loading">drawing the rule…</div>}
          <p>{rule.description}</p>
          {rule.shape?.operation && <div className="ops"><span><b>shape</b> {rule.shape.operation}</span></div>}
          {rule.symbols.length > 0 && <div className="chips">{rule.symbols.map((s) => <SymbolChip key={s} symbol={s} />)}</div>}
          {!rule.enabled && <div className="reason">No site matches in this state.</div>}
          {rule.enabled && <div className="groups">{rule.groups.map((g) => <Group key={g.label} rule={rule} group={g} />)}</div>}
        </div>
      )}
    </div>
  );
}

export default function RulePalette() {
  const scene = useStore((s) => s.scene);
  const pack = useStore(packOf);
  const selected = useStore((s) => s.selected);
  const previewSite = useStore((s) => s.previewSite);
  const [open, setOpen] = useState<string | null>(null);
  const [showAuto, setShowAuto] = useState(false);
  const rules = scene?.rules ?? NONE;
  const auto = pack?.rules.filter((r) => r.auto) ?? [];
  const consequences = scene?.step.consequences ?? [];

  const first = rules.find((r) => r.enabled)?.id ?? null;
  const shown = open && rules.some((r) => r.id === open) ? open : first;
  const here = selected
    ? rules.flatMap((r) => r.groups.flatMap((g) => g.sites.filter((s) => s.nodes.includes(selected)).map((s) => ({ r, g, s }))))
    : [];

  return (
    <div className="palette">
      {selected && (
        <section className="at-selection">
          <h3>At {selected}</h3>
          {here.length === 0
            ? <p className="muted">No rule can be applied at this node in this state.</p>
            : here.map(({ r, g, s }) => (
                <button key={r.id + s.key} className={"site" + (s.decisive ? " decisive" : "")} onClick={() => previewSite(r.id, s.key, s.label)}
                  title={g.label}>
                  <span><b>{r.id}</b> {g.label}</span><span className="muted">{s.label}</span>
                </button>
              ))}
        </section>
      )}
      {Object.entries(GRAMMARS).map(([g, title]) => {
        const mine = rules.filter((r) => r.grammar === g);
        if (mine.length === 0) return null;
        return (
          <section key={g}>
            <h3>{title}</h3>
            {mine.map((r) => <RuleEntry key={r.id} rule={r} open={shown === r.id} toggle={() => setOpen(shown === r.id ? "" : r.id)} />)}
          </section>
        );
      })}
      {auto.length > 0 && (
        <section className="auto">
          <h3><button className="plain" onClick={() => setShowAuto(!showAuto)} aria-expanded={showAuto}>
            {showAuto ? "▾" : "▸"} Consequences ({auto.length} rules)
          </button></h3>
          <p className="muted">Applied wherever they match, after every choice. They are what a shared face gives for free on the shape side.</p>
          {showAuto && auto.map((r) => {
            const n = consequences.filter((c) => c.rule === r.id).length;
            return (
              <div key={r.id} className="auto-rule">
                <span className="rid">{r.id}</span><span className="rname">{r.title}<em>{r.verb}</em></span>
                <span className="count">{n > 0 ? `×${n}` : ""}</span>
              </div>
            );
          })}
        </section>
      )}
    </div>
  );
}
