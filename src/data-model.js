import { METHODENSAMMLUNG_DATA } from "./generated/methodensammlung-data.js?v=20260324b";

/**
 * @typedef {Object} Method
 * @property {string} method_id
 * @property {string} name_de
 * @property {string | null} short_description
 * @property {string | null} full_description
 * @property {number | null} duration_min
 * @property {number | null} duration_max
 * @property {string | null} materials
 * @property {string | null} facilitator_notes
 * @property {string | null} safeguarding_flag
 */

/**
 * @typedef {Object} MethodVariant
 * @property {string} variant_id
 * @property {string} method_id
 * @property {string} variant_name
 * @property {string | null} phase
 * @property {string | null} use_case
 * @property {string | null} active_session_prompt
 * @property {string | null} facilitator_tip
 * @property {string | null} risk_alert
 */

/**
 * @typedef {Object} SessionBlockInstance
 * @property {string} id
 * @property {"method" | "variant"} sourceType
 * @property {string} sourceId
 * @property {string} blockRefId
 * @property {number | null} manualDuration
 * @property {string | null} customNote
 */

/**
 * @typedef {Object} SessionDraft
 * @property {string} id
 * @property {string} name
 * @property {SessionBlockInstance[]} blocks
 * @property {number} updatedAt
 */

const sheets = METHODENSAMMLUNG_DATA.sheets;

const methodById = new Map(sheets.methods.map((item) => [item.method_id, item]));
const variantById = new Map(sheets.methodVariants.map((item) => [item.variant_id, item]));
const vectorById = new Map(sheets.vectors.map((item) => [item.vector_id, item]));
const collectionById = new Map(sheets.collections.map((item) => [item.collection_id, item]));
const blockById = new Map(sheets.composerBlocksReference.map((item) => [item.block_ref_id, item]));

const tagsByMethodId = groupBy(sheets.methodTags, "method_id");
const variantsByMethodId = groupBy(sheets.methodVariants, "method_id");
const vectorMapByMethodId = groupBy(sheets.methodVectorMap, "method_id");
const collectionItemsByCollectionId = groupBy(sheets.collectionItems, "collection_id");

const collectionsBySourceId = new Map();
for (const item of sheets.collectionItems) {
  const existing = collectionsBySourceId.get(item.method_id_or_variant_id) ?? [];
  existing.push(item);
  collectionsBySourceId.set(item.method_id_or_variant_id, existing);
}

function groupBy(items, key) {
  const grouped = new Map();
  for (const item of items) {
    const bucket = grouped.get(item[key]) ?? [];
    bucket.push(item);
    grouped.set(item[key], bucket);
  }
  return grouped;
}

function normalizeText(value) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

