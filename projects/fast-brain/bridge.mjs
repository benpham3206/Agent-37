import http from 'node:http';
import net from 'node:net';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { URL, fileURLToPath } from 'node:url';

const moduleRoot = process.env.FAST_BRAIN_NODE_MODULES || 'D:\\Codex\\2026-08-26\\plea\\work\\mindcraft-ce\\node_modules';
const require = createRequire(`${moduleRoot}\\package.json`);
const mineflayer = require('mineflayer');
const THREE = require('three');
const { createCanvas } = require('node-canvas-webgl/lib');
const { Viewer, WorldView, getBufferFromStream } = require('prismarine-viewer/viewer');
const prismarineViewer = require('prismarine-viewer');
const { supportedVersions } = prismarineViewer;
const { WebSocketServer } = require('ws');

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC_DIR = path.join(HERE, 'public');
const VIEWER_PUBLIC = path.join(moduleRoot, 'prismarine-viewer', 'public');
const LOG_DIR = path.join(HERE, 'logs');
fs.mkdirSync(LOG_DIR, { recursive: true });

const HOST = process.env.FAST_BRAIN_BIND || '127.0.0.1';
const PORT = Number(process.env.FAST_BRAIN_PORT || 8876);
const MC_HOST = process.env.MC_HOST || '127.0.0.1';
const MC_PORT = Number(process.env.MC_PORT || 25565);
const MC_USERNAME = process.env.MC_USERNAME || 'FastBrain';
const MC_VERSION = process.env.MC_VERSION || undefined;
const WIDTH = Number(process.env.FAST_BRAIN_WIDTH || 400);
const HEIGHT = Number(process.env.FAST_BRAIN_HEIGHT || 225);
const FRAME_INTERVAL_MS = Number(process.env.FAST_BRAIN_FRAME_MS || 50);
const MOTOR_INTERVAL_MS = Number(process.env.FAST_BRAIN_MOTOR_MS || 20);
const ACTION_TTL_MS = Number(process.env.FAST_BRAIN_ACTION_TTL_MS || 120);
const FOV_DEG = Number(process.env.FAST_BRAIN_FOV || 70);
const VIEWER_PORT = Number(process.env.FAST_BRAIN_VIEWER_PORT || 8877);
const VIEWER_FOV_Y = 75 * Math.PI / 180; // prismarine-viewer browser default
const VIEW_DISTANCE = Number(process.env.FAST_BRAIN_VIEW_DISTANCE || 3);
const TEACHER_NAME = process.env.FAST_BRAIN_TEACHER || '6ento';
const MAX_BODY_BYTES = 64 * 1024;
const EYE_HEIGHT = 1.62;
const ENTITY_RADIUS = 24;
const ENTITY_EMIT_RADIUS = Number(process.env.FAST_BRAIN_ENTITY_EMIT_RADIUS || 16);
const PROJECTILE_RADIUS = 32;
const EVENT_REPLAY = 200;
const EVENT_RING = 2000;
const MAX_EVENTS_PER_TICK = 120;

const ARMOR_POINTS = { helmet: { leather: 1, chainmail: 2, iron: 2, golden: 2, diamond: 3, netherite: 3, turtle: 2 }, chestplate: { leather: 3, chainmail: 5, iron: 6, golden: 5, diamond: 8, netherite: 8 }, leggings: { leather: 2, chainmail: 4, iron: 5, golden: 3, diamond: 6, netherite: 6 }, boots: { leather: 1, chainmail: 1, iron: 2, golden: 1, diamond: 3, netherite: 3 } };
function armorPoints(equipment) {
    // entity.equipment: [main, off, boots, leggings, chestplate, helmet]
    if (!Array.isArray(equipment)) return null;
    let pts = 0;
    for (let i = 2; i <= 5; i++) {
        const name = equipment[i]?.name;
        if (!name) continue;
        const piece = name.endsWith('_helmet') ? 'helmet' : name.endsWith('_chestplate') ? 'chestplate' : name.endsWith('_leggings') ? 'leggings' : name.endsWith('_boots') ? 'boots' : name === 'turtle_helmet' ? 'helmet' : null;
        if (piece) pts += ARMOR_POINTS[piece][name.replace(`_${piece}`, '')] ?? 1;
    }
    return pts;
}

const PROJECTILE_NAMES = /small_fireball|fireball|arrow|trident|dragon_fireball|shulker_bullet|wither_skull|snowball|egg|llama_spit/;
const GRAVITY_PROJECTILES = /arrow|trident|snowball|egg/;
const BOI_NAMES = /_log$|^stone$|_ore$|^crafting_table$|^water$|^lava$/;

const BOOLS = ['forward', 'back', 'left', 'right', 'jump', 'sprint', 'sneak', 'attack', 'use'];
const emptyAction = () => ({
    forward: false, back: false, left: false, right: false, jump: false,
    sprint: false, sneak: false, attack: false, use: false,
    hotbar: null, yaw_delta: 0, pitch_delta: 0,
});

function finite(value, fallback = 0) {
    return Number.isFinite(Number(value)) ? Number(value) : fallback;
}

function clamp(value, lo, hi) {
    return Math.max(lo, Math.min(hi, value));
}

function round3(v) { return Math.round(v * 1000) / 1000; }

// pure: rotate teacher velocity into his yaw frame -> inferred held keys.
// MC convention: yaw 0 faces +z (south). fwd>0 = moving the way he looks.
export function inferTeacherInputs(vel, yaw, prevVy, flags = {}, swing = false) {
    const fwd = -Math.sin(yaw) * vel.x + Math.cos(yaw) * vel.z;
    const strafe = Math.cos(yaw) * vel.x + Math.sin(yaw) * vel.z;
    return {
        forward: fwd > 0.03, back: fwd < -0.03,
        left: strafe < -0.03, right: strafe > 0.03,
        jump: prevVy <= 0 && vel.y > 0.3,
        sneak: !!flags.sneaking, sprint: !!flags.sprinting,
        attack: !!swing, use: !!flags.using_item,
    };
}
function round2(v) { return Math.round(v * 100) / 100; }

function sanitizeAction(raw = {}) {
    const action = emptyAction();
    for (const key of BOOLS) action[key] = raw[key] === true;
    action.hotbar = Number.isInteger(raw.hotbar) && raw.hotbar >= 0 && raw.hotbar <= 8 ? raw.hotbar : null;
    action.yaw_delta = clamp(finite(raw.yaw_delta), -0.5, 0.5);
    action.pitch_delta = clamp(finite(raw.pitch_delta), -0.5, 0.5);
    return action;
}

function json(res, status, value) {
    const body = JSON.stringify(value);
    res.writeHead(status, { 'content-type': 'application/json', 'cache-control': 'no-store' });
    res.end(body);
}

function readBody(req) {
    return new Promise((resolve, reject) => {
        let body = '';
        req.setEncoding('utf8');
        req.on('data', chunk => {
            body += chunk;
            if (body.length > MAX_BODY_BYTES) reject(new Error('body_too_large'));
        });
        req.on('end', () => {
            try { resolve(JSON.parse(body || '{}')); } catch { reject(new Error('invalid_json')); }
        });
        req.on('error', reject);
    });
}

function vec(value) {
    return value ? { x: +Number(value.x).toFixed(3), y: +Number(value.y).toFixed(3), z: +Number(value.z).toFixed(3) } : null;
}

function chooseViewerVersion(version) {
    if (supportedVersions.includes(version)) return version;
    const major = String(version || '').split('.').slice(0, 2).join('.');
    return [...supportedVersions].reverse().find(candidate => candidate.startsWith(`${major}.`))
        || supportedVersions.at(-1)
        || version;
}

// Camera-space transform + pinhole projection (Agent-37 bridge/public/projection.js math).
function cameraPoint(point, self) {
    const dx = point.x - self.position.x;
    const dy = point.y - self.position.y - (self.eye_height ?? EYE_HEIGHT);
    const dz = point.z - self.position.z;
    const sy = Math.sin(self.yaw), cy = Math.cos(self.yaw);
    const sp = Math.sin(self.pitch), cp = Math.cos(self.pitch);
    return {
        x: cy * dx - sy * dz,
        y: sy * sp * dx + cp * dy + cy * sp * dz,
        z: -sy * cp * dx + sp * dy - cy * cp * dz,
    };
}

function projectPoint(point, width, height, fovY) {
    if (point.z < 0.05) return null;
    const focal = height / (2 * Math.tan(fovY / 2));
    return { x: width / 2 + focal * point.x / point.z, y: height / 2 - focal * point.y / point.z };
}

function projectAabb(aabb, self, width, height, fovY) {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    let anyFront = false;
    for (let i = 0; i < 8; i++) {
        const corner = {
            x: (i & 1 ? aabb.max : aabb.min).x,
            y: (i & 2 ? aabb.max : aabb.min).y,
            z: (i & 4 ? aabb.max : aabb.min).z,
        };
        const p = projectPoint(cameraPoint(corner, self), width, height, fovY);
        if (p === null) continue;
        anyFront = true;
        x0 = Math.min(x0, p.x); y0 = Math.min(y0, p.y);
        x1 = Math.max(x1, p.x); y1 = Math.max(y1, p.y);
    }
    if (!anyFront) return null;
    x0 = clamp(x0, 0, width); y0 = clamp(y0, 0, height);
    x1 = clamp(x1, 0, width); y1 = clamp(y1, 0, height);
    if (x1 <= x0 || y1 <= y0) return null;
    return [Math.round(x0), Math.round(y0), Math.round(x1), Math.round(y1)];
}

// yaw/pitch needed to look from eye position at target (mineflayer convention:
// yaw 0 = -Z, increasing yaw turns left; pitch + = up).
function lookAngles(from, target, eyeHeight = EYE_HEIGHT) {
    const dx = target.x - from.x;
    const dy = target.y - (from.y + eyeHeight);
    const dz = target.z - from.z;
    const yaw = Math.atan2(-dx, -dz);
    const pitch = Math.atan2(dy, Math.hypot(dx, dz));
    return { yaw, pitch };
}

function wrapAngle(a) {
    while (a > Math.PI) a -= 2 * Math.PI;
    while (a < -Math.PI) a += 2 * Math.PI;
    return a;
}

