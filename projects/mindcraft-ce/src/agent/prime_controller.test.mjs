import test from 'node:test';
import assert from 'node:assert/strict';
import { validatePrimeAction } from './prime_controller.js';

test('validates bounded native CE actions', () => {
    assert.deepEqual(validatePrimeAction({ kind: 'craft_recipe', item: 'stone_pickaxe', count: 1 }), {
        kind: 'craft_recipe', item: 'stone_pickaxe', count: 1,
    });
    assert.deepEqual(validatePrimeAction({ kind: 'collect_blocks', block: 'cobblestone', count: 3, max_distance: 32 }), {
        kind: 'collect_blocks', block: 'cobblestone', count: 3, max_distance: 32,
    });
    assert.deepEqual(validatePrimeAction({ kind: 'go_to_bed' }), { kind: 'go_to_bed' });
});

test('rejects arbitrary methods, names, counts, and extra fields', () => {
    for (const action of [
        { kind: 'exec', code: 'bot.chat("bad")' },
        { kind: 'craft_recipe', item: 'command_block', count: 1 },
        { kind: 'collect_blocks', block: 'stone', count: 17, max_distance: 32 },
        { kind: 'equip', item: 'diamond_sword' },
        { kind: 'go_to_bed', extra: true },
    ]) {
        assert.throws(() => validatePrimeAction(action), { code: 'invalid_prime_action' });
    }
});