function parseBodyParagraphs(value) {
  if (!value) {
    return [];
  }
  return String(value)
    .split(/\n+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatDurationRange(min, max) {
  if (!min && !max) {
    return null;
  }
  if (min && max && min !== max) {
    return `${min}–${max} Min.`;
  }
  return `${min ?? max} Min.`;
}

function formatMethodDuration(method) {
  return formatDurationRange(method.duration_min, method.duration_max);
}

function booleanLabel(value) {
  return value ? "Ja" : "Nein";
}

function iconForHint(hint) {
  const normalized = normalizeText(hint);
  if (normalized.includes("beweg")) return "MV";
  if (normalized.includes("herz")) return "HF";
  if (normalized.includes("karte")) return "KT";
  if (normalized.includes("fokus")) return "FK";
  if (normalized.includes("reflex")) return "RF";
  return "PS";
}

function buildMethodDecoration(seed) {
  const palette = [
    ["rgba(255,177,194,0.24)", "rgba(124,214,205,0.18)"],
    ["rgba(124,214,205,0.22)", "rgba(232,197,0,0.14)"],
    ["rgba(255,76,135,0.2)", "rgba(232,197,0,0.12)"],
    ["rgba(124,214,205,0.16)", "rgba(255,255,255,0.08)"],
  ];
  const bucket = palette[Math.abs(hashCode(seed)) % palette.length];
  return `background:
    radial-gradient(circle at top left, ${bucket[0]}, transparent 42%),
    linear-gradient(135deg, ${bucket[1]}, rgba(19,19,19,0.92));`;
}

function hashCode(value) {
  let hash = 0;
  for (const char of String(value)) {
    hash = (hash << 5) - hash + char.charCodeAt(0);
    hash |= 0;
  }
  return hash;
}

function getMethodTags(methodId) {
  return tagsByMethodId.get(methodId) ?? [];
}

function getVectorsForMethod(methodId) {
  return (vectorMapByMethodId.get(methodId) ?? [])
    .map((item) => vectorById.get(item.vector_id))
    .filter(Boolean);
}

function getCollectionsForSource(sourceId) {
  return (collectionsBySourceId.get(sourceId) ?? [])
    .map((item) => collectionById.get(item.collection_id))
    .filter(Boolean);
}

function getVariantsForMethod(methodId) {
  return variantsByMethodId.get(methodId) ?? [];
}

function uniqueValues(values) {
  return Array.from(new Set(values.filter(Boolean)));
}

function buildSearchBlob(entity) {
  if (entity.type === "variant") {
    const method = methodById.get(entity.method_id);
    return normalizeText(
      [
        entity.variant_name,
        entity.variant_label,
        entity.phase,
        entity.use_case,
        entity.instruction_short,
        entity.composer_card_summary,
        entity.active_session_prompt,
        method?.name_de,
        method?.short_description,
      ].join(" | "),
    );
  }
  const tags = getMethodTags(entity.method_id).map((item) => item.tag_value);
  const vectors = getVectorsForMethod(entity.method_id).map((item) => item.vector_name_de);
  return normalizeText(
    [
      entity.name_de,
      entity.short_description,
      entity.full_description,
      entity.primary_purpose,
      entity.group_form,
      entity.materials,
      entity.facilitator_notes,
      entity.safeguarding_flag,
      tags.join(" "),
      vectors.join(" "),
    ].join(" | "),
  );
}

const searchIndex = [
  ...sheets.methods.map((item) => ({
    type: "method",
    id: item.method_id,
    weight: 1,
    blob: buildSearchBlob(item),
    titleBlob: normalizeText(item.name_de),
    source: item,
  })),
  ...sheets.methodVariants.map((item) => ({
    type: "variant",
    id: item.variant_id,
    weight: 1.12,
    blob: buildSearchBlob(item),
    titleBlob: normalizeText([item.variant_name, item.variant_label].filter(Boolean).join(" ")),
    source: item,
  })),
];

const SEARCH_LEXICON = {
  unruhig: ["fokus", "achtsamkeit", "konzentration", "beruhigen"],
  laut: ["beruhigen", "fokus", "achtsamkeit"],
  muede: ["aktivieren", "bewegung", "energizer", "wach"],
  mude: ["aktivieren", "bewegung", "energizer", "wach"],
  energielos: ["aktivieren", "bewegung", "warm-up"],
  kennenlernen: ["ankommen", "warm-up", "gemeinschaft"],
  einstieg: ["ankommen", "warm-up", "starten"],
  start: ["ankommen", "warm-up", "starten"],
  konflikt: ["vertrauen", "beziehungen", "gefuhle", "kooperation"],
  streit: ["vertrauen", "beziehungen", "gefuhle", "kooperation"],
  reflexion: ["reflektieren", "feedback", "abschluss"],
  feedback: ["reflektieren", "abschluss"],
  abschluss: ["reflektieren", "abschluss", "runterfahren"],
  konzentration: ["fokus", "achtsamkeit", "wahrnehmung"],
  ruhe: ["beruhigen", "fokus", "achtsamkeit"],
  auflockern: ["aktivieren", "bewegung", "energizer"],
  bewegen: ["bewegung", "aktivieren"],
  stärken: ["staerken", "ressourcen", "selbstvertrauen"],
  stärkenarbeit: ["staerken", "ressourcen", "selbstvertrauen"],
};

function expandSearchTerms(query) {
  const baseTokens = normalizeText(query).split(/\s+/).filter(Boolean);
  const expandedTokens = [];
  for (const token of baseTokens) {
    const related = SEARCH_LEXICON[token] ?? [];
    for (const item of related) {
      expandedTokens.push(item);
    }
  }
  return {
    baseTokens,
    expandedTokens: Array.from(new Set(expandedTokens)),
  };
}

function searchEntities(query, limit = 18) {
  const trimmed = normalizeText(query).trim();
  if (!trimmed) {
    return [];
  }
  const { baseTokens, expandedTokens } = expandSearchTerms(query);
  return searchIndex
    .map((entry) => {
      let score = 0;
      for (const token of baseTokens) {
        if (entry.blob.includes(token)) {
          score += token.length * entry.weight * 1.2;
        }
        if (entry.titleBlob.includes(token)) {
          score += token.length * entry.weight * 2.2;
        }
      }
      for (const token of expandedTokens) {
        if (entry.blob.includes(token)) {
          score += token.length * entry.weight * 0.68;
        }
      }
      if (entry.blob.includes(trimmed)) {
        score += 12 * entry.weight;
      }
      if (entry.titleBlob.includes(trimmed)) {
        score += 18 * entry.weight;
      }
      return score > 0 ? { ...entry, score } : null;
    })
    .filter(Boolean)
    .sort((left, right) => right.score - left.score)
    .slice(0, limit);
}

function scoreIntent(intent, query) {
  const queryBlob = normalizeText(query);
  const { baseTokens, expandedTokens } = expandSearchTerms(query);
  const intentBlob = normalizeText(
    [
      intent.intent_label_de,
      intent.user_need_statement,
      intent.description,
      intent.class_state,
      intent.energy_target,
      intent.ranking_notes,
    ].join(" | "),
  );
  let score = intentBlob.includes(queryBlob) ? 24 : 0;
  for (const token of baseTokens) {
    if (intentBlob.includes(token)) {
      score += token.length * 2.4;
    }
  }
  for (const token of expandedTokens) {
    if (intentBlob.includes(token)) {
      score += token.length * 1.1;
    }
  }
  return score;
}

function hydrateSource(sourceType, sourceId) {
  if (sourceType === "variant") {
    const variant = variantById.get(sourceId);
    if (!variant) {
      return null;
    }
    const method = methodById.get(variant.method_id);
    return buildHydratedCard({
      method,
      variant,
      sourceType,
      sourceId,
    });
  }
  const method = methodById.get(sourceId);
  if (!method) {
    return null;
  }
  return buildHydratedCard({
    method,
    variant: null,
    sourceType,
    sourceId,
  });
}

function buildHydratedCard({ method, variant, sourceType, sourceId, blockRef }) {
  if (!method) {
    return null;
  }
  const vectors = getVectorsForMethod(method.method_id);
  const tags = getMethodTags(method.method_id);
  const collections = getCollectionsForSource(variant?.variant_id ?? method.method_id);
  const duration = variant?.recommended_duration ?? formatMethodDuration(method);
  const notes = [variant?.facilitator_tip, method.facilitator_notes].filter(Boolean);
  const risks = [variant?.risk_alert, method.safeguarding_flag].filter(Boolean);
  return {
    sourceType,
    sourceId,
    blockRefId: blockRef?.block_ref_id ?? null,
    method,
    variant,
    title: variant?.variant_name ?? method.name_de,
    subtitle: variant?.variant_label ?? method.short_description,
    summary:
      variant?.composer_card_summary ??
      variant?.instruction_short ??
      method.short_description ??
      method.full_description,
    prompt:
      variant?.active_session_prompt ??
      variant?.instruction_short ??
      method.short_description ??
      method.full_description,
    duration,
    icon: iconForHint(blockRef?.icon_hint ?? variant?.energy_role ?? method.primary_purpose),
    phase: blockRef?.phase ?? variant?.phase ?? derivePrimaryTag(method.method_id, "phase"),
    energy: blockRef?.energy_role ?? variant?.energy_role ?? method.energy_level,
    energyRole: blockRef?.energy_role ?? variant?.energy_role ?? null,
    energyLevel: method.energy_level ?? null,
    energyLevelSource: method.energy_level_source ?? null,
    groupSetting: blockRef?.group_setting ?? variant?.social_setting ?? method.group_form,
    materials: variant?.materials_override ?? blockRef?.materials_hint ?? method.materials,
    vectors,
    tags,
    collections,
    notes,
    risks,
    descriptionParagraphs: parseBodyParagraphs(method.full_description || method.short_description),
    durationLabel: typeof duration === "number" ? `${duration} Min.` : duration,
    decoration: buildMethodDecoration(sourceId),
  };
}

function derivePrimaryTag(methodId, tagType) {
  return getMethodTags(methodId).find((item) => item.tag_type === tagType)?.tag_value ?? null;
}

const FINDER_TIME_BUCKETS = [
  { value: "short", label: "<=10 Min." },
  { value: "medium", label: "11-20 Min." },
  { value: "long", label: ">20 Min." },
  { value: "open", label: "Dauer offen" },
];

const FINDER_MATERIAL_BUCKETS = [
  { value: "none", label: "Kein Material" },
  { value: "light", label: "Wenig Material" },
  { value: "more", label: "Mehr Material" },
  { value: "open", label: "Material offen" },
];

function getMethodTagsOfType(methodId, tagType) {
  return getMethodTags(methodId)
    .filter((item) => item.tag_type === tagType && item.tag_value)
    .map((item) => item.tag_value);
}

function methodHasTagValue(methodId, tagType, value) {
  const expected = normalizeText(value);
  return getMethodTagsOfType(methodId, tagType).some((tagValue) => normalizeText(tagValue) === expected);
}

function buildFinderTagOptions(tagType) {
  const counts = new Map();
  for (const method of sheets.methods) {
    const values = new Set(getMethodTagsOfType(method.method_id, tagType));
    for (const value of values) {
      counts.set(value, (counts.get(value) ?? 0) + 1);
    }
  }
  return Array.from(counts.entries())
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0], "de"))
    .map(([value, count]) => ({ value, count }));
}