const CONTROL_PAGE = `<!doctype html><meta charset="utf-8"><title>fast-brain</title>
<style>
body{font:13px system-ui;background:#111;color:#ddd;margin:1rem}
#wrap{position:relative;display:inline-block}
#view{display:block;border:1px solid #444;cursor:crosshair}
#ov{position:absolute;inset:0;pointer-events:none}
#stop{background:#c22;color:#fff;font-size:1.6rem;padding:.4rem 1.6rem;border:0;border-radius:8px;cursor:pointer}
#resume{background:#284;color:#fff;padding:.4rem 1.4rem;border:0;border-radius:8px;cursor:pointer}
button{margin:.15rem}
#log{height:16em;overflow:auto;background:#181818;padding:.5rem;font:11px monospace;white-space:pre}
#hint{color:#888}
</style>
<div id="wrap"><img id="view" src="/v1/stream"><canvas id="ov"></canvas></div>
<p>
<button id="stop">STOP</button><button id="resume">RESUME</button>
<select id="skill"><option>approach</option><option>mine</option><option>attack</option><option>flee</option></select>
<select id="target"></select>
<button id="goskill">Run skill</button><button id="cancelskill">Cancel skill</button>
<label><input type="checkbox" id="verbose"> show per-tick events</label>
</p>
<div id="hint">Click the view + drag = draw goal box (unused for now). Click view & press WASD = human control (pointer lock). Esc releases.</div>
<pre id="log"></pre>
<script>
const W=${WIDTH},H=${HEIGHT};
const img=document.getElementById('view'),ov=document.getElementById('ov'),log=document.getElementById('log'),sel=document.getElementById('target');
ov.width=W;ov.height=H;ov.style.width=img.clientWidth+'px';ov.style.height=img.clientHeight+'px';
const ctx=ov.getContext('2d');
let targets=[],human={keys:{},active:false},keymap={KeyW:'forward',KeyS:'back',KeyA:'left',KeyD:'right',Space:'jump',ShiftLeft:'sneak',ShiftRight:'sneak',ControlLeft:'sprint'};
function say(m){log.textContent=new Date().toLocaleTimeString()+' '+m+'\\n'+log.textContent.split('\\n').slice(0,300).join('\\n')}
function draw(){ctx.clearRect(0,0,W,H);ctx.strokeStyle='#0f0';ctx.lineWidth=1.5;
 for(const t of targets){ctx.strokeRect(t.bbox[0],t.bbox[1],t.bbox[2]-t.bbox[0],t.bbox[3]-t.bbox[1]);ctx.fillStyle='#0f0';ctx.font='10px sans-serif';ctx.fillText(t.name,t.bbox[0],Math.max(9,t.bbox[1]-2))}
 requestAnimationFrame(draw)}
draw();
const es=new EventSource('/v1/events');
const PERTICK=new Set(['self','entity','projectile']);
es.onmessage=e=>{try{const ev=JSON.parse(e.data);if(PERTICK.has(ev.kind)&&!document.getElementById('verbose').checked)return;say(JSON.stringify(ev))}catch{}};
async function poll(){try{const t=await(await fetch('/v1/targets')).json();targets=t.targets||[];
 sel.innerHTML='';for(const t of targets){const o=document.createElement('option');o.value=JSON.stringify(t);o.textContent=t.kind+' '+t.name+' @'+t.distance;sel.appendChild(o)}}catch{};setTimeout(poll,2000)}
poll();
document.getElementById('stop').onclick=async()=>{const r=await fetch('/v1/stop',{method:'POST'});say('STOP -> '+r.status)};
document.getElementById('resume').onclick=async()=>{const r=await fetch('/v1/resume',{method:'POST'});say('resume -> '+r.status)};
document.getElementById('goskill').onclick=async()=>{const s=document.getElementById('skill').value;let args={};
 try{const t=JSON.parse(sel.value||'{}');if(t.kind==='entity')args={entity_id:t.id};else if(t.kind==='block')args={block_at:[t.position.x,t.position.y,t.position.z]}}catch{}
 const r=await fetch('/v1/skill',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({name:s,args})});say('skill '+s+' -> '+r.status+' '+(await r.text()))};
document.getElementById('cancelskill').onclick=async()=>{const r=await fetch('/v1/skill',{method:'DELETE'});say('cancel -> '+r.status)};
// human control: pointer lock on the view; posts key/mouse state every 100ms
async function sendHuman(){if(!human.active)return;const r=await fetch('/v1/input',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({keys:human.keys})}).catch(()=>null);setTimeout(sendHuman,100)}
img.addEventListener('click',()=>{img.requestPointerLock()});
document.addEventListener('pointerlockchange',()=>{human.active=document.pointerLockElement===img;
 if(human.active){say('human control ON');sendHuman()}else{say('human control OFF -> release');fetch('/v1/input',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({keys:{}})});human.keys={}}});
addEventListener('keydown',e=>{if(!human.active)return;const k=keymap[e.code];if(k){human.keys[k]=true;e.preventDefault()}if(e.code==='Digit1'||/Digit[1-9]/.test(e.code))human.hotbar=+e.code.slice(5)-1});
addEventListener('keyup',e=>{if(!human.active)return;const k=keymap[e.code];if(k){human.keys[k]=false;e.preventDefault()}});
addEventListener('mousedown',e=>{if(!human.active)return;if(e.button===0)human.keys.attack=true;if(e.button===2)human.keys.use=true});
addEventListener('mouseup',e=>{if(e.button===0)human.keys.attack=false;if(e.button===2)human.keys.use=false});
addEventListener('mousemove',e=>{if(!human.active)return;if(e.movementX||e.movementY)fetch('/v1/input',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({dyaw:-e.movementX*0.003,dpitch:-e.movementY*0.003})}).catch(()=>{})});
document.getElementById('view').addEventListener('contextmenu',e=>e.preventDefault());
</script>`;

class FastBrainBridge {
    constructor() {
        this.bot = null;
        this.botLifecycle = { state: 'left', error: null, generation: 0, viewer_generation: 0 };
        this.botGeneration = 0;
        this.viewer = null;
        this.worldView = null;
        this.renderer = null;
        this.canvas = null;
        this.frame = null;
        this.frameId = 0;
        this.captureBusy = false;
        this.captureMs = [];
        this.action = emptyAction();       // model action (POST /v1/action)
        this.actionSeq = 0;
        this.actionReceivedAt = 0;
        this.actionDeadline = 0;
        this.cameraAppliedSeq = 0;
        this.skillAction = emptyAction();  // reflex action, rewritten per tick by skill
        this.skillActive = false;
        this.human = { keys: {}, until: 0 };
        this.held = {};                    // last applied control states -> for key events
        this.prevHeldAttack = false;
        this.prevHeldUse = false;
        this.diggingTarget = null;
        this.lastAttackAt = 0;
        this.startedAt = Date.now();
        this.connected = false;
        this.stopped = false;
        this.halted = false;
        this.respawned = false;
        this.server = null;
        this.motorTimer = null;
        this.frameTimer = null;
        // event sensor state
        this.tick = 0;
        this.eventRing = [];
        this.sseClients = new Set();
        this.eventsThisTick = 0;
        this.droppedThisTick = 0;
        this.lastSelf = null;
        this.lastVel = null;
        this.lastAccel = null;
        this.lastInv = new Map();
        this.entityTrack = new Map(); // id -> {pos, vel, name, category, health, lastEmitted:{pos,dist}}
        this.projectileTrack = new Map(); // id -> {prevPos, vel}
        this.keyframeData = null;
        this.sysMessages = [];
        this.gameTick = 0;
        this.emittedWindow = [];
        this.droppedWindow = [];
        this.skill = null;
        this.reflexes = { block_projectiles: { enabled: true, useUntil: 0, strafe: null } };
        // cockpit (Agent-37-style) state
        this.wsClients = new Map(); // socket -> lastSeen ms
        this.uiTarget = 'zombie';
        this.recording = { state: 'idle', encounter_id: null };
        this.lastHit = null; // {t, amount}
        this.viewerPort = null;
        this.viewerError = null;
        this.viewerGeneration = 0;
        this.wss = null;
        this.stateTimer = null;
        // lazy frame capture: render only while demanded
        this.mjpegClients = 0;
        this.frameDemandUntil = 0;
        // teacher tracking (player FAST_BRAIN_TEACHER, default 6ento)
        this.teacher = {
            pos: null, vel: null, lastEmittedVel: null,
            look: null, flags: {}, held: {}, inputs: null,
            fallTicks: 0, falling: false, prevVy: 0,
            health: null, food: null, air: null, dimension: null, inv: new Map(),
            online: false, pollMisses: 0, pollBackoff: 1000, lastPoll: 0, metaLogged: false,
        };
        this.selfFalling = { ticks: 0, falling: false };
        // absolute look target shared by human/model/reflex; deltas accumulate
        // so sub-quantum (0.15 deg) increments are never dropped by bot.look.
        this.lookTarget = null; // {yaw, pitch} absolute
        this.lookPending = false;
        this.lookSrc = 'model';
        this.loadoutDue = 0;
        this.trajPath = null;
        this.sensorMs = [];
        this.sessionTs = new Date().toISOString().replace(/[:.]/g, '-');
        this.trajPath = path.join(LOG_DIR, `trajectory-${this.sessionTs}.jsonl`);
        this.traj = fs.createWriteStream(this.trajPath, { flags: 'a' });
        this.advLogged = false;
    }

    // ---------------- event sensor ----------------
    emit(kind, fields = {}) {
        if (this.eventsThisTick >= MAX_EVENTS_PER_TICK) { this.droppedThisTick++; return; }
        this.eventsThisTick++;
        const ev = { tick: this.tick, game_tick: this.gameTick, t_ms: Date.now(), kind, ...fields };
        this.eventRing.push(ev);
        if (this.eventRing.length > EVENT_RING) this.eventRing.shift();
        const line = JSON.stringify(ev);
        // Backpressure guard: never let the trajectory write block the tick.
        // Entity 'move' events are droppable; everything else is always written.
        if (!(kind === 'entity' && fields.field === 'move' && this.traj.writableLength > 4 * 1024 * 1024)) {
            this.traj.write(line + '\n');
        } else {
            this.droppedThisTick++;
        }
        const sse = `data: ${line}\n\n`;
        for (const res of this.sseClients) { try { res.write(sse); } catch { this.sseClients.delete(res); } }
    }

    rateTick() {
        const now = Date.now();
        this.emittedWindow.push({ t: now, n: this.eventsThisTick });
        this.droppedWindow.push({ t: now, n: this.droppedThisTick });
        while (this.emittedWindow.length && now - this.emittedWindow[0].t > 1000) this.emittedWindow.shift();
        while (this.droppedWindow.length && now - this.droppedWindow[0].t > 1000) this.droppedWindow.shift();
    }

    eventsPerSec() {
        return this.emittedWindow.reduce((s, w) => s + w.n, 0);
    }

    droppedPerSec() {
        return this.droppedWindow.reduce((s, w) => s + w.n, 0);
    }

    onPhysicsTick() {
        const t0 = performance.now();
        this.tick++;
        this.eventsThisTick = 0;
        this.droppedThisTick = 0;
        const bot = this.bot;
        const e = bot?.entity;
        if (!e) { this.rateTick(); return; }
        this.gameTick = bot.time?.age ?? 0;
        // ---- self: dead reckoning — emit corrections, not state ----
        const pos = e.position, vel = e.velocity;
        if (this.lastSelf && this.lastVel) {
            const expected = { x: this.lastSelf.position.x + this.lastVel.x, y: this.lastSelf.position.y + this.lastVel.y, z: this.lastSelf.position.z + this.lastVel.z };
            if (Math.abs(pos.x - expected.x) > 0.05 || Math.abs(pos.y - expected.y) > 0.05 || Math.abs(pos.z - expected.z) > 0.05) {
                this.emit('self', { field: 'correction', expected: vec(expected), actual: vec(pos), vel: vec(vel) });
            }
        }
        const cur = {
            health: bot.health, food: bot.food, on_ground: e.onGround,
            in_water: e.isInWater ?? null, xp: bot.experience?.level ?? null,
            yaw: round3(e.yaw), pitch: round3(e.pitch),
        };
        if (this.lastSelf) {
            for (const f of ['health', 'food', 'on_ground', 'in_water', 'xp']) {
                if (cur[f] !== this.lastSelf[f]) {
                    if (f === 'health' && cur[f] < this.lastSelf[f]) {
                        const amount = this.lastSelf[f] - cur[f];
                        this.lastHit = { t: Date.now(), amount };
                        this.emit('damage', { amount });
                    }
                    this.emit('self', { field: f, from: this.lastSelf[f], to: cur[f] });
                }
            }
        }
        this.lastVel = { x: vel.x, y: vel.y, z: vel.z };
        this.lastSelf = { position: vec(pos), velocity: vec(vel), ...cur };
        // ---- inventory diff ----
        const inv = new Map();
        for (const item of bot.inventory?.items?.() ?? []) inv.set(item.name, (inv.get(item.name) ?? 0) + item.count);
        const names = new Set([...inv.keys(), ...this.lastInv.keys()]);
        for (const name of names) {
            const a = this.lastInv.get(name) ?? 0, b = inv.get(name) ?? 0;
            if (a !== b) { this.emit('inventory', { item: name, delta: b - a, count: b }); this.loadoutDue = Date.now() + 1000; }
        }
        this.lastInv = inv;
        // ---- entities ----
        const seen = new Set();
        const moveCandidates = [];
        for (const ent of Object.values(bot.entities)) {
            if (!ent?.position || ent === e) continue;
            const d = ent.position.distanceTo(pos);
            const isProjectile = PROJECTILE_NAMES.test(ent.name ?? '');
            if (d > ENTITY_RADIUS && !isProjectile) continue;
            seen.add(ent.id);
            const category = this.entityKind(ent);
            const prev = this.entityTrack.get(ent.id);
            if (!prev) {
                this.emit('entity', { id: ent.id, name: ent.name ?? 'entity', category, field: 'spawn', to: vec(ent.position) });
                this.entityTrack.set(ent.id, { pos: vec(ent.position), vel: { x: 0, y: 0, z: 0 }, name: ent.name, category, health: ent.health, lastEmittedVel: null });
                continue;
            }
            const v = { x: ent.position.x - prev.pos.x, y: ent.position.y - prev.pos.y, z: ent.position.z - prev.pos.z };
            const hp = ent.health;
            if (prev.health != null && hp != null && hp < prev.health) {
                this.emit('entity', { id: ent.id, name: ent.name ?? 'entity', category, field: 'hurt', from: prev.health, to: hp });
            }
            // emit motion only when velocity changed > 0.03 b/tick on any axis
            // (or first sighting); a mob walking straight = one event, standing = zero.
            const lv = prev.lastEmittedVel;
            const velChanged = !lv || Math.abs(v.x - lv.x) > 0.03 || Math.abs(v.y - lv.y) > 0.03 || Math.abs(v.z - lv.z) > 0.03;
            const emitsThisTick = (isProjectile || (category !== 'item' && velChanged)) && (isProjectile || d <= ENTITY_RADIUS);
            if (emitsThisTick && category !== 'item') {
                moveCandidates.push({ ent, d, v, category });
            }
            this.entityTrack.set(ent.id, {
                pos: vec(ent.position), vel: v, name: ent.name, category, health: hp,
                lastEmittedVel: emitsThisTick ? v : lv,
            });
        }
        // cap-aware: emit nearest moves first so the farthest are dropped
        moveCandidates.sort((a, b) => a.d - b.d);
        for (const c of moveCandidates) {
            this.emit('entity', { id: c.ent.id, name: c.ent.name ?? 'entity', category: c.category, field: 'motion', pos: vec(c.ent.position), vel: vec(c.v), dist: round2(c.d) });
        }
        for (const [id, prev] of this.entityTrack) {
            if (!seen.has(id)) { this.emit('entity', { id, name: prev.name, category: prev.category, field: 'despawn' }); this.entityTrack.delete(id); this.projectileTrack.delete(id); }
        }
        // ---- projectiles ----
        for (const ent of Object.values(bot.entities)) {
            if (!ent?.position || !PROJECTILE_NAMES.test(ent.name ?? '')) continue;
            const d = ent.position.distanceTo(pos);
            if (d > PROJECTILE_RADIUS) { this.projectileTrack.delete(ent.id); continue; }
            const prev = this.projectileTrack.get(ent.id);
            const v = prev ? { x: ent.position.x - prev.pos.x, y: ent.position.y - prev.pos.y, z: ent.position.z - prev.pos.z } : { x: 0, y: 0, z: 0 };
            const speed = Math.hypot(v.x, v.y, v.z);
            const closing = prev ? round3(prev.dist - d) : 0;
            let tti = null, willHit = false;
            if (speed > 0.02) {
                const grav = GRAVITY_PROJECTILES.test(ent.name) ? 0.05 : 0;
                const drag = GRAVITY_PROJECTILES.test(ent.name) ? 0.99 : 1;
                let px = ent.position.x, py = ent.position.y, pz = ent.position.z;
                let vx = v.x, vy = v.y, vz = v.z;
                for (let t = 1; t <= 40; t++) {
                    px += vx; py += vy; pz += vz;
                    if (grav) { vx *= drag; vz *= drag; vy = vy * drag - grav; }
                    const ex = 0.6;
                    if (Math.abs(px - pos.x) <= 0.3 + ex && py >= pos.y - ex && py <= pos.y + 1.8 + ex && Math.abs(pz - pos.z) <= 0.3 + ex) {
                        willHit = true; tti = t; break;
                    }
                }
            }
            this.emit('projectile', { id: ent.id, name: ent.name, distance: round2(d), closing_speed_bpt: closing, tti_ticks: tti, will_hit: willHit });
            this.projectileTrack.set(ent.id, { pos: { x: ent.position.x, y: ent.position.y, z: ent.position.z }, dist: d, willHit, tti });
        }
        // ---- self falling (for cockpit HUD) ----
        if (vel.y < -0.6) this.selfFalling.ticks++; else this.selfFalling.ticks = 0;
        if (!this.selfFalling.falling && this.selfFalling.ticks >= 3) this.selfFalling.falling = true;
        if (this.selfFalling.falling && (e.onGround || vel.y >= -0.1)) this.selfFalling.falling = false;
        // ---- teacher tracking ----
        this.trackTeacher();
        // ---- loadout watchdog (debounced: loadoutDue set by inventory diffs/spawn) ----
        if (this.loadoutDue && Date.now() >= this.loadoutDue) { this.loadoutDue = 0; this.checkLoadout(); }
        // ---- reflex: block_projectiles ----
        this.reflexBlockProjectiles();
        // ---- skill step ----
        if (this.skill) this.stepSkill();
        // ---- keyframe ----
        if (this.tick % 40 === 0) this.buildKeyframe();
        if (this.droppedThisTick) { const n = this.droppedThisTick; this.droppedThisTick = 0; this.emit('dropped', { n }); }
        this.rateTick();
        const ms = performance.now() - t0;
        this.sensorMs.push(ms);
        if (this.sensorMs.length > 400) this.sensorMs.shift();
        if (this.tick % 200 === 0) {
            const s = [...this.sensorMs].sort((a, b) => a - b);
            console.log(`sensor p50=${s[Math.floor(s.length / 2)].toFixed(1)}ms p95=${s[Math.floor(s.length * 0.95)].toFixed(1)}ms tick=${this.tick} eps=${this.eventsPerSec()}`);
        }
    }

