"use strict";

// Restricted child process. It does not load Mineflayer or open a socket until
// an explicit attach request passes validation. The parent adapter remains the
// owner of target, lease, timeout, and evidence policy.
const readline = require("node:readline");
const fs = require("node:fs");
const net = require("node:net");
const path = require("node:path");
const { cursorHitsTarget } = require("./dig_los.cjs");
const { ashArriveOk, ashGotoSucceeded, blockHasExposedFace, withinGotoRange } = require("./ash_path.cjs");
const { createAshPathOverlay } = require("./baritone_path_overlay.cjs");

console.log = () => {};
console.info = () => {};
console.debug = () => {};

const MAX_CHAT_LENGTH = 200;
const MAX_CHAT_EVENTS = 64;
const DIRECTIONS = new Set(["forward", "back", "left", "right"]);
const SECRET_MARKER = /(?:api[_-]?key|access[_-]?token|auth[_-]?token|token|password|passwd|secret|bearer)\s*[:=]/i;
const CONTROL_STATES = ["forward", "back", "left", "right", "jump", "sprint", "sneak"];
const WOOD_TARGETS = new Set([
  "oak_log",
  "spruce_log",
  "birch_log",
  "jungle_log",
  "acacia_log",
  "dark_oak_log",
  "mangrove_log",
  "cherry_log",
]);
const NAVIGATE_TARGETS = new Set([
  ...WOOD_TARGETS,
  "stone",
  "cobblestone",
  "coal_ore",
  "deepslate",
  "iron_ore",
  "dirt",
]);
const DIG_TARGETS = new Set(NAVIGATE_TARGETS);
const CRAFT_TARGETS = new Set([
  "oak_planks",
  "spruce_planks",
  "birch_planks",
  "jungle_planks",
  "acacia_planks",
  "dark_oak_planks",
  "mangrove_planks",
  "cherry_planks",
  "stick",
  "crafting_table",
  "wooden_pickaxe",
  "wooden_axe",
  "wooden_shovel",
  "wooden_sword",
  "wooden_hoe",
  "furnace",
  "stone_pickaxe",
  "stone_axe",
  "stone_shovel",
  "stone_sword",
  "torch",
]);
const PLACE_TARGETS = new Set(["crafting_table"]);
const ADVANCEMENT_ID = /^[a-z0-9_.-]+:[a-z0-9_./-]+$/;
const CRITERION_ID = /^[a-z0-9_.:-]+$/;
const GAMEPLAY_ADVANCEMENT = /^minecraft:(story|adventure|nether|end|husbandry)\//;
const WOOD_TO_PLANKS = new Map([
  ["oak_log", "oak_planks"],
  ["spruce_log", "spruce_planks"],
  ["birch_log", "birch_planks"],
  ["jungle_log", "jungle_planks"],
  ["acacia_log", "acacia_planks"],
  ["dark_oak_log", "dark_oak_planks"],
  ["mangrove_log", "mangrove_planks"],
  ["cherry_log", "cherry_planks"],
]);
const PLANK_TARGETS = new Set(WOOD_TO_PLANKS.values());
const HAZARD_BLOCKS = new Set(["lava", "fire", "soul_fire", "cactus", "magma_block"]);
const MIN_OPERATION_HEALTH = 8;
const MAX_WOOD_CANDIDATES = 8;
const WOOD_OPERATION_BUDGET_MS = 24000;

let bot = null;
let pathOverlay = null;
let actionEnabled = false;
let motionTimer = null;
let stopping = false;
let chatInbox = [];
let ashGoals = null;
let advancementState = { known: false, entries: {} };
let lastAutoReplyAtMs = 0;
const AUTO_REPLY_COOLDOWN_MS = 1250;
let movementLogPath = null;
let movementTimer = null;

function movementSample(entity, scope) {
  if (!entity || !entity.position) return null;
  const position = entity.position;
  const x = Number(position.x);
  const y = Number(position.y);
  const z = Number(position.z);
  if (![x, y, z].every(Number.isFinite)) return null;
  let support = null;
  try {
    const Vec3 = require("vec3").Vec3;
    support = bot && typeof bot.blockAt === "function"
      ? bot.blockAt(new Vec3(Math.floor(x), Math.floor(y) - 1, Math.floor(z)))
      : null;
  } catch (_error) {
    support = null;
  }
  const supportY = support && support.position ? Number(support.position.y) : NaN;
  const supported = Number.isFinite(supportY) && Math.abs(y - (supportY + 1)) <= 0.2;
  return {
    schema: "minecraft-ce/movement",
    schema_version: 1,
    ts_ms: Date.now(),
    emitted_at: new Date().toISOString(),
    telemetry_scope: scope,
    entity_id: entity.id === undefined ? null : String(entity.id),
    username: typeof entity.username === "string" ? entity.username : null,
    position: { x, y, z },
    yaw_rad: Number.isFinite(Number(entity.yaw)) ? Number(entity.yaw) : null,
    pitch_rad: Number.isFinite(Number(entity.pitch)) ? Number(entity.pitch) : null,
    yaw_deg: Number.isFinite(Number(entity.yaw)) ? Number(entity.yaw) * 180 / Math.PI : null,
    pitch_deg: Number.isFinite(Number(entity.pitch)) ? Number(entity.pitch) * 180 / Math.PI : null,
    control_state: scope === "bot_full" && bot && bot.controlState ? { ...bot.controlState } : null,
    raw_input_available: scope === "bot_full",
    support_state: support === null ? "unknown" : supported ? "standing" : "airborne",
    support_block: supported ? {
      block: blockId(support),
      position: { x: Number(support.position.x), y: supportY, z: Number(support.position.z) },
    } : null,
  };
}

function recordMovement() {
  if (!movementLogPath || !bot || !bot.entity) return;
  const samples = [];
  const botSample = movementSample(bot.entity, "bot_full");
  if (botSample) samples.push(botSample);
  const entities = bot.entities && typeof bot.entities === "object" ? Object.values(bot.entities) : [];
  for (const entity of entities) {
    if (!entity || entity === bot.entity || entity.type !== "player") continue;
    const sample = movementSample(entity, "player_observable");
    if (sample) samples.push(sample);
  }
  try {
    for (const sample of samples) fs.appendFileSync(movementLogPath, `${JSON.stringify(sample)}\n`, "utf8");
  } catch (_error) {
    // Movement evidence is best effort; it must never interrupt gameplay.
  }
}

