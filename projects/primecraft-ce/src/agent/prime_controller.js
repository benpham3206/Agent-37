import * as skills from './library/skills.js';

const MAX_COUNT = 16;
const MAX_RANGE = 64;
const MAX_MOVE_MS = 1000;
const NAVIGATION_BLOCKS = new Set(['oak_log', 'spruce_log', 'birch_log', 'jungle_log', 'acacia_log', 'dark_oak_log', 'mangrove_log', 'cherry_log', 'crafting_table', 'stone']);
const SAFE_NAME = /^[a-z0-9_]+$/;
const COLLECTABLE_BLOCKS = new Set([
    'oak_log', 'spruce_log', 'birch_log', 'jungle_log', 'acacia_log',
    'dark_oak_log', 'mangrove_log', 'cherry_log', 'cobblestone', 'stone'
]);
const CRAFTABLE_ITEMS = new Set([
    'oak_planks', 'spruce_planks', 'birch_planks', 'jungle_planks',
    'acacia_planks', 'dark_oak_planks', 'mangrove_planks', 'cherry_planks',
    'stick', 'wooden_pickaxe', 'stone_pickaxe'
]);
const EQUIPPABLE_ITEMS = new Set([
    'wooden_pickaxe', 'stone_pickaxe', 'stone_sword', 'wooden_sword',
    'stone_axe', 'wooden_axe', 'shield', 'hand'
]);

function reject(message) {
    const error = new Error(message);
    error.code = 'invalid_prime_action';
    throw error;
}

function exactKeys(action, keys) {
    const actual = Object.keys(action).sort();
    const expected = [...keys].sort();
    return actual.length === expected.length && actual.every((key, index) => key === expected[index]);
}

function name(value, label, allowed) {
    if (typeof value !== 'string' || !SAFE_NAME.test(value) || !allowed.has(value)) reject(`${label}_not_allowlisted`);
    return value;
}

function count(value, label) {
    if (!Number.isInteger(value) || value < 1 || value > MAX_COUNT) reject(`${label}_out_of_bounds`);
    return value;
}

function range(value) {
    if (!Number.isInteger(value) || value < 1 || value > MAX_RANGE) reject('range_out_of_bounds');
    return value;
}

/** Validate one typed Prime action without touching the game. */
export function validatePrimeAction(rawAction) {
    if (!rawAction || typeof rawAction !== 'object' || Array.isArray(rawAction) || typeof rawAction.kind !== 'string') {
        reject('invalid_action');
    }
    switch (rawAction.kind) {
        case 'move':
            if (!exactKeys(rawAction, ['kind', 'direction', 'duration_ms']) || !['forward', 'back', 'left', 'right'].includes(rawAction.direction) || !Number.isInteger(rawAction.duration_ms) || rawAction.duration_ms < 1 || rawAction.duration_ms > MAX_MOVE_MS) reject('invalid_move_action');
            return { kind: rawAction.kind, direction: rawAction.direction, duration_ms: rawAction.duration_ms };
        case 'look':
            if (!exactKeys(rawAction, ['kind', 'yaw_deg', 'pitch_deg']) || typeof rawAction.yaw_deg !== 'number' || !Number.isFinite(rawAction.yaw_deg) || rawAction.yaw_deg < -360 || rawAction.yaw_deg > 360 || typeof rawAction.pitch_deg !== 'number' || !Number.isFinite(rawAction.pitch_deg) || rawAction.pitch_deg < -90 || rawAction.pitch_deg > 90) reject('invalid_look_action');
            return { kind: rawAction.kind, yaw_deg: rawAction.yaw_deg, pitch_deg: rawAction.pitch_deg };
        case 'navigate':
            if (!exactKeys(rawAction, ['kind', 'block', 'max_distance'])) reject('invalid_navigate_action');
            return { kind: rawAction.kind, block: name(rawAction.block, 'block', NAVIGATION_BLOCKS), max_distance: range(rawAction.max_distance) };
        case 'collect_blocks':
            if (!exactKeys(rawAction, ['kind', 'block', 'count', 'max_distance'])) reject('invalid_collect_action');
            return {
                kind: rawAction.kind,
                block: name(rawAction.block, 'block', COLLECTABLE_BLOCKS),
                count: count(rawAction.count, 'count'),
                max_distance: range(rawAction.max_distance),
            };
        case 'craft_recipe':
            if (!exactKeys(rawAction, ['kind', 'item', 'count'])) reject('invalid_craft_action');
            return {
                kind: rawAction.kind,
                item: name(rawAction.item, 'item', CRAFTABLE_ITEMS),
                count: count(rawAction.count, 'count'),
            };
        case 'equip':
            if (!exactKeys(rawAction, ['kind', 'item'])) reject('invalid_equip_action');
            return { kind: rawAction.kind, item: name(rawAction.item, 'item', EQUIPPABLE_ITEMS) };
        case 'go_to_bed':
            if (!exactKeys(rawAction, ['kind'])) reject('invalid_bed_action');
            return { kind: rawAction.kind };
        case 'chat':
            if (!exactKeys(rawAction, ['kind', 'message']) || typeof rawAction.message !== 'string' || rawAction.message.length < 1 || rawAction.message.length > 200 || [...rawAction.message].some((char) => char.charCodeAt(0) < 32)) reject('invalid_chat_action');
            return { kind: rawAction.kind, message: rawAction.message };
        default:
            reject('unsupported_prime_action');
    }
}

/**
 * Validate and execute one Prime-owned action through CE's ActionManager.
 * The caller still owns leases, idempotency, and post-state verification.
 */
export async function executePrimeAction(agent, rawAction) {
    const action = validatePrimeAction(rawAction);
    let label;
    let operation;
    switch (action.kind) {
        case 'move':
            label = `prime:move:${action.direction}`;
            operation = async () => {
                agent.bot.setControlState(action.direction, true);
                try { await skills.wait(agent.bot, action.duration_ms); }
                finally { agent.bot.clearControlStates(); }
            };
            break;
        case 'look':
            label = 'prime:look';
            operation = () => agent.bot.look(action.yaw_deg * Math.PI / 180, action.pitch_deg * Math.PI / 180, true);
            break;
        case 'navigate':
            label = `prime:navigate:${action.block}`;
            operation = () => skills.goToNearestBlock(agent.bot, action.block, 2, action.max_distance);
            break;
        case 'collect_blocks':
            label = `prime:collect_blocks:${action.block}`;
            operation = async () => {
                const target = agent.bot.findBlock({
                    matching: (block) => block?.name === action.block,
                    maxDistance: action.max_distance,
                    count: 1,
                });
                if (!target) return false;
                return skills.collectBlock(agent.bot, action.block, action.count);
            };
            break;
        case 'craft_recipe':
            label = `prime:craft_recipe:${action.item}`;
            operation = () => skills.craftRecipe(agent.bot, action.item, action.count);
            break;
        case 'equip':
            label = `prime:equip:${action.item}`;
            operation = () => skills.equip(agent.bot, action.item);
            break;
        case 'go_to_bed':
            label = 'prime:go_to_bed';
            operation = () => skills.goToBed(agent.bot);
            break;
        case 'chat':
            label = 'prime:chat';
            operation = () => agent.openChat(action.message);
            break;
        default:
            reject('unsupported_prime_action');
    }
    const result = await agent.actions.runAction(label, operation, { timeout: 2 });
    return { success: result.success === true, action_kind: action.kind, result };
}
