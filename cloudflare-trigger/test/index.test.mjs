import test from "node:test";
import assert from "node:assert/strict";

import { dispatch, modeForCron } from "../src/index.mjs";


test("09:20 cron maps to production workflow", () => {
  assert.equal(modeForCron("20 1 * * *"), "production");
});

test("10:05 cron maps to read-only watchdog workflow", () => {
  assert.equal(modeForCron("5 2 * * *"), "watchdog");
});


test("dispatch sends production input without exposing token in body", async () => {
  let request;
  const fakeFetch = async (url, options) => {
    request = { url, options };
    return new Response(null, { status: 204 });
  };

  await dispatch(
    { GITHUB_TOKEN: "secret", REPO: "owner/repo" },
    "production",
    fakeFetch,
  );

  assert.match(request.url, /daily-report.yml\/dispatches$/);
  assert.equal(JSON.parse(request.options.body).inputs.mode, "production");
  assert.doesNotMatch(request.options.body, /secret/);
});


test("non-204 GitHub response fails visibly", async () => {
  const fakeFetch = async () => new Response("failed", { status: 500 });

  await assert.rejects(
    dispatch(
      { GITHUB_TOKEN: "secret", REPO: "owner/repo" },
      "production",
      fakeFetch,
    ),
    /500/,
  );
});
