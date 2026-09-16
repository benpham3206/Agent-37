import test from 'node:test';
import assert from 'node:assert/strict';
import { applyAdvancementPacket } from './advancements.js';

test('normalizes advancement definitions and progress without display data', () => {
    const state = applyAdvancementPacket({ known: false, entries: {} }, {
        reset: false,
        advancementMapping: [{
            key: 'minecraft:story/mine_stone',
            value: { requirements: [['get_stone']], displayData: { title: { text: 'hidden' } } },
        }],
        identifiers: [],
        progressMapping: [{
            key: 'minecraft:story/mine_stone',
            value: [{ criterionIdentifier: 'get_stone', criterionProgress: 123 }],
        }],
    });
    assert.deepEqual(state, { known: true, entries: {
        'minecraft:story/mine_stone': { requirements: [['get_stone']], criteria: { get_stone: 123 } },
    }});
});

test('applies reset and identifier removal', () => {
    const previous = { known: true, entries: { 'minecraft:story/mine_stone': { requirements: [], criteria: {} } } };
    const state = applyAdvancementPacket(previous, { reset: false, advancementMapping: [], identifiers: ['minecraft:story/mine_stone'], progressMapping: [] });
    assert.deepEqual(state.entries, {});
});
