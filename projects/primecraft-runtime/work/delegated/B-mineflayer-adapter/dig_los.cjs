"use strict";

function isSameBlockPosition(left, right) {
  return Boolean(
    left
    && right
    && Number.isInteger(left.x)
    && Number.isInteger(left.y)
    && Number.isInteger(left.z)
    && left.x === right.x
    && left.y === right.y
    && left.z === right.z
  );
}

function cursorHitsTarget(cursorBlock, targetBlock) {
  if (!targetBlock || !targetBlock.position) return false;
  if (!cursorBlock || !cursorBlock.position) return false;
  return isSameBlockPosition(cursorBlock.position, targetBlock.position);
}

module.exports = {
  isSameBlockPosition,
  cursorHitsTarget,
};
