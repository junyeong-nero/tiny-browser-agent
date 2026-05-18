import shutil
import subprocess
from pathlib import Path


def _copy_script(tmp_path: Path) -> Path:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    script_path = scripts_dir / "clean_zero_step_logs.sh"
    shutil.copy2(Path("scripts/clean_zero_step_logs.sh"), script_path)
    return script_path


def _session(base: Path, name: str, *, query: str, steps: int) -> Path:
    session = base / "logs" / "history" / name
    history = session / "history"
    history.mkdir(parents=True)
    (session / "session.json").write_text(f'{{"query": "{query}"}}\n', encoding="utf-8")
    (session / "events.jsonl").write_text(
        f'{{"type": "task_started", "query": "{query}"}}\n',
        encoding="utf-8",
    )
    for step in range(1, steps + 1):
        (history / f"step-{step:04d}.json").write_text("{}\n", encoding="utf-8")
    return session


def test_clean_logs_removes_zero_step_and_test_query_sessions(tmp_path):
    script = _copy_script(tmp_path)
    history = tmp_path / "logs" / "history"
    zero_step = _session(tmp_path, "zero-step", query="real task", steps=0)
    test_query = _session(tmp_path, "test-query", query="test_query", steps=2)
    kept = _session(tmp_path, "kept", query="real task", steps=1)

    result = subprocess.run(
        [str(script)],
        cwd=tmp_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )

    assert not zero_step.exists()
    assert not test_query.exists()
    assert kept.exists()
    assert "removing (zero steps):" in result.stdout
    assert "removing (test_query):" in result.stdout
    assert "done: 2 folder(s) removed, 1 kept." in result.stdout
    assert history.exists()


def test_clean_logs_dry_run_keeps_test_query_session(tmp_path):
    script = _copy_script(tmp_path)
    test_query = _session(tmp_path, "test-query", query="test_query", steps=1)

    result = subprocess.run(
        [str(script), "--dry-run"],
        cwd=tmp_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )

    assert test_query.exists()
    assert "would remove (test_query):" in result.stdout
    assert "dry-run: 1 folder(s) would be removed, 0 kept." in result.stdout


def test_clean_logs_treats_missing_history_subdir_as_zero_step(tmp_path):
    script = _copy_script(tmp_path)
    session = tmp_path / "logs" / "history" / "missing-history"
    session.mkdir(parents=True)
    (session / "session.json").write_text('{"query": "real task"}\n', encoding="utf-8")

    result = subprocess.run(
        [str(script), "--dry-run"],
        cwd=tmp_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )

    assert session.exists()
    assert "would remove (zero steps):" in result.stdout
    assert "dry-run: 1 folder(s) would be removed, 0 kept." in result.stdout