function deriveFinderTimeBucket(method) {
  const min = method.duration_min;
  const max = method.duration_max;
  if (!min && !max) {
    return "open";
  }
  const effectiveMax = max ?? min ?? null;
  if (effectiveMax === null) {
    return "open";
  }
  if (effectiveMax <= 10) {
    return "short";
  }
  if (effectiveMax <= 20) {
    return "medium";
  }
  return "long";
}

function splitMaterialTokens(materials) {
  return String(materials ?? "")
    .split(/[\n,;/]+/g)
    .map((item) => item.replace(/\s+/g, " ").trim())
    .filter(Boolean);
}

function deriveFinderMaterialBucket(method) {
  if (method.materials == null) {
    return "open";
  }
  const normalized = normalizeText(method.materials).trim();
  if (!normalized) {
    return "none";
  }
  if (normalized.includes("kein material") || normalized.includes("ohne material") || normalized === "kein") {
    return "none";
  }
  const tokenCount = splitMaterialTokens(method.materials).length;
  if (!tokenCount) {
    return "none";
  }
  if (tokenCount <= 2) {
    return "light";
  }
  return "more";
}

function getFinderFilterOptions() {
  const groupCounts = new Map();
  const timeCounts = new Map(FINDER_TIME_BUCKETS.map((item) => [item.value, 0]));
  const materialCounts = new Map(FINDER_MATERIAL_BUCKETS.map((item) => [item.value, 0]));

  for (const method of sheets.methods) {
    if (method.group_form) {
      groupCounts.set(method.group_form, (groupCounts.get(method.group_form) ?? 0) + 1);
    }
    timeCounts.set(deriveFinderTimeBucket(method), (timeCounts.get(deriveFinderTimeBucket(method)) ?? 0) + 1);
    materialCounts.set(deriveFinderMaterialBucket(method), (materialCounts.get(deriveFinderMaterialBucket(method)) ?? 0) + 1);
  }

  return {
    goals: buildFinderTagOptions("use_case"),
    phases: buildFinderTagOptions("phase"),
    groups: Array.from(groupCounts.entries())
      .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0], "de"))
      .map(([value, count]) => ({ value, count })),
    timeBuckets: FINDER_TIME_BUCKETS.map((item) => ({ ...item, count: timeCounts.get(item.value) ?? 0 })),
    materialBuckets: FINDER_MATERIAL_BUCKETS.map((item) => ({ ...item, count: materialCounts.get(item.value) ?? 0 })),
  };
}

