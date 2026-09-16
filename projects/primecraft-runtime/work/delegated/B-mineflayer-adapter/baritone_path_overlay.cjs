"use strict";

const VIEWER_PATH_ID = "baritone-path";
const VIEWER_PATH_COLOR = 0x00ffff;
const PATH_LIFT = 0.1;

function pathPointsFromAsh(path) {
  if (!Array.isArray(path)) return [];
  const points = [];
  for (const node of path) {
    const pos = node && node.worldPos ? node.worldPos : node;
    if (!pos || typeof pos.x !== "number" || typeof pos.y !== "number" || typeof pos.z !== "number") continue;
    if (!Number.isFinite(pos.x) || !Number.isFinite(pos.y) || !Number.isFinite(pos.z)) continue;
    points.push({ x: pos.x, y: pos.y + PATH_LIFT, z: pos.z });
  }
  return points;
}

function createAshPathOverlay() {
  let lastPath = null;

  function draw(bot, path) {
    if (path !== undefined) lastPath = path;
    try {
      if (!bot || !bot.viewer || typeof bot.viewer.drawLine !== "function") return false;
      const points = pathPointsFromAsh(lastPath);
      if (points.length < 2) {
        if (typeof bot.viewer.erase === "function") bot.viewer.erase(VIEWER_PATH_ID);
        return false;
      }
      bot.viewer.drawLine(VIEWER_PATH_ID, points, VIEWER_PATH_COLOR);
      return true;
    } catch (error) {
      const message = error && error.message ? error.message : "viewer_path_draw_failed";
      process.stderr.write(`viewer_path_draw_failed:${message}\n`);
      return false;
    }
  }

  function erase(bot) {
    lastPath = null;
    try {
      if (!bot || !bot.viewer || typeof bot.viewer.erase !== "function") return;
      bot.viewer.erase(VIEWER_PATH_ID);
    } catch (error) {
      const message = error && error.message ? error.message : "viewer_path_erase_failed";
      process.stderr.write(`viewer_path_erase_failed:${message}\n`);
    }
  }

  function bind(bot) {
    if (!bot || !bot.ashfinder || typeof bot.ashfinder.on !== "function") return;
    bot.ashfinder.on("pathStarted", (event) => {
      draw(bot, event && event.path);
    });
    bot.ashfinder.on("stopped", () => {
      erase(bot);
    });
  }

  return { draw, erase, bind };
}

module.exports = {
  VIEWER_PATH_ID,
  VIEWER_PATH_COLOR,
  pathPointsFromAsh,
  createAshPathOverlay,
};
