const crypto = require("node:crypto");

const ALGORITHM = "pbkdf2_sha256";
const ITERATIONS = 600000;
const SALT_BYTES = 16;

function hashPassword(password) {
  if (typeof password !== "string" || password.length < 1 || password.length > 128) {
    throw new TypeError("Password must be a string with 1–128 characters.");
  }
  const salt = crypto.randomBytes(SALT_BYTES);
  const digest = crypto.pbkdf2Sync(password, salt, ITERATIONS, 32, "sha256");
  return ALGORITHM + "$" + ITERATIONS + "$" + salt.toString("hex") + "$" + digest.toString("hex");
}

function verifyPassword(password, stored) {
  if (typeof password !== "string" || typeof stored !== "string" || !password || !stored) {
    return { valid: false, legacy: false };
  }
  if (!stored.startsWith(ALGORITHM + "$")) {
    const a = Buffer.from(password, "utf8");
    const b = Buffer.from(stored, "utf8");
    return { valid: a.length === b.length && crypto.timingSafeEqual(a, b), legacy: true };
  }
  try {
    const [algorithm, roundsText, saltHex, digestHex] = stored.split("$");
    const rounds = Number(roundsText);
    if (algorithm !== ALGORITHM || !Number.isInteger(rounds) ||
        rounds < 100000 || rounds > 1000000 ||
        !/^[0-9a-f]{32}$/.test(saltHex) || !/^[0-9a-f]{64}$/.test(digestHex)) {
      return { valid: false, legacy: false };
    }
    const expected = Buffer.from(digestHex, "hex");
    const actual = crypto.pbkdf2Sync(password, Buffer.from(saltHex, "hex"), rounds, 32, "sha256");
    return { valid: crypto.timingSafeEqual(actual, expected), legacy: false };
  } catch {
    return { valid: false, legacy: false };
  }
}

module.exports = { hashPassword, verifyPassword };
