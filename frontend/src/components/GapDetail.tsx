import { useState } from "react";
import type { Claim, EvidenceItem, Gap } from "../types";
import { GapTypeBadge, ConfidenceBadge } from "./Badges";
import EvidenceChips from "./EvidenceChips";
import { saveGap } from "../api";

function ClaimList({ claims, evidence }: { claims: Claim[]; evidence: Record<string, EvidenceItem> }) {
  if (claims.length === 0) return <p className="text-sm text-slate-400 italic">No verified evidence for this section.</p>;
  return (
    <ul className="space-y-1.5">
      {claims.map((claim, i) => (
        <li key={i} className="text-sm text-slate-700">
          {claim.text}
          <EvidenceChips evidenceIds={claim.evidence_ids} evidence={evidence} />
        </li>
      ))}
    </ul>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1.5">{title}</div>
      {children}
    </div>
  );
}

export default function GapDetail({
  gap,
  evidence,
  scanId,
}: {
  gap: Gap;
  evidence: Record<string, EvidenceItem>;
  scanId: string;
}) {
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState(false);

  return (
    <div>
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold text-slate-900">{gap.category}</h2>
        <ConfidenceBadge level={gap.confidence} />
      </div>
      <div className="mt-1"><GapTypeBadge type={gap.gap_type} /></div>

      <Section title="What exists"><ClaimList claims={gap.what_exists} evidence={evidence} /></Section>
      <Section title="What customers say"><ClaimList claims={gap.what_customers_say} evidence={evidence} /></Section>
      <Section title="What people search"><ClaimList claims={gap.what_people_search} evidence={evidence} /></Section>
      <Section title="What is changing"><ClaimList claims={gap.what_is_changing} evidence={evidence} /></Section>
      <Section title="Why we think this"><ClaimList claims={gap.why_we_think_this} evidence={evidence} /></Section>

      {gap.conflicts.length > 0 && (
        <Section title="⚠ Signals disagree">
          <div className="space-y-2">
            {gap.conflicts.map((c) => (
              <div key={c.rule_id} className="text-sm bg-amber-50 border border-amber-200 rounded-lg p-2.5">
                <div className="font-medium text-amber-800">{c.label}</div>
                <div className="text-amber-700 mt-0.5">{c.explanation}</div>
                {c.validate_next.length > 0 && (
                  <div className="text-amber-600 mt-1 text-xs">Validate: {c.validate_next.join("; ")}</div>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      <Section title="Confidence & what's missing">
        <ul className="text-sm text-slate-600 space-y-1">
          {gap.confidence_reasons.map((r, i) => (
            <li key={i}>· {r}</li>
          ))}
        </ul>
        {gap.missing_information.length > 0 && (
          <ul className="text-sm text-slate-400 mt-1.5 space-y-1">
            {gap.missing_information.map((m, i) => (
              <li key={i}>— {m}</li>
            ))}
          </ul>
        )}
      </Section>

      {gap.validate_next.length > 0 && (
        <Section title="Validate next">
          <ul className="text-sm text-slate-700 space-y-1 list-disc list-inside">
            {gap.validate_next.map((v, i) => (
              <li key={i}>{v}</li>
            ))}
          </ul>
        </Section>
      )}

      {gap.dropped_claim_count > 0 && (
        <p className="mt-4 text-xs text-slate-400 italic">
          {gap.dropped_claim_count} claim(s) were removed by the verifier as unverifiable.
        </p>
      )}

      <div className="mt-5 border-t border-slate-200 pt-3">
        {saved ? (
          <div className="text-sm text-emerald-600">Saved.</div>
        ) : (
          <div className="flex gap-2">
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Optional note..."
              className="flex-1 text-sm border border-slate-300 rounded-lg px-2 py-1.5"
            />
            <button
              onClick={async () => {
                await saveGap(scanId, gap.gap_id, note);
                setSaved(true);
              }}
              className="text-sm px-3 py-1.5 rounded-lg bg-slate-800 text-white hover:bg-slate-700"
            >
              Save hypothesis
            </button>
          </div>
        )}
      </div>

      <p className="mt-4 text-[11px] text-slate-400 leading-relaxed">
        This is an evidence-backed opportunity hypothesis, not a prediction of business success. Validate it
        in person before acting on it.
      </p>
    </div>
  );
}
