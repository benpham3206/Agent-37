"use strict";

const assert = require("node:assert/strict");
const { cursorHitsTarget, isSameBlockPosition } = require("./dig_los.cjs");

function block(name, x, y, z) {
  return { name, position: { x, y, z } };
}

assert.equal(isSameBlockPosition({ x: 10, y: 64, z: 4 }, { x: 10, y: 64, z: 4 }), true);
assert.equal(isSameBlockPosition({ x: 10, y: 64, z: 4 }, { x: 9, y: 64, z: 4 }), false);
assert.equal(cursorHitsTarget(null, block("oak_log", 10, 64, 4)), false);
assert.equal(cursorHitsTarget(block("oak_log", 10, 64, 4), null), false);

const wall = block("cobblestone", 9, 64, 4);
const log = block("oak_log", 10, 64, 4);
assert.equal(
  cursorHitsTarget(wall, log),
  false,
  "looking at a wall in front of a log must not count as a legal dig",
);
assert.equal(cursorHitsTarget(log, log), true);
assert.equal(cursorHitsTarget(block("oak_log", 10, 64, 5), log), false);

console.log("test_dig_los.cjs ok");
