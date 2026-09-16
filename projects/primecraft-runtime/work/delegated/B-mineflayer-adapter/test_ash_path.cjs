"use strict";

const assert = require("node:assert/strict");
const { ashGotoSucceeded, ashArriveOk, blockHasExposedFace, runAshWalk, withinGotoRange } = require("./ash_path.cjs");

function pos(x, y, z) {
  return {
    x,
    y,
    z,
    offset(dx, dy, dz) {
      return pos(x + dx, y + dy, z + dz);
    },
  };
}

assert.equal(ashGotoSucceeded(undefined), false);
assert.equal(ashGotoSucceeded({ status: "failed" }), false);
assert.equal(ashGotoSucceeded({ status: "partial" }), false);
assert.equal(ashGotoSucceeded({ status: "success" }), true);

const solid = { name: "stone", boundingBox: "block" };
const air = { name: "air", boundingBox: "empty" };
const buried = { name: "stone", position: pos(10, 64, 4) };
const cliff = { name: "stone", position: pos(12, 64, 4) };

function worldAt(block) {
  return (at) => {
    if (at.x === 10 && at.y === 64 && at.z === 4) return buried;
    if (at.x === 12 && at.y === 64 && at.z === 4) return cliff;
    if (at.x === 13 && at.y === 64 && at.z === 4) return air;
    return solid;
  };
}

assert.equal(blockHasExposedFace(buried, worldAt()), false, "buried stone must not count as pathable");
assert.equal(blockHasExposedFace(cliff, worldAt()), true, "stone with an air face must count as pathable");
assert.equal(blockHasExposedFace(null, worldAt()), false);

assert.equal(ashArriveOk({ status: "failed" }, 2, 3.5).ok, false);
assert.equal(ashArriveOk({ status: "failed" }, 2, 3.5).errorCode, "path_not_found");
assert.equal(ashArriveOk({ status: "success" }, 10, 3.5).ok, false);
assert.equal(ashArriveOk({ status: "success" }, 10, 3.5).errorCode, "path_incomplete");
assert.equal(ashArriveOk({ status: "success" }, 2, 3.5).ok, true);

assert.equal(withinGotoRange({ x: 0, y: 64, z: 0 }, { x: 10, y: 64, z: 0 }, 64), true);
assert.equal(withinGotoRange({ x: 0, y: 64, z: 0 }, { x: 100, y: 64, z: 0 }, 64), false);
assert.equal(withinGotoRange({ x: 0, y: 64, z: 0 }, { x: 1.5, y: 64, z: 0 }, 64), false);

(async () => {
  let gotoCalls = 0;
  let position = 8;
  const closeWalk = await runAshWalk({
    goto: async () => {
      gotoCalls += 1;
      position = 2;
      return { status: "success" };
    },
    distanceAfter: () => position,
    arriveMax: 3.5,
  });
  assert.equal(gotoCalls, 1, "pathfinder must be invoked even when already somewhat close");
  assert.equal(closeWalk.ok, true);

  gotoCalls = 0;
  const failedClose = await runAshWalk({
    goto: async () => {
      gotoCalls += 1;
      return { status: "failed" };
    },
    distanceAfter: () => 3.0,
    arriveMax: 3.5,
  });
  assert.equal(gotoCalls, 1, "failed ashfinder.goto must still be called, not skipped by Euclidean distance");
  assert.equal(failedClose.ok, false);
  assert.equal(failedClose.errorCode, "path_not_found");

  const noWalk = await runAshWalk({
    goto: async () => ({ status: "success" }),
    distanceAfter: () => 8,
    arriveMax: 3.5,
  });
  assert.equal(noWalk.ok, false);
  assert.equal(noWalk.errorCode, "path_incomplete");

  console.log("test_ash_path.cjs ok");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
