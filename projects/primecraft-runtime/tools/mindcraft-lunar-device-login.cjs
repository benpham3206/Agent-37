"use strict";

const path = require("node:path");
const mineflayer = require("mineflayer");

const target = Object.freeze({ host: "6ento.lunarclient.world", port: 64680, version: "26.1.2" });
const cacheDir = process.env.MINDCRAFT_AUTH_CACHE_DIR;
const accountAlias = process.env.MINDCRAFT_AUTH_ALIAS || "MindcraftAlt";

if (typeof cacheDir !== "string" || !path.isAbsolute(cacheDir)) {
  throw new Error("MINDCRAFT_AUTH_CACHE_DIR must be an absolute D: path");
}
if (!/^[A-Za-z0-9_]{3,16}$/.test(accountAlias)) {
  throw new Error("MINDCRAFT_AUTH_ALIAS must be 3-16 letters, numbers, or underscores");
}

console.log("Mindcraft CE Microsoft authentication is starting for the Lunar Hosted World.");
console.log("Sign in with the SECOND official Java Minecraft account intended for the bot, not the account hosting the world.");

let completed = false;
const bot = mineflayer.createBot({
  ...target,
  auth: "microsoft",
  username: accountAlias,
  profilesFolder: cacheDir,
  onMsaCode(data) {
    console.log("\nDEVICE CODE REQUIRED");
    console.log(`Open: ${data.verification_uri || "https://microsoft.com/link"}`);
    console.log(`Code: ${data.user_code || "(shown in the browser prompt)"}`);
    console.log("Then complete sign-in with the bot account. This window will confirm its Minecraft profile and exit safely.\n");
  },
});

bot.once("spawn", () => {
  completed = true;
  const position = bot.entity && bot.entity.position;
  console.log(JSON.stringify({
    event: "authenticated_spawn",
    minecraft_profile: bot.username,
    position: position ? { x: position.x, y: position.y, z: position.z } : null,
  }));
  setTimeout(() => bot.quit("Mindcraft auth cache ready"), 1000);
});

bot.once("end", (reason) => {
  console.log(JSON.stringify({ event: "ended", authenticated: completed, reason: String(reason || "") }));
  process.exitCode = completed ? 0 : 1;
});

bot.once("error", (error) => {
  console.error(JSON.stringify({ event: "error", message: String(error && error.message ? error.message : error) }));
});

process.once("SIGINT", () => bot.quit("Authentication cancelled"));
