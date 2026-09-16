// Live right-click verification: hold water_bucket, look down, use -> water placed,
// pitch unchanged (no lookAt side-effect). Then use empty bucket -> water removed.
const require2 = require('module').createRequire('D:/Codex/2026-08-26/plea/work/mindcraft-ce/node_modules/package.json');
const WebSocket = require2('ws');

const jget = async (p) => fetch(`http://127.0.0.1:8876${p}`).then(r => r.json());
const recent = async (n = 300) => (await jget(`/v1/events/recent?n=${n}`)).events;

(async () => {
    const ws = new WebSocket('ws://127.0.0.1:8876/control');
    let lastState = null;
    ws.on('message', d => { const m = JSON.parse(d); if (m.type === 'state') lastState = m; });
    await new Promise(r => ws.on('open', r));
    const send = m => ws.send(JSON.stringify(m));
    send({ type: 'resume_control' });
    await new Promise(r => setTimeout(r, 500));

    const inv = lastState?.observation?.inventory;
    if (!inv) { console.log('FAIL: no inventory in state'); process.exit(1); }
    console.log('hotbar:', inv.hotbar.map(i => i?.name).join('|'), 'offhand:', inv.offhand);
    let slot = inv.hotbar.findIndex(i => i?.name === 'water_bucket');
    if (slot < 0) { console.log('FAIL: no water_bucket in hotbar'); process.exit(1); }
    send({ type: 'control', action: { hotbar: slot } });
    await new Promise(r => setTimeout(r, 300));

    // pitch down to look at ground
    send({ type: 'control', action: { pitch_delta: 1.2, hotbar: slot } });
    await new Promise(r => setTimeout(r, 400));
    const obs0 = (await jget('/v1/observation')).observation;
    const yaw0 = obs0.self.yaw, pitch0 = obs0.self.pitch;
    console.log('before: yaw', yaw0.toFixed(4), 'pitch', pitch0.toFixed(4), '| held:', obs0.self.held_item);

    const mark = Date.now();
    // hold use ~700ms
    const t0 = Date.now();
    while (Date.now() - t0 < 700) { send({ type: 'control', action: { use: true, hotbar: slot } }); await new Promise(r => setTimeout(r, 50)); }
    send({ type: 'control', action: { use: false, hotbar: slot } });
    await new Promise(r => setTimeout(r, 800));

    const obs1 = (await jget('/v1/observation')).observation;
    const dpitch = Math.abs(obs1.self.pitch - pitch0), dyaw = Math.abs(obs1.self.yaw - yaw0);
    console.log('after : yaw', obs1.self.yaw.toFixed(4), 'pitch', obs1.self.pitch.toFixed(4));
    console.log('dpitch:', dpitch.toFixed(4), 'dyaw:', dyaw.toFixed(4), dpitch < 0.01 ? 'PASS(no lookAt)' : 'FAIL');

    const evs = (await recent(500)).filter(e => e.t_ms >= mark - 500);
    const water = evs.find(e => e.kind === 'block' && e.to === 'water');
    const invEv = evs.filter(e => e.kind === 'inventory' && /bucket/.test(e.item));
    console.log('block->water event:', water ? `${water.from}->water @tick ${water.tick}` : 'none');
    console.log('bucket inventory events:', JSON.stringify(invEv.map(e => `${e.item} ${e.delta}`)));

    // second click with the now-empty bucket removes the water
    const mark2 = Date.now();
    const t1 = Date.now();
    while (Date.now() - t1 < 700) { send({ type: 'control', action: { use: true, hotbar: slot } }); await new Promise(r => setTimeout(r, 50)); }
    send({ type: 'control', action: { use: false, hotbar: slot } });
    await new Promise(r => setTimeout(r, 800));
    const evs2 = (await recent(500)).filter(e => e.t_ms >= mark2 - 500);
    const removed = evs2.find(e => e.kind === 'block' && e.from === 'water');
    console.log('water removed on second use:', removed ? `water->${removed.to} @tick ${removed.tick}` : 'none');

    // sprint check: forward without sneak -> sprint flag
    const t2 = Date.now();
    while (Date.now() - t2 < 800) { send({ type: 'control', action: { forward: true, hotbar: slot } }); await new Promise(r => setTimeout(r, 50)); }
    const sprintEv = (await recent(300)).filter(e => e.kind === 'key' && e.key === 'sprint').pop();
    console.log('sprint key event while forward:', JSON.stringify(sprintEv));
    send({ type: 'release' });
    ws.close();
    process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
