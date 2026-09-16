import http from 'node:http';
import { io } from 'socket.io-client';

const args = new Map();
for (let i = 2; i < process.argv.length; i += 1) {
    if (process.argv[i].startsWith('--')) args.set(process.argv[i], process.argv[++i]);
}
const mindserverPort = Number(args.get('--mindserver-port') || 8080);
const controlPort = Number(args.get('--control-port') || 18766);
const agentName = args.get('--agent');
const token = process.env.PRIME_CE_BRIDGE_TOKEN;
if (!agentName || !Number.isInteger(mindserverPort) || !Number.isInteger(controlPort) || !token) {
    throw new Error('agent, valid ports, and PRIME_CE_BRIDGE_TOKEN are required');
}

const allowedKinds = new Set(['move', 'look', 'navigate', 'collect_blocks', 'craft_recipe', 'equip', 'go_to_bed', 'chat']);
let latestState = null;
let recentChat = [];
let connected = false;
const socket = io(`http://127.0.0.1:${mindserverPort}`, { transports: ['websocket'] });
socket.on('connect', () => {
    connected = true;
    socket.emit('listen-to-agents');
});
socket.on('disconnect', () => { connected = false; });
socket.on('prime-chat', (source, message) => {
    if (source !== agentName || !message || typeof message !== 'object') return;
    if (typeof message.sender !== 'string' || typeof message.message !== 'string' || !Number.isInteger(message.received_at_ms)) return;
    recentChat.push({ sender: message.sender, message: message.message, received_at_ms: message.received_at_ms });
    if (recentChat.length > 32) recentChat.shift();
});
socket.on('state-update', (states) => {
    if (states && typeof states === 'object' && states[agentName]) latestState = states[agentName];
});

function json(res, status, value) {
    const body = JSON.stringify(value);
    res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    res.end(body);
}
function authorized(req) {
    return req.headers['x-prime-controller'] === token;
}
function readBody(req) {
    return new Promise((resolve, reject) => {
        let data = '';
        req.on('data', (chunk) => { data += chunk; if (data.length > 8192) reject(new Error('body_too_large')); });
        req.on('end', () => { try { resolve(JSON.parse(data || '{}')); } catch (_error) { reject(new Error('invalid_json')); } });
        req.on('error', reject);
    });
}
function validAction(action) {
    return action && typeof action === 'object' && !Array.isArray(action) && allowedKinds.has(action.kind);
}

const server = http.createServer(async (req, res) => {
    if (req.url === '/healthz' && req.method === 'GET') {
        json(res, 200, { state: 'ready', connected, agent: agentName, action_enabled: connected });
        return;
    }
    if (!authorized(req)) { json(res, 401, { error: 'unauthorized' }); return; }
    if (req.url === '/v1/observation' && req.method === 'GET') {
        if (!connected) { json(res, 503, { error: 'mindserver_unavailable' }); return; }
        json(res, 200, { agent: agentName, observation: latestState, recent_chat: recentChat });
        return;
    }
    if (req.url === '/v1/action' && req.method === 'POST') {
        try {
            const body = await readBody(req);
            if (body.agent !== agentName || !validAction(body.action)) { json(res, 400, { error: 'invalid_action' }); return; }
            if (!connected) { json(res, 503, { error: 'mindserver_unavailable' }); return; }
            socket.emit('prime-action', agentName, body.action, (result) => json(res, result?.success ? 200 : 409, result || { success: false, error: 'no_result' }));
        } catch (error) { json(res, 400, { error: error.message }); }
        return;
    }
    json(res, 404, { error: 'not_found' });
});
server.listen(controlPort, '127.0.0.1', () => console.log(`Prime CE bridge listening on 127.0.0.1:${controlPort}`));
process.on('SIGINT', () => { server.close(); socket.close(); });