function addFinderScore(scoreMap, sourceType, sourceId, score) {
  const key = `${sourceType}:${sourceId}`;
  const current = scoreMap.get(key);
  scoreMap.set(key, {
    sourceType,
    sourceId,
    score: (current?.score ?? 0) + score,
  });
}

function addFinderSearchResults(scoreMap, query, startingScore, limit = 24) {
  searchEntities(query, limit).forEach((entry, index) => {
    addFinderScore(scoreMap, entry.type, entry.id, Math.max(8, startingScore - index * 2));
  });
}

function addScopedFinderSearchResults(scoreMap, query, startingScore, limit = 24) {
  const allowedKeys = new Set(scoreMap.keys());
  searchEntities(query, limit).forEach((entry, index) => {
    const key = `${entry.type}:${entry.id}`;
    if (!allowedKeys.has(key)) {
      return;
    }
    addFinderScore(scoreMap, entry.type, entry.id, Math.max(8, startingScore - index * 2));
  });
}

function buildIntentContextQuery(intent) {
  return [
    intent.intent_label_de,
    intent.user_need_statement,
    intent.class_state,
    intent.energy_target,
    intent.ranking_notes,
  ]
    .filter(Boolean)
    .join(" ");
}

function getDirectGoalMatches(goal) {
  if (!goal) {
    return [];
  }
  return sheets.methods
    .filter((method) => methodHasTagValue(method.method_id, "use_case", goal))
    .map((method) => method.method_id);
}