    entityKind(ent) {
        const t = ent.type;
        if (t === 'player') return 'player';
        if (PROJECTILE_NAMES.test(ent.name ?? '') || t === 'projectile') return 'projectile';
        if (t === 'mob' || t === 'hostile') return 'mob';
        if (t === 'animal') return 'animal';
        if (t === 'orb' || ent.name === 'item' || ent.displayName === 'Item') return 'item';
        return 'other';
    }

    buildKeyframe() {
        const bot = this.bot, e = bot?.entity;
        if (!e) return;
        const inv = [];
        for (const item of bot.inventory?.items?.() ?? []) inv.push({ name: item.name, count: item.count });
        const entities = [];
        for (const ent of Object.values(bot.entities)) {
            if (!ent?.position || ent === e) continue;
            const d = ent.position.distanceTo(e.position);
            if (d <= ENTITY_RADIUS) entities.push({ id: ent.id, name: ent.name ?? 'entity', category: this.entityKind(ent), position: vec(ent.position), velocity: vec(this.entityTrack.get(ent.id)?.vel ?? { x: 0, y: 0, z: 0 }), distance: round2(d) });
        }
        const boi = [];
        try {
            const ids = [];
            for (const [name, b] of Object.entries(bot.registry?.blocksByName ?? {})) if (BOI_NAMES.test(name)) ids.push(b.id);
            for (const pos of bot.findBlocks({ matching: ids, maxDistance: 16, count: 48 })) {
                const block = bot.blockAt(pos);
                if (block) boi.push({ name: block.name, at: vec(pos), distance: round2(pos.distanceTo(e.position)) });
            }
        } catch { }
        this.keyframeData = {
            self: { position: vec(e.position), velocity: vec(e.velocity), yaw: round3(e.yaw), pitch: round3(e.pitch), health: bot.health, food: bot.food, xp: bot.experience?.level ?? null, on_ground: e.onGround, in_water: e.isInWater ?? null, held_item: bot.heldItem?.name ?? null, inventory: inv },
            entities, blocks_of_interest: boi,
            sensor: { events_per_sec: this.eventsPerSec(), dropped_per_sec: this.droppedPerSec(), sensor_ms_p50: this.sensorMs.length ? [...this.sensorMs].sort((a, b) => a - b)[Math.floor(this.sensorMs.length / 2)] : null },
            teacher: this.teacher.online ? {
                position: this.teacher.pos, vel: this.teacher.vel ? vec(this.teacher.vel) : null,
                yaw: this.teacher.look?.yaw ?? null, pitch: this.teacher.look?.pitch ?? null,
                health: this.teacher.health, food: this.teacher.food,
                held_item: this.teacher.held, flags: this.teacher.flags, falling: this.teacher.falling,
            } : null,
            dimension: bot.game?.dimension ?? null,
            time_of_day: bot.time?.timeOfDay ?? null,
            game_tick: bot.time?.age ?? null,
        };
        this.emit('keyframe', this.keyframeData);
    }

    // ---------------- reflexes & skills ----------------
    reflexBlockProjectiles() {
        const r = this.reflexes.block_projectiles;
        if (!r.enabled || this.halted || !this.bot?.entity) return;
        const now = this.tick;
        let threat = null;
        for (const [id, p] of this.projectileTrack) {
            if (p.willHit && p.tti != null && p.tti <= 7) { threat = { id, ...p }; break; }
        }
        if (r.strafe && now >= r.strafe.until) { this.skillAction.left = false; this.skillAction.right = false; r.strafe = null; }
        if (!threat) {
            if (r.useUntil && now >= r.useUntil) { this.skillAction.use = false; r.useUntil = 0; }
            return;
        }
        const hasShield = this.bot.inventory?.slots?.[45]?.name === 'shield';
        if (hasShield) {
            this.skillAction.use = true;
            r.useUntil = now + threat.tti + 3;
            this.emit('reflex', { name: 'block', projectile_id: threat.id, tti_ticks: threat.tti });
        } else {
            const p = this.projectileTrack.get(threat.id);
            const ent = this.bot.entities[threat.id];
            if (ent) {
                const v = p?.vel ?? { x: 0, z: 0 };
                // strafe perpendicular to projectile travel direction
                const fwd = { x: -Math.sin(this.bot.entity.yaw), z: -Math.cos(this.bot.entity.yaw) };
                const side = Math.sign(v.x * fwd.z - v.z * fwd.x) || 1;
                this.skillAction.left = side > 0; this.skillAction.right = side < 0;
                this.skillAction.sprint = true;
                r.strafe = { until: now + threat.tti + 3 };
                this.emit('reflex', { name: 'sidestep', projectile_id: threat.id, tti_ticks: threat.tti });
            }
        }
    }

    startSkill(name, args) {
        if (this.skill) return { error: 'skill_busy', current: this.skill.name };
        const skill = { name, args, started_tick: this.tick, done: null, strafe: null };
        if (!this.makeSkillStep(skill)) return { error: 'bad_args' };
        this.skill = skill;
        this.skillActive = true;
        this.emit('skill', { name, field: 'start', args });
        return { started: true };
    }

    makeSkillStep(skill) {
        const bot = this.bot;
        const a = skill.args ?? {};
        const timeout = a.timeout_ticks ?? (skill.name === 'tactical' ? 6000 : (skill.name === 'approach' || skill.name === 'flee' ? 400 : 600));
        const targetPos = () => {
            if (a.entity_id != null) return this.bot.entities[a.entity_id]?.position ?? null;
            if (a.block_at) return { x: a.block_at[0] + 0.5, y: a.block_at[1] + 0.5, z: a.block_at[2] + 0.5 };
            if (a.position) return a.position;
            return null;
        };
        const targetEntity = () => (a.entity_id != null ? this.bot.entities[a.entity_id] : null);
        skill.timeout = timeout;
        switch (skill.name) {
            case 'approach':
                if (a.entity_id == null && !a.block_at && !a.position) return false;
                skill.step = (act) => {
                    const t = targetPos(); if (!t) return { done: false, reason: 'target_lost' };
                    const dist = Math.hypot(t.x - bot.entity.position.x, t.z - bot.entity.position.z);
                    if (dist <= (a.stop_distance ?? 2.5)) return { done: true, result: { distance: round2(dist) } };
                    this.faceToward(t, act);
                    act.forward = true; act.sprint = dist > 4;
                    if (bot.entity.isCollidedHorizontally) act.jump = true;
                    return null;
                };
                return true;
            case 'mine':
                if (!a.block_at) return false;
                skill.step = (act) => {
                    const bp = { x: a.block_at[0], y: a.block_at[1], z: a.block_at[2] };
                    const center = { x: bp.x + 0.5, y: bp.y + 0.5, z: bp.z + 0.5 };
                    const block = bot.blockAt(center) ?? bot.blockAt(bp);
                    if (!block || block.name === 'air' || block.boundingBox === 'empty') return { done: true, result: { mined: true } };
                    const dist = Math.hypot(center.x - bot.entity.position.x, center.z - bot.entity.position.z);
                    if (dist > 4) {
                        this.faceToward(center, act);
                        act.forward = true; act.sprint = dist > 6;
                        if (bot.entity.isCollidedHorizontally) act.jump = true;
                    } else {
                        this.faceToward(center, act);
                        act.attack = true; // bridge digs the block under the cursor while held
                    }
                    return null;
                };
                return true;
            case 'attack':
                if (a.entity_id == null) return false;
                skill.lastSwing = 0;
                skill.strafeSide = 1;
                skill.step = (act) => {
                    const ent = targetEntity();
                    if (!ent) return { done: true, result: { killed: true } };
                    const dist = ent.position.distanceTo(bot.entity.position);
                    this.faceToward({ x: ent.position.x, y: ent.position.y + (ent.height ?? 1.6) * 0.8, z: ent.position.z }, act);
                    if (dist > 3) { act.forward = true; act.sprint = dist > 5; }
                    if (bot.entity.isCollidedHorizontally) act.jump = true;
                    if (this.tick - skill.lastSwing >= 12 && dist <= 3.5) {
                        skill.lastSwing = this.tick;
                        try { bot.attack(ent); } catch { }
                        this.emit('swing', { src: 'reflex', target: ent.id });
                    }
                    if (this.tick % 20 === 0) skill.strafeSide *= -1;
                    act.left = skill.strafeSide < 0; act.right = skill.strafeSide > 0;
                    return null;
                };
                return true;
            case 'flee':
                if (a.entity_id == null && !a.from && !a.position) return false;
                skill.step = (act) => {
                    const t = a.entity_id != null ? this.bot.entities[a.entity_id]?.position : (a.from ?? a.position);
                    if (!t) return { done: false, reason: 'source_lost' };
                    const dist = t.distanceTo ? t.distanceTo(bot.entity.position) : Math.hypot(t.x - bot.entity.position.x, t.z - bot.entity.position.z);
                    if (dist >= (a.distance ?? 12)) return { done: true, result: { distance: round2(dist) } };
                    // face away from the threat
                    const away = { x: 2 * bot.entity.position.x - t.x, y: bot.entity.position.y + EYE_HEIGHT, z: 2 * bot.entity.position.z - t.z };
                    this.faceToward(away, act);
                    act.forward = true; act.sprint = true; act.jump = true;
                    return null;
                };
                return true;
            case 'tactical': {
                if (a.entity_id == null) return false;
                skill.tactic = null;
                skill.tacticSeq = 0;
                skill.tacticDeadline = 0;
                skill.lastSwing = 0;
                skill.step = (act) => {
                    const ent = targetEntity();
                    if (!ent) return { done: true, result: { target_lost: true } };
                    const t = skill.tactic;
                    const live = t && Date.now() <= skill.tacticDeadline;
                    if (live && t.movement === 'disengage') {
                        // face away and run — flee behavior without ending the skill
                        const away = { x: 2 * bot.entity.position.x - ent.position.x, y: bot.entity.position.y + EYE_HEIGHT, z: 2 * bot.entity.position.z - ent.position.z };
                        this.faceToward(away, act);
                        act.forward = true; act.sprint = true; act.jump = true;
                        return null;
                    }
                    this.faceToward({ x: ent.position.x, y: ent.position.y + (ent.height ?? 1.6) * 0.8, z: ent.position.z }, act);
                    if (!live) return null; // fail-closed hold: no movement, no attack
                    const dist = ent.position.distanceTo(bot.entity.position);
                    if (t.movement === 'advance') act.forward = true;
                    else if (t.movement === 'back_off') act.back = true;
                    else if (t.movement === 'strafe_left') act.left = true;
                    else if (t.movement === 'strafe_right') act.right = true;
                    act.sprint = !!t.sprint && (t.movement === 'advance' || t.movement === 'back_off');
                    act.jump = !!t.jump || !!bot.entity.isCollidedHorizontally;
                    act.use = !!t.block; // shield/block through the 'use' edge path
                    if (t.attack && dist <= 3.5 && this.tick - skill.lastSwing >= 12) {
                        skill.lastSwing = this.tick;
                        try { bot.attack(ent); } catch { }
                        this.emit('swing', { src: 'tactical', target: ent.id });
                    }
                    return null;
                };
                return true;
            }
            default:
                return false;
        }
    }

