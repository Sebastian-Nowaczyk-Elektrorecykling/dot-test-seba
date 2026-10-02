import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops" / "host"))
from portctl import Controller, Docker, Refused, atomic_json, port_of, runtime_fingerprint, validate_request, validate_host_config

A, B, C, TREE = "a" * 40, "b" * 40, "c" * 40, "d" * 40
IMG_A = "ghcr.io/example/app@sha256:" + "a" * 64
IMG_B = "ghcr.io/example/app@sha256:" + "b" * 64

class FakeGitHub:
    def __init__(self):
        self.tree = TREE
        self.calls = []
        self.ref_fail = False
        self.fail_after_pull = False
        self.ref_checks = 0
    def target_tree(self, branch, expected_sha):
        self.ref_checks += 1
        if self.ref_fail or (self.fail_after_pull and self.ref_checks > 1):
            raise Refused("BRANCH_MOVED")
        self.calls.append(("ref", branch, expected_sha))
        return self.tree
    def create_deployment(self, *args):
        self.calls.append(("create",))
        return len(self.calls)
    def deployment_status(self, *args):
        self.calls.append(("status", *args))

class FakeDocker:
    def __init__(self):
        self.items = {}
        self.calls = []
        self.fail_ids = set()
        self.fail_new = False
        self.crash = False
    def inspect(self, name):
        record = self.items.get(name)
        if record is None:
            return None
        return {"Config": {"Image": record["image"], "Labels": {
            "portctl.deployment": record["deployment_id"]}}, "State": {"Running": record.get("running", True)}}
    def verify(self, name, record, port):
        if record is None and name not in self.items:
            return
        item = self.items.get(name)
        if not item or not record or item["deployment_id"] != record["deployment_id"] or not item.get("running", True):
            raise Refused("DRIFT")
    def image(self, *args):
        self.calls.append(("pull", *args))
    def stop(self, name):
        self.calls.append(("stop", name))
        self.items[name]["running"] = False
    def rename(self, a, b):
        self.calls.append(("rename", a, b))
        self.items[b] = self.items.pop(a)
    def remove(self, name):
        self.calls.append(("remove", name))
        self.items.pop(name, None)
    def start(self, name):
        self.calls.append(("start", name))
        self.items[name]["running"] = True
    def run(self, name, record, slot):
        self.calls.append(("run", name, record["image"]))
        self.items[name] = copy.deepcopy(record)
        if self.fail_new:
            self.fail_ids.add(record["deployment_id"])
        if self.crash:
            raise KeyboardInterrupt("simulated hard interruption")
    def healthy(self, record, slot):
        return record["deployment_id"] not in self.fail_ids