function matchesFinderPhase(item, phase) {
  if (!phase) {
    return true;
  }
  return normalizeText(item.phase) === normalizeText(phase) || methodHasTagValue(item.method.method_id, "phase", phase);
}

function matchesFinderGroup(item, group) {
  if (!group) {
    return true;
  }
  return normalizeText(item.method.group_form) === normalizeText(group);
}

function finderSoftPreferenceScore(bucket, selectedBucket) {
  if (!selectedBucket) {
    return 0;
  }
  if (bucket === selectedBucket) {
    return 240;
  }
  if (bucket === "open") {
    return 120;
  }
  return 0;
}

function getFinderIntents() {
  return sheets.finderIntents.map((intent) => ({
    ...intent,
    recommendations: (intent.recommended_method_ids_or_variant_ids ?? [])
      .map((id) => hydrateSource(id.includes("_v_") ? "variant" : "method", id))
      .filter(Boolean),
  }));
}

function getFinderContextualOptions(items, { selectedPhase = "", selectedGroup = "", selectedMaterial = "" } = {}) {
  const baseOptions = getFinderFilterOptions();
  const phaseCounts = new Map();
  const groupCounts = new Map();
  const materialCounts = new Map(FINDER_MATERIAL_BUCKETS.map((item) => [item.value, 0]));

  for (const item of items) {
    const phaseValues = new Set([item.phase, ...getMethodTagsOfType(item.method.method_id, "phase")].filter(Boolean));
    for (const value of phaseValues) {
      phaseCounts.set(value, (phaseCounts.get(value) ?? 0) + 1);
    }

    if (item.method.group_form) {
      groupCounts.set(item.method.group_form, (groupCounts.get(item.method.group_form) ?? 0) + 1);
    }

    const materialBucket = item.finderMaterialBucket ?? deriveFinderMaterialBucket(item.method);
    materialCounts.set(materialBucket, (materialCounts.get(materialBucket) ?? 0) + 1);
  }

  return {
    phases: baseOptions.phases
      .filter((option) => (phaseCounts.get(option.value) ?? 0) > 0 || option.value === selectedPhase)
      .map((option) => ({ ...option, count: phaseCounts.get(option.value) ?? 0 })),
    groups: baseOptions.groups
      .filter((option) => (groupCounts.get(option.value) ?? 0) > 0 || option.value === selectedGroup)
      .map((option) => ({ ...option, count: groupCounts.get(option.value) ?? 0 })),
    materialBuckets: baseOptions.materialBuckets
      .filter((option) => (materialCounts.get(option.value) ?? 0) > 0 || option.value === selectedMaterial)
      .map((option) => ({ ...option, count: materialCounts.get(option.value) ?? 0 })),
  };
}