    faceToward(target, act) {
        const e = this.bot.entity;
        const want = lookAngles(e.position, target);
        const dyaw = wrapAngle(want.yaw - e.yaw);
        const dpitch = wrapAngle(want.pitch - e.pitch);
        const maxTurn = 15 * Math.PI / 180;
        const ay = clamp(dyaw, -maxTurn, maxTurn), ap = clamp(dpitch, -maxTurn, maxTurn);
        if (Math.abs(ay) > 0.003 || Math.abs(ap) > 0.003) this.queueLookDelta(ay, ap, 'reflex');
    }

    // ---------------- look seam ----------------
    // One absolute target for all sources; deltas accumulate (no per-message
    // clamp) so bot.look's 0.15 deg per-call quantization can't drop small
    // increments. Applied once per motor tick.
    queueLookDelta(dyaw, dpitch, src) {
        const e = this.bot?.entity;
        if (!e || (!dyaw && !dpitch)) return;
        if (!this.lookTarget) this.lookTarget = { yaw: e.yaw, pitch: e.pitch };
        this.lookTarget.yaw += dyaw;
        this.lookTarget.pitch = clamp(this.lookTarget.pitch + dpitch, -Math.PI / 2, Math.PI / 2);
        this.lookSrc = src;
        this.lookPending = true;
    }

    syncLookTarget() {
        const e = this.bot?.entity;
        if (e && this.lookTarget) { this.lookTarget.yaw = e.yaw; this.lookTarget.pitch = e.pitch; }
    }

    applyLook() {
        const e = this.bot?.entity;
        if (!this.lookPending || !e || !this.lookTarget) return;
        const dyaw = wrapAngle(this.lookTarget.yaw - e.yaw);
        const dpitch = clamp(this.lookTarget.pitch, -Math.PI / 2, Math.PI / 2) - e.pitch;
        if (Math.abs(dyaw) < 1e-4 && Math.abs(dpitch) < 1e-4) { this.lookPending = false; return; }
        // sub-quantum residual: bot.look can't apply it; keep it pending so it
        // accumulates with the next deltas instead of spamming look events
        if (Math.abs(dyaw) < 0.0014 && Math.abs(dpitch) < 0.0014) return;
        const STEP = 1.2; // rad per 20 ms tick; overshoot carries to next tick
        const ay = clamp(dyaw, -STEP, STEP), ap = clamp(dpitch, -STEP, STEP);
        this.bot.look(e.yaw + ay, clamp(e.pitch + ap, -Math.PI / 2, Math.PI / 2), true);
        this.emit('look', { dyaw_deg: round2(ay * 180 / Math.PI), dpitch_deg: round2(ap * 180 / Math.PI), yaw: round3(e.yaw), pitch: round3(e.pitch), src: this.lookSrc });
    }

    stepSkill() {
        const s = this.skill;
        if (!s) return;
        if (this.halted) { this.finishSkill({ done: false, reason: 'halted' }); return; }
        if (this.tick - s.started_tick > s.timeout) { this.finishSkill({ done: false, reason: 'timeout' }); return; }
        let result = null;
        try { result = s.step(this.skillAction); } catch (err) { this.finishSkill({ done: false, reason: `error:${err.message}` }); return; }
        if (result) this.finishSkill(result);
    }

    finishSkill(result) {
        const s = this.skill;
        this.skill = null;
        this.skillAction = emptyAction();
        this.skillActive = false;
        this.emit('skill', { name: s?.name, field: result.done ? 'done' : 'fail', ...(result.done ? { result: result.result } : { reason: result.reason }) });
    }

    // ---------------- teacher tracking ----------------
    // Entity metadata indexes (server protocol, verified against minecraft-data
    // for 26.1.2 — shared-entity layout is stable since 1.9):
    //   index 0 (byte): 0x01 on_fire, 0x02 sneaking, 0x08 sprinting, 0x10 swimming(legacy)
    //   index 6 (pose enum): 1=fall_flying(elytra), 3=swimming, 5=sneaking
    //   index 8 (living-entity flags byte): 0x01 hand active (using item), 0x02 offhand
    trackTeacher() {
        const bot = this.bot;
        const ent = bot?.players?.[TEACHER_NAME]?.entity;
        const t = this.teacher;
        if (!ent?.position || !bot?.entity) {
            if (t.online) { t.online = false; this.emit('teacher', { name: TEACHER_NAME, field: 'offline' }); }
            return;
        }
        if (!t.online) {
            t.online = true;
            this.emit('teacher', { name: TEACHER_NAME, field: 'online' });
            t.pos = null; t.vel = null; t.look = null; t.flags = {}; t.held = {}; t.inputs = null;
        }
        if (!t.metaLogged && ent.metadata) {
            t.metaLogged = true;
            console.log(`teacher metadata sample: ${JSON.stringify(ent.metadata)}`);
        }
        const pos = ent.position;
        const vel = t.pos ? { x: pos.x - t.pos.x, y: pos.y - t.pos.y, z: pos.z - t.pos.z } : { x: 0, y: 0, z: 0 };
        // pose correction (dead reckoning): expected = lastPos + lastVel
        if (t.pos && t.vel) {
            const expected = { x: t.pos.x + t.vel.x, y: t.pos.y + t.vel.y, z: t.pos.z + t.vel.z };
            if (Math.abs(pos.x - expected.x) > 0.05 || Math.abs(pos.y - expected.y) > 0.05 || Math.abs(pos.z - expected.z) > 0.05) {
                this.emit('teacher', { name: TEACHER_NAME, field: 'pose_correction', expected: vec(expected), actual: vec(pos), vel: vec(vel) });
            }
        }
        // look
        const yaw = ent.yaw ?? 0, pitch = ent.pitch ?? 0;
        if (t.look) {
            let dyaw = yaw - t.look.yaw;
            while (dyaw > Math.PI) dyaw -= 2 * Math.PI;
            while (dyaw < -Math.PI) dyaw += 2 * Math.PI;
            const dpitch = pitch - t.look.pitch;
            if (Math.abs(dyaw) > 0.0087 || Math.abs(dpitch) > 0.0087) {
                this.emit('teacher', { name: TEACHER_NAME, field: 'look', yaw: round3(yaw), pitch: round3(pitch), dyaw: round3(dyaw), dpitch: round3(dpitch) });
            }
        }
        t.look = { yaw, pitch };
        // metadata flags
        const m = ent.metadata ?? [];
        const b0 = Number(m[0]) || 0;
        const pose = Number(m[6]);
        const living = Number(m[8]) || 0;
        const flags = {
            on_fire: !!(b0 & 0x01), sneaking: !!(b0 & 0x02), sprinting: !!(b0 & 0x08),
            swimming: pose === 3 || !!(b0 & 0x10), elytra: pose === 1,
            using_item: !!(living & 0x01),
        };
        for (const [flag, on] of Object.entries(flags)) {
            if (t.flags[flag] !== on) { this.emit('teacher', { name: TEACHER_NAME, field: 'flag', flag, to: on }); t.flags[flag] = on; }
        }
        // held items (main hand = heldItem, off hand = equipment[4])
        const held = { main: ent.heldItem?.name ?? null, off: ent.equipment?.[4]?.name ?? null };
        for (const slot of ['main', 'off']) {
            if (t.held[slot] !== held[slot]) { this.emit('teacher', { name: TEACHER_NAME, field: 'held_item', slot, item: held[slot] }); t.held[slot] = held[slot]; }
        }
        // inferred inputs: rotate velocity into yaw frame (MC yaw 0 = +z south)
        const inputs = inferTeacherInputs(vel, yaw, t.prevVy, flags, !!t.swingNow);
        const key = Object.entries(inputs).map(([k, v]) => v ? k : '').join(',');
        if (t.inputs !== key) {
            t.inputs = key;
            this.emit('teacher', { name: TEACHER_NAME, field: 'input_inferred', ...inputs });
        }
        // falling situation: vy < -0.6 for 3 ticks AND no solid block within 4 below feet
        if (vel.y < -0.6) t.fallTicks++; else t.fallTicks = 0;
        if (!t.falling && t.fallTicks >= 3) {
            let solidBelow = false;
            try {
                for (let i = 1; i <= 4 && !solidBelow; i++) {
                    const b = bot.blockAt({ x: Math.floor(pos.x), y: Math.floor(pos.y) - i, z: Math.floor(pos.z) });
                    if (b && b.boundingBox === 'block') solidBelow = true;
                }
            } catch { }
            if (!solidBelow) {
                t.falling = true;
                this.emit('teacher', { name: TEACHER_NAME, field: 'falling', to: true, vy: round3(vel.y), blocks_below: 4 });
            }
        } else if (t.falling && (ent.onGround || vel.y >= -0.1)) {
            t.falling = false;
            this.emit('teacher', { name: TEACHER_NAME, field: 'falling', to: false, vy: round3(vel.y), blocks_below: 0 });
        }
        t.prevVy = vel.y;
        t.pos = { x: pos.x, y: pos.y, z: pos.z };
        t.vel = vel;
        t.swingNow = false;
    }

    // 1 Hz SNBT poll for health/food/air/dimension/inventory (player data is not
    // in entity packets). Bypasses the /v1/command rate limit — internal path.
    teacherPoll() {
        const t = this.teacher, now = Date.now();
        if (!this.connected || this.halted) return;
        if (!t.online && now - t.lastPoll < 10000) return;
        if (t.online && now - t.lastPoll < t.pollBackoff) return;
        if (t.pendingSince && now - t.pendingSince < 2500) return; // previous poll still in flight
        if (t.pendingSince) { // poll went unanswered
            t.pollMisses++;
            if (t.pollMisses >= 3) t.pollBackoff = 10000;
            if (t.pollMisses === 3) this.emit('teacher', { name: TEACHER_NAME, field: 'poll_error', misses: t.pollMisses });
        }
        // full-dump /data get is ~4KB+ and truncates before Health; poll one
        // path per tick and rotate so each field refreshes ~every 6 s.
        const PATHS = ['Health', 'foodLevel', 'Air', 'Dimension', 'SelectedItemSlot', 'Inventory'];
        t.pollPath = PATHS[(t.pollIdx = (t.pollIdx ?? 0) + 1) % PATHS.length];
        t.pendingSince = now;
        t.lastPoll = now;
        try { this.bot.chat(`/data get entity ${TEACHER_NAME} ${t.pollPath}`); } catch { }
    }