class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cfg = {"configured": True, "repository": "example/app", "operators": ["manager"],
                    "state_dir": str(self.root / "state"), "slots": {}}
        for port in (4101,4102,4103):
            env = self.root / f"p{port}.env"
            env.write_text("DEMO_ONLY=1\n")
            env.chmod(0o600)
            self.cfg["slots"][f"deploy/p{port}"] = {"port": port, "environment": f"p{port}",
                "url": f"http://127.0.0.1:{port}", "bind_address": "127.0.0.1",
                "health_address": "127.0.0.1", "network": f"portapp-p{port}",
                "env_file": str(env), "cpus": 1, "memory": "512m", "config_revision": "c1",
                "data_epoch": "e1", "health_timeout_seconds": 1}
        self.gh, self.docker = FakeGitHub(), FakeDocker()
        self.ctl = Controller(self.cfg, self.gh, self.docker)
        self.ctx = {"actor": "manager", "run_id": "123", "attempt": "1", "controller_sha": C,
                    "run_url": "https://github.com/example/app/actions/runs/123"}
    def tearDown(self):
        self.tmp.cleanup()
    def req(self, op="deploy", port=4101, gen=0, sha=A, image=IMG_A):
        return {"operation": op, "slot_branch": f"deploy/p{port}", "target_sha": sha,
                "image": image, "expected_generation": str(gen), "confirm": f"deploy/p{port}",
                "reason": "Release decision #123", "promote_from": "deploy/p4101",
                "source_deployment_id": ""}
    def deploy(self, **kw):
        return self.ctl.execute(self.req(**kw), self.ctx)
    def test_exact_branch(self):
        self.assertEqual(port_of("deploy/p4101", self.cfg["slots"]), 4101)
    def test_invalid_branch_formats(self):
        for branch in ("deploy/p04101", "Deploy/p4101", "feat/1-p4101", "deploy/p4101-demo", "deploy/p4101;id", "deploy/p9999"):
            with self.subTest(branch=branch), self.assertRaises(Refused):
                port_of(branch, self.cfg["slots"])
    def test_port_registry_mismatch(self):
        self.cfg["slots"]["deploy/p4101"]["port"] = 4102
        with self.assertRaises(Refused):
            port_of("deploy/p4101", self.cfg["slots"])
    def test_confirmation_required(self):
        req = self.req(); req["confirm"] = "yes"
        with self.assertRaisesRegex(Refused, "CONFIRM_TARGET"):
            self.ctl.execute(req, self.ctx)
    def test_full_sha_required(self):
        with self.assertRaisesRegex(Refused,"TARGET_SHA_REQUIRED"):
            self.deploy(sha="abc123")
    def test_generation_format(self):
        for gen in ("", "-1", "00", "0;id"):
            with self.subTest(gen=gen), self.assertRaisesRegex(Refused,"EXPECTED_GENERATION"):
                self.deploy(gen=gen)
    def test_actor_required(self):
        self.ctx["actor"] = "outsider"
        with self.assertRaisesRegex(Refused,"ACTOR_NOT_AUTHORIZED"):
            self.deploy()
    def test_unconfigured_host_refuses(self):
        self.cfg["configured"] = False
        with self.assertRaisesRegex(Refused,"HOST_NOT_CONFIGURED"):
            self.deploy()
    def test_first_deploy(self):
        result = self.deploy()
        self.assertEqual(result["observed"],"RUNNING")
        self.assertEqual(result["generation"],1)
        self.assertIsNone(result["previous"])
        self.assertNotIn("runtime_fingerprint",result["active"])
        self.assertFalse(self.ctl.pending_path(4101).exists())
    def test_deploy_preserves_previous(self):
        first = self.deploy()
        result = self.deploy(gen=1,sha=B,image=IMG_B)
        self.assertEqual(result["active"]["image"], IMG_B)
        self.assertEqual(result["previous"]["deployment_id"], first["active"]["deployment_id"])
        self.assertEqual(len(self.docker.items),1)
    def test_stale_generation_does_nothing(self):
        self.deploy()
        before = len(self.docker.calls)
        with self.assertRaisesRegex(Refused,"STALE_GENERATION"):
            self.deploy()
        self.assertEqual(len(self.docker.calls),before)
    def test_branch_moved(self):
        self.gh.ref_fail = True
        with self.assertRaisesRegex(Refused,"BRANCH_MOVED"):
            self.deploy()
        self.assertEqual(self.docker.items,{})
    def test_branch_moves_during_pull(self):
        self.gh.fail_after_pull = True
        with self.assertRaisesRegex(Refused,"BRANCH_MOVED"):
            self.deploy()
        self.assertFalse(any(c[0] == "stop" for c in self.docker.calls))
    def test_unapproved_registry(self):
        with self.assertRaisesRegex(Refused,"INVALID_IMAGE"):
            self.deploy(image="evil.example/app@sha256:"+"a"*64)
    def test_mutable_tag_refused(self):
        with self.assertRaisesRegex(Refused,"INVALID_IMAGE"):
            self.deploy(image="ghcr.io/example/app:latest")
    def test_failed_health_restores_old(self):
        first = self.deploy()
        self.docker.fail_new = True
        with self.assertRaisesRegex(Refused,"FAILED_RESTORED"):
            self.deploy(gen=1,sha=B,image=IMG_B)
        state = self.ctl.load(4101)
        self.assertEqual(state["generation"],2)
        self.assertEqual(state["active"]["deployment_id"], first["active"]["deployment_id"])
        self.assertFalse(self.ctl.pending_path(4101).exists())
    def test_failed_initial_deploy_leaves_empty(self):
        self.docker.fail_new = True
        with self.assertRaisesRegex(Refused,"FAILED_RESTORED"):
            self.deploy()
        self.assertEqual(self.ctl.load(4101)["last_result"],"FAILED_EMPTY")
        self.assertEqual(self.docker.items,{})
    def test_failed_recovery_retains_journal(self):
        first = self.deploy()
        self.docker.fail_ids.add(first["active"]["deployment_id"])
        self.docker.fail_new = True
        with self.assertRaisesRegex(Refused,"RECOVERY_REQUIRED"):
            self.deploy(gen=1,sha=B,image=IMG_B)
        self.assertTrue(self.ctl.pending_path(4101).exists())
        with self.assertRaisesRegex(Refused,"INCOMPLETE_TRANSACTION"):
            self.deploy(gen=1)
    def test_interruption_is_not_claimed_as_rollback(self):
        self.docker.crash = True
        with self.assertRaises(KeyboardInterrupt):
            self.deploy()
        self.assertTrue(self.ctl.pending_path(4101).exists())
    def test_audit_failure_after_commit_does_not_undo_runtime(self):
        with patch.object(self.ctl,"append_audit", side_effect=OSError("disk failed")):
            with self.assertRaisesRegex(Refused,"DEPLOYED_RECORDING_INCOMPLETE"):
                self.deploy()
        self.assertIsNotNone(self.ctl.load(4101)["active"])
        self.assertTrue(self.ctl.pending_path(4101).exists())
    def test_promote_same_tree_different_commit(self):
        source = self.deploy()
        req = self.req(op="promote",port=4102,sha=B,image="")
        req["source_deployment_id"] = source["active"]["deployment_id"]
        result = self.ctl.execute(req,self.ctx)
        self.assertEqual(result["active"]["build_sha"],A)
        self.assertEqual(result["active"]["target_sha"],B)
        self.assertEqual(result["active"]["image"],IMG_A)
        self.assertEqual(self.ctl.load(4101)["generation"],1)
    def test_promotion_tree_mismatch(self):
        source = self.deploy(); self.gh.tree = "e"*40
        req = self.req(op="promote",port=4102,sha=B)
        req["source_deployment_id"] = source["active"]["deployment_id"]
        with self.assertRaisesRegex(Refused,"TREE_MISMATCH"):
            self.ctl.execute(req,self.ctx)
    def test_promotion_source_changed(self):
        source = self.deploy()
        req = self.req(op="promote",port=4102,sha=B)
        req["source_deployment_id"] = source["active"]["deployment_id"]
        self.deploy(gen=1,sha=B,image=IMG_B)
        with self.assertRaisesRegex(Refused,"PROMOTION_SOURCE_CHANGED"):
            self.ctl.execute(req,self.ctx)
    def test_rollback_uses_exact_prior_image(self):
        self.deploy(); self.deploy(gen=1,sha=B,image=IMG_B)
        result = self.deploy(op="rollback",gen=2,sha="",image="")
        self.assertEqual(result["active"]["image"],IMG_A)
        self.assertEqual(result["previous"]["image"],IMG_B)
    def test_new_deploy_refuses_changed_runtime_configuration(self):
        self.deploy()
        Path(self.cfg["slots"]["deploy/p4101"]["env_file"]).write_text("SECRET=new\n")
        before = len(self.docker.calls)
        with self.assertRaisesRegex(Refused,"RUNTIME_CONFIG_CHANGED"):
            self.deploy(gen=1,sha=B,image=IMG_B)
        self.assertEqual(len(self.docker.calls),before)
    def test_configuration_change_during_pull_prevents_unsafe_recovery(self):
        self.deploy()
        def change_config(*args):
            Path(self.cfg["slots"]["deploy/p4101"]["env_file"]).write_text("SECRET=new\n")
        self.docker.image = change_config
        with self.assertRaisesRegex(Refused,"RECOVERY_REQUIRED"):
            self.deploy(gen=1,sha=B,image=IMG_B)
        self.assertTrue(self.ctl.pending_path(4101).exists())
        self.assertFalse(any(call[0] == "start" for call in self.docker.calls))
    def test_rollback_refuses_config_change(self):
        self.deploy(); self.deploy(gen=1,sha=B,image=IMG_B)
        Path(self.cfg["slots"]["deploy/p4101"]["env_file"]).write_text("SECRET=changed\n")
        with self.assertRaisesRegex(Refused,"CONFIG_OR_DATA_EPOCH_CHANGED"):
            self.deploy(op="rollback",gen=2,sha="")
    def test_rollback_refuses_data_epoch_change(self):
        self.deploy(); self.deploy(gen=1,sha=B,image=IMG_B)
        self.cfg["slots"]["deploy/p4101"]["data_epoch"] = "new-schema"
        with self.assertRaisesRegex(Refused,"CONFIG_OR_DATA_EPOCH_CHANGED"):
            self.deploy(op="rollback",gen=2,sha="")
    def test_stop_and_restore(self):
        self.deploy()
        stopped = self.deploy(op="stop",gen=1,sha="")
        self.assertIsNone(stopped["active"])
        self.assertEqual(self.docker.items,{})
        restored = self.deploy(op="rollback",gen=2,sha="")
        self.assertEqual(restored["active"]["image"],IMG_A)
    def test_stop_does_not_require_old_environment_file(self):
        self.deploy()
        Path(self.cfg["slots"]["deploy/p4101"]["env_file"]).unlink()
        result = self.deploy(op="stop",gen=1,sha="")
        self.assertEqual(result["last_result"],"STOPPED")
        self.assertIsNone(result["active"])
    def test_metadata_failure_after_success_keeps_runtime(self):
        def fail_status(*args):
            raise Refused("GITHUB_API_FAILED")
        self.gh.deployment_status = fail_status
        result = self.deploy()
        self.assertEqual(result["observed"], "RUNNING")
        self.assertIn("warning", result)
        self.assertFalse(self.ctl.pending_path(4101).exists())
    def test_promotion_source_unhealthy(self):
        source = self.deploy()
        self.docker.fail_ids.add(source["active"]["deployment_id"])
        req = self.req(op="promote",port=4102,sha=B)
        req["source_deployment_id"] = source["active"]["deployment_id"]
        with self.assertRaisesRegex(Refused, "PROMOTION_SOURCE_UNHEALTHY"):
            self.ctl.execute(req,self.ctx)
    def test_env_symlink_refused(self):
        env = Path(self.cfg["slots"]["deploy/p4101"]["env_file"])
        other = env.with_suffix(".secret")
        env.rename(other)
        env.symlink_to(other)
        with self.assertRaisesRegex(Refused,"ENV_FILE_MISSING_OR_SYMLINK"):
            self.deploy()
    def test_no_previous_release(self):
        with self.assertRaisesRegex(Refused,"NO_PREVIOUS_RELEASE"):
            self.deploy(op="rollback",sha="")
    def test_status_needs_no_confirmation(self):
        req = {"operation":"status","slot_branch":"deploy/p4101"}
        self.assertEqual(self.ctl.execute(req,self.ctx)["generation"],0)
    def test_status_reports_drift(self):
        self.deploy(); self.docker.items.clear()
        status = self.ctl.execute({"operation":"status","slot_branch":"deploy/p4101"},self.ctx)
        self.assertEqual(status["observed"],"DRIFT_OR_ENGINE_UNAVAILABLE")
    def test_stale_backup_is_not_silently_deleted(self):
        self.docker.items["portapp-p4101-previous-0"] = {"deployment_id":"foreign", "image":IMG_A}
        with self.assertRaisesRegex(Refused,"STALE_BACKUP"):
            self.deploy()
        self.assertIn("portapp-p4101-previous-0",self.docker.items)
    def test_env_file_permissions(self):
        Path(self.cfg["slots"]["deploy/p4101"]["env_file"]).chmod(0o644)
        with self.assertRaisesRegex(Refused,"ENV_FILE_PERMISSIONS"):
            self.deploy()
    def test_public_bind_refused(self):
        self.cfg["slots"]["deploy/p4101"]["bind_address"] = "0.0.0.0"
        with self.assertRaisesRegex(Refused,"ALL_INTERFACES_FORBIDDEN"):
            validate_host_config(self.cfg)
    def test_reason_is_data_not_shell(self):
        req = self.req(); req["reason"] = "Issue #123; $(touch /never-created)"
        result = self.ctl.execute(req,self.ctx)
        self.assertEqual(result["generation"],1)

