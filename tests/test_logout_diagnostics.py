"""start.js keeps a flight recorder for the moment WhatsApp Web logs a session out.

Why it exists: a paired install can be answered `post_logout=1` a few seconds
after the page loads while the phone still lists the linked device and the
profile on disk is byte-identical to one that connected hours earlier. The URL
carries no reason (`logout_reason=unknown`) and wppconnect.log is replaced on
the next launch, so the cause was unrecoverable after the fact. The recorder
keeps the last page events in memory and writes them out when the logout
navigation arrives — to wppconnect.log and to `logout_diagnostics.log` beside
`userDataDir`, which survives the next launch.

What these tests pin is the part that could do harm rather than the part that
merely logs: the recorder must ride on its own CDP session (the document-only
Fetch interception is documented as fragile), it must never read what the page
sends or stores, and a failure inside it must not stop a session from starting.
Like test_pinned_page_interception.py they run the real start.js, since a
`node --check` cannot see a ReferenceError swallowed by a try/catch.
"""

import json
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
API = ROOT / "client" / "api"
PATCHES = ROOT / "client" / "api_patches"

HARNESS = r"""
'use strict';
const path = require('path');
const Module = require('module');
const apiDir = process.argv[2];
const scenario = process.argv[3];

const out = {
  sessions: 0,
  fetchEnableSessions: [],
  networkEnableSessions: [],
  fetchPatterns: [],
  error: null,
  warnings: [],
};

const distConfig = path.join(apiDir, 'dist', 'config');
const distIndex = path.join(apiDir, 'dist', 'index');
const origLoad = Module._load;
Module._load = function (request) {
  if (request === distConfig) return { default: { createOptions: {}, webhook: {}, log: {} } };
  if (request === distIndex) return { initServer: () => {} };
  return origLoad.apply(this, arguments);
};

const origWarn = console.warn;
console.warn = function () {
  out.warnings.push(Array.from(arguments).join(' '));
};

const wppEntry = require.resolve('@wppconnect-team/wppconnect/package.json', { paths: [apiDir] });
const browser = require(path.join(path.dirname(wppEntry), 'dist', 'controllers', 'browser'));
browser.initWhatsapp = async function () { return 'spy'; };

require(path.join(apiDir, 'start.js'));

const pageHandlers = {};
const cdpHandlers = [];
function makeCdp(id) {
  const handlers = {};
  cdpHandlers.push(handlers);
  return {
    send: async (method, params) => {
      if (method === 'Fetch.enable') {
        out.fetchEnableSessions.push(id);
        out.fetchPatterns = (params && params.patterns) || [];
      }
      if (method === 'Network.enable') out.networkEnableSessions.push(id);
    },
    on: (event, fn) => { handlers[event] = fn; },
  };
}
const page = {
  createCDPSession: async () => {
    out.sessions += 1;
    // 'network-fails' makes the recorder's own session throw, to prove that a
    // broken diagnostic cannot stop the pinned interception from installing.
    if (scenario === 'network-fails' && out.sessions === 1) throw new Error('boom');
    return makeCdp(out.sessions);
  },
  on: (event, fn) => { pageHandlers[event] = fn; },
  mainFrame: () => MAIN,
};
const MAIN = { url: () => 'https://web.whatsapp.com/' };

const waVersion = require(require.resolve('@wppconnect/wa-version', { paths: [path.dirname(wppEntry)] }));
const versions = waVersion.getAvailableVersions();
const pinned = versions[versions.length - 1];

(async () => {
  try {
    await browser.initWhatsapp(page, 'token', false, pinned, null, () => {});
    if (scenario === 'logout') {
      pageHandlers.console && pageHandlers.console({ type: () => 'error', text: () => 'stream error 401' });
      for (const h of cdpHandlers) {
        h['Network.webSocketCreated'] && h['Network.webSocketCreated']({ requestId: 'r1', url: 'wss://web.whatsapp.com/ws/chat' });
        h['Network.webSocketFrameReceived'] && h['Network.webSocketFrameReceived']({
          requestId: 'r1', response: { opcode: 8, payloadData: 'CLOSE-CODE-4001' } });
        // An ordinary data frame must never be read.
        h['Network.webSocketFrameReceived'] && h['Network.webSocketFrameReceived']({
          requestId: 'r1', response: { opcode: 2, payloadData: 'SECRET-PAYLOAD' } });
      }
      const url = 'https://web.whatsapp.com/?post_logout=1';
      MAIN.url = () => url;
      pageHandlers.framenavigated && pageHandlers.framenavigated(MAIN);
      await new Promise((r) => setTimeout(r, 4600));
    }
  } catch (e) {
    out.error = String((e && e.message) || e);
  }
  console.log('__RESULT__' + JSON.stringify(out));
  process.exit(0);
})();
"""