function getFinderResults({
  query = "",
  intentId = null,
  goal = "",
  phase = "",
  group = "",
  time = "",
  material = "",
}) {
  const intent = intentId ? sheets.finderIntents.find((item) => item.intent_id === intentId) ?? null : null;
  const trimmedQuery = query.trim();
  const matchedIntents = query.trim()
    ? sheets.finderIntents
        .map((candidate) => ({
          intent: candidate,
          score: scoreIntent(candidate, query),
        }))
        .filter((item) => item.score > 0)
        .sort((left, right) => right.score - left.score)
        .slice(0, 3)
    : [];
  const fallbackIntent = intent ?? matchedIntents[0]?.intent ?? null;
  const scoreMap = new Map();
  const directGoalMatches = getDirectGoalMatches(goal);
  const hasExplicitBase = Boolean(intent || goal || phase || group || time || material);

  if (intent) {
    (intent.recommended_method_ids_or_variant_ids ?? []).forEach((sourceId, index) => {
      addFinderScore(scoreMap, sourceId.includes("_v_") ? "variant" : "method", sourceId, Math.max(64, 220 - index * 8));
    });
    addFinderSearchResults(scoreMap, buildIntentContextQuery(intent), 108, 18);
  }

  if (!intent && matchedIntents[0]?.intent) {
    matchedIntents[0].intent.recommended_method_ids_or_variant_ids?.forEach((sourceId, index) => {
      addFinderScore(scoreMap, sourceId.includes("_v_") ? "variant" : "method", sourceId, Math.max(28, 92 - index * 4));
    });
    addFinderSearchResults(scoreMap, buildIntentContextQuery(matchedIntents[0].intent), 72, 14);
  }

  if (goal) {
    directGoalMatches.forEach((methodId, index) => {
      addFinderScore(scoreMap, "method", methodId, Math.max(78, 200 - index * 4));
    });
    addFinderSearchResults(scoreMap, goal, 124, 28);
  }

  if (trimmedQuery) {
    if (hasExplicitBase && scoreMap.size) {
      addScopedFinderSearchResults(scoreMap, trimmedQuery, 150, 40);
    } else {
      addFinderSearchResults(scoreMap, trimmedQuery, 150, 40);
    }
  }

  if (!scoreMap.size && (phase || group || time || material)) {
    sheets.methods.forEach((method, index) => {
      addFinderScore(scoreMap, "method", method.method_id, Math.max(8, 60 - index));
    });
  }

  if (!scoreMap.size && !fallbackIntent && !trimmedQuery) {
    sheets.methods.slice(0, 18).forEach((method, index) => {
      addFinderScore(scoreMap, "method", method.method_id, Math.max(8, 48 - index));
    });
  }

  let items = Array.from(scoreMap.values())
    .map((entry) => {
      const hydrated = hydrateSource(entry.sourceType, entry.sourceId);
      if (!hydrated) {
        return null;
      }
      const timeBucket = deriveFinderTimeBucket(hydrated.method);
      const materialBucket = deriveFinderMaterialBucket(hydrated.method);
      return {
        ...hydrated,
        finderScore:
          entry.score +
          finderSoftPreferenceScore(timeBucket, time) +
          finderSoftPreferenceScore(materialBucket, material),
        finderTimeBucket: timeBucket,
        finderMaterialBucket: materialBucket,
      };
    })
    .filter(Boolean)
    .filter((item) => matchesFinderPhase(item, phase))
    .filter((item) => matchesFinderGroup(item, group))
    .sort((left, right) => right.finderScore - left.finderScore || left.title.localeCompare(right.title, "de"));

  const relatedByQuery = trimmedQuery
    ? items.filter((item) => !intent || !intent.recommended_method_ids_or_variant_ids?.includes(item.sourceId))
    : [];

  const softNotes = [];
  if (time) {
    const openDurationCount = items.filter((item) => item.finderTimeBucket === "open").length;
    if (openDurationCount) {
      softNotes.push(`${openDurationCount} weitere passende Methoden ohne gesicherte Dauer bleiben sichtbar.`);
    }
  }
  if (material) {
    const openMaterialCount = items.filter((item) => item.finderMaterialBucket === "open").length;
    if (openMaterialCount) {
      softNotes.push(`${openMaterialCount} weitere passende Methoden mit offenem Materialbedarf bleiben sichtbar.`);
    }
  }

  return {
    intent,
    inferredIntent: !intent ? fallbackIntent : null,
    matchedIntents,
    directGoalMatches,
    items,
    relatedByQuery,
    softNotes,
  };
}

