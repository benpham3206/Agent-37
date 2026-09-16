const ID = /^[a-z0-9_.-]+:[a-z0-9_./-]+$/;
const CRITERION = /^[a-z0-9_.:-]+$/;

function safeId(value) {
    return typeof value === 'string' && value.length <= 256 && ID.test(value) ? value : null;
}

function safeCriteria(value) {
    if (!Array.isArray(value) || value.length > 128) return [];
    return value.filter((item) => typeof item === 'string' && item.length <= 128 && CRITERION.test(item));
}

/**
 * Keep only bounded advancement identity, requirements, and criterion progress.
 * Display/NBT data is deliberately discarded.
 */
export function applyAdvancementPacket(previous, packet) {
    const state = previous && typeof previous === 'object' ? structuredClone(previous) : { known: false, entries: {} };
    if (!state.entries || typeof state.entries !== 'object' || Array.isArray(state.entries)) state.entries = {};
    if (packet?.reset === true) state.entries = {};

    for (const id of Array.isArray(packet?.identifiers) ? packet.identifiers : []) {
        const safe = safeId(id);
        if (safe) delete state.entries[safe];
    }
    for (const pair of Array.isArray(packet?.advancementMapping) ? packet.advancementMapping : []) {
        const id = safeId(pair?.key);
        if (!id || !pair.value || typeof pair.value !== 'object') continue;
        const requirements = Array.isArray(pair.value.requirements) && pair.value.requirements.length <= 128
            ? pair.value.requirements.map(safeCriteria).filter((group) => group.length > 0)
            : [];
        state.entries[id] = { requirements, criteria: state.entries[id]?.criteria || {} };
    }
    for (const pair of Array.isArray(packet?.progressMapping) ? packet.progressMapping : []) {
        const id = safeId(pair?.key);
        if (!id || !state.entries[id]) continue;
        const criteria = {};
        for (const progress of Array.isArray(pair.value) ? pair.value.slice(0, 128) : []) {
            const criterion = progress?.criterionIdentifier;
            if (typeof criterion !== 'string' || criterion.length > 128 || !CRITERION.test(criterion)) continue;
            const timestamp = progress.criterionProgress;
            criteria[criterion] = timestamp === null || timestamp === undefined
                ? null
                : Number.isInteger(timestamp) && timestamp >= 0 ? timestamp : null;
        }
        state.entries[id].criteria = criteria;
    }
    state.known = true;
    return state;
}
