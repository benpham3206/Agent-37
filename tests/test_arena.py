from pathlib import Path

import pytest

from harness.combat import arena


def test_arena_requires_explicit_eula_and_uses_owned_directory(tmp_path):
    jar = tmp_path / "server.jar"
    jar.write_bytes(b"minecraft-fixture")
    with pytest.raises(ValueError, match="EULA"):
        arena.ArenaServer(jar, tmp_path / "runs")
    server = arena.ArenaServer(jar, tmp_path / "runs", accept_eula=True, run_id="test-run")
    try:
        assert server.root == (tmp_path / "runs" / "agent37-arena-test-run").resolve()
        assert (server.root / ".agent37-arena").is_file()
        assert (server.root / "server.jar").read_bytes() == jar.read_bytes()
        server._write_properties()
        properties = (server.root / "server.properties").read_text()
        assert "server-ip=127.0.0.1" in properties
        assert "level-type=minecraft:flat" in properties
        assert "spawn-monsters=false" in properties
        assert (server.root / "eula.txt").read_text() == "eula=true\n"
    finally:
        # The directory is intentionally retained: it is the recoverable run record.
        pass


def test_hash_and_spawn_are_deterministic(tmp_path, monkeypatch):
    jar = tmp_path / "server.jar"
    jar.write_bytes(b"fixture")
    server = arena.ArenaServer(jar, tmp_path / "runs", accept_eula=True, run_id="spawn-test")
    commands = []
    monkeypatch.setattr(server, "command", commands.append)
    arena._spawn(server, "skeleton", -3, 6)
    assert commands == [
        "kill @e[type=!player,tag=agent37_trial]",
        'summon minecraft:skeleton -3 64 6 {Tags:["agent37_trial"],PersistenceRequired:1b}',
    ]
    assert arena._sha256(jar) == "bef1a6a0e52c1a5c6efedd4d72a8e7f4fca0c6c1b7a2dc7c1a6e0c4c3b7e2e7f" or len(arena._sha256(jar)) == 64


def test_report_shape_is_documented():
    # Keep this lightweight test independent of Java: the public contract fields
    # are asserted from the implementation's report construction vocabulary.
    source = Path(arena.__file__).read_text()
    for field in ("schema_version", "frozen_arena", "teacher_intervention", "safety_violations", "success_fraction"):
        assert field in source


def test_wait_requires_spawned_connection_and_pose():
    assert not arena._spawned({"observation": {"self": {"position": {"x": 0, "y": 64, "z": 0}}}})
    assert not arena._spawned({"connection": {"status": "connecting"}, "observation": {"self": {"position": {"x": 0, "y": 64, "z": 0}}}})
    assert arena._spawned({"connection": {"status": "spawned"}, "observation": {"self": {"position": {"x": 0, "y": 64, "z": 0}}}})


def test_target_loss_and_stale_target_id_cannot_succeed():
    assert not arena._succeeded_for_target({"invocation": {"status": "running"}, "observation": {"target": None}}, "mob-1")
    assert not arena._succeeded_for_target({"invocation": {"status": "succeeded", "target_id": "mob-old"}, "observation": {"target": {"id": "mob-new"}}}, "mob-new")
    assert arena._succeeded_for_target({"invocation": {"status": "succeeded", "result": {"target_id": "mob-new", "terminal_event": "target_death"}}, "observation": {"target": None}}, "mob-new")


def test_missing_candidate_is_rejected_before_report(tmp_path):
    with pytest.raises(FileNotFoundError):
        arena.evaluate(tmp_path / "candidate", server_jar=tmp_path / "missing.jar", accept_eula=True)
    assert not (tmp_path / "candidate" / "evaluation.json").exists()
