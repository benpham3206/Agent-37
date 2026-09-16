"use strict";

function ashGotoSucceeded(result) {
  return Boolean(result && result.status === "success");
}

function ashArriveOk(result, endDistance, arriveMax) {
  if (!ashGotoSucceeded(result)) {
    return {
      ok: false,
      errorCode: "path_not_found",
      component: "ashfinder",
      rootCause: "goto_status_not_success",
      failureType: "pathfinder_failed",
    };
  }
  if (!Number.isFinite(endDistance) || endDistance > arriveMax) {
    return {
      ok: false,
      errorCode: "path_incomplete",
      component: "ashfinder",
      rootCause: "still_beyond_arrive_max",
      failureType: "pathfinder_did_not_arrive",
    };
  }
  return {
    ok: true,
    errorCode: null,
    component: "ashfinder",
    rootCause: null,
    failureType: null,
  };
}

async function runAshWalk({ goto, distanceAfter, arriveMax }) {
  if (typeof goto !== "function" || typeof distanceAfter !== "function" || !Number.isFinite(arriveMax)) {
    return {
      ok: false,
      errorCode: "unsafe_action",
      component: "ashfinder",
      rootCause: "invalid_walk_args",
      failureType: "invalid_input",
    };
  }
  const result = await goto();
  return ashArriveOk(result, distanceAfter(), arriveMax);
}

function withinGotoRange(from, dest, maxRange) {
  if (!from || !dest || !Number.isFinite(from.x) || !Number.isFinite(from.y) || !Number.isFinite(from.z)) return false;
  if (!Number.isInteger(dest.x) || !Number.isInteger(dest.y) || !Number.isInteger(dest.z)) return false;
  if (!Number.isFinite(maxRange) || maxRange <= 0) return false;
  const dx = dest.x - from.x;
  const dy = dest.y - from.y;
  const dz = dest.z - from.z;
  const distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
  return Number.isFinite(distance) && distance <= maxRange;
}

function isEmptyBlock(block) {
  if (!block) return true;
  if (block.boundingBox === "empty") return true;
  return block.name === "air" || block.name === "cave_air" || block.name === "void_air";
}

function blockHasExposedFace(block, blockAt) {
  if (!block || !block.position || typeof blockAt !== "function") return false;
  const origin = block.position;
  const dirs = [
    [0, 1, 0],
    [0, -1, 0],
    [1, 0, 0],
    [-1, 0, 0],
    [0, 0, 1],
    [0, 0, -1],
  ];
  for (const [dx, dy, dz] of dirs) {
    if (isEmptyBlock(blockAt(origin.offset(dx, dy, dz)))) return true;
  }
  return false;
}

module.exports = {
  ashGotoSucceeded,
  ashArriveOk,
  runAshWalk,
  withinGotoRange,
  isEmptyBlock,
  blockHasExposedFace,
};