def _run(tmp_path, scenario):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH")
    if not (API / "start.js").exists():
        pytest.skip("client/api/ not set up here (run setup_api.py)")
    if not (API / "node_modules" / "@wppconnect-team" / "wppconnect").exists():
        pytest.skip("client/api/node_modules not installed here")
    if b"createLogoutDiagnostics" not in (API / "start.js").read_bytes():
        pytest.skip("client/api/start.js predates the recorder (run setup_api.py)")

    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    user_data = tmp_path / "global" / "userDataDir"
    user_data.mkdir(parents=True)
    import os
    env = dict(os.environ, WINZAPP_USER_DATA_DIR=str(user_data))
    proc = subprocess.run(
        [node, str(harness), str(API), scenario],
        capture_output=True, text=True, timeout=180, env=env,
    )
    for line in proc.stdout.splitlines():
        if line.startswith("__RESULT__"):
            return json.loads(line[len("__RESULT__"):]), tmp_path / "global"
    raise AssertionError(
        f"harness produced no result.\nexit={proc.returncode}\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )


class TestTheRecorderDoesNotTouchTheInterception:
    def test_it_rides_on_its_own_cdp_session(self, tmp_path):
        result, _ = _run(tmp_path, "install")
        assert result["error"] is None, result["error"]
        assert result["networkEnableSessions"], "the recorder never enabled Network"
        assert result["fetchEnableSessions"], "the pinned interception was not installed"
        assert not set(result["networkEnableSessions"]) & set(result["fetchEnableSessions"]), (
            "Network.enable and Fetch.enable share a CDP session; the recorder must "
            "stay off the session that carries the document-only interception"
        )

    def test_the_document_patterns_are_unchanged(self, tmp_path):
        result, _ = _run(tmp_path, "install")
        urls = [p["urlPattern"] for p in result["fetchPatterns"]]
        assert urls == [
            "https://web.whatsapp.com/",
            "https://web.whatsapp.com/check-update*",
        ]

    def test_a_failing_recorder_does_not_stop_the_interception(self, tmp_path):
        result, _ = _run(tmp_path, "network-fails")
        assert result["error"] is None, result["error"]
        assert result["fetchEnableSessions"], (
            "the recorder's own CDP session failing must not keep the pinned "
            "interception from being installed"
        )


class TestTheDumpOnLogout:
    def test_the_events_around_the_logout_are_written_out(self, tmp_path):
        result, global_dir = _run(tmp_path, "logout")
        assert result["error"] is None, result["error"]
        dumps = [w for w in result["warnings"] if "[logout-diagnostics]" in w]
        assert dumps, f"no dump reached the log: {result['warnings']}"
        text = dumps[0]
        assert "trigger=post_logout" in text
        assert "stream error 401" in text
        assert "ws.closeFrame CLOSE-CODE-4001" in text
        assert "post_logout" in text

        persisted = (global_dir / "logout_diagnostics.log").read_text(encoding="utf-8")
        assert "ws.closeFrame CLOSE-CODE-4001" in persisted

    def test_ordinary_websocket_frames_are_never_read(self, tmp_path):
        result, global_dir = _run(tmp_path, "logout")
        everything = "\n".join(result["warnings"])
        everything += (global_dir / "logout_diagnostics.log").read_text(encoding="utf-8")
        assert "SECRET-PAYLOAD" not in everything


class TestTheSource:
    def test_the_recorder_reads_no_page_storage_or_request_bodies(self):
        src = (PATCHES / "start.js").read_text(encoding="utf-8")
        start = src.index("function createLogoutDiagnostics")
        end = src.index("async function installPinnedPageInterception")
        block = src[start:end]
        for forbidden in ("postData", "localStorage", "indexedDB", "page.evaluate",
                          "Network.getResponseBody", "Runtime.evaluate"):
            assert forbidden not in block, (
                f"the flight recorder must stay read-only over page events; found {forbidden}"
            )

    def test_the_two_copies_of_start_js_match(self):
        if not (API / "start.js").exists():
            pytest.skip("client/api/ not set up here")
        assert (API / "start.js").read_bytes() == (PATCHES / "start.js").read_bytes()