function getLibraryFeed({ query = "", vectorId = null }) {
  let items = sheets.methods.map((method) => hydrateSource("method", method.method_id));
  if (vectorId) {
    items = items.filter((item) => item.vectors.some((vector) => vector.vector_id === vectorId));
  }
  if (query.trim()) {
    const ranked = new Map(
      searchEntities(query, 60)
        .filter((item) => item.type === "method")
        .map((item) => [item.id, item.score]),
    );
    items = items
      .filter((item) => ranked.has(item.method.method_id))
      .sort((left, right) => (ranked.get(right.method.method_id) ?? 0) - (ranked.get(left.method.method_id) ?? 0));
  }
  return items;
}

function getCollectionDetail(collectionId) {
  const collection = collectionById.get(collectionId);
  if (!collection) {
    return null;
  }
  const items = (collectionItemsByCollectionId.get(collectionId) ?? [])
    .slice()
    .sort((left, right) => (left.sort_order ?? 0) - (right.sort_order ?? 0))
    .map((item) => hydrateSource(item.item_type, item.method_id_or_variant_id))
    .filter(Boolean);
  return { collection, items };
}

function getMethodDetail(methodId, variantId = null) {
  const method = methodById.get(methodId);
  if (!method) {
    return null;
  }
  const variant = variantId ? variantById.get(variantId) ?? null : null;
  const hydrated = buildHydratedCard({
    method,
    variant,
    sourceType: variant ? "variant" : "method",
    sourceId: variant ? variant.variant_id : method.method_id,
  });
  hydrated.relatedCollections = getCollectionsForSource(variant?.variant_id ?? method.method_id);
  hydrated.relatedVariants = getVariantsForMethod(method.method_id);
  hydrated.allTags = getMethodTags(method.method_id);
  hydrated.openQuestions = sheets.openQuestions;
  return hydrated;
}

function getComposerPool({ query = "", phase = "", energy = "" }) {
  let pool = sheets.composerBlocksReference.map((blockRef) => {
    const hydrated = hydrateSource(blockRef.source_type, blockRef.source_id);
    if (!hydrated) {
      return null;
    }
    return {
      ...hydrated,
      blockRef,
      title: blockRef.display_title || hydrated.title,
      summary: blockRef.card_summary || hydrated.summary,
      searchableText: blockRef.searchable_text || "",
      filterText: blockRef.filter_text || "",
    };
  }).filter(Boolean);

  if (phase) {
    pool = pool.filter((item) => normalizeText(item.blockRef.phase).includes(normalizeText(phase)));
  }
  if (energy) {
    pool = pool.filter((item) => normalizeText(item.blockRef.energy_role).includes(normalizeText(energy)));
  }
  if (query.trim()) {
    const ranked = new Map(
      pool.map((item) => {
        const blob = normalizeText(
          [item.title, item.summary, item.searchableText, item.filterText, item.phase, item.energy].join(" "),
        );
        const queryBlob = normalizeText(query);
        let score = blob.includes(queryBlob) ? 20 : 0;
        for (const token of queryBlob.split(/\s+/).filter(Boolean)) {
          if (blob.includes(token)) {
            score += token.length;
          }
        }
        return [item.blockRef.block_ref_id, score];
      }),
    );
    pool = pool
      .filter((item) => (ranked.get(item.blockRef.block_ref_id) ?? 0) > 0)
      .sort((left, right) => (ranked.get(right.blockRef.block_ref_id) ?? 0) - (ranked.get(left.blockRef.block_ref_id) ?? 0));
  }

  return pool;
}

