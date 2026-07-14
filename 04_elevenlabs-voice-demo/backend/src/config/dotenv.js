// src/config/dotenv.js
import dotenv from "dotenv";
import path from "path";
import { fileURLToPath } from "url";
import dns from "dns"; // ✅ add this

// Needed to resolve __dirname in ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config({
  path: path.join(__dirname, "../../.env"), // points to your project root
});

// ✅ FIX: Override DNS servers (CRITICAL for mongodb+srv)
if (process.env.NODE_ENV !== "production") {
  dns.setServers(["1.1.1.1", "8.8.8.8"]);
  console.log("🌐 DNS override enabled (dev only)");
}

console.log("✅ .env loaded");
