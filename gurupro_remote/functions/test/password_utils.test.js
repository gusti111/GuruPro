const test = require("node:test");
const assert = require("node:assert/strict");
const { hashPassword, verifyPassword } = require("../password_utils");

test("PBKDF2 password hashes are salted and not plaintext", () => {
  const first = hashPassword("CorrectHorseBattery99");
  const second = hashPassword("CorrectHorseBattery99");
  assert.notEqual(first, "CorrectHorseBattery99");
  assert.notEqual(first, second);
  assert.deepEqual(verifyPassword("CorrectHorseBattery99", first), { valid: true, legacy: false });
});

test("wrong passwords fail", () => {
  const encoded = hashPassword("CorrectHorseBattery99");
  assert.deepEqual(verifyPassword("wrong", encoded), { valid: false, legacy: false });
});

test("legacy plaintext is accepted only for controlled migration", () => {
  assert.deepEqual(verifyPassword("legacy", "legacy"), { valid: true, legacy: true });
  assert.deepEqual(verifyPassword("not-legacy", "legacy"), { valid: false, legacy: true });
});

test("malformed hashes and excessive iteration counts fail closed", () => {
  assert.deepEqual(verifyPassword("x", "pbkdf2_sha256$broken"), { valid: false, legacy: false });
  assert.deepEqual(verifyPassword("x", "pbkdf2_sha256$999999999$" + "a".repeat(32) + "$" + "b".repeat(64)), { valid: false, legacy: false });
});

test("empty and overlong passwords are rejected during hashing", () => {
  assert.throws(() => hashPassword(""));
  assert.throws(() => hashPassword("x".repeat(129)));
});