function createDraftBlock(blockRefId) {
  const blockRef = blockById.get(blockRefId);
  if (!blockRef) {
    return null;
  }
  return {
    id: `session-block-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    sourceType: blockRef.source_type,
    sourceId: blockRef.source_id,
    blockRefId,
    manualDuration: null,
    customNote: null,
  };
}

function hydrateDraftBlock(block) {
  const blockRef = blockById.get(block.blockRefId);
  const hydrated = hydrateSource(block.sourceType, block.sourceId);
  if (!hydrated) {
    return null;
  }
  return {
    ...hydrated,
    runtimeId: block.id,
    manualDuration: block.manualDuration ?? null,
    customNote: block.customNote ?? null,
    resolvedDuration: block.manualDuration ?? parseExplicitDuration(hydrated.duration),
    blockRef,
  };
}

function parseExplicitDuration(duration) {
  if (typeof duration === "number") {
    return duration;
  }
  if (typeof duration === "string") {
    const match = duration.match(/\d+/);
    return match ? Number(match[0]) : null;
  }
  return null;
}

function summarizeDraft(blocks) {
  const hydratedBlocks = blocks.map(hydrateDraftBlock).filter(Boolean);
  let known = 0;
  let unknown = 0;
  for (const block of hydratedBlocks) {
    if (typeof block.resolvedDuration === "number") {
      known += block.resolvedDuration;
    } else {
      unknown += 1;
    }
  }
  return {
    hydratedBlocks,
    knownMinutes: known,
    unknownBlocks: unknown,
    totalLabel: unknown ? `${known} Min. bekannt · ${unknown} offen` : `${known} Min.`,
  };
}

function getSessionHydration(draft) {
  const summary = summarizeDraft(draft.blocks);
  return {
    ...summary,
    draft,
  };
}

function getActiveSessionViewModel(block) {
  if (!block) {
    return null;
  }

  const overviewLines = uniqueValues([
    block.subtitle && block.subtitle !== block.title ? block.subtitle : null,
    block.summary && block.summary !== block.subtitle && block.summary !== block.prompt ? block.summary : null,
  ]);

  const frameItems = [
    block.durationLabel ? { label: "Dauer", value: block.durationLabel } : null,
    block.groupSetting ? { label: "Setting", value: block.groupSetting } : null,
    block.materials ? { label: "Material", value: block.materials } : null,
    block.variant?.variant_name ? { label: "Variante", value: block.variant.variant_name } : null,
  ].filter(Boolean);

  const vectors = block.vectors.map((vector) => vector.vector_name_de).filter(Boolean);
  const notes = uniqueValues(block.notes);
  const risks = uniqueValues(block.risks);
  const flowSteps = block.descriptionParagraphs;

  return {
    methodHref: `#/library/method/${block.method.method_id}${block.variant ? `?variant=${block.variant.variant_id}` : ""}`,
    overview: {
      title: "Überblick",
      lines: overviewLines,
      variantLabel: block.variant?.variant_label ?? null,
      sourceLabel: block.variant ? "Variantenmodus" : "Methodenmodus",
      hasContent: Boolean(overviewLines.length || block.variant?.variant_label),
    },
    sections: {
      ablauf: {
        key: "ablauf",
        label: "Ablauf",
        hasContent: flowSteps.length > 0,
        steps: flowSteps,
      },
      rahmen: {
        key: "rahmen",
        label: "Rahmen",
        hasContent: Boolean(frameItems.length || vectors.length),
        items: frameItems,
        vectors,
      },
      hinweise: {
        key: "hinweise",
        label: "Hinweise",
        hasContent: Boolean(notes.length || risks.length),
        notes,
        risks,
      },
    },
  };
}

export {
  METHODENSAMMLUNG_DATA,
  sheets,
  formatDurationRange,
  formatMethodDuration,
  getFinderIntents,
  getFinderContextualOptions,
  getFinderFilterOptions,
  getFinderResults,
  getLibraryFeed,
  getCollectionDetail,
  getMethodDetail,
  getComposerPool,
  getSessionHydration,
  getActiveSessionViewModel,
  getCollectionsForSource,
  getVectorsForMethod,
  getVariantsForMethod,
  createDraftBlock,
  hydrateDraftBlock,
  methodById,
  variantById,
  collectionById,
  vectorById,
  blockById,
  buildMethodDecoration,
  booleanLabel,
};
