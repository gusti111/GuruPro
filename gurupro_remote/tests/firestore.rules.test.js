const { before, after, beforeEach, describe, it } = require("node:test");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { initializeTestEnvironment, assertFails, assertSucceeds } = require("@firebase/rules-unit-testing");
const { doc, getDoc, setDoc } = require("firebase/firestore");

const projectId = "demo-gurupro-rules";
let testEnv;

before(async () => {
  testEnv = await initializeTestEnvironment({
    projectId,
    firestore: {
      rules: readFileSync(join(__dirname, "..", "firestore.rules"), "utf8"),
    },
  });
});

after(async () => {
  await testEnv.cleanup();
});

beforeEach(async () => {
  await testEnv.clearFirestore();
});

describe("Firestore baseline rules", () => {
  it("denies unauthenticated reads and writes", async () => {
    const db = testEnv.unauthenticatedContext().firestore();
    const ref = doc(db, "users", "sample-user");
    await assertFails(getDoc(ref));
    await assertFails(setDoc(ref, { name: "sample" }));
  });

  it("denies authenticated client reads and writes until ownership rules are implemented", async () => {
    const db = testEnv.authenticatedContext("sample-uid").firestore();
    const ref = doc(db, "users", "sample-user");
    await assertFails(getDoc(ref));
    await assertFails(setDoc(ref, { uid: "sample-uid", name: "sample" }));
  });

  it("allows no client access to remote sessions", async () => {
    const db = testEnv.authenticatedContext("sample-uid").firestore();
    const ref = doc(db, "remote_sessions", "sample-session");
    await assertFails(getDoc(ref));
    await assertFails(setDoc(ref, { uid: "sample-uid", status: "connected" }));
  });
});