function startMovementLog() {
  if (!movementLogPath || movementTimer !== null) return;
  recordMovement();
  movementTimer = setInterval(recordMovement, 200);
}

function stopMovementLog() {
  if (movementTimer !== null) clearInterval(movementTimer);
  movementTimer = null;
}

function safeAdvancementId(value) {
  return typeof value === "string" && value.length <= 256 && ADVANCEMENT_ID.test(value) ? value : null;
}

function safeCriteria(value) {
  if (!Array.isArray(value) || value.length > 32) return [];
  return value.filter((item) => typeof item === "string" && item.length <= 128 && CRITERION_ID.test(item));
}

function applyAdvancementPacket(previous, packet) {
  const state = previous && typeof previous === "object" ? { known: previous.known === true, entries: { ...(previous.entries || {}) } } : { known: false, entries: {} };
  if (!state.entries || typeof state.entries !== "object" || Array.isArray(state.entries)) state.entries = {};
  if (packet && packet.reset === true) state.entries = {};
  for (const id of Array.isArray(packet && packet.identifiers) ? packet.identifiers : []) {
    const safe = safeAdvancementId(id);
    if (safe) delete state.entries[safe];
  }
  for (const pair of Array.isArray(packet && packet.advancementMapping) ? packet.advancementMapping : []) {
    const id = safeAdvancementId(pair && pair.key);
    if (!id || !GAMEPLAY_ADVANCEMENT.test(id) || !pair.value || typeof pair.value !== "object") continue;
    if (!state.entries[id] && Object.keys(state.entries).length >= 64) continue;
    const requirements = Array.isArray(pair.value.requirements) && pair.value.requirements.length <= 32
      ? pair.value.requirements.map(safeCriteria).filter((group) => group.length > 0)
      : [];
    state.entries[id] = { requirements, criteria: (state.entries[id] && state.entries[id].criteria) || {} };
  }
  for (const pair of Array.isArray(packet && packet.progressMapping) ? packet.progressMapping : []) {
    const id = safeAdvancementId(pair && pair.key);
    if (!id || !state.entries[id]) continue;
    const criteria = {};
    for (const progress of Array.isArray(pair.value) ? pair.value.slice(0, 32) : []) {
      const criterion = progress && progress.criterionIdentifier;
      if (typeof criterion !== "string" || criterion.length > 128 || !CRITERION_ID.test(criterion)) continue;
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

function advancementsSnapshot() {
  return {
    known: advancementState.known === true,
    entries: advancementState.entries,
  };
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function exactKeys(value, expected) {
  if (!isObject(value)) return false;
  const actual = Object.keys(value).sort();
  const wanted = [...expected].sort();
  return actual.length === wanted.length && actual.every((key, index) => key === wanted[index]);
}

function explicitVersion(value) {
  return typeof value === "string" && /^[0-9]+(?:\.[0-9]+){1,2}$/.test(value);
}

function explicitUsername(value) {
  return typeof value === "string" && /^[A-Za-z0-9_]{3,16}$/.test(value);
}

function safeHost(value) {
  return typeof value === "string" && /^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$/.test(value);
}

function safePort(value) {
  return Number.isInteger(value) && value >= 1 && value <= 65535;
}

function safeAuthCacheDir(value) {
  return value === null || (typeof value === "string" && path.isAbsolute(value) && !/[\u0000-\u001f]/.test(value));
}

function safeText(value, maxLength) {
  return typeof value === "string" && value.length > 0 && value.length <= maxLength && !/[\u0000-\u001f]/.test(value);
}

function recordChat(username, message) {
  if (!bot || username === bot.username || typeof username !== "string" || username.length < 1 || username.length > 16 || /[\u0000-\u001f]/.test(username) || !safeText(message, MAX_CHAT_LENGTH)) return;
  chatInbox.push({
    message_id: `chat-${Date.now()}-${chatInbox.length}`,
    received_at_ms: Date.now(),
    username,
    message,
  });
  if (chatInbox.length > MAX_CHAT_EVENTS) chatInbox.shift();
  // Bridge relay: answer players even when the model is busy elsewhere.
  if (actionEnabled) {
    autoReplyToPlayer(username, message);
  }
}

function autoReplyToPlayer(username, message) {
  if (!bot || stopping) return;
  if (/^\s*primebot\s+(join|leave)\b/i.test(message)) return;
  const now = Date.now();
  if (now - lastAutoReplyAtMs < AUTO_REPLY_COOLDOWN_MS) return;
  const snippet = message.length > 120 ? `${message.slice(0, 117)}...` : message;
  // Prefix so the line is obviously from PrimeBot, not an echo of the player.
  const replyText = `hey ${username}, got your chat: ${snippet}`;
  if (!safeText(replyText, MAX_CHAT_LENGTH) || SECRET_MARKER.test(replyText)) return;
  lastAutoReplyAtMs = now;
  try {
    bot.chat(replyText);
  } catch (_error) {
    // Best-effort relay; inbox still retained for the model.
  }
}

function reply(value) {
  process.stdout.write(`${JSON.stringify(value)}\n`);
}

function errorReply(errorCode) {
  reply({ ok: false, error_code: errorCode });
}

function clearMotion() {
  if (motionTimer !== null) {
    clearTimeout(motionTimer);
    motionTimer = null;
  }
  if (bot && typeof bot.setControlState === "function") {
    for (const state of CONTROL_STATES) bot.setControlState(state, false);
  }
  if (bot && bot.ashfinder && typeof bot.ashfinder.stop === "function") bot.ashfinder.stop();
}

function dimensionName(value) {
  if (value === "minecraft:the_nether" || value === "the_nether" || value === "nether") return "the_nether";
  if (value === "minecraft:the_end" || value === "the_end" || value === "end") return "the_end";
  return "overworld";
}

function numberOr(value, fallback) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function itemId(item) {
  if (!item || typeof item.name !== "string") return null;
  return item.name.includes(":") ? item.name : `minecraft:${item.name}`;
}

function blockId(block) {
  if (!block || typeof block.name !== "string") return "minecraft:air";
  return block.name.includes(":") ? block.name : `minecraft:${block.name}`;
}

function blockAt(offsetX, offsetY, offsetZ) {
  try {
    return blockId(bot.blockAt(bot.entity.position.offset(offsetX, offsetY, offsetZ)));
  } catch (_error) {
    return "minecraft:air";
  }
}

function sleep(delayMs) {
  return new Promise((resolve) => setTimeout(resolve, delayMs));
}

async function within(promise, timeoutMs, errorCode) {
  let timer = null;
  try {
    return await Promise.race([
      promise,
      new Promise((_resolve, reject) => {
        timer = setTimeout(() => reject(new Error(errorCode)), timeoutMs);
      }),
    ]);
  } finally {
    if (timer !== null) clearTimeout(timer);
  }
}

function inventoryCount(names) {
  if (!bot || !bot.inventory || !Array.isArray(bot.inventory.slots)) return 0;
  let count = 0;
  for (const item of bot.inventory.slots) {
    if (item && names.has(item.name)) count += Math.max(0, Number(item.count) || 0);
  }
  return count;
}

function inventoryCounts() {
  return {
    logs: inventoryCount(WOOD_TARGETS),
    planks: inventoryCount(PLANK_TARGETS),
    crafting_tables: inventoryCount(new Set(["crafting_table"])),
  };
}

function operationResult(event, reason, maxDistance, before, options = {}) {
  return {
    ok: true,
    event,
    reason,
    max_distance: maxDistance,
    target: options.target || null,
    target_after: options.targetAfter || null,
    before,
    after_harvest: options.afterHarvest || null,
    after_planks: options.afterPlanks || null,
    after: options.after || inventoryCounts(),
  };
}

const VIEWER_PORT = 3000;
const VIEWER_HOST = "127.0.0.1";
const VIEWER_FOV_DEG = 90;
const VIEWER_START_RETRY_MS = 250;
const VIEWER_START_RETRY_LIMIT = 12;

function applyViewerFov(fovDeg) {
  let pkgDir;
  try {
    pkgDir = path.dirname(require.resolve("prismarine-viewer/package.json"));
  } catch (_error) {
    return;
  }
  for (const rel of ["viewer/lib/viewer.js", "public/index.js"]) {
    const file = path.join(pkgDir, rel);
    try {
      const text = fs.readFileSync(file, "utf8");
      const next = text.replace(/PerspectiveCamera\(\d+\)?\s*,/g, `PerspectiveCamera(${fovDeg},`);
      if (next !== text) fs.writeFileSync(file, next);
    } catch (_error) {
      continue;
    }
  }
}

function applyViewerListenLoopback() {
  let pkgDir;
  try {
    pkgDir = path.dirname(require.resolve("prismarine-viewer/package.json"));
  } catch (_error) {
    return;
  }
  const file = path.join(pkgDir, "lib/mineflayer.js");
  try {
    const text = fs.readFileSync(file, "utf8");
    if (text.includes('listen(port, "127.0.0.1"')) return;
    const next = text.replace("http.listen(port,", 'http.listen(port, "127.0.0.1",');
    if (next !== text) fs.writeFileSync(file, next);
  } catch (_error) {
    return;
  }
}

async function confirmVisibleDig(target, deadlineMs) {
  if (!target || !bot.canDigBlock(target) || Date.now() + 500 >= deadlineMs) return false;
  try {
    await within(
      bot.lookAt(target.position.offset(0.5, 0.5, 0.5), true),
      Math.min(2000, Math.max(1, deadlineMs - Date.now())),
      "look_timeout",
    );
  } catch (_error) {
    return false;
  }
  return cursorHitsTarget(bot.blockAtCursor(5), target);
}

function nearGoal(position, distance) {
  const Vec3 = require("vec3").Vec3;
  return new ashGoals.GoalNear(
    new Vec3(Math.floor(position.x), Math.floor(position.y), Math.floor(position.z)),
    distance,
  );
}

function harvestGoal(position) {
  return nearGoal(position, 1.75);
}

function applySafeAshConfig() {
  if (!bot || !bot.ashfinder || !bot.ashfinder.config) return;
  const config = bot.ashfinder.config;
  config.parkour = false;
  config.proParkour = false;
  config.breakBlocks = false;
  config.placeBlocks = false;
  config.allowSprinting = true;
  config.swimming = true;
  config.maxFallDist = 1;
  const avoid = new Set([...(config.blocksToStayAway || []), ...HAZARD_BLOCKS]);
  config.blocksToStayAway = [...avoid];
  if (typeof bot.ashfinder.disableBreaking === "function") bot.ashfinder.disableBreaking();
  if (typeof bot.ashfinder.disablePlacing === "function") bot.ashfinder.disablePlacing();
}

async function gotoAsh(goal, timeoutMs, errorCode) {
  applySafeAshConfig();
  const result = await within(bot.ashfinder.goto(goal), timeoutMs, errorCode);
  if (!ashGotoSucceeded(result)) throw new Error("path_not_found");
  return result;
}

function enableAutoEat() {
  if (!bot || !bot.autoEat) return;
  bot.autoEat.options.priority = "foodPoints";
  bot.autoEat.options.startAt = 14;
  bot.autoEat.options.bannedFood = [
    "pufferfish",
    "spider_eye",
    "poisonous_potato",
    "rotten_flesh",
    "chorus_fruit",
    "chicken",
    "suspicious_stew",
    "golden_apple",
  ];
  bot.autoEat.enable();
}

function viewerPortOpen(onResult) {
  let settled = false;
  const finish = (open) => {
    if (settled) return;
    settled = true;
    onResult(open);
  };
  const socket = net.connect({ host: VIEWER_HOST, port: VIEWER_PORT }, () => {
    socket.end();
    finish(true);
  });
  socket.setTimeout(400, () => {
    socket.destroy();
    finish(false);
  });
  socket.on("error", () => finish(false));
}

let viewerStartAttempts = 0;

function startBrowserViewer() {
  if (!bot || stopping) return;
  try {
    applyViewerFov(VIEWER_FOV_DEG);
    applyViewerListenLoopback();
    const mineflayerViewer = require("prismarine-viewer").mineflayer;
    const host = new Proxy(bot, {
      get(target, prop, receiver) {
        if (prop === "version") return "1.21.4";
        const value = Reflect.get(target, prop, receiver);
        return typeof value === "function" ? value.bind(target) : value;
      },
      set(target, prop, value) {
        target[prop] = value;
        return true;
      },
    });
    mineflayerViewer(host, { port: VIEWER_PORT, firstPerson: true, viewDistance: 6 });
    if (pathOverlay) pathOverlay.draw(bot);
  } catch (error) {
    const message = error && error.message ? error.message : "viewer_start_failed";
    process.stderr.write(`viewer_start_failed:${message}\n`);
  }
}

function ensureBrowserViewer() {
  if (!bot || stopping) return;
  viewerPortOpen((open) => {
    if (stopping || !bot) return;
    if (open) {
      viewerStartAttempts = 0;
      if (pathOverlay) pathOverlay.draw(bot);
      return;
    }
    closeBrowserViewer();
    startBrowserViewer();
    viewerStartAttempts += 1;
    if (viewerStartAttempts <= VIEWER_START_RETRY_LIMIT) {
      setTimeout(ensureBrowserViewer, VIEWER_START_RETRY_MS);
    }
  });
}

function closeBrowserViewer() {
  if (!bot || !bot.viewer || typeof bot.viewer.close !== "function") return;
  try {
    bot.viewer.close();
  } catch (_error) {
    return;
  }
}

function hazardNear(position) {
  for (let offsetX = -1; offsetX <= 1; offsetX += 1) {
    for (let offsetY = -1; offsetY <= 1; offsetY += 1) {
      for (let offsetZ = -1; offsetZ <= 1; offsetZ += 1) {
        const block = bot.blockAt(position.offset(offsetX, offsetY, offsetZ));
        if (!block || HAZARD_BLOCKS.has(block.name)) return true;
      }
    }
  }
  return false;
}

function unsafeStateReason() {
  if (!bot || !bot.entity || !bot.game || dimensionName(bot.game.dimension) !== "overworld") return "wrong_dimension";
  if (!Number.isFinite(bot.health) || bot.health < MIN_OPERATION_HEALTH) return "low_health";
  if (Number(bot.entity.fireTicks) > 0) return "on_fire";
  const feet = bot.blockAt(bot.entity.position.offset(0, 0, 0));
  const head = bot.blockAt(bot.entity.position.offset(0, 1, 0));
  const below = bot.blockAt(bot.entity.position.offset(0, -1, 0));
  if (!feet || !head || !below || HAZARD_BLOCKS.has(feet.name) || HAZARD_BLOCKS.has(head.name) || HAZARD_BLOCKS.has(below.name)) return "immediate_hazard";
  if (head.boundingBox === "block") return "suffocating";
  return null;
}

function targetReceipt(target) {
  return {
    block: blockId(target),
    x: Number(target.position.x),
    y: Number(target.position.y),
    z: Number(target.position.z),
  };
}

function recipeConsumes(recipe, itemType, count) {
  return recipe && Array.isArray(recipe.delta) && recipe.delta.some((delta) => delta.id === itemType && delta.count <= -count);
}

async function waitForCountIncrease(names, baseline, targetPosition, deadlineMs) {
  const firstDeadline = Math.min(deadlineMs, Date.now() + 2500);
  while (Date.now() < firstDeadline) {
    if (inventoryCount(names) > baseline) return true;
    await sleep(100);
  }
  const drops = Object.values(bot.entities || {})
    .filter((entity) => entity && entity.position && (entity.name === "item" || entity.objectType === "Item"))
    .filter((entity) => entity.position.distanceTo(targetPosition) <= 8)
    .sort((left, right) => bot.entity.position.distanceTo(left.position) - bot.entity.position.distanceTo(right.position));
  if (drops.length > 0 && Date.now() + 500 < deadlineMs) {
    try {
      await gotoAsh(nearGoal(drops[0].position, 1.5), Math.min(3000, deadlineMs - Date.now()), "pickup_timeout");
    } catch (_error) {
      if (bot.ashfinder && typeof bot.ashfinder.stop === "function") bot.ashfinder.stop();
    }
  }
  while (Date.now() < deadlineMs) {
    if (inventoryCount(names) > baseline) return true;
    await sleep(100);
  }
  return false;
}

function worldSummary() {
  const nearbyBlocks = [];
  const origin = bot.entity.position;
  for (let offsetX = -2; offsetX <= 2; offsetX += 1) {
    for (let offsetY = -1; offsetY <= 2; offsetY += 1) {
      for (let offsetZ = -2; offsetZ <= 2; offsetZ += 1) {
        const block = bot.blockAt(origin.offset(offsetX, offsetY, offsetZ));
        const name = blockId(block);
        if (name === "minecraft:air" || !block || !block.position) continue;
        const dx = Number(block.position.x) - Number(origin.x);
        const dy = Number(block.position.y) - Number(origin.y);
        const dz = Number(block.position.z) - Number(origin.z);
        const distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (Number.isFinite(distance)) {
          nearbyBlocks.push({
            block: name,
            distance,
            position: {
              x: Number(block.position.x),
              y: Number(block.position.y),
              z: Number(block.position.z),
            },
          });
        }
      }
    }
  }
  nearbyBlocks.sort((left, right) => left.distance - right.distance);
  return {
    below: blockAt(0, -1, 0),
    feet: blockAt(0, 0, 0),
    head: blockAt(0, 1, 0),
    nearby_blocks: nearbyBlocks.slice(0, 32),
  };
}

function observation() {
  if (!bot || !bot.entity) throw new Error("not_attached");
  const entity = bot.entity;
  const position = entity.position || {};
  const velocity = entity.velocity || {};
  const inventory = [];
  const slots = bot.inventory && Array.isArray(bot.inventory.slots) ? bot.inventory.slots : [];
  for (let slot = 0; slot < slots.length && inventory.length < 128; slot += 1) {
    const item = slots[slot];
    const itemName = itemId(item);
    if (itemName !== null) inventory.push({ slot, item: itemName, count: Math.max(1, Math.min(64, Number(item.count) || 1)) });
  }
  const nearby = [];
  const entities = bot.entities && typeof bot.entities === "object" ? Object.values(bot.entities) : [];
  for (const other of entities) {
    if (!other || other === entity || other.position === undefined || other.id === undefined) continue;
    const otherPosition = other.position;
    const dx = numberOr(otherPosition.x, 0) - numberOr(position.x, 0);
    const dy = numberOr(otherPosition.y, 0) - numberOr(position.y, 0);
    const dz = numberOr(otherPosition.z, 0) - numberOr(position.z, 0);
    const distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
    if (Number.isFinite(distance) && distance <= 512 && nearby.length < 64) {
      nearby.push({ entity_id: String(other.id), kind: String(other.name || other.type || "entity"), distance });
    }
  }
  return {
    schema_version: "observation.v3",
    observation_id: `obs-${Date.now()}`,
    observed_at_ms: Date.now(),
    dimension: dimensionName(bot.game && bot.game.dimension),
    position: { x: numberOr(position.x, 0), y: numberOr(position.y, 0), z: numberOr(position.z, 0) },
    velocity: { x: numberOr(velocity.x, 0), y: numberOr(velocity.y, 0), z: numberOr(velocity.z, 0) },
    health: Math.max(0, Math.min(20, numberOr(bot.health, 0))),
    food: Math.max(0, Math.min(20, Math.trunc(numberOr(bot.food, 0)))),
    air: Math.max(0, Math.min(300, Math.trunc(numberOr(bot.oxygenLevel, 300)))),
    fire_ticks: Math.max(0, Math.trunc(numberOr(entity.fireTicks, 0))),
    is_alive: numberOr(bot.health, 0) > 0,
    selected_slot: Math.max(0, Math.min(8, Math.trunc(numberOr(bot.quickBarSlot, 0)))),
    inventory,
    nearby_entities: nearby,
    recent_chat: chatInbox.slice(0, 32).map((message) => ({
      sender: message.username,
      message: message.message,
      received_at_ms: message.received_at_ms,
    })),
    world: worldSummary(),
    advancements: advancementsSnapshot(),
  };
}

async function attach(request) {
  if (!exactKeys(request, ["op", "host", "port", "version", "auth", "username", "auth_cache_dir", "action_enabled", "movement_log_path"])) {
    errorReply("invalid_attach");
    return;
  }
  if (bot !== null || stopping || !safeHost(request.host) || !safePort(request.port) || !explicitVersion(request.version) || !["offline", "microsoft"].includes(request.auth) || !explicitUsername(request.username) || !safeAuthCacheDir(request.auth_cache_dir) || typeof request.action_enabled !== "boolean" || typeof request.movement_log_path !== "string" || !path.isAbsolute(request.movement_log_path) || /[\u0000-\u001f]/.test(request.movement_log_path)) {
    errorReply("invalid_attach");
    return;
  }
  actionEnabled = request.action_enabled;
  movementLogPath = request.movement_log_path;
  chatInbox = [];
  advancementState = { known: false, entries: {} };
  let mineflayer;
  let baritone;
  let autoEatPlugin;
  try {
    mineflayer = require("mineflayer");
    baritone = require("@miner-org/mineflayer-baritone");
    autoEatPlugin = require("mineflayer-auto-eat").plugin;
    ashGoals = baritone.goals;
  } catch (_error) {
    errorReply("gameplay_dependencies_unavailable");
    return;
  }
  try {
    const options = {
      host: request.host,
      port: request.port,
      version: request.version,
      auth: request.auth,
      username: request.username,
    };
    if (request.auth === "microsoft" && typeof request.auth_cache_dir === "string") {
      options.profilesFolder = request.auth_cache_dir;
    }
    bot = mineflayer.createBot(options);
    bot.loadPlugin(baritone.loader);
    bot.loadPlugin(autoEatPlugin);
    pathOverlay = createAshPathOverlay();
    pathOverlay.bind(bot);
    applySafeAshConfig();
    bot.on("chat", recordChat);
    bot._client.on("advancements", (packet) => {
      advancementState = applyAdvancementPacket(advancementState, packet);
    });
    await new Promise((resolve, reject) => {
      let settled = false;
      const finish = (error) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        if (error) reject(error);
        else resolve();
      };
      const timer = setTimeout(() => finish(new Error("attach_timeout")), 120000);
      bot.once("spawn", () => finish());
      bot.once("error", () => finish(new Error("client_error")));
      bot.once("kicked", () => finish(new Error("kicked")));
      bot.once("end", () => finish(new Error("connection_ended")));
    });
    enableAutoEat();
    applySafeAshConfig();
    bot.on("spawn", () => {
      viewerStartAttempts = 0;
      startMovementLog();
      setImmediate(ensureBrowserViewer);
    });
    reply({ ok: true, event: "attached" });
    viewerStartAttempts = 0;
    setImmediate(ensureBrowserViewer);
  } catch (error) {
    stopMovementLog();
    movementLogPath = null;
    clearMotion();
    pathOverlay = null;
    bot = null;
    errorReply(error && error.message === "attach_timeout" ? "attach_timeout" : "client_failure");
  }
}

function look(request) {
  if (!actionEnabled || !bot || !exactKeys(request, ["op", "yaw_deg", "pitch_deg"]) || typeof request.yaw_deg !== "number" || !Number.isFinite(request.yaw_deg) || request.yaw_deg < -360 || request.yaw_deg > 360 || typeof request.pitch_deg !== "number" || !Number.isFinite(request.pitch_deg) || request.pitch_deg < -90 || request.pitch_deg > 90) {
    errorReply("unsafe_action");
    return;
  }
  bot.look(request.yaw_deg * Math.PI / 180, request.pitch_deg * Math.PI / 180, true)
    .then(() => reply({ ok: true, event: "look_completed" }))
    .catch(() => errorReply("look_failed"));
}

function blockIsHazard(block) {
  return !block || HAZARD_BLOCKS.has(block.name);
}

async function navigate(request) {
  if (!actionEnabled || !bot || !bot.ashfinder || !ashGoals || !exactKeys(request, ["op", "block", "max_distance"]) || typeof request.block !== "string" || (!NAVIGATE_TARGETS.has(request.block) && request.block !== "wood") || !Number.isInteger(request.max_distance) || request.max_distance < 1 || request.max_distance > 64) {
    errorReply("unsafe_action");
    return;
  }
  const targetNames = request.block === "wood" ? WOOD_TARGETS : new Set([request.block]);
  const positions = bot.findBlocks({
    matching: (candidate) => candidate && targetNames.has(candidate.name),
    maxDistance: request.max_distance,
    count: 64,
  });
  const candidates = positions
    .map((position) => bot.blockAt(position))
    .filter((candidate) => candidate && candidate.position && !blockIsHazard(bot.blockAt(candidate.position.offset(0, -1, 0))) && blockHasExposedFace(candidate, (at) => bot.blockAt(at)));
  if (candidates.length === 0) {
    errorReply("target_not_found");
    return;
  }
  candidates.sort((left, right) => bot.entity.position.distanceTo(left.position) - bot.entity.position.distanceTo(right.position));
  const target = candidates[0];
  try {
    const result = await gotoAsh(nearGoal(target.position, 2), 20000, "path_timeout");
    const distance = bot.entity.position.distanceTo(target.position);
    const arrival = ashArriveOk(result, distance, 3.5);
    if (!arrival.ok) {
      errorReply(arrival.errorCode);
      return;
    }
    reply({
      ok: true,
      event: "pathfound",
      target: { block: target.name, x: target.position.x, y: target.position.y, z: target.position.z },
      distance,
    });
  } catch (_error) {
    if (bot.ashfinder && typeof bot.ashfinder.stop === "function") bot.ashfinder.stop();
    errorReply("path_not_found");
  }
}

async function woodToTable(request) {
  if (!actionEnabled || !bot || !bot.ashfinder || !ashGoals || !exactKeys(request, ["op", "max_distance"]) || !Number.isInteger(request.max_distance) || request.max_distance < 1 || request.max_distance > 64) {
    errorReply("unsafe_action");
    return;
  }
  const maxDistance = request.max_distance;
  const before = inventoryCounts();
  const initialUnsafe = unsafeStateReason();
  if (initialUnsafe !== null) {
    clearMotion();
    reply(operationResult("unsafe", "initial_state_unsafe", maxDistance, before));
    return;
  }

  const deadlineMs = Date.now() + WOOD_OPERATION_BUDGET_MS;
  const positions = bot.findBlocks({
    matching: (candidate) => candidate && WOOD_TARGETS.has(candidate.name),
    maxDistance,
    count: 64,
  });
  const candidates = positions
    .map((position) => bot.blockAt(position))
    .filter((candidate) => candidate && candidate.position && WOOD_TARGETS.has(candidate.name) && !hazardNear(candidate.position) && blockHasExposedFace(candidate, (at) => bot.blockAt(at)))
    .sort((left, right) => bot.entity.position.distanceTo(left.position) - bot.entity.position.distanceTo(right.position))
    .slice(0, MAX_WOOD_CANDIDATES);
  if (candidates.length === 0) {
    clearMotion();
    reply(operationResult("target_unavailable", "no_log_in_range", maxDistance, before));
    return;
  }

  let target = null;
  for (const candidate of candidates) {
    if (Date.now() + 1000 >= deadlineMs) break;
    const current = bot.blockAt(candidate.position);
    if (!current || !WOOD_TARGETS.has(current.name) || hazardNear(current.position)) continue;
    try {
      await gotoAsh(harvestGoal(current.position), Math.min(8000, deadlineMs - Date.now()), "path_timeout");
      const refreshed = bot.blockAt(current.position);
      const distance = bot.entity.position.distanceTo(current.position);
      if (refreshed && WOOD_TARGETS.has(refreshed.name) && Number.isFinite(distance) && distance <= 4.5 && await confirmVisibleDig(refreshed, deadlineMs)) {
        target = refreshed;
        break;
      }
    } catch (_error) {
      if (bot.ashfinder && typeof bot.ashfinder.stop === "function") bot.ashfinder.stop();
    }
  }
  if (target === null) {
    clearMotion();
    reply(operationResult("target_unavailable", "no_safe_reachable_log", maxDistance, before));
    return;
  }

  const targetInfo = targetReceipt(target);
  if (unsafeStateReason() !== null || hazardNear(bot.entity.position)) {
    clearMotion();
    reply(operationResult("unsafe", "reached_state_unsafe", maxDistance, before, { target: targetInfo, targetAfter: blockId(bot.blockAt(target.position)) }));
    return;
  }

  try {
    const targetName = target.name;
    const planksName = WOOD_TO_PLANKS.get(targetName);
    const targetLogNames = new Set([targetName]);
    const targetPlankNames = new Set([planksName]);
    const targetLogBefore = inventoryCount(targetLogNames);
    const targetPlanksBefore = inventoryCount(targetPlankNames);
    const targetPosition = target.position.clone();
    if (!planksName || !(await confirmVisibleDig(target, deadlineMs))) throw new Error("harvest_precondition_failed");

    await within(bot.dig(target, true), Math.min(8000, deadlineMs - Date.now()), "harvest_timeout");
    const targetAfterDig = blockId(bot.blockAt(targetPosition));
    if (targetAfterDig === `minecraft:${targetName}`) throw new Error("target_not_removed");
    const collected = await waitForCountIncrease(targetLogNames, targetLogBefore, targetPosition, Math.min(deadlineMs, Date.now() + 5000));
    const afterHarvest = inventoryCounts();
    if (!collected || inventoryCount(targetLogNames) < targetLogBefore + 1 || afterHarvest.logs < before.logs + 1) throw new Error("harvest_not_collected");

    const logItem = bot.registry.itemsByName[targetName];
    const planksItem = bot.registry.itemsByName[planksName];
    const tableItem = bot.registry.itemsByName.crafting_table;
    if (!logItem || !planksItem || !tableItem) throw new Error("recipe_data_unavailable");
    const plankRecipe = bot.recipesFor(planksItem.id, null, 4, null)
      .find((recipe) => recipe.result && recipe.result.id === planksItem.id && recipeConsumes(recipe, logItem.id, 1));
    if (!plankRecipe) throw new Error("plank_recipe_unavailable");
    await within(bot.craft(plankRecipe, 1, null), Math.min(5000, deadlineMs - Date.now()), "plank_craft_timeout");
    const afterPlanks = inventoryCounts();
    if (inventoryCount(targetPlankNames) < targetPlanksBefore + 4 || afterPlanks.planks < before.planks + 4 || afterPlanks.logs > afterHarvest.logs - 1) throw new Error("plank_postcondition_failed");

    const tableBefore = before.crafting_tables;
    const planksBeforeTable = inventoryCount(targetPlankNames);
    const tableRecipe = bot.recipesFor(tableItem.id, null, 1, null)
      .find((recipe) => recipe.result && recipe.result.id === tableItem.id && recipeConsumes(recipe, planksItem.id, 4));
    if (!tableRecipe) throw new Error("table_recipe_unavailable");
    await within(bot.craft(tableRecipe, 1, null), Math.min(5000, deadlineMs - Date.now()), "table_craft_timeout");
    const after = inventoryCounts();
    if (inventoryCount(targetPlankNames) > planksBeforeTable - 4 || after.crafting_tables < tableBefore + 1) throw new Error("table_postcondition_failed");

    const targetAfter = blockId(bot.blockAt(targetPosition));
    if (targetAfter === `minecraft:${targetName}`) throw new Error("target_postcondition_failed");
    clearMotion();
    reply(operationResult("wood_to_table_complete", "completed", maxDistance, before, {
      target: targetInfo,
      targetAfter,
      afterHarvest,
      afterPlanks,
      after,
    }));
  } catch (error) {
    clearMotion();
    const allowed = new Set([
      "harvest_precondition_failed",
      "harvest_timeout",
      "target_not_removed",
      "harvest_not_collected",
      "recipe_data_unavailable",
      "plank_recipe_unavailable",
      "plank_craft_timeout",
      "plank_postcondition_failed",
      "table_recipe_unavailable",
      "table_craft_timeout",
      "table_postcondition_failed",
      "target_postcondition_failed",
    ]);
    errorReply(error && allowed.has(error.message) ? error.message : "wood_to_table_failed");
  }
}

async function findReachableBlock(targetNames, maxDistance, deadlineMs) {
  const positions = bot.findBlocks({
    matching: (candidate) => candidate && targetNames.has(candidate.name),
    maxDistance,
    count: 64,
  });
  const candidates = positions
    .map((position) => bot.blockAt(position))
    .filter((candidate) => candidate && candidate.position && !blockIsHazard(bot.blockAt(candidate.position.offset(0, -1, 0))) && !hazardNear(candidate.position) && blockHasExposedFace(candidate, (at) => bot.blockAt(at)))
    .sort((left, right) => bot.entity.position.distanceTo(left.position) - bot.entity.position.distanceTo(right.position))
    .slice(0, MAX_WOOD_CANDIDATES);
  for (const candidate of candidates) {
    if (Date.now() + 1000 >= deadlineMs) break;
    const current = bot.blockAt(candidate.position);
    if (!current || !targetNames.has(current.name)) continue;
    try {
      await gotoAsh(harvestGoal(current.position), Math.min(8000, deadlineMs - Date.now()), "path_timeout");
      const refreshed = bot.blockAt(current.position);
      const distance = bot.entity.position.distanceTo(current.position);
      if (refreshed && targetNames.has(refreshed.name) && Number.isFinite(distance) && distance <= 4.5 && await confirmVisibleDig(refreshed, deadlineMs)) return refreshed;
    } catch (_error) {
      if (bot.ashfinder && typeof bot.ashfinder.stop === "function") bot.ashfinder.stop();
    }
  }
  return null;
}

async function gotoPos(request) {
  if (!actionEnabled || !bot || !bot.ashfinder || !ashGoals || !exactKeys(request, ["op", "x", "y", "z"])) {
    errorReply("unsafe_action");
    return;
  }
  const x = request.x;
  const y = request.y;
  const z = request.z;
  if (!Number.isInteger(x) || !Number.isInteger(y) || !Number.isInteger(z) || y < -64 || y > 320) {
    errorReply("unsafe_action");
    return;
  }
  const origin = bot.entity.position;
  if (!withinGotoRange(origin, { x, y, z }, 64)) {
    errorReply("unsafe_action");
    return;
  }
  const Vec3 = require("vec3").Vec3;
  const dest = new Vec3(x, y, z);
  try {
    const result = await gotoAsh(nearGoal(dest, 2), 20000, "path_timeout");
    const distance = bot.entity.position.distanceTo(dest);
    const arrival = ashArriveOk(result, distance, 3.5);
    if (!arrival.ok) {
      errorReply(arrival.errorCode);
      return;
    }
    reply({
      ok: true,
      event: "pathfound",
      target: { x, y, z },
      distance,
    });
  } catch (_error) {
    if (bot.ashfinder && typeof bot.ashfinder.stop === "function") bot.ashfinder.stop();
    errorReply("path_not_found");
  }
}

async function dig(request) {
  if (!actionEnabled || !bot || !bot.ashfinder || !ashGoals || !exactKeys(request, ["op", "block", "max_distance"]) || typeof request.block !== "string" || !DIG_TARGETS.has(request.block) || !Number.isInteger(request.max_distance) || request.max_distance < 1 || request.max_distance > 64) {
    errorReply("unsafe_action");
    return;
  }
  const targetNames = new Set([request.block]);
  const names = new Set([request.block]);
  if (request.block === "stone") {
    names.add("cobblestone");
  }
  const before = inventoryCount(names);
  const deadlineMs = Date.now() + WOOD_OPERATION_BUDGET_MS;
  const target = await findReachableBlock(targetNames, request.max_distance, deadlineMs);
  if (target === null) {
    clearMotion();
    errorReply("target_not_found");
    return;
  }
  try {
    if (["stone", "cobblestone", "deepslate", "coal_ore", "iron_ore"].includes(target.name)) {
      const pickaxe = bot.inventory.items().find((i) => i && i.name.endsWith("_pickaxe"));
      if (pickaxe) await bot.equip(pickaxe, "hand");
    } else if (WOOD_TARGETS.has(target.name)) {
      const axe = bot.inventory.items().find((i) => i && i.name.endsWith("_axe"));
      if (axe) await bot.equip(axe, "hand");
    } else if (["dirt", "grass_block", "sand", "gravel"].includes(target.name)) {
      const shovel = bot.inventory.items().find((i) => i && i.name.endsWith("_shovel"));
      if (shovel) await bot.equip(shovel, "hand");
    }
    if (!(await confirmVisibleDig(target, deadlineMs))) throw new Error("harvest_precondition_failed");
    const targetPosition = target.position.clone();
    await within(bot.dig(target, true), Math.min(8000, deadlineMs - Date.now()), "harvest_timeout");
    const collected = await waitForCountIncrease(names, before, targetPosition, Math.min(deadlineMs, Date.now() + 5000));
    clearMotion();
    reply({ ok: true, event: "dug", block: request.block, collected: collected === true });
  } catch (error) {
    clearMotion();
    const allowed = new Set(["harvest_precondition_failed", "harvest_timeout"]);
    errorReply(error && allowed.has(error.message) ? error.message : "dig_failed");
  }
}

async function craft(request) {
  if (!actionEnabled || !bot || !exactKeys(request, ["op", "item", "count"]) || typeof request.item !== "string" || !CRAFT_TARGETS.has(request.item) || !Number.isInteger(request.count) || request.count < 1 || request.count > 4) {
    errorReply("unsafe_action");
    return;
  }
  try {
    const item = bot.registry.itemsByName[request.item];
    if (!item) throw new Error("recipe_data_unavailable");
    const craftingTable = bot.findBlock({
      matching: bot.registry.blocksByName.crafting_table ? bot.registry.blocksByName.crafting_table.id : null,
      maxDistance: 32,
    });
    if (craftingTable && bot.ashfinder && bot.entity.position.distanceTo(craftingTable.position) > 3.5) {
      try {
        await gotoAsh(nearGoal(craftingTable.position, 2.5), 5000, "path_timeout");
      } catch (_error) {
        if (bot.ashfinder && typeof bot.ashfinder.stop === "function") bot.ashfinder.stop();
      }
    }
    let recipes = bot.recipesFor(item.id, null, 1, craftingTable);
    if ((!Array.isArray(recipes) || recipes.length === 0) && craftingTable) {
      recipes = bot.recipesFor(item.id, null, 1, null);
    }
    if (!Array.isArray(recipes) || recipes.length === 0) throw new Error("recipe_unavailable");
    const recipe = recipes[0];
    const targetTable = recipe.requiresTable ? craftingTable : null;
    if (recipe.requiresTable && !targetTable) throw new Error("recipe_unavailable");
    await within(bot.craft(recipe, request.count, targetTable), 8000, "craft_timeout");
    reply({ ok: true, event: "crafted", item: request.item, count: request.count });
  } catch (error) {
    const allowed = new Set(["recipe_data_unavailable", "recipe_unavailable", "craft_timeout"]);
    errorReply(error && allowed.has(error.message) ? error.message : "craft_failed");
  }
}

async function place(request) {
  if (!actionEnabled || !bot || !exactKeys(request, ["op", "item"]) || typeof request.item !== "string" || !PLACE_TARGETS.has(request.item)) {
    errorReply("unsafe_action");
    return;
  }
  try {
    const Vec3 = require("vec3");
    const held = bot.inventory.items().find((slot) => slot && slot.name === request.item);
    if (!held) throw new Error("item_unavailable");
    await bot.equip(held, "hand");
    const origin = bot.entity.position;
    let reference = null;
    for (let offsetX = -2; offsetX <= 2 && reference === null; offsetX += 1) {
      for (let offsetZ = -2; offsetZ <= 2; offsetZ += 1) {
        const support = bot.blockAt(origin.offset(offsetX, -1, offsetZ));
        const dest = bot.blockAt(origin.offset(offsetX, 0, offsetZ));
        if (support && support.name !== "air" && dest && dest.name === "air" && !HAZARD_BLOCKS.has(support.name)) {
          reference = support;
          break;
        }
      }
    }
    if (reference === null) throw new Error("place_target_unavailable");
    await within(bot.placeBlock(reference, new Vec3(0, 1, 0)), 5000, "place_timeout");
    reply({ ok: true, event: "placed", item: request.item });
  } catch (error) {
    const allowed = new Set(["item_unavailable", "place_target_unavailable", "place_timeout"]);
    errorReply(error && allowed.has(error.message) ? error.message : "place_failed");
  }
}

function move(request) {
  if (!actionEnabled || !bot || !exactKeys(request, ["op", "direction", "duration_ms"]) || !DIRECTIONS.has(request.direction) || !Number.isInteger(request.duration_ms) || request.duration_ms < 1 || request.duration_ms > 5000) {
    errorReply("unsafe_action");
    return;
  }
  clearMotion();
  bot.setControlState(request.direction, true);
  motionTimer = setTimeout(() => clearMotion(), request.duration_ms);
  reply({ ok: true, event: "move_started", duration_ms: request.duration_ms });
}

function chat(request) {
  if (!actionEnabled || !bot || !exactKeys(request, ["op", "message"]) || !safeText(request.message, MAX_CHAT_LENGTH) || SECRET_MARKER.test(request.message)) {
    errorReply("unsafe_chat");
    return;
  }
  bot.chat(request.message);
  reply({ ok: true, event: "chat_sent", text_length: request.message.length });
}

function readChat(request) {
  if (!bot || !exactKeys(request, ["op"])) {
    errorReply("not_attached");
    return;
  }
  const messages = chatInbox;
  chatInbox = [];
  reply({ ok: true, messages });
}

function stopMotion(request) {
  if (!exactKeys(request, ["op"]) || !bot) {
    errorReply("not_attached");
    return;
  }
  clearMotion();
  reply({ ok: true, event: "motion_stopped" });
}

function stop(request) {
  if (!exactKeys(request, ["op"])) {
    errorReply("invalid_stop");
    return;
  }
  stopping = true;
  stopMovementLog();
  movementLogPath = null;
  clearMotion();
  if (pathOverlay) {
    pathOverlay.erase(bot);
    pathOverlay = null;
  }
  closeBrowserViewer();
  if (bot && typeof bot.quit === "function") bot.quit("adapter stop");
  bot = null;
  reply({ ok: true, event: "stopped" });
  setTimeout(() => process.exit(0), 150);
}

async function handle(request) {
  if (!isObject(request) || typeof request.op !== "string") {
    errorReply("invalid_request");
    return;
  }
  if (request.op === "attach") return attach(request);
  if (request.op === "observe") {
    if (!exactKeys(request, ["op"]) || !bot) return errorReply("not_attached");
    try {
      reply({ ok: true, observation: observation() });
    } catch (_error) {
      errorReply("observation_failure");
    }
    return;
  }
  if (request.op === "move") return move(request);
  if (request.op === "look") return look(request);
  if (request.op === "navigate") return navigate(request);
  if (request.op === "goto") return gotoPos(request);
  if (request.op === "wood_to_table") return woodToTable(request);
  if (request.op === "dig") return dig(request);
  if (request.op === "craft") return craft(request);
  if (request.op === "place") return place(request);
  if (request.op === "chat") return chat(request);
  if (request.op === "read_chat") return readChat(request);
  if (request.op === "stop_motion") return stopMotion(request);
  if (request.op === "stop") return stop(request);
  errorReply("unsupported_operation");
}

const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
input.on("line", (line) => {
  if (!line.trim()) return errorReply("invalid_request");
  let request;
  try {
    request = JSON.parse(line);
  } catch (_error) {
    return errorReply("invalid_request");
  }
  Promise.resolve(handle(request)).catch(() => errorReply("client_failure"));
});
input.on("close", () => {
  stopMovementLog();
  movementLogPath = null;
  if (!stopping) {
    clearMotion();
    closeBrowserViewer();
    if (bot && typeof bot.quit === "function") bot.quit("adapter input closed");
  }
  process.exit(0);
});
