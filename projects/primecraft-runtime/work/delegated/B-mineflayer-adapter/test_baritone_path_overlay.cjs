"use strict";

const assert = require("node:assert/strict");
const { EventEmitter } = require("node:events");
const {
  VIEWER_PATH_ID,
  VIEWER_PATH_COLOR,
  pathPointsFromAsh,
  createAshPathOverlay,
} = require("./baritone_path_overlay.cjs");

assert.deepEqual(pathPointsFromAsh(null), []);
assert.deepEqual(
  pathPointsFromAsh([{ worldPos: { x: 1, y: 2, z: 3 } }, { worldPos: { x: 4, y: 5, z: 6 } }]),
  [
    { x: 1, y: 2.1, z: 3 },
    { x: 4, y: 5.1, z: 6 },
  ],
);
assert.deepEqual(
  pathPointsFromAsh([{ x: 0, y: 64, z: 1 }, { x: 2, y: 64, z: 1 }]),
  [
    { x: 0, y: 64.1, z: 1 },
    { x: 2, y: 64.1, z: 1 },
  ],
);

const overlay = createAshPathOverlay();
const lines = [];
const erased = [];
const ash = new EventEmitter();
const bot = {
  ashfinder: ash,
  viewer: {
    drawLine(id, points, color) {
      lines.push({ id, points, color });
    },
    erase(id) {
      erased.push(id);
    },
  },
};
overlay.bind(bot);
ash.emit("pathStarted", {
  path: [{ worldPos: { x: 0, y: 64, z: 0 } }, { worldPos: { x: 1, y: 64, z: 0 } }],
});
assert.equal(lines.length, 1);
assert.equal(lines[0].id, VIEWER_PATH_ID);
assert.equal(lines[0].color, VIEWER_PATH_COLOR);
assert.deepEqual(lines[0].points, [
  { x: 0, y: 64.1, z: 0 },
  { x: 1, y: 64.1, z: 0 },
]);

const queued = createAshPathOverlay();
const pendingAsh = new EventEmitter();
const pendingBot = { ashfinder: pendingAsh, viewer: null };
queued.bind(pendingBot);
pendingAsh.emit("pathStarted", {
  path: [{ worldPos: { x: 8, y: 70, z: 8 } }, { worldPos: { x: 9, y: 70, z: 8 } }],
});
assert.equal(queued.draw(pendingBot), false);
pendingBot.viewer = {
  last: null,
  drawLine(id, points, color) {
    this.last = { id, points, color };
  },
  erase() {},
};
assert.equal(queued.draw(pendingBot), true);
assert.equal(pendingBot.viewer.last.id, VIEWER_PATH_ID);
assert.equal(pendingBot.viewer.last.color, VIEWER_PATH_COLOR);

ash.emit("stopped");
assert.deepEqual(erased, [VIEWER_PATH_ID]);

console.log("test_baritone_path_overlay.cjs ok");
