import { boxEdges, cameraPoint, project } from './projection.js';
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const overlay = $('overlay');
  const viewer = $('viewer');
  const action = { forward:false, back:false, left:false, right:false, jump:false, sprint:false, sneak:false, attack:false, use:false, hotbar:0, mouse_dx:0, mouse_dy:0, yaw_delta:0, pitch_delta:0, emergency_stop:false, manual_abort:false };
  let socket, state = {}, reconnectTimer, viewerPort, viewerGeneration = null, armed = false, capturePending = false, emergencyLatched = false, released = false, directAction = null, directUntil = 0;
  const keys = new Map([['KeyW','forward'],['KeyS','back'],['KeyA','left'],['KeyD','right'],['Space','jump'],['ShiftLeft','sneak'],['ShiftRight','sneak']]);
  const finite = value => Number.isFinite(value) ? value : 0;
  const send = message => { if (socket && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message)); };
  const active = () => armed && document.hasFocus() && !document.hidden && document.pointerLockElement === overlay && socket?.readyState === WebSocket.OPEN;
  const clearAction = () => { Object.keys(action).forEach(k => { if (typeof action[k] === 'boolean') action[k] = false; }); action.mouse_dx = action.mouse_dy = action.yaw_delta = action.pitch_delta = 0; };
  const release = (emergency = false) => { clearAction(); armed = false; if (emergency) { emergencyLatched = true; send({type:'emergency_stop'}); } else if (!released) { released = true; send({type:'release'}); } };
  const sendControl = () => { if(directAction){if(Date.now()<directUntil){released=false;send({type:'control',action:{...directAction}});directAction.yaw_delta=directAction.pitch_delta=0;return;}send({type:'control',action:{...emptyAction()}});directAction=null;release();return;} if (!active()) { release(); return; } released = false; send({type:'control',action:{...action, mouse_dx:finite(action.mouse_dx), mouse_dy:finite(action.mouse_dy), yaw_delta:finite(action.yaw_delta), pitch_delta:finite(action.pitch_delta)}}); action.mouse_dx=action.mouse_dy=action.yaw_delta=action.pitch_delta=0; action.emergency_stop=false; };
  const emptyAction = () => ({forward:false,back:false,left:false,right:false,jump:false,sprint:false,sneak:false,attack:false,use:false,hotbar:action.hotbar,mouse_dx:0,mouse_dy:0,yaw_delta:0,pitch_delta:0,emergency_stop:false,manual_abort:false});
  const drive = (patch, duration=600) => { emergencyLatched=false; released=false; armed=false; send({type:'resume_control'}); directAction={...emptyAction(),...patch}; directUntil=Date.now()+duration; sendControl(); };
  function connect() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    socket = new WebSocket(`${protocol}//${location.host}/control`);
    socket.addEventListener('open', () => { released = false; $('connection').textContent = 'Connected'; $('connection').classList.add('live'); $('error').textContent = ''; });
    socket.addEventListener('message', event => { try { const message = JSON.parse(event.data); if (message.type === 'state') updateState(message); } catch (_) { $('error').textContent = 'Invalid state from bridge'; } });
    socket.addEventListener('close', () => { armed = false; $('connection').textContent = 'Disconnected'; $('connection').classList.remove('live'); clearTimeout(reconnectTimer); reconnectTimer = setTimeout(connect, 1000); });
    socket.addEventListener('error', () => { $('error').textContent = 'Control connection error'; });
  }
  function updateState(message) {
    state = message; const o = message.observation || {}; const self = o.self || {}; const target = o.target || null; const configuredTarget=o.selector && o.selector.target_type; if(configuredTarget && $('target').value!==configuredTarget) $('target').value=configuredTarget;
    updateBotLifecycle(message.bot_lifecycle);
    $('session').textContent = message.session_id || '—'; $('encounter').textContent = message.encounter_id || '—'; $('recording').textContent = message.recording_state || 'idle';
    $('health').textContent = display(self.health); $('target-health').textContent = target ? display(target.health) : '—'; $('distance').textContent = target ? display(target.distance, 2) : '—'; $('tracked').textContent = target ? 'yes' : 'no'; $('los').textContent = target ? (target.line_of_sight == null ? '—' : (target.line_of_sight ? 'yes' : 'no')) : '—';
    const incoming=self.incoming_attack||{}, attacker=incoming.attacker_name||incoming.attacker_mob_type; const threat=$('threat'); threat.className='threat'; if(incoming.hit_received){const amount=display(incoming.damage,1); threat.classList.add('hit'); threat.textContent=`HIT${amount==='—'?'':` −${amount} HP`}${attacker?` by ${attacker}`:''}`; $('incoming').textContent='HIT';}else{threat.classList.add('quiet'); threat.textContent='Incoming: quiet'; $('incoming').textContent='quiet';} $('last-hit').textContent=incoming.hit_age_ms==null?'—':`${(incoming.hit_age_ms/1000).toFixed(1)}s · ${display(incoming.damage,1)} HP`;
    const nextViewerGeneration = message.bot_lifecycle?.viewer_generation ?? message.viewer_generation ?? null;
    if (message.viewer_port && (message.viewer_port !== viewerPort || nextViewerGeneration !== viewerGeneration)) {
      viewerPort = message.viewer_port; viewerGeneration = nextViewerGeneration; viewer.src = `/viewer/?generation=${encodeURIComponent(viewerGeneration ?? Date.now())}`;
    }
    if (message.viewer_error) $('error').textContent = `Viewer: ${message.viewer_error}`;
    const teacher = message.teacher || null;
    $('teacher-name').textContent = teacher ? teacher.name : '—';
    $('teacher-hp').textContent = teacher ? display(teacher.health, 1) : '—';
    $('teacher-food').textContent = teacher ? display(teacher.food) : '—';
    $('teacher-held').textContent = teacher ? (teacher.held_item?.main || '—') : '—';
    $('teacher-keys').textContent = teacher && teacher.inputs?.length ? teacher.inputs.map(g => ({forward:'W',back:'S',left:'A',right:'D',jump:'SPC',sneak:'SHF',sprint:'SPR',attack:'LMB',use:'RMB'})[g] || g).join(' ') : '—';
    $('teacher-falling').hidden = !(teacher && teacher.falling);
    drawTarget(target, self);
  }
  function updateBotLifecycle(lifecycle) {
    if (!lifecycle) return;
    const stateName = String(lifecycle.state || 'left');
    const labels = { joined: 'Joined', joining: 'Joining', left: 'Left', leaving: 'Leaving', error: 'Error' };
    const stateEl = $('bot-lifecycle');
    stateEl.textContent = labels[stateName] || stateName;
    stateEl.className = `bot-state ${stateName}`;
    const button = $('bot-toggle');
    button.textContent = stateName === 'joined' || stateName === 'joining' ? 'Leave bot' : 'Join bot';
    button.disabled = stateName === 'leaving';
    if (stateName === 'error' && lifecycle.error) $('error').textContent = `Bot: ${lifecycle.error}`;
  }
  async function toggleBot() {
    const current = state.bot_lifecycle?.state || 'left';
    const leaving = current === 'joined' || current === 'joining';
    const endpoint = leaving ? '/v1/bot/leave' : '/v1/bot/join';
    const button = $('bot-toggle');
    button.disabled = true;
    if (leaving) { release(); document.exitPointerLock?.(); }
    try {
      const response = await fetch(endpoint, { method: 'POST' });
      const payload = await response.json().catch(() => ({}));
      if (payload.bot_lifecycle) { state.bot_lifecycle = payload.bot_lifecycle; updateBotLifecycle(payload.bot_lifecycle); }
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      $('error').textContent = '';
    } catch (error) {
      $('error').textContent = `Bot: ${error.message}`;
      button.disabled = false;
    }
  }
  function display(value, digits = 0) { return value == null || !Number.isFinite(Number(value)) ? '—' : Number(value).toFixed(digits); }
  function resize() { const rect = overlay.getBoundingClientRect(); const dpr = window.devicePixelRatio || 1; overlay.width = Math.max(1, Math.round(rect.width*dpr)); overlay.height = Math.max(1, Math.round(rect.height*dpr)); overlay.getContext('2d').setTransform(dpr,0,0,dpr,0,0); drawTarget(state.observation && state.observation.target, state.observation && state.observation.self); }
  function drawTarget(target, self) {
    const ctx = overlay.getContext('2d'); const w = overlay.clientWidth, h = overlay.clientHeight; ctx.clearRect(0,0,w,h); if (!target || !target.aabb || !self?.position) return;
    const fovY = Number(state.viewer_fov_y ?? state.observation?.viewer_fov_y ?? (75 * Math.PI / 180)); const edges = boxEdges(target.aabb, { ...self, yaw: Number(self.yaw || 0), pitch: Number(self.pitch || 0) }, w, h, fovY);
    ctx.strokeStyle = target.line_of_sight === false ? '#ff786f' : '#55e68a'; ctx.lineWidth = 2; ctx.beginPath(); for (const edge of edges) { if (!edge[0] || !edge[1]) continue; ctx.moveTo(edge[0].x, edge[0].y); ctx.lineTo(edge[1].x, edge[1].y); } ctx.stroke();
    const aim = target.aim_point || { x:(target.aabb.min.x+target.aabb.max.x)/2, y:(target.aabb.min.y+target.aabb.max.y)/2, z:(target.aabb.min.z+target.aabb.max.z)/2 }; const aimScreen = project(cameraPoint(aim, { ...self, yaw:Number(self.yaw || 0), pitch:Number(self.pitch || 0) }), w, h, fovY); if (aimScreen) { ctx.fillStyle = ctx.strokeStyle; ctx.beginPath(); ctx.arc(aimScreen.x, aimScreen.y, 4, 0, Math.PI*2); ctx.fill(); }
    ctx.strokeStyle = '#fff9'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(w/2-8,h/2); ctx.lineTo(w/2+8,h/2); ctx.moveTo(w/2,h/2-8); ctx.lineTo(w/2,h/2+8); ctx.stroke();
    drawHud(ctx, w, h, self);
  }
  let lastHeldName = null, heldFlashUntil = 0, lastDamageAt = 0, lastDamageSeen = null;
  function drawHud(ctx, w, h, self) {
    const inv = state.observation?.inventory;
    // damage flash
    const inc = self?.incoming_attack;
    if (inc?.hit_received) {
      if (lastDamageSeen == null || inc.hit_age_ms < lastDamageSeen) lastDamageAt = performance.now();
      lastDamageSeen = inc.hit_age_ms;
      const a = Math.max(0, 1 - (performance.now() - lastDamageAt) / 700);
      if (a > 0) { ctx.fillStyle = `rgba(180,30,30,${(a * 0.28).toFixed(3)})`; ctx.fillRect(0, 0, w, h); }
    }
    // chat / system pane (teacher poll replies are filtered server-side)
    const msgs = state.messages || [];
    ctx.font = '10px monospace'; ctx.textBaseline = 'top';
    msgs.forEach((m, i) => {
      const y = h - 190 - (msgs.length - 1 - i) * 13;
      ctx.fillStyle = '#0008'; ctx.fillRect(8, y - 1, ctx.measureText(m).width + 6, 12);
      ctx.fillStyle = '#dde6ea'; ctx.fillText(m.slice(0, 90), 11, y);
    });
    // coords + facing (yaw 0 = -Z = N)
    const p = self?.position;
    if (p) {
      const dirs = ['N', 'W', 'S', 'E'];
      const dir = dirs[((Math.round(Number(self.yaw || 0) / (Math.PI / 2)) % 4) + 4) % 4];
      ctx.fillStyle = '#0008'; ctx.fillRect(8, h - 30, 150, 14);
      ctx.fillStyle = '#cfe'; ctx.fillText(`${p.x.toFixed(1)} ${p.y.toFixed(1)} ${p.z.toFixed(1)}  ${dir}`, 11, h - 28);
    }
    if (!inv) return;
    const slot = 44, gap = 4, n = 9, offX = 14;
    const rowW = n * slot + (n - 1) * gap;
    const x0 = (w - rowW) / 2, y0 = h - slot - 10;
    for (let i = 0; i < n; i++) {
      const x = x0 + i * (slot + gap);
      ctx.fillStyle = '#000a'; ctx.fillRect(x, y0, slot, slot);
      ctx.strokeStyle = i === inv.selected ? '#ffe27a' : '#556'; ctx.lineWidth = i === inv.selected ? 2 : 1;
      ctx.strokeRect(x + 0.5, y0 + 0.5, slot - 1, slot - 1);
      const it = inv.hotbar?.[i];
      if (it) {
        ctx.fillStyle = '#eef4f8';
        const label = it.name.replace('minecraft:', '').slice(0, 8);
        ctx.fillText(label, x + 2, y0 + 4, slot - 4);
        ctx.fillText(String(it.count ?? ''), x + 2, y0 + slot - 14);
      }
    }
    // offhand slot, left of the row
    const ox = x0 - slot - offX;
    ctx.fillStyle = '#000a'; ctx.fillRect(ox, y0, slot, slot);
    ctx.strokeStyle = '#8a6dbb'; ctx.strokeRect(ox + 0.5, y0 + 0.5, slot - 1, slot - 1);
    if (inv.offhand) { ctx.fillStyle = '#d9c8ff'; ctx.fillText(inv.offhand.replace('minecraft:', '').slice(0, 8), ox + 2, y0 + 4, slot - 4); }
    // held item name on slot change (vanilla-style flash above hotbar)
    if (inv.main_hand !== lastHeldName) { lastHeldName = inv.main_hand; heldFlashUntil = performance.now() + 1400; }
    if (inv.main_hand && performance.now() < heldFlashUntil) {
      ctx.font = 'bold 13px system-ui';
      const label = inv.main_hand.replace('minecraft:', '').replaceAll('_', ' ');
      ctx.fillStyle = '#0008'; ctx.fillRect(w / 2 - ctx.measureText(label).width / 2 - 6, y0 - 44, ctx.measureText(label).width + 12, 18);
      ctx.fillStyle = '#ffe27a'; ctx.fillText(label, w / 2 - ctx.measureText(label).width / 2, y0 - 41);
      ctx.font = '10px monospace';
    }
    // xp bar + level, directly above hotbar
    const xp = Math.max(0, Math.min(1, Number(self?.xp_progress ?? 0)));
    ctx.fillStyle = '#000a'; ctx.fillRect(x0, y0 - 7, rowW, 4);
    ctx.fillStyle = '#7ee050'; ctx.fillRect(x0, y0 - 7, rowW * xp, 4);
    if (self?.xp_level > 0) { ctx.fillStyle = '#7ee050'; ctx.font = 'bold 11px monospace'; ctx.fillText(String(self.xp_level), w / 2 - 4, y0 - 22); ctx.font = '10px monospace'; }
    // armor + hp bars (left), food + air bubbles (right)
    const bw = rowW / 2 - 4, bh = 7, by = y0 - bh - 14;
    ctx.fillStyle = '#000a'; ctx.fillRect(x0, by, bw, bh); ctx.fillRect(x0 + bw + 8, by, bw, bh);
    const hp = Math.max(0, Math.min(20, Number(self?.health ?? 0)));
    const fd = Math.max(0, Math.min(20, Number(self?.food ?? 0)));
    ctx.fillStyle = '#c33'; ctx.fillRect(x0 + 1, by + 1, (bw - 2) * hp / 20, bh - 2);
    ctx.fillStyle = '#b96'; ctx.fillRect(x0 + bw + 9, by + 1, (bw - 2) * fd / 20, bh - 2);
    const ar = Math.max(0, Math.min(20, Number(self?.armor ?? 0)));
    if (ar > 0) {
      ctx.fillStyle = '#000a'; ctx.fillRect(x0, by - 10, bw, 5);
      ctx.fillStyle = '#9ab'; ctx.fillRect(x0 + 1, by - 9, (bw - 2) * ar / 20, 3);
    }
    if (self?.in_water && self?.oxygen != null && self.oxygen < 20) {
      const bubbles = Math.ceil(self.oxygen / 2);
      for (let i = 0; i < 10; i++) {
        ctx.fillStyle = i < bubbles ? '#6cf' : '#234';
        ctx.beginPath(); ctx.arc(x0 + bw + 12 + i * 9, by - 11, 3.4, 0, Math.PI * 2); ctx.fill();
      }
    }
    // FALLING badge
    if (self?.falling) {
      ctx.fillStyle = '#c22'; ctx.font = 'bold 16px system-ui';
      ctx.fillText('FALLING', w / 2 - 40, h * 0.35);
      ctx.font = '10px monospace';
    }
  }
  function key(event, down) { if (down && event.code === 'Escape') { release(true); document.exitPointerLock?.(); return; } if (!active()) return; const mapped = keys.get(event.code); if (mapped) { event.preventDefault(); action[mapped] = down; sendControl(); } if (down && /^Digit[1-9]$/.test(event.code)) { action.hotbar = Number(event.code.slice(-1))-1; event.preventDefault(); sendControl(); } }
  document.addEventListener('keydown', e => key(e,true)); document.addEventListener('keyup', e => key(e,false));
  overlay.addEventListener('click', () => { if (socket?.readyState !== WebSocket.OPEN) return; emergencyLatched = false; capturePending = true; released = false; send({type:'resume_control'}); overlay.requestPointerLock?.(); $('start-hint').style.display='none'; });
  document.addEventListener('mousemove', e => { if (!active()) return; const width = Math.max(1, overlay.clientWidth), height = Math.max(1, overlay.clientHeight); const fovX = Math.PI/2, fovY = 2*Math.atan(Math.tan(fovX/2)/(width/height)); const dy = -finite(e.movementX) * fovX / width, dp = -finite(e.movementY) * fovY / height; action.mouse_dx += finite(e.movementX); action.mouse_dy += finite(e.movementY); action.yaw_delta += dy; action.pitch_delta += dp; if (camYaw != null) { camYaw += dy; camPitch = Math.max(-Math.PI/2, Math.min(Math.PI/2, camPitch + dp)); lastMouseMoveAt = performance.now(); } });
  overlay.addEventListener('mousedown', e => { if (!active()) return; e.preventDefault(); if (e.button === 0) action.attack=true; if (e.button === 2) action.use=true; sendControl(); });
  overlay.addEventListener('mouseup', e => { if (!active()) return; if (e.button === 0) action.attack=false; if (e.button === 2) action.use=false; sendControl(); }); overlay.addEventListener('wheel', e => { if (!active()) return; action.hotbar = Math.max(0, Math.min(8, action.hotbar + (e.deltaY > 0 ? 1 : -1))); e.preventDefault(); sendControl(); }); overlay.addEventListener('contextmenu', e => e.preventDefault());
  document.addEventListener('pointerlockchange', () => { if (document.pointerLockElement === overlay) { capturePending = false; armed = true; released = false; } else if (!emergencyLatched) { capturePending = false; release(); } }); window.addEventListener('blur', () => { capturePending = false; release(); }); document.addEventListener('visibilitychange', () => { if (document.hidden) { capturePending = false; release(); } });
  $('target').addEventListener('change', () => send({type:'target', mob_type:$('target').value})); document.querySelectorAll('[data-record]').forEach(button => button.addEventListener('click', () => send({type:'record',command:button.dataset.record}))); document.querySelectorAll('[data-label]').forEach(button => button.addEventListener('click', () => send({type:'label',label:button.dataset.label})));
  const drives={forward:[{forward:true,sprint:true},800],back:[{back:true},600],left:[{left:true},600],right:[{right:true},600],shield:[{use:true},800],attack:[{attack:true},180],jump:[{forward:true,jump:true},350],'turn-left':[{yaw_delta:Math.PI/15},120],'turn-right':[{yaw_delta:-Math.PI/15},120]}; document.querySelectorAll('[data-drive]').forEach(button=>button.addEventListener('click',()=>{const [patch,duration]=drives[button.dataset.drive];drive(patch,duration);}));
  $('bot-toggle').addEventListener('click', toggleBot);
  setInterval(sendControl, 100);
  // fast path: flush accumulated mouse deltas at ~60 Hz so look isn't stuck behind the heartbeat
  setInterval(() => { if (active() && (action.yaw_delta || action.pitch_delta || action.mouse_dx || action.mouse_dy)) sendControl(); }, 16);

  // ---- local camera: the /viewer/ iframe is same-origin, so drive its camera
  // directly every rAF. Mouse deltas rotate instantly; position lerps toward
  // the server's 20 Hz updates; yaw/pitch reconciles (snap > 5 deg, else ease).
  let camYaw = null, camPitch = null, srvPos = null, camFrames = 0, lastMouseMoveAt = 0;
  const wrapPi = a => { a = (a + Math.PI) % (Math.PI * 2); if (a < 0) a += Math.PI * 2; return a - Math.PI; };
  viewer.addEventListener('load', () => {
    const win = viewer.contentWindow;
    win.fbCam = (pos, yaw, pitch) => {
      srvPos = { x: pos.x, y: pos.y + 1.62, z: pos.z };
      if (camYaw == null || !armed) { camYaw = yaw; camPitch = pitch; return; }
      const ye = wrapPi(yaw - camYaw), pe = pitch - camPitch;
      if (Math.abs(ye) > 0.087 || Math.abs(pe) > 0.087) { camYaw = yaw; camPitch = pitch; }
      else { camYaw += ye * 0.25; camPitch += pe * 0.25; }
    };
  });
  function camLoop() {
    requestAnimationFrame(camLoop);
    const v = viewer.contentWindow?.viewer;
    if (v?.camera) {
      if (camYaw != null) v.camera.rotation.set(camPitch, camYaw, 0, 'ZYX');
      const p = v.camera.position;
      if (srvPos) { p.x += (srvPos.x - p.x) * 0.35; p.y += (srvPos.y - p.y) * 0.35; p.z += (srvPos.z - p.z) * 0.35; }
      if (lastMouseMoveAt) { window.__inputToCamMs = performance.now() - lastMouseMoveAt; lastMouseMoveAt = 0; }
    }
    camFrames++;
    drawTarget(state.observation?.target, state.observation?.self);
  }
  requestAnimationFrame(camLoop);
  setInterval(() => { window.__fps = camFrames / 5; camFrames = 0; }, 5000);
  new ResizeObserver(resize).observe(overlay); window.addEventListener('resize', resize); connect();
})();
