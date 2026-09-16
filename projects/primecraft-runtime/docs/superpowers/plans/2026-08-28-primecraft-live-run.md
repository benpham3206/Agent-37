# Primecraft live run implementation plan

> For agentic workers: execute this plan inline in the current task and keep the live run observable.

**Goal:** Make `primecraft` launch the D:-drive local Survival server, Mineflayer adapter, and a Prime-Agent session that keeps PrimeBot connected, observes the world, responds in chat, and performs bounded movement/actions until the user explicitly stops it.

**Architecture:** The server owns the world, the Mineflayer adapter owns one bot connection, and Prime-Agent owns the decision loop through the `minecraft-control` skill. The first live slice proves presence, chat, observation, and movement; progression capabilities are added behind the same generic action boundary.

**Tech Stack:** PowerShell orchestration, Java server, Python Mineflayer adapter, Node.js Mineflayer worker, Prime-Agent IPython skill bridge, D:-drive logs/evidence.

## Global Constraints

- Keep project, runtime, logs, pads, and evidence under `D:\Codex\2026-08-26`.
- Preserve the user’s explicit-stop rule: the live loop must not intentionally call disconnect/stop during ordinary death, failure, or being stuck.
- Do not run native Mindcraft CE’s separate LLM controller at the same time as Prime-Agent’s actor.
- Do not claim The End progression is implemented until the corresponding capabilities exist and are observed.
- Use focused runtime proof and only the smallest supporting checks; this is specification-driven work, not test-count optimization.

## Tasks

1. **Expose a persistent generic action boundary**
   - Add a `presence_action(...)` function to the Prime skill bridge for short movement/look actions.
   - Preserve episode/controller metadata and return a fresh post-action observation.
   - Keep unsupported actions explicit rather than silently translating them into a fake success.

2. **Create the `primecraft` launcher**
   - Start or adopt the configured 25566 server and 18765 adapter idempotently.
   - Set the target port and D:-drive evidence paths.
   - Launch Prime-Agent with Luna/xhigh and a persistent live-run goal.
   - Provide an explicit stop/status path without invoking it during this run.

3. **Give Prime-Agent the live-loop contract**
   - Start presence once, read observations, answer chat, and take bounded actions.
   - Continue after deaths and recoverable action failures; record shortcomings in the session pad.
   - Never call the stop/disconnect operation unless the user explicitly requests it.

4. **Launch and verify the visible checkpoint**
   - Launch the orchestrator visibly and let the user’s Lunar client join the same local world.
   - Verify server listener, bot join, model-attributed chat, fresh observation, and a changed position/action receipt in D:-drive evidence.
   - Record the actual result and the next missing capability in the current session pad.

## Definition of Done

`primecraft` is running visibly; Lunar can show the world; PrimeBot remains connected; Prime-Agent has read a live observation, sent a chat response, and caused at least one bounded movement/look action with post-action evidence. Any larger progression gap is stated plainly for the next slice.
