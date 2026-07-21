// ============================================================================
// PREDAIOT — Ontology Terminology Resolver (Phase 5)
// The frontend NEVER decides what the facility is; it renders what the backend
// understood. This module carries ZERO industrial vocabulary. It humanizes any
// ontology id generically (works for a 2035 industry with no code change) and
// prefers a backend-provided label when the profile carries one.
//
// GOLDEN RULE: no `if industry`, no hardcoded "Battery"/"Kiln"/"EAF". Adding an
// industry is a knowledge-pack change on the backend — this file is untouched.
// ============================================================================

const titlecase = (s) =>
  String(s == null ? '' : s).replace(/_/g, ' ').replace(/\s+/g, ' ').trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());

// id (or {id,label}) → human label. A backend-provided `label` always wins.
export function label(idOrNode) {
  if (idOrNode && typeof idOrNode === 'object') return idOrNode.label || titlecase(idOrNode.id);
  return titlecase(idOrNode) || '—';
}

// The human name of the facility (facility hypothesis, else recognized equipment).
export function facilityName(profile) {
  const ft = profile?.facility_type?.value;
  if (ft && ft !== 'Unknown') return ft;
  const eq = profile?.equipment?.[0]?.identity?.value;
  if (eq && eq !== 'Unknown' && eq !== 'Generic') return titlecase(eq);
  return 'Industrial Facility';
}

// The economic SUBJECT for generated sentences ("The Electric Arc Furnace …").
export function facilitySubject(profile) {
  const eq = profile?.equipment?.[0]?.identity?.value;
  if (eq && eq !== 'Unknown' && eq !== 'Generic') return `The ${titlecase(eq)}`;
  const ft = profile?.facility_type?.value;
  if (ft && ft !== 'Unknown') return `The ${ft}`;
  return 'The facility';
}

// The recognized capability labels (for headers / lenses), backend-driven.
export function capabilityLabels(profile) {
  return (profile?.equipment?.[0]?.capabilities || []).map((c) => titlecase(c.value));
}

// Confidence (0..1) of the facility hypothesis, for the UI to show honestly.
export function facilityConfidence(profile) {
  return profile?.facility_type?.confidence ?? null;
}

// Does the recognized facility have a given capability? Lets the UI show a
// capability-specific instrument (e.g. State of Charge) ONLY when the ontology
// says the facility has it — never guessed from asset type.
export function hasCapability(profile, capId) {
  return (profile?.equipment || []).some(
    (e) => (e.capabilities || []).some((c) => c.value === capId));
}

export { titlecase };