class DockerCommandTests(unittest.TestCase):
    def test_hardening_flags_and_no_host_checkout(self):
        docker = Docker("example/app")
        calls = []
        docker.cmd = lambda *args, **kw: calls.append(args) or ""
        slot = {"network":"portapp-p4101", "cpus":1, "memory":"512m", "port":4101,
                "bind_address":"127.0.0.1", "env_file":"/etc/port-releases/p4101.env"}
        record = {"image":IMG_A, "build_sha":A, "target_sha":B, "deployment_id":"gh-1-1-p4101-g1"}
        docker.run("portapp-p4101",record,slot)
        args = calls[-1]
        for flag in ("--read-only","--cap-drop","--pids-limit","--memory","--user","--security-opt"):
            self.assertIn(flag,args)
        self.assertNotIn("--privileged",args)
        self.assertNotIn("--volume",args)
        self.assertIn("127.0.0.1:4101:8080",args)
        self.assertEqual(args[-1], IMG_A)
    def test_image_declared_volume_refused(self):
        docker = Docker("example/app")
        data = {"Config":{"Volumes":{"/data":{}},"Labels":{
            "org.opencontainers.image.revision":A,"io.portctl.tree":TREE,
            "org.opencontainers.image.source":"https://github.com/example/app"}},"Os":"linux","Architecture":"amd64"}
        docker.cmd = lambda *args, **kw: json.dumps([data]) if args[:2] == ("image","inspect") else ""
        with self.assertRaisesRegex(Refused,"IMAGE_VOLUMES_FORBIDDEN"):
            docker.image(IMG_A,A,TREE)

if __name__ == "__main__":
    unittest.main()