    teacherDataReply(text) {
        const t = this.teacher;
        t.pendingSince = 0;
        t.pollMisses = 0;
        t.pollBackoff = 1000;
        // reply shape: "<name> has the following entity data: <value>"
        const i = text.indexOf('entity data:');
        if (i < 0) return;
        const val = text.slice(i + 'entity data:'.length).trim();
        const num = parseFloat(val);
        const fieldMap = { Health: 'health', foodLevel: 'food', Air: 'air', Dimension: 'dimension', SelectedItemSlot: 'held_slot' };
        const field = fieldMap[t.pollPath];
        if (field) {
            const v = t.pollPath === 'Dimension' ? val.replace(/^"|"$/g, '') : (Number.isFinite(num) ? num : null);
            if (v != null && t[field] !== v) { this.emit('teacher', { name: TEACHER_NAME, field, to: v }); t[field] = v; }
        } else if (t.pollPath === 'Inventory') {
            const inv = new Map();
            for (const item of val.matchAll(/\{[^{}]*\}/g)) {
                const id = item[0].match(/id:\s*"([^"]+)"/), c = item[0].match(/count:\s*(\d+)/);
                if (id) { const n = id[1].replace('minecraft:', ''); inv.set(n, (inv.get(n) ?? 0) + (c ? Number(c[1]) : 1)); }
            }
            for (const name of new Set([...inv.keys(), ...t.inv.keys()])) {
                const a = t.inv.get(name) ?? 0, b = inv.get(name) ?? 0;
                if (a !== b) this.emit('teacher', { name: TEACHER_NAME, field: 'inventory', item: name, delta: b - a, count: b });
            }
            t.inv = inv;
        }
    }

    // ---------------- loadout ----------------
    op(command) {
        try { this.bot?.chat(command); this.emit('command', { command, src: 'loadout' }); } catch { }
    }

    checkLoadout() {
        const bot = this.bot;
        if (!bot?.inventory || !this.connected || this.halted) return;
        const slots = bot.inventory.slots ?? [];
        const items = bot.inventory.items?.() ?? [];
        if (slots[45]?.name !== 'shield') {
            this.op(`/item replace entity ${MC_USERNAME} weapon.offhand with minecraft:shield`);
            this.emit('loadout', { action: 'offhand_shield', item: 'shield' });
        }
        if (!items.some(i => i.name === 'water_bucket')) {
            const empty = items.find(i => i.name === 'bucket');
            if (empty && empty.slot >= 36 && empty.slot <= 44) {
                this.op(`/item replace entity ${MC_USERNAME} hotbar.${empty.slot - 36} with minecraft:water_bucket`);
                this.emit('loadout', { action: 'replace_bucket', item: 'water_bucket', slot: empty.slot - 36 });
            } else {
                this.op(`/give ${MC_USERNAME} minecraft:water_bucket`);
                this.emit('loadout', { action: 'give_bucket', item: 'water_bucket' });
            }
        }
    }

    // ---------------- bot lifecycle ----------------
    isCurrentBot(bot, generation) {
        return this.bot === bot && this.botLifecycle.generation === generation;
    }

    setBotLifecycle(state, error = null) {
        this.botLifecycle = {
            ...this.botLifecycle,
            state,
            error: error == null ? null : String(error),
            viewer_generation: this.viewerGeneration,
        };
    }

    disposeViewer(bot = this.bot) {
        const worldView = this.worldView;
        if (worldView && bot) {
            try { worldView.removeListenersFromBot(bot); } catch { }
        }
        try { worldView?.removeAllListeners?.(); } catch { }
        try { bot?.viewer?.close?.(); } catch (error) { console.warn(`bot viewer close failed: ${error.message}`); }
        try { this.viewer?.close?.(); } catch { }
        try { this.renderer?.dispose?.(); } catch { }
        this.worldView = null;
        this.viewer = null;
        this.renderer = null;
        this.canvas = null;
        this.frame = null;
        this.viewerPort = null;
        this.viewerError = null;
        this.viewerGeneration++;
        this.botLifecycle.viewer_generation = this.viewerGeneration;
    }

    handleBotDisconnect(bot, generation, reason = 'disconnected') {
        if (!this.isCurrentBot(bot, generation)) return;
        this.failClosed();
        this.connected = false;
        this.disposeViewer(bot);
        this.bot = null;
        // Mineflayer can emit `error` without closing the underlying client;
        // explicitly terminate the stale transport before a later join creates
        // a replacement bot with the same username.
        try { bot?.quit?.(); } catch { try { bot?._client?.end?.(); } catch { } }
        this.setBotLifecycle(this.botLifecycle.state === 'leaving' ? 'left' : 'error', reason);
    }

    connectBot() {
        if (this.botLifecycle.state === 'joining') return { status: 202, value: { state: 'joining' } };
        if (this.botLifecycle.state === 'joined' && this.bot) return { status: 200, value: { state: 'joined' } };
        const generation = ++this.botGeneration;
        this.botLifecycle.generation = generation;
        this.setBotLifecycle('joining');
        const bot = mineflayer.createBot({ host: MC_HOST, port: MC_PORT, username: MC_USERNAME, version: MC_VERSION });
        this.bot = bot;
        const current = handler => (...args) => {
            if (this.isCurrentBot(bot, generation)) handler(...args);
        };
        bot.once('spawn', current(() => this.onSpawn(bot, generation)));
        bot.on('end', current(reason => this.handleBotDisconnect(bot, generation, reason || 'ended')));
        bot.on('kicked', current(reason => this.handleBotDisconnect(bot, generation, reason || 'kicked')));
        bot.on('error', current(error => this.handleBotDisconnect(bot, generation, error?.message || error || 'error')));
        bot.on('physicsTick', current(() => this.onPhysicsTick()));
        bot.on('death', current(() => {
            this.emit('death', {});
            this.failClosed();
            this.respawned = true;
        }));
        bot.on('respawn', current(() => this.emit('respawn', {})));
        bot.on('chat', current((username, message) => { if (username !== bot.username) this.emit('chat', { from: username, text: message }); }));
        // server-authoritative yaw/pitch corrections (teleport/forced move):
        // reconcile the look target after mineflayer applies the packet
        for (const pkt of ['player_rotation', 'position']) {
            bot._client.on(pkt, current(() => setImmediate(current(() => this.syncLookTarget()))));
        }
        // system messages (command replies, whispers) arrive with no username
        bot.on('message', current((jsonMsg) => {
            const text = jsonMsg?.toString?.() ?? String(jsonMsg);
            // teacher /data poll replies are consumed, not echoed as chat noise.
            // (26.1.2 renders the success dump as a system message; match loosely —
            // the first message containing SNBT-looking data while a poll is pending)
            // teacher /data poll replies are consumed, not echoed as chat noise:
            // first "entity data" message while a poll is pending is the reply.
            if (this.teacher.pendingSince && /entity data/i.test(text)) { this.teacherDataReply(text); return; }
            // "No entity was found" is a poll reply too — count it as a miss so
            // the backoff kicks in while the teacher is offline.
            if (this.teacher.pendingSince && /No entity was found/i.test(text)) {
                this.teacher.pendingSince = 0;
                this.teacher.pollMisses++;
                if (this.teacher.pollMisses >= 3) this.teacher.pollBackoff = 10000;
                if (this.teacher.pollMisses === 3) this.emit('teacher', { name: TEACHER_NAME, field: 'poll_error', misses: this.teacher.pollMisses });
                return;
            }
            this.sysMessages.push({ t: Date.now(), text });
            if (this.sysMessages.length > 500) this.sysMessages.shift();
            this.emit('chat', { from: 'system', text });
            console.log(`[system] ${text}`);
        }));
        bot.on('entitySwingArm', current((ent) => {
            if (ent?.id === bot.players?.[TEACHER_NAME]?.entity?.id) {
                this.teacher.swingNow = true;
                this.emit('teacher', { name: TEACHER_NAME, field: 'swing' });
            }
        }));
        bot.on('entityHurt', current((ent) => {
            if (ent?.id === bot.players?.[TEACHER_NAME]?.entity?.id) {
                this.emit('teacher', { name: TEACHER_NAME, field: 'hurt' });
            }
        }));
        bot.on('blockUpdate', current((oldBlock, newBlock) => {
            const p = newBlock?.position ?? oldBlock?.position;
            if (!p || !bot?.entity || p.distanceTo(bot.entity.position) > 16) return;
            this.emit('block', { at: vec(p), from: oldBlock?.name ?? null, to: newBlock?.name ?? null });
        }));
        bot.on('diggingCompleted', current((block) => this.emit('dig', { at: vec(block?.position), block: block?.name, field: 'complete' })));
        bot.on('diggingAborted', current((block) => this.emit('dig', { at: vec(block?.position), block: block?.name, field: 'abort' })));
        if (bot._client?.on) {
            bot._client.on('advancements', current((packet) => {
                try {
                    if (!this.advLogged) {
                        this.advLogged = true;
                        fs.writeFileSync(path.join(LOG_DIR, 'advancements-packet-sample.json'), JSON.stringify(packet, null, 2));
                    }
                    const mappings = packet?.advancementMapping ?? packet?.advancements ?? [];
                    const list = Array.isArray(mappings) ? mappings : Object.keys(mappings);
                    for (const adv of list) {
                        const name = typeof adv === 'string' ? adv : (adv?.key?.value ?? adv?.key ?? adv?.id ?? String(adv));
                        this.emit('advancement', { name: String(name) });
                    }
                } catch (err) { console.error(`advancements parse: ${err.message}`); }
            }));
        }
        return { status: 202, value: { state: 'joining' } };
    }

    leaveBot() {
        if (this.botLifecycle.state === 'left') return { status: 200, value: { state: 'left' } };
        if (this.botLifecycle.state === 'leaving') return { status: 202, value: { state: 'leaving' } };
        const bot = this.bot;
        this.setBotLifecycle('leaving');
        this.failClosed();
        this.connected = false;
        this.bot = null;
        this.botGeneration++;
        this.disposeViewer(bot);
        try { bot?.quit?.(); } catch (error) { this.setBotLifecycle('error', error.message); return { status: 500, value: { state: 'error', error: error.message } }; }
        this.setBotLifecycle('left');
        return { status: 200, value: { state: 'left' } };
    }

    start() {
        this.connectBot();
        this.motorTimer = setInterval(() => this.applyMotor(), MOTOR_INTERVAL_MS);
        this.frameTimer = setInterval(() => { void this.captureFrame(); }, FRAME_INTERVAL_MS);
        this.teacherPollTimer = setInterval(() => this.teacherPoll(), 1000);
        this.server = http.createServer((req, res) => { void this.handle(req, res); });
        // manual upgrade dispatch: ws' `path` option aborts every other upgrade,
        // which would kill the /viewer socket.io tunnel.
        this.wss = new WebSocketServer({ noServer: true });
        this.wss.on('connection', (sock) => this.onControlSocket(sock));
        this.server.on('upgrade', (req, socket, head) => {
            const p = (req.url || '').split('?')[0];
            if (p === '/control') { this.wss.handleUpgrade(req, socket, head, s => this.wss.emit('connection', s, req)); return; }
            if (p === '/viewer/socket.io') { this.tunnelViewerSocket(req, socket, head); return; }
            socket.destroy();
        });
        this.stateTimer = setInterval(() => this.pushState(), 100);
        this.server.listen(PORT, HOST, () => console.log(`fast-brain bridge listening on http://${HOST}:${PORT}`));
    }

    // ---------------- /viewer/ same-origin prismarine-viewer client ----------------
    // The bundle connects socket.io at window.location.pathname + 'socket.io'
    // (= /viewer/socket.io) — proxied to the viewer's real server on 8877 so
    // the cockpit iframe is same-origin and can drive viewer.camera at 60 fps.
    tunnelViewerSocket(req, socket, head) {
        const upstream = net.connect(VIEWER_PORT, MC_HOST, () => {
            upstream.write(`${req.method} ${req.url.replace('/viewer/socket.io', '/socket.io')} HTTP/${req.httpVersion}\r\n`);
            for (let i = 0; i < req.rawHeaders.length; i += 2) {
                const k = req.rawHeaders[i];
                const v = k.toLowerCase() === 'host' ? `${MC_HOST}:${VIEWER_PORT}` : req.rawHeaders[i + 1];
                upstream.write(`${k}: ${v}\r\n`);
            }
            upstream.write('\r\n');
            if (head?.length) upstream.write(head);
            upstream.pipe(socket);
            socket.pipe(upstream);
        });
        upstream.on('error', () => socket.destroy());
        socket.on('error', () => upstream.destroy());
    }

    proxyViewerIo(req, res) {
        const up = http.request({
            host: MC_HOST, port: VIEWER_PORT, method: req.method,
            path: req.url.replace('/viewer/socket.io', '/socket.io'),
            headers: { ...req.headers, host: `${MC_HOST}:${VIEWER_PORT}` },
        }, (r) => { res.writeHead(r.statusCode, r.headers); r.pipe(res); });
        up.on('error', () => { if (!res.headersSent) res.writeHead(502); res.end(); });
        req.pipe(up);
    }

    serveViewer(pathname, res) {
        let rel = decodeURIComponent(pathname.slice('/viewer/'.length)) || 'index.html';
        const file = path.join(VIEWER_PUBLIC, rel);
        if (!file.startsWith(VIEWER_PUBLIC) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
            json(res, 404, { error: 'not_found' });
            return;
        }
        // patch the bundle once: expose the Viewer instance and route the
        // 20 Hz server position updates through window.fbCam so the cockpit
        // can drive camera.rotation locally at 60 fps instead.
        if (rel === 'index.js') {
            if (!this.viewerBundlePatched) {
                const src = fs.readFileSync(file, 'utf8');
                const m = src.match(/([A-Za-z_$][\w$]*)\.setFirstPersonCamera\(([^)]*)\)/);
                if (!m) { this.viewerBundlePatched = src; console.warn('viewer bundle patch anchor not found'); }
                else {
                    this.viewerBundlePatched = src.replace(m[0],
                        `(window.viewer=${m[1]},window.fbCam?window.fbCam(${m[2]}):${m[1]}.setFirstPersonCamera(${m[2]}))`);
                    console.log(`viewer bundle patched (${m[1]} exposed as window.viewer)`);
                }
            }
            res.writeHead(200, { 'content-type': 'application/javascript', 'cache-control': 'no-store' });
            res.end(this.viewerBundlePatched);
            return;
        }
        const ext = path.extname(file).toLowerCase();
        const types = { '.html': 'text/html', '.js': 'application/javascript', '.png': 'image/png', '.json': 'application/json', '.txt': 'text/plain', '.css': 'text/css', '.gz': 'application/gzip' };
        res.writeHead(200, { 'content-type': types[ext] ?? 'application/octet-stream', 'cache-control': 'no-store' });
        fs.createReadStream(file).pipe(res);
    }

    // ---------------- cockpit websocket ----------------
    onControlSocket(sock) {
        this.wsClients.set(sock, Date.now());
        sock.on('message', (raw) => {
            try {
                this.wsClients.set(sock, Date.now());
                const m = JSON.parse(raw);
                if (m.type === 'control') {
                    const a = m.action ?? {};
                    this.humanInput({
                        keys: Object.fromEntries(BOOLS.map(k => [k, !!a[k]])),
                        dyaw: finite(a.yaw_delta), dpitch: finite(a.pitch_delta),
                        hotbar: Number.isInteger(a.hotbar) ? a.hotbar : undefined,
                    });
                } else if (m.type === 'resume_control') {
                    this.halted = false;
                    this.stopped = false;
                } else if (m.type === 'release') {
                    this.human.keys = {};
                    this.human.until = 0;
                } else if (m.type === 'emergency_stop') {
                    this.halted = true;
                    this.stopped = true;
                    this.human.until = 0;
                    this.releaseAll('human');
                } else if (m.type === 'record') {
                    this.recordCommand(m.command);
                } else if (m.type === 'label') {
                    const action = { good: 'good', bad: 'bad', excluded: 'excluded' }[m.label];
                    if (action) this.emit('label', { encounter_id: this.recording.encounter_id, action });
                } else if (m.type === 'target') {
                    this.uiTarget = String(m.mob_type ?? 'zombie');
                }
            } catch { }
        });
        sock.on('close', () => {
            this.wsClients.delete(sock);
            this.human.keys = {};
            this.human.until = 0;
        });
    }

    recordCommand(command) {
        if (!['start', 'pause', 'resume', 'stop'].includes(command)) return;
        if (command === 'start' || command === 'resume') {
            this.recording.encounter_id = `enc-${Date.now().toString(36)}`;
            this.recording.state = 'recording';
        } else if (command === 'pause') {
            if (this.recording.state !== 'recording') return;
            this.recording.state = 'paused';
        } else if (command === 'stop') {
            if (this.recording.state === 'idle') return;
            this.recording.state = 'idle';
        }
        this.emit('label', { encounter_id: this.recording.encounter_id, action: command });
    }

    findUiTarget() {
        const bot = this.bot, e = bot?.entity;
        if (!e) return null;
        const matches = (ent) => this.uiTarget === 'player'
            ? ent.type === 'player' && ent !== e
            : ent.name === this.uiTarget;
        return Object.values(bot.entities)
            .filter(ent => ent?.position && ent !== e && matches(ent) && ent.position.distanceTo(e.position) <= 32)
            .sort((a, b) => a.position.distanceTo(e.position) - b.position.distanceTo(e.position))[0] ?? null;
    }

    pushState() {
        if (!this.wsClients.size) return;
        // stale-control failsafe: no message in 500 ms -> release human keys
        const now = Date.now();
        for (const [sock, last] of this.wsClients) {
            if (now - last > 500 && this.human.until > now) this.human.until = now;
        }
        const bot = this.bot, e = bot?.entity;
        let target = null;
        const ent = this.findUiTarget();
        if (ent) {
            const w = ent.width ?? 0.6, h = ent.height ?? 1.8;
            const aabb = {
                min: { x: ent.position.x - w / 2, y: ent.position.y, z: ent.position.z - w / 2 },
                max: { x: ent.position.x + w / 2, y: ent.position.y + h, z: ent.position.z + w / 2 },
            };
            const aim = { x: ent.position.x, y: ent.position.y + h * 0.7, z: ent.position.z };
            let los = null;
            try {
                if (bot.world?.raycast) {
                    const eye = e.position.offset(0, EYE_HEIGHT, 0);
                    const d = { x: aim.x - eye.x, y: aim.y - eye.y, z: aim.z - eye.z };
                    const len = Math.hypot(d.x, d.y, d.z);
                    const hit = len > 0 ? bot.world.raycast(eye, { x: d.x / len, y: d.y / len, z: d.z / len }, len) : null;
                    los = !hit;
                }
            } catch { los = null; }
            target = {
                id: ent.id, name: ent.name ?? 'entity', aabb, aim_point: aim,
                distance: round2(ent.position.distanceTo(e.position)),
                health: ent.health ?? null, line_of_sight: los,
            };
        }
        const hitAge = this.lastHit ? now - this.lastHit.t : null;
        // hotbar HUD data (slots 36-44, offhand 45)
        let inventory = null;
        try {
            const slots = bot?.inventory?.slots ?? [];
            inventory = {
                hotbar: [36, 37, 38, 39, 40, 41, 42, 43, 44].map(i => slots[i] ? { name: slots[i].name, count: slots[i].count } : null),
                selected: bot?.quickBarSlot ?? 0,
                offhand: slots[45]?.name ?? null,
                main_hand: bot?.heldItem?.name ?? null,
            };
        } catch { }
        const tp = this.teacher;
        const msg = JSON.stringify({
            type: 'state',
            bot_lifecycle: this.botLifecycle,
            viewer_generation: this.viewerGeneration,
            observation: {
                self: e ? {
                    position: vec(e.position), yaw: e.yaw, pitch: e.pitch,
                    velocity: vec(e.velocity), eye_height: EYE_HEIGHT,
                    health: bot.health ?? null, food: bot.food ?? null,
                    armor: armorPoints(e.equipment), oxygen: bot.oxygenLevel ?? null,
                    xp_level: bot.experience?.level ?? null, xp_progress: bot.experience?.progress ?? null,
                    in_water: e.isInWater ?? null,
                    falling: this.selfFalling.falling,
                    incoming_attack: {
                        hit_received: hitAge != null && hitAge < 1500,
                        damage: this.lastHit?.amount ?? null,
                        hit_age_ms: hitAge,
                    },
                } : null,
                inventory,
                target,
                selector: { target_type: this.uiTarget },
            },
            teacher: tp.online ? {
                name: TEACHER_NAME, health: tp.health, food: tp.food,
                held_item: tp.held, falling: tp.falling, flags: tp.flags,
                inputs: tp.inputs ? tp.inputs.split(',').filter(Boolean) : [],
            } : null,
            recording_state: this.recording.state,
            session_id: this.sessionTs,
            encounter_id: this.recording.encounter_id,
            viewer_port: this.viewerPort,
            viewer_fov_y: VIEWER_FOV_Y,
            viewer_error: this.viewerError,
            messages: this.sysMessages.slice(-8).map(m => m.text),
        });
        for (const sock of this.wsClients.keys()) { try { sock.send(msg); } catch { } }
    }

    onSpawn(bot = this.bot, generation = this.botLifecycle.generation) {
        if (!this.isCurrentBot(bot, generation)) return;
        this.connected = true;
        this.stopped = false;
        this.setBotLifecycle('joined');
        this.canvas = createCanvas(WIDTH, HEIGHT);
        this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas });
        this.viewer = new Viewer(this.renderer);
        const viewerVersion = chooseViewerVersion(this.bot.version);
        this.viewer.setVersion(viewerVersion);
        const center = this.bot.entity.position;
        this.worldView = new WorldView(this.bot.world, VIEW_DISTANCE, center);
        this.viewer.listen(this.worldView);
        this.worldView.listenToBot(this.bot);
        void this.worldView.init(center).then(() => {
            if (this.isCurrentBot(bot, generation)) void this.captureFrame();
        });
        this.buildKeyframe();
        this.loadoutDue = Date.now() + 1500;
        // browser viewer (client-side WebGL) for the cockpit iframe — version shimmed
        // to the newest supported asset set when 26.x is not listed.
        try {
            const actual = this.bot.version;
            const ver = supportedVersions.includes(actual) ? actual : supportedVersions.at(-1);
            const vbot = ver === actual ? this.bot : new Proxy(this.bot, {
                get: (t, p, r) => (p === 'version' ? ver : Reflect.get(t, p, r)),
            });
            prismarineViewer.mineflayer(vbot, { port: VIEWER_PORT, firstPerson: true, viewDistance: VIEW_DISTANCE });
            this.viewerPort = VIEWER_PORT;
            console.log(`browser viewer on :${VIEWER_PORT} (version ${ver})`);
        } catch (error) {
            this.viewerError = String(error?.message ?? error);
            console.error(`browser viewer failed: ${this.viewerError}`);
        }
        console.log(`bot spawned version=${this.bot.version} renderer_version=${viewerVersion}`);
    }

    failClosed() {
        this.connected = false;
        this.stopped = true;
        this.action = emptyAction();
        this.skillAction = emptyAction();
        this.actionDeadline = 0;
        this.diggingTarget = null;
        this.lookPending = false;
        this.lookTarget = null;
        if (this.bot?.clearControlStates) this.bot.clearControlStates();
        this.bot?.deactivateItem?.();
        try { this.bot?.stopDigging?.(); } catch { }
        for (const k of Object.keys(this.held)) { this.emit('key', { key: k, to: false, src: 'reflex' }); this.held[k] = false; }
    }

    observation() {
        const entity = this.bot?.entity;
        const respawned = this.respawned;
        this.respawned = false;
        const inventory = [];
        try {
            for (const item of this.bot?.inventory?.items() ?? []) inventory.push({ name: item.name, count: item.count });
        } catch { }
        return {
            observation_id: `${this.frameId}:${this.actionSeq}`,
            captured_at_ms: this.frame?.capturedAtMs ?? null,
            frame_id: this.frame?.id ?? null,
            connected: this.connected,
            stopped: this.stopped,
            halted: this.halted,
            respawned,
            tick: this.tick,
            self: entity ? {
                position: vec(entity.position), velocity: vec(entity.velocity),
                yaw: entity.yaw ?? null, pitch: entity.pitch ?? null,
                on_ground: entity.onGround ?? null,
                health: Number.isFinite(this.bot.health) ? this.bot.health : null,
                hunger: Number.isFinite(this.bot.food) ? this.bot.food : null,
                held_item: this.bot.heldItem?.name ?? null,
            } : null,
            inventory,
            skill: this.skill ? { name: this.skill.name, tick: this.tick - this.skill.started_tick } : null,
            action: { seq: this.actionSeq, age_ms: this.actionReceivedAt ? Date.now() - this.actionReceivedAt : null },
        };
    }

    targets() {
        const entity = this.bot?.entity;
        if (!entity) return [];
        const self = { position: entity.position, yaw: entity.yaw, pitch: entity.pitch, eye_height: EYE_HEIGHT };
        const fovY = FOV_DEG * Math.PI / 180;
        const out = [];
        try {
            const ids = [];
            const names = this.bot.registry?.blocksByName ?? {};
            for (const name of Object.keys(names)) {
                if (/_log$/.test(name) || name === 'stone' || /_ore$/.test(name) || name === 'crafting_table') ids.push(names[name].id);
            }
            for (const pos of this.bot.findBlocks({ matching: ids, maxDistance: 24, count: 32 })) {
                const block = this.bot.blockAt(pos);
                if (!block) continue;
                const bbox = projectAabb({ min: { x: pos.x, y: pos.y, z: pos.z }, max: { x: pos.x + 1, y: pos.y + 1, z: pos.z + 1 } }, self, WIDTH, HEIGHT, fovY);
                if (bbox) out.push({ kind: 'block', name: block.name, position: vec(pos), distance: +pos.distanceTo(entity.position).toFixed(2), bbox, frame_id: this.frame?.id ?? null });
            }
        } catch (error) { console.error(`target blocks failed: ${error.message}`); }
        try {
            for (const e of Object.values(this.bot.entities)) {
                if (!e || e === entity || !e.position) continue;
                if (e.position.distanceTo(entity.position) > 24) continue;
                const w = e.width ?? 0.6, h = e.height ?? 1.8;
                const bbox = projectAabb({
                    min: { x: e.position.x - w / 2, y: e.position.y, z: e.position.z - w / 2 },
                    max: { x: e.position.x + w / 2, y: e.position.y + h, z: e.position.z + w / 2 },
                }, self, WIDTH, HEIGHT, fovY);
                if (bbox) out.push({ kind: 'entity', id: e.id, name: e.name ?? e.displayName ?? 'entity', position: vec(e.position), distance: +e.position.distanceTo(entity.position).toFixed(2), bbox, frame_id: this.frame?.id ?? null });
            }
        } catch (error) { console.error(`target entities failed: ${error.message}`); }
        return out;
    }

    async captureFrame() {
        // lazy: only render while a consumer wants frames (MJPEG client, recent
        // /v1/frame request, or a heartbeating runner)
        if (this.mjpegClients === 0 && Date.now() > this.frameDemandUntil) return;
        if (this.captureBusy || !this.connected || !this.worldView || !this.bot?.entity) return;
        this.captureBusy = true;
        const t0 = Date.now();
        try {
            const position = this.bot.entity.position;
            await this.worldView.updatePosition(position);
            this.viewer.setFirstPersonCamera(position, this.bot.entity.yaw, this.bot.entity.pitch);
            this.viewer.update();
            this.renderer.render(this.viewer.scene, this.viewer.camera);
            const stream = this.canvas.createJPEGStream({ bufsize: 4096, quality: 70, progressive: false });
            const buffer = await getBufferFromStream(stream);
            this.frame = { id: ++this.frameId, capturedAtMs: Date.now(), buffer };
            const ms = Date.now() - t0;
            this.captureMs.push(ms);
            if (this.captureMs.length > 200) this.captureMs.shift();
            if (this.frame.id % 200 === 0) {
                const sorted = [...this.captureMs].sort((a, b) => a - b);
                console.log(`capture p50=${sorted[Math.floor(sorted.length / 2)]}ms p95=${sorted[Math.floor(sorted.length * 0.95)]}ms n=${sorted.length}`);
            }
        } catch (error) {
            console.error(`frame capture failed: ${error.message}`);
        } finally {
            this.captureBusy = false;
        }
    }

    // ---------------- arbiter ----------------
    setKey(key, to, src) {
        if (this.held[key] === to) return;
        this.held[key] = to;
        this.emit('key', { key, to, src });
    }

    applyMotor() {
        const bot = this.bot;
        if (!bot?.entity) return;
        const now = Date.now();
        const humanActive = this.human.until > now;
        if (!this.connected || this.stopped || this.halted) {
            this.releaseAll(humanActive ? 'human' : 'reflex');
            return;
        }
        const modelLive = this.actionDeadline && now <= this.actionDeadline;
        // merge: human > reflex(skill) > model
        const eff = emptyAction();
        const srcOf = {};
        if (modelLive) for (const k of BOOLS) { eff[k] = this.action[k]; if (this.action[k]) srcOf[k] = 'model'; }
        if (this.skillActive || this.skill) for (const k of BOOLS) { if (this.skillAction[k]) { eff[k] = true; srcOf[k] = 'reflex'; } }
        if (humanActive) for (const k of BOOLS) { if (k in this.human.keys) { eff[k] = !!this.human.keys[k]; srcOf[k] = 'human'; } }
        if (!modelLive && this.actionDeadline) {
            this.action = emptyAction();
            this.actionDeadline = 0;
            bot.clearControlStates?.();
            bot.deactivateItem?.();
            if (this.diggingTarget) { try { bot.stopDigging?.(); } catch { } this.diggingTarget = null; }
        }
        const hotbar = humanActive && Number.isInteger(this.human.hotbar) ? this.human.hotbar
            : (this.skillAction.hotbar ?? (modelLive ? this.action.hotbar : null));
        if (hotbar !== null && hotbar !== this.held.hotbar) {
            bot.setQuickBarSlot?.(hotbar);
            this.emit('hotbar', { slot: hotbar, src: humanActive ? 'human' : 'reflex' });
            this.held.hotbar = hotbar;
        }
        // model camera deltas applied once per accepted seq
        if (modelLive && this.cameraAppliedSeq !== this.actionSeq) {
            this.cameraAppliedSeq = this.actionSeq;
            const a = this.action;
            if (a.yaw_delta || a.pitch_delta) this.queueLookDelta(a.yaw_delta, a.pitch_delta, 'model');
        }
        this.applyLook();
        // sprint is automatic: forward && !sneak -> sprint (applies to human/reflex/model)
        eff.sprint = eff.forward && !eff.sneak;
        for (const key of ['forward', 'back', 'left', 'right', 'jump', 'sprint', 'sneak']) {
            bot.setControlState(key, eff[key]);
            this.setKey(key, eff[key], srcOf[key] ?? 'model');
        }
        // use edge semantics — never activateBlock/activateEntity (they lookAt first,
        // which was the visible pitch-jump bug); send packets directly
        if (eff.use && !this.prevHeldUse) {
            this.setKey('use', true, srcOf.use ?? 'model');
            this.useEdge();
        } else if (!eff.use && this.prevHeldUse) {
            this.setKey('use', false, srcOf.use ?? 'model');
            bot.deactivateItem?.();
        }
        this.prevHeldUse = eff.use;
        // attack: dig targeted block while held; else entityAtCursor attack <=4Hz
        if (eff.attack) {
            if (!this.prevHeldAttack) this.setKey('attack', true, srcOf.attack ?? 'model');
            const block = bot.blockAtCursor?.(5);
            if (block && bot.canDigBlock?.(block)) {
                const key = block.position.toString();
                if (this.diggingTarget !== key) {
                    try { bot.stopDigging?.(); } catch { }
                    this.diggingTarget = key;
                    this.emit('dig', { at: vec(block.position), block: block.name, field: 'start' });
                    bot.dig(block, false).catch(() => { });
                }
            } else {
                if (this.diggingTarget) { try { bot.stopDigging?.(); } catch { } this.diggingTarget = null; }
                if (now - this.lastAttackAt >= 250) {
                    this.lastAttackAt = now;
                    const target = bot.entityAtCursor?.(4);
                    if (target) bot.attack(target);
                    else bot.swingArm?.('right');
                }
            }
        } else if (this.prevHeldAttack) {
            this.setKey('attack', false, srcOf.attack ?? 'model');
            if (this.diggingTarget) { try { bot.stopDigging?.(); } catch { } this.diggingTarget = null; }
        }
        this.prevHeldAttack = eff.attack;
    }

    // right-click edge: entity > item-use set > block. No camera moves.
    useEdge() {
        const bot = this.bot;
        if (!bot?.entity) return;
        const USE_ITEMS = /(^|_)bucket$|shield$|^bow$|crossbow|trident$|ender_pearl$|snowball$|^egg$|fishing_rod$|potion$|firework_rocket|spyglass$|^elytra$/;
        const isUseItem = (it) => !!it && (USE_ITEMS.test(it.name) || Number(it.foodPoints) > 0);
        // 1. entity at cursor within 4 blocks — direct use_entity (no lookAt)
        try {
            const ent = bot.entityAtCursor?.(4);
            if (ent) {
                bot._client.write('use_entity', { target: ent.id, mouse: 0, sneaking: false, hand: 0, location: { x: 0, y: 0, z: 0 } });
                return;
            }
        } catch { }
        // 2. item the server resolves by its own raycast (water_bucket, shield, food, ...)
        const main = bot.heldItem, off = bot.inventory?.slots?.[45];
        if (isUseItem(main)) { bot.activateItem?.(); return; }
        if (isUseItem(off)) { bot.activateItem?.(true); return; }
        // 3. block at cursor — direct block_place with real face/intersect, then one arm swing
        try {
            const block = bot.blockAtCursor?.(5);
            if (block && block.face != null && block.face !== 255) {
                const cursor = block.intersect
                    ? { x: block.intersect.x - block.position.x, y: block.intersect.y - block.position.y, z: block.intersect.z - block.position.z }
                    : { x: 0.5, y: 0.5, z: 0.5 };
                // 1.21.3+ packet shape (blockPlaceHasInsideBlock branch)
                bot._client.write('block_place', {
                    location: block.position, direction: block.face, hand: 0,
                    cursorX: cursor.x, cursorY: cursor.y, cursorZ: cursor.z,
                    insideBlock: false, sequence: 0, worldBorderHit: false,
                });
                bot.swingArm?.('right');
            }
        } catch { }
    }

    releaseAll(src) {
        const bot = this.bot;
        for (const key of BOOLS) this.setKey(key, false, src);
        bot?.clearControlStates?.();
        bot?.deactivateItem?.();
        if (this.diggingTarget) { try { bot.stopDigging?.(); } catch { } this.diggingTarget = null; }
        this.prevHeldAttack = false;
        this.prevHeldUse = false;
        this.lookPending = false;
        this.lookTarget = null;
    }

    acceptAction(body) {
        if (!body || typeof body !== 'object' || Array.isArray(body)) return { status: 400, value: { error: 'invalid_action' } };
        if (this.halted) return { status: 409, value: { error: 'halted', seq: this.actionSeq } };
        const seq = Number(body.seq);
        if (!Number.isSafeInteger(seq) || seq <= this.actionSeq) return { status: 409, value: { error: 'stale_action', latest_seq: this.actionSeq } };
        if (body.action && typeof body.action !== 'object') return { status: 400, value: { error: 'invalid_action' } };
        this.actionSeq = seq;
        this.action = sanitizeAction(body.action);
        this.actionReceivedAt = Date.now();
        this.actionDeadline = this.actionReceivedAt + clamp(finite(body.ttl_ms, ACTION_TTL_MS), 20, 500);
        this.stopped = false;
        return { status: 200, value: { accepted: true, seq, deadline_ms: this.actionDeadline } };
    }

    acceptTactic(body) {
        const MOVEMENTS = ['advance', 'back_off', 'strafe_left', 'strafe_right', 'hold', 'disengage'];
        if (!body || typeof body !== 'object' || Array.isArray(body)) return { status: 400, value: { error: 'invalid_tactic' } };
        if (this.halted) return { status: 409, value: { error: 'halted' } };
        const s = this.skill;
        if (s?.name !== 'tactical') return { status: 409, value: { error: 'no_tactical_skill' } };
        const seq = Number(body.seq);
        if (!Number.isSafeInteger(seq) || seq <= s.tacticSeq) return { status: 409, value: { error: 'stale_tactic', latest_seq: s.tacticSeq } };
        if (!MOVEMENTS.includes(body.movement)) return { status: 400, value: { error: 'invalid_tactic' } };
        const tactic = {
            movement: body.movement,
            attack: body.attack === true,
            sprint: body.sprint === true,
            jump: body.jump === true,
            block: body.block === true,
        };
        if (body.meta && typeof body.meta === 'object' && !Array.isArray(body.meta)) tactic.meta = body.meta;
        s.tactic = tactic;
        s.tacticSeq = seq;
        s.tacticDeadline = Date.now() + clamp(finite(body.ttl_ms, 600), 100, 2000);
        this.emit('tactic', { seq, ...tactic });
        return { status: 200, value: { accepted: true, seq, deadline_ms: s.tacticDeadline } };
    }

    humanInput(body) {
        const now = Date.now();
        if (this.halted) return { status: 409, value: { error: 'halted' } };
        if (body.keys && typeof body.keys === 'object') {
            this.human.keys = body.keys;
            this.human.until = now + 400;
            if (Number.isInteger(body.hotbar)) this.human.hotbar = body.hotbar;
        }
        if (Number.isFinite(body.dyaw) || Number.isFinite(body.dpitch)) {
            this.queueLookDelta(finite(body.dyaw), finite(body.dpitch), 'human');
            this.human.until = now + 400;
        }
        return { status: 200, value: { ok: true } };
    }

    // ---------------- http ----------------
    async handle(req, res) {
        const url = new URL(req.url, `http://${req.headers.host}`);
        if (req.method === 'GET' && url.pathname === '/healthz') {
            json(res, 200, { state: this.connected ? 'ready' : 'connecting', connected: this.connected, bot_lifecycle: this.botLifecycle, stopped: this.stopped, halted: this.halted, frame_id: this.frameId, action_seq: this.actionSeq, tick: this.tick, events_per_sec: this.eventsPerSec(), dropped_per_sec: this.droppedPerSec() });
            return;
        }
        if (req.method === 'POST' && url.pathname === '/v1/bot/join') {
            try {
                const result = this.connectBot();
                json(res, result.status, { ...result.value, bot_lifecycle: this.botLifecycle });
            } catch (error) {
                this.setBotLifecycle('error', error.message);
                json(res, 500, { state: 'error', error: error.message, bot_lifecycle: this.botLifecycle });
            }
            return;
        }
        if (req.method === 'POST' && url.pathname === '/v1/bot/leave') {
            try {
                const result = this.leaveBot();
                json(res, result.status, { ...result.value, bot_lifecycle: this.botLifecycle });
            } catch (error) {
                this.setBotLifecycle('error', error.message);
                json(res, 500, { state: 'error', error: error.message, bot_lifecycle: this.botLifecycle });
            }
            return;
        }
        if (url.pathname.startsWith('/viewer/socket.io')) { this.proxyViewerIo(req, res); return; }
        if (url.pathname === '/viewer') { res.writeHead(302, { location: '/viewer/' }); res.end(); return; }
        if (req.method === 'GET' && url.pathname.startsWith('/viewer/')) { this.serveViewer(url.pathname, res); return; }
        if (req.method === 'GET' && ['/', '/index.html', '/app.js', '/style.css', '/projection.js'].includes(url.pathname)) {
            const asset = url.pathname === '/' ? 'index.html' : url.pathname.slice(1);
            const file = path.resolve(PUBLIC_DIR, asset);
            if (!file.startsWith(PUBLIC_DIR + path.sep) || !fs.existsSync(file)) { json(res, 404, { error: 'not_found' }); return; }
            const type = asset.endsWith('.js') ? 'text/javascript' : asset.endsWith('.css') ? 'text/css' : 'text/html';
            res.writeHead(200, { 'content-type': `${type}; charset=utf-8`, 'cache-control': 'no-store' });
            fs.createReadStream(file).pipe(res);
            return;
        }
        if (req.method === 'GET' && url.pathname === '/v1/observation') {
            json(res, 200, { observation: this.observation() });
            return;
        }
        if (req.method === 'GET' && url.pathname === '/v1/targets') {
            json(res, 200, { targets: this.targets(), frame_id: this.frame?.id ?? null });
            return;
        }
        if (req.method === 'GET' && url.pathname === '/v1/keyframe') {
            if (!this.keyframeData) this.buildKeyframe();
            json(res, 200, { keyframe: this.keyframeData });
            return;
        }
        if (req.method === 'GET' && url.pathname === '/v1/events') {
            res.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-store', 'connection': 'keep-alive' });
            for (const ev of this.eventRing.slice(-EVENT_REPLAY)) res.write(`data: ${JSON.stringify(ev)}\n\n`);
            this.sseClients.add(res);
            req.on('close', () => this.sseClients.delete(res));
            return;
        }
        if (req.method === 'GET' && url.pathname === '/v1/events/recent') {
            const n = clamp(parseInt(url.searchParams.get('n') ?? '200', 10) || 200, 1, EVENT_RING);
            json(res, 200, { events: this.eventRing.slice(-n) });
            return;
        }
        if (req.method === 'GET' && url.pathname === '/v1/frame') {
            this.frameDemandUntil = Date.now() + 2000;
            if (!this.frame || Date.now() - this.frame.capturedAtMs > 500) await this.captureFrame();
            if (!this.frame) { json(res, 503, { error: 'frame_unavailable' }); return; }
            res.writeHead(200, { 'content-type': 'image/jpeg', 'cache-control': 'no-store', 'x-frame-id': String(this.frame.id), 'x-captured-at-ms': String(this.frame.capturedAtMs) });
            res.end(this.frame.buffer);
            return;
        }
        if (req.method === 'POST' && url.pathname === '/v1/frame/subscribe') {
            this.frameDemandUntil = Date.now() + 2000;
            json(res, 200, { ok: true, until: this.frameDemandUntil });
            return;
        }
        if (req.method === 'GET' && url.pathname === '/v1/stream') {
            res.writeHead(200, { 'content-type': 'multipart/x-mixed-replace; boundary=fb', 'cache-control': 'no-store', 'connection': 'close' });
            this.mjpegClients++;
            let closed = false;
            req.on('close', () => { closed = true; this.mjpegClients--; });
            let lastSent = 0;
            const timer = setInterval(() => {
                if (closed) { clearInterval(timer); try { res.end(); } catch { } return; }
                const frame = this.frame;
                if (!frame || frame.id === lastSent) return;
                lastSent = frame.id;
                res.write(`--fb\r\ncontent-type: image/jpeg\r\ncontent-length: ${frame.buffer.length}\r\n\r\n`);
                res.write(frame.buffer);
                res.write('\r\n');
            }, 100);
            return;
        }
        if (req.method === 'GET' && url.pathname === '/v1/skill') {
            json(res, 200, { skill: this.skill ? { name: this.skill.name, args: this.skill.args, elapsed_ticks: this.tick - this.skill.started_tick, ...(this.skill.name === 'tactical' ? { tactic: { seq: this.skill.tacticSeq, deadline_ms: this.skill.tacticDeadline, current: this.skill.tactic } } : {}) } : null, reflexes: { block_projectiles: this.reflexes.block_projectiles.enabled } });
            return;
        }
        if (req.method === 'POST' && url.pathname === '/v1/skill') {
            try {
                const body = await readBody(req);
                const result = this.startSkill(String(body.name), body.args ?? {});
                json(res, result.error ? 400 : 200, result);
            } catch (error) { json(res, 400, { error: error.message }); }
            return;
        }
        if (req.method === 'DELETE' && url.pathname === '/v1/skill') {
            if (this.skill) this.finishSkill({ done: false, reason: 'cancelled' });
            json(res, 200, { cancelled: true });
            return;
        }
        if (req.method === 'GET' && url.pathname === '/v1/tactic') {
            const s = this.skill?.name === 'tactical' ? this.skill : null;
            const now = Date.now();
            json(res, 200, {
                active: !!(s && s.tactic && now <= s.tacticDeadline),
                seq: s?.tacticSeq ?? 0,
                tactic: s?.tactic ?? null,
                deadline_ms: s?.tacticDeadline ?? 0,
                target_id: s?.args?.entity_id ?? null,
            });
            return;
        }
        if (req.method === 'POST' && url.pathname === '/v1/tactic') {
            try { const result = this.acceptTactic(await readBody(req)); json(res, result.status, result.value); } catch (error) { json(res, 400, { error: error.message }); }
            return;
        }
        if (req.method === 'POST' && url.pathname === '/v1/action') {
            try { const result = this.acceptAction(await readBody(req)); json(res, result.status, result.value); } catch (error) { json(res, 400, { error: error.message }); }
            return;
        }
        if (req.method === 'POST' && url.pathname === '/v1/input') {
            try { const result = this.humanInput(await readBody(req)); json(res, result.status, result.value); } catch (error) { json(res, 400, { error: error.message }); }
            return;
        }
        if (req.method === 'POST' && url.pathname === '/v1/command') {
            try {
                const body = await readBody(req);
                const command = String(body.command ?? body.text ?? '');
                if (!command.startsWith('/')) { json(res, 400, { error: 'must_start_with_slash' }); return; }
                if (this.halted) { json(res, 409, { error: 'halted' }); return; }
                const now = Date.now();
                this.lastCommands = (this.lastCommands ?? []).filter(t => now - t < 1000);
                if (this.lastCommands.length >= 2) { json(res, 429, { error: 'rate_limited' }); return; }
                this.lastCommands.push(now);
                const since = Date.now();
                this.bot.chat(command);
                this.emit('command', { command });
                // wait for the server's real reply (success/permission/syntax error)
                await new Promise(r => setTimeout(r, 1500));
                const responses = this.sysMessages.filter(m => m.t >= since).map(m => m.text);
                json(res, 200, { ok: true, command, responses });
            } catch (error) { json(res, 400, { error: error.message }); }
            return;
        }
        if (req.method === 'POST' && url.pathname === '/v1/equip') {
            try {
                const body = await readBody(req);
                const name = String(body.item ?? '');
                const dest = String(body.dest ?? 'hand');
                const item = this.bot?.inventory?.items?.().find(i => i.name === name || i.name.endsWith(name));
                if (!item) { json(res, 404, { error: 'item_not_found', item: name }); return; }
                await this.bot.equip(item, dest);
                this.emit('key', { key: `equip:${dest}`, to: true, src: 'reflex' });
                json(res, 200, { ok: true, item: item.name, dest });
            } catch (error) { json(res, 400, { error: error.message }); }
            return;
        }
        if (req.method === 'POST' && url.pathname === '/v1/stop') {
            this.halted = true;
            this.stopped = true;
            this.action = emptyAction();
            this.actionDeadline = 0;
            this.diggingTarget = null;
            this.human.until = 0;
            if (this.skill) this.finishSkill({ done: false, reason: 'stopped' });
            this.bot?.clearControlStates?.();
            this.bot?.deactivateItem?.();
            try { this.bot?.stopDigging?.(); } catch { }
            json(res, 200, { stopped: true, halted: true, seq: this.actionSeq });
            return;
        }
        if (req.method === 'POST' && url.pathname === '/v1/resume') {
            this.halted = false;
            this.stopped = false;
            json(res, 200, { halted: false, seq: this.actionSeq });
            return;
        }
        if (req.method === 'GET' && url.pathname === '/v1/encounters') {
            try {
                const encounters = new Map(); // id -> {start_tick, end_tick, labels[], counts}
                const order = [];
                const lines = fs.readFileSync(this.trajPath, 'utf8').split('\n');
                let current = null;
                for (const line of lines) {
                    if (!line) continue;
                    let ev; try { ev = JSON.parse(line); } catch { continue; }
                    if (ev.kind === 'label') {
                        if (['start', 'resume'].includes(ev.action)) {
                            if (current && current.end_tick == null) current.end_tick = ev.tick;
                            current = encounters.get(ev.encounter_id) ?? { encounter_id: ev.encounter_id, start_tick: ev.tick, end_tick: null, labels: [], counts: { teacher: 0, damage: 0, key: 0, block: 0 } };
                            current.start_tick = ev.tick; current.end_tick = null;
                            if (!encounters.has(ev.encounter_id)) { encounters.set(ev.encounter_id, current); order.push(ev.encounter_id); }
                            current.labels.push(ev.action);
                        } else if (ev.action === 'stop' || ev.action === 'pause') {
                            if (current && current.end_tick == null) current.end_tick = ev.tick;
                            current?.labels.push(ev.action);
                            if (ev.action === 'stop') current = null;
                        } else if (current) {
                            current.labels.push(ev.action); // good/bad/excluded
                        }
                    } else if (current && current.end_tick == null && ['teacher', 'damage', 'key', 'block'].includes(ev.kind)) {
                        current.counts[ev.kind]++;
                    }
                }
                json(res, 200, { encounters: order.map(id => encounters.get(id)) });
            } catch (error) { json(res, 500, { error: error.message }); }
            return;
        }
        json(res, 404, { error: 'not_found' });
    }

    close() {
        this.leaveBot();
        clearInterval(this.motorTimer);
        clearInterval(this.frameTimer);
        clearInterval(this.teacherPollTimer);
        clearInterval(this.stateTimer);
        try { this.wss?.close?.(); } catch { }
        this.server?.close();
        this.traj.end();
    }
}

// The 1.21.4 asset set does not cover every 26.1 block/entity; a missing texture
// must not kill the bridge (worst case it renders magenta).
process.on('unhandledRejection', (error) => console.error(`unhandledRejection: ${error?.message ?? error}`));
process.on('uncaughtException', (error) => {
    if (String(error?.message ?? '').includes('No such file or directory')) {
        console.error(`missing asset tolerated: ${error.message}`);
        return;
    }
    console.error(error);
    process.exit(1);
});

export { FastBrainBridge };
if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
    const bridge = new FastBrainBridge();
    bridge.start();
    process.once('SIGINT', () => bridge.close());
    process.once('SIGTERM', () => bridge.close());
}
