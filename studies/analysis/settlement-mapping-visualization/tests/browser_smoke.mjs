#!/usr/bin/env node

import assert from "node:assert/strict";

const endpoint = process.argv[2] || "http://127.0.0.1:9351";
const pages = await fetch(`${endpoint}/json/list`).then((response) => response.json());
const page = pages.find((item) => item.type === "page");
assert.ok(page, "chrome exposes a page target");

const socket = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, { once: true });
  socket.addEventListener("error", reject, { once: true });
});

let sequence = 0;
const pending = new Map();
const requests = [];
socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (message.method === "Network.requestWillBeSent") requests.push(message.params.request.url);
  if (!message.id || !pending.has(message.id)) return;
  const { resolve, reject } = pending.get(message.id);
  pending.delete(message.id);
  if (message.error) reject(new Error(message.error.message));
  else resolve(message.result);
});

function send(method, params = {}) {
  const id = ++sequence;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
}

async function evaluate(expression) {
  const result = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
  return result.result.value;
}

async function waitFor(expression, attempts = 80) {
  for (let index = 0; index < attempts; index += 1) {
    if (await evaluate(expression)) return;
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  throw new Error(`condition did not become true: ${expression}`);
}

async function pressKey(key, code = key) {
  const virtualKeys = { Enter: 13, Tab: 9, ArrowLeft: 37, ArrowRight: 39 };
  const windowsVirtualKeyCode = virtualKeys[key] || 0;
  await send("Input.dispatchKeyEvent", { type: "rawKeyDown", key, code, windowsVirtualKeyCode });
  if (key === "Enter") await send("Input.dispatchKeyEvent", { type: "char", key, code, text: "\r", windowsVirtualKeyCode });
  await send("Input.dispatchKeyEvent", { type: "keyUp", key, code, windowsVirtualKeyCode });
}

let checks = 0;
const equal = (actual, expected, message) => {
  assert.deepEqual(actual, expected, message);
  checks += 1;
};
const ok = (value, message) => {
  assert.ok(value, message);
  checks += 1;
};

await send("Runtime.enable");
await send("Page.enable");
await send("Network.enable");
await send("Emulation.clearDeviceMetricsOverride");
await send("Page.reload", { ignoreCache: true });
await waitFor("document.readyState === 'complete' && document.querySelectorAll('[data-scenario-id]').length === 2");

equal(await evaluate("document.querySelectorAll('[data-scenario-id]').length"), 2, "two matched scenarios");
equal(await evaluate("document.querySelectorAll('[data-observer] .datum').length"), 4, "four observer conditions");
equal(await evaluate("document.querySelectorAll('[data-field] [data-moment-id]').length"), 6, "six field moments including separate admission");
equal(await evaluate("document.querySelectorAll('[data-return-path] [data-moment-id]').length"), 4, "four return stages");
equal(await evaluate("document.querySelectorAll('[data-trace] [data-moment-id]').length"), 6, "six readable trace moments");
equal(await evaluate("[...document.querySelectorAll('[data-scenario-id]')].map(node => node.textContent.trim())"), ["matched fictional pathscenario a", "matched fictional pathscenario b"], "scenario navigation is neutral");
equal(await evaluate("document.querySelector('[data-condition-label]').textContent"), "read the switch before the verdict", "condition heading is neutral");
ok(await evaluate("document.querySelector('[data-readable-account]').textContent.includes('live alternative') && document.querySelector('[data-readable-account]').textContent.includes('explicit non-claim') && document.querySelector('[data-readable-account]').textContent.includes('return-path readings')"), "complete textual equivalent exposes alternatives, non-claims, and return readings");
ok(await evaluate("document.querySelector('[data-detail-title]').textContent.includes('priority declared')"), "initial detail is present");

await evaluate("document.querySelector('[data-field] [data-moment-id=\"protective-03\"]').focus(); document.querySelector('[data-field] [data-moment-id=\"protective-03\"]').click(); true");
ok(await evaluate("document.querySelector('[data-detail-title]').textContent.includes('small build chosen')"), "field selection updates detail");
equal(await evaluate("document.querySelector('[data-trace] [data-moment-id=\"protective-03\"]').getAttribute('aria-pressed')"), "true", "field selection updates trace");
equal(await evaluate("document.querySelector('[data-return-path] [data-moment-id=\"protective-03\"]').getAttribute('aria-pressed')"), "true", "field selection updates path");

await evaluate("document.querySelector('[data-scenario-id=\"protective-retention\"]').focus(); true");
await pressKey("ArrowRight");
equal(await evaluate("document.querySelector('[data-scenario-id=\"stale-capture\"]').getAttribute('aria-pressed')"), "true", "arrow key switches scenario");
ok(await evaluate("document.activeElement.dataset.scenarioId === 'stale-capture'"), "scenario switch retains keyboard focus");
equal(await evaluate("document.querySelector('[data-condition-label]').textContent"), "read the switch before the verdict", "scenario change does not promote verdict into heading");
ok(await evaluate("document.querySelector('[data-condition] .condition-verdict').textContent.includes('stale capture')"), "bounded verdict remains available after condition facts");

await evaluate("document.querySelector('[data-trace] [data-moment-id=\"stale-04\"]').focus(); document.querySelector('[data-trace] [data-moment-id=\"stale-04\"]').click(); true");
ok(await evaluate("document.querySelector('[data-detail-title]').textContent.includes('priority replaced')"), "trace selection updates detail");
equal(await evaluate("document.querySelector('[data-field] [data-moment-id=\"stale-04\"]').getAttribute('aria-pressed')"), "true", "trace selection updates field");
equal(await evaluate("document.querySelector('[data-return-path] [data-moment-id=\"stale-04\"]').getAttribute('aria-pressed')"), "true", "trace selection updates path");

await evaluate("document.querySelector('[data-dependency-id=\"stale-edge-02\"]').focus(); true");
await pressKey("Enter");
ok(await evaluate("document.querySelector('[data-detail-title]').textContent.includes('b-04 → b-05')"), "keyboard activation selects the exact dependency");
ok(await evaluate("document.querySelector('[data-detail]').textContent.includes('the displayed owner role carries revision authority')"), "dependency detail uses the source-object claim ceiling");
equal(await evaluate("document.querySelector('[data-dependency-id=\"stale-edge-02\"]').getAttribute('aria-pressed')"), "true", "relation selection remains distinct from its target moment");

await evaluate("document.body.focus(); document.documentElement.focus(); true");
await pressKey("Tab");
ok(await evaluate("document.activeElement.matches('a, button, [tabindex]')"), "tab reaches an interactive control");
ok(await evaluate("(() => { const s=getComputedStyle(document.activeElement); return s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0; })()"), "keyboard focus is visibly outlined");

await send("Emulation.setDeviceMetricsOverride", { width: 320, height: 900, deviceScaleFactor: 1, mobile: false });
const overflow = await evaluate("({scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth, offenders: [...document.querySelectorAll('body *')].map(node => ({name: node.tagName + '.' + node.className, right: Math.round(node.getBoundingClientRect().right), width: Math.round(node.getBoundingClientRect().width)})).filter(item => item.right > window.innerWidth + 1 || item.width > window.innerWidth + 1).slice(0, 8)})");
equal(overflow.scrollWidth <= overflow.innerWidth, true, `320px has no document-wide overflow: ${JSON.stringify(overflow)}`);
equal(await evaluate("[...document.querySelectorAll('button')].filter(node => { const r=node.getBoundingClientRect(); return r.width < 44 || r.height < 44; }).length"), 0, "all visible controls meet 44px target floor");
await send("Emulation.setPageScaleFactor", { pageScaleFactor: 2 });
ok(await evaluate("window.visualViewport && window.visualViewport.scale >= 1.99"), "browser reaches 200 percent page scale");
equal(await evaluate("document.documentElement.scrollWidth <= window.innerWidth"), true, "200 percent scale preserves document-wide containment");
ok(await evaluate("document.querySelector('[data-readable-account]').getBoundingClientRect().width > 0"), "textual equivalent remains laid out at 200 percent");
await send("Emulation.setPageScaleFactor", { pageScaleFactor: 1 });
await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] });
ok(await evaluate("getComputedStyle(document.querySelector('.scenario-button')).transitionDuration === '0.00001s' || parseFloat(getComputedStyle(document.querySelector('.scenario-button')).transitionDuration) < 0.01"), "reduced motion removes meaningful transitions");

requests.length = 0;
await send("Page.reload", { ignoreCache: true });
await waitFor("document.readyState === 'complete' && document.querySelector('[data-scenario-id=\"protective-retention\"]')");
equal(await evaluate("document.querySelector('[data-scenario-id=\"protective-retention\"]').getAttribute('aria-pressed')"), "true", "reload resets scenario attention");
equal(await evaluate("document.querySelector('[data-detail-title]').textContent.includes('priority declared')"), true, "reload resets selected moment");
await new Promise((resolve) => setTimeout(resolve, 100));
ok(requests.length >= 4, "browser observed local resource requests");
ok(requests.every((url) => url.startsWith("file://")), "all browser requests remain local files");

socket.close();
console.log(`browser smoke passed: ${checks} checks`);
