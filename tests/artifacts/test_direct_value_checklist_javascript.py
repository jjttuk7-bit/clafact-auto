from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path


HTML_PATH = (
    Path(__file__).resolve().parents[2]
    / "deliverables"
    / "CLAFACT_AUTO_8번_직접값_381건_전체체크리스트_20260825.html"
)


def test_actual_javascript_enforces_evidence_and_phase_order() -> None:
    html = HTML_PATH.read_text(encoding="utf-8")
    match = re.search(r"<script>([\s\S]+?)</script>", html)
    assert match is not None
    script = match.group(1)
    boot_marker = "    let state = loadState();"
    assert boot_marker in script
    library = script.split(boot_marker, maxsplit=1)[0]
    checks = r"""
const localStorage = { getItem() { return null; }, setItem() {} };
let state = defaultState();
if (phases.length !== 10) throw new Error(`phase count ${phases.length}`);
if (allTasks.length !== 58) throw new Error(`task count ${allTasks.length}`);

const valid = {
  completionSummary: "완료함",
  evidenceReference: "result.json",
  verificationResult: "PASS",
  criteriaConfirmed: true,
  completed: false,
  completedAt: "",
  reversalReason: ""
};
if (!canComplete(valid)) throw new Error("valid evidence was rejected");
for (const field of ["completionSummary", "evidenceReference", "verificationResult", "criteriaConfirmed"]) {
  const invalid = { ...valid };
  invalid[field] = field === "criteriaConfirmed" ? false : "";
  if (canComplete(invalid)) throw new Error(`missing ${field} was accepted`);
}
if (phaseUnlocked(1)) throw new Error("phase 1 unlocked before phase 0 completion");
for (const task of phaseTasks(0)) state.tasks[task.id] = { ...valid, completed: true, completedAt: new Date().toISOString() };
if (!phaseComplete(0)) throw new Error("phase 0 did not complete");
if (!phaseUnlocked(1)) throw new Error("phase 1 stayed locked");

state.tasks[phaseTasks(1)[0].id] = { ...valid, completed: true, completedAt: new Date().toISOString() };
state.tasks[phaseTasks(0)[0].id].completed = false;
enforceSequentialCompletion(state);
if (state.tasks[phaseTasks(1)[0].id].completed) throw new Error("later phase completion was not cleared");
console.log("javascript_gate_check=PASS phases=10 tasks=58");
"""
    with tempfile.TemporaryDirectory() as directory:
        script_path = Path(directory) / "checklist-gate-check.js"
        script_path.write_text(library + checks, encoding="utf-8")
        result = subprocess.run(
            ["node", str(script_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    assert result.returncode == 0, result.stderr
    assert "javascript_gate_check=PASS phases=10 tasks=58" in result.stdout

