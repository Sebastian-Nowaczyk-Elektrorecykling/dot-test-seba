#!/usr/bin/env python3
"""Reference port release controller. Linux + Docker, one stateless service per slot.
Install outside the repository checkout. Never run a controller from a candidate branch.
See docs/PLAYBOOK_PL.md for its deliberately limited application contract.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import datetime as dt
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

VERSION = "1.0.0"
SHA = re.compile(r"^[0-9a-f]{40}$")
BRANCH = re.compile(r"^deploy/p([1-9][0-9]{3,4})$")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
OPS = {"deploy", "promote", "rollback", "status", "stop"}


class Refused(RuntimeError):
    """Safe refusal or failed operation requiring a new status check."""


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8") as f:
        os.chmod(temp, 0o600)
        json.dump(data, f, ensure_ascii=True, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def port_of(branch, slots):
    match = BRANCH.fullmatch(branch)
    if not match or branch not in slots:
        raise Refused("UNKNOWN_SLOT: use an exact branch from the approved registry")
    port = int(match[1])
    if not 1024 <= port <= 65535 or slots[branch].get("port") != port:
        raise Refused("INVALID_PORT: branch and registry must agree")
    return port


def validate_request(req, cfg):
    op = req.get("operation", "")
    if op not in OPS:
        raise Refused("INVALID_OPERATION")
    port_of(req.get("slot_branch", ""), cfg["slots"])
    if op == "status":
        return
    if req.get("confirm") != req["slot_branch"]:
        raise Refused("CONFIRM_TARGET: repeat the exact destination branch")
    value = str(req.get("expected_generation", ""))
    if not re.fullmatch(r"0|[1-9][0-9]{0,11}", value):
        raise Refused("EXPECTED_GENERATION: copy it from a recent status")
    reason = req.get("reason", "")
    if not 3 <= len(reason) <= 300 or any(ord(c) < 32 for c in reason):
        raise Refused("REASON_REQUIRED: 3-300 characters, one line, no secrets")
    if op in {"deploy", "promote"} and not SHA.fullmatch(req.get("target_sha", "")):
        raise Refused("TARGET_SHA_REQUIRED: exact 40-character target branch HEAD")
    if op == "promote":
        source = req.get("promote_from", "")
        port_of(source, cfg["slots"])
        if source == req["slot_branch"]:
            raise Refused("SAME_SLOT: promotion must use another slot")
        if not re.fullmatch(r"gh-[0-9]+-[0-9]+-p[0-9]+-g[0-9]+", req.get("source_deployment_id", "")):
            raise Refused("SOURCE_DEPLOYMENT_ID_REQUIRED")


class GitHub:
    def __init__(self, repository, token):
        if not REPO.fullmatch(repository):
            raise Refused("INVALID_REPOSITORY")
        self.repo = repository
        self.token = token

    def api(self, path, body=None):
        if not self.token:
            raise Refused("MISSING_GITHUB_TOKEN")
        req = urllib.request.Request(
            f"https://api.github.com/repos/{self.repo}/{path}",
            data=None if body is None else canonical(body),
            headers={"Authorization": f"Bearer {self.token}",
                     "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.load(response)
        except (urllib.error.URLError, ValueError) as e:
            # Do not print HTTP response bodies or credentials.
            raise Refused(f"GITHUB_API_FAILED: {type(e).__name__}") from e

    def target_tree(self, branch, expected_sha):
        ref = self.api("git/ref/heads/" + urllib.parse.quote(branch, safe="/"))
        if ref["object"]["sha"] != expected_sha:
            raise Refused("BRANCH_MOVED: target no longer points to the approved SHA")
        tree = self.api("git/commits/" + expected_sha)["tree"]["sha"]
        if not SHA.fullmatch(tree):
            raise Refused("UNSUPPORTED_OBJECT_FORMAT")
        return tree

    def create_deployment(self, record, environment, op, run_url):
        result = self.api("deployments", {
            "ref": record["target_sha"], "task": "deploy", "auto_merge": False,
            "required_contexts": [], "environment": environment,
            "transient_environment": False, "production_environment": False,
            "description": f"{op}: {record['deployment_id']}",
            "payload": {"image": record["image"], "build_sha": record["build_sha"],
                        "tree_sha": record["tree_sha"], "controller_version": VERSION,
                        "run_url": run_url}})
        dep_id = result.get("id")
        if not isinstance(dep_id, int):
            raise Refused("DEPLOYMENT_RECORD_NOT_CREATED")
        self.deployment_status(dep_id, "in_progress", environment, run_url, "")
        return dep_id

    def deployment_status(self, dep_id, status, environment, run_url, url):
        body = {"state": status, "environment": environment, "log_url": run_url,
                "description": "Port release controller " + VERSION,
                "auto_inactive": status == "success"}
        if url:
            body["environment_url"] = url
        self.api(f"deployments/{dep_id}/statuses", body)


class Docker:
    """No shell execution, arbitrary Compose files, host mounts or user commands."""
    def __init__(self, repository):
        self.repo = repository

    def cmd(self, *args, timeout=180):
        try:
            result = subprocess.run(["docker", *args], text=True, capture_output=True,
                                    timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise Refused(f"DOCKER_UNAVAILABLE: {type(e).__name__}") from e
        if result.returncode:
            # Engine errors can contain environment or application output. Keep logs private.
            raise Refused(f"DOCKER_FAILED: {' '.join(args[:2])}; inspect host privately")
        return result.stdout.strip()

    def inspect(self, name):
        # Listing first distinguishes 'not found' from a broken daemon.
        ids = self.cmd("container", "ls", "-a", "--filter", f"name=^/{name}$", "-q")
        if not ids:
            return None
        return json.loads(self.cmd("container", "inspect", name))[0]

    def verify(self, name, record, port):
        actual = self.inspect(name)
        if record is None:
            if actual:
                raise Refused("UNMANAGED_CONTAINER: no matching release record")
            return
        if not actual:
            raise Refused("DRIFT: recorded active container is absent")
        labels = actual.get("Config", {}).get("Labels", {}) or {}
        if (labels.get("portctl.repository") != self.repo
                or labels.get("portctl.port") != str(port)
                or labels.get("portctl.deployment") != record["deployment_id"]
                or actual.get("Config", {}).get("Image") != record["image"]
                or not actual["State"]["Running"]):
            raise Refused("DRIFT: container identity or running state differs")

    def image(self, image, build_sha, tree_sha):
        self.cmd("pull", image, timeout=600)
        data = json.loads(self.cmd("image", "inspect", image))[0]
        labels = data.get("Config", {}).get("Labels", {}) or {}
        if labels.get("org.opencontainers.image.revision") != build_sha:
            raise Refused("IMAGE_REVISION_MISMATCH")
        if labels.get("io.portctl.tree") != tree_sha:
            raise Refused("IMAGE_TREE_MISMATCH")
        if labels.get("org.opencontainers.image.source") != "https://github.com/" + self.repo:
            raise Refused("IMAGE_REPOSITORY_MISMATCH")
        if data.get("Config", {}).get("Volumes"):
            raise Refused("IMAGE_VOLUMES_FORBIDDEN: persistent data needs a reviewed adapter")
        if data.get("Os") != "linux" or data.get("Architecture") != "amd64":
            raise Refused("UNSUPPORTED_IMAGE_PLATFORM: reference adapter is linux/amd64")

    def stop(self, name):
        self.cmd("stop", "--time", "30", name, timeout=60)

    def rename(self, before, after):
        self.cmd("rename", before, after)

    def remove(self, name):
        if self.inspect(name):
            self.cmd("rm", "-f", name)

    def start(self, name):
        self.cmd("start", name)

    def run(self, name, record, slot):
        # The network must be provisioned by the administrator, not by candidate code.
        self.cmd("network", "inspect", slot["network"])
        self.cmd(
            "run", "-d", "--name", name, "--restart", "unless-stopped", "--init",
            "--network", slot["network"], "--user", "10001:10001",
            "--read-only", "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=64m",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
            "--pids-limit", "256", "--cpus", str(slot["cpus"]),
            "--memory", slot["memory"], "--memory-swap", slot["memory"],
            "--log-opt", "max-size=10m", "--log-opt", "max-file=3",
            "-p", f"{slot['bind_address']}:{slot['port']}:8080",
            "--env-file", slot["env_file"],
            "-e", f"APP_GIT_SHA={record['build_sha']}",
            "-e", f"DEPLOY_TARGET_SHA={record['target_sha']}",
            "-e", f"DEPLOYMENT_ID={record['deployment_id']}",
            "-e", f"DEPLOY_SLOT=p{slot['port']}",
            "--label", f"portctl.repository={self.repo}",
            "--label", f"portctl.port={slot['port']}",
            "--label", f"portctl.deployment={record['deployment_id']}", record["image"])

    def healthy(self, record, slot):
        # Use a local address specified by trusted host configuration; never follow redirects.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        base = f"http://{slot['health_address']}:{slot['port']}"
        end = time.monotonic() + slot.get("health_timeout_seconds", 60)
        while time.monotonic() < end:
            try:
                with opener.open(base + "/healthz", timeout=3) as r:
                    if not 200 <= r.status < 300:
                        raise ValueError("not ready")
                with opener.open(base + "/_meta", timeout=3) as r:
                    data = json.loads(r.read(16384))
                if not isinstance(data, dict):
                    raise ValueError("invalid identity response")
                if (data.get("build_sha") == record["build_sha"]
                        and data.get("deployment_id") == record["deployment_id"]):
                    return True
            except (urllib.error.URLError, ValueError, TimeoutError, OSError):
                pass
            time.sleep(2)
        return False


def runtime_fingerprint(slot):
    env_path = Path(slot["env_file"])
    if not env_path.is_file() or env_path.is_symlink():
        raise Refused("ENV_FILE_MISSING_OR_SYMLINK")
    if env_path.stat().st_mode & 0o077:
        raise Refused("ENV_FILE_PERMISSIONS: require 0600")
    # Do not expose this digest in summaries: low-entropy secret values can be guessed.
    relevant = {k: slot[k] for k in ("port", "bind_address", "health_address", "network",
                                     "cpus", "memory", "config_revision", "data_epoch")}
    return hashlib.sha256(canonical(relevant) + b"\0" + env_path.read_bytes()).hexdigest()


class Controller:
    def __init__(self, cfg, github, engine):
        self.cfg, self.github, self.engine = cfg, github, engine
        self.root = Path(cfg["state_dir"])
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def state_path(self, port):
        return self.root / f"p{port}.json"

    def pending_path(self, port):
        return self.root / f"p{port}.pending.json"

    def load(self, port):
        path = self.state_path(port)
        if not path.exists():
            return {"schema": 1, "generation": 0, "active": None, "previous": None,
                    "last_result": "EMPTY"}
        data = json.loads(path.read_text())
        if data.get("schema") != 1 or type(data.get("generation")) is not int:
            raise Refused("INVALID_STATE: administrator recovery required")
        return data

    @contextlib.contextmanager
    def locks(self, ports):
        # Same physical host + port is the resource, not a branch name or repository job.
        files = []
        try:
            for port in sorted(set(ports)):
                f = (self.root / f"host-port-{port}.lock").open("a")
                files.append(f)
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            for f in reversed(files):
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                f.close()

    def append_audit(self, port, state, req, context):
        # Host log is operational history, not tamper-proof forensic storage.
        item = {"at": now(), "actor": context["actor"], "operation": req["operation"],
                "reason": req.get("reason", ""), "run_url": context["run_url"],
                "generation": state["generation"], "result": state["last_result"],
                "active_id": (state.get("active") or {}).get("deployment_id")}
        path = self.root / f"p{port}.history.jsonl"
        with path.open("a") as f:
            os.chmod(path, 0o600)
            f.write(json.dumps(item) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def status(self, port, slot):
        state = self.load(port)
        state = copy.deepcopy(state)
        state["pending_transaction"] = self.pending_path(port).exists()
        for key in ("active", "previous"):
            if state.get(key):
                state[key].pop("runtime_fingerprint", None)
        try:
            self.engine.verify(f"portapp-p{port}", state.get("active"), port)
            state["observed"] = "RUNNING" if state.get("active") else "STOPPED_OR_EMPTY"
            if state.get("active") and not self.engine.healthy(state["active"], slot):
                state["observed"] = "UNHEALTHY"
        except Exception:
            state["observed"] = "DRIFT_OR_ENGINE_UNAVAILABLE"
        state["port"] = port
        state["url"] = slot["url"]
        return state

    def execute(self, req, context):
        validate_request(req, self.cfg)
        branch, op = req["slot_branch"], req["operation"]
        port = port_of(branch, self.cfg["slots"])
        ports = [port]
        if op == "promote":
            ports.append(port_of(req["promote_from"], self.cfg["slots"]))
        with self.locks(ports):
            slot = self.cfg["slots"][branch]
            if op == "status":
                return self.status(port, slot)
            if not self.cfg.get("configured"):
                raise Refused("HOST_NOT_CONFIGURED")
            if context["actor"] not in self.cfg["operators"]:
                raise Refused("ACTOR_NOT_AUTHORIZED")
            if any(self.pending_path(p).exists() for p in ports):
                raise Refused("INCOMPLETE_TRANSACTION: run status; administrator must reconcile")
            state = self.load(port)
            if int(req["expected_generation"]) != state["generation"]:
                raise Refused("STALE_GENERATION: target changed; request fresh status")
            name = f"portapp-p{port}"
            self.engine.verify(name, state["active"], port)
            old = copy.deepcopy(state)
            backup = name + "-previous-" + str(state["generation"])
            if self.engine.inspect(backup):
                raise Refused("STALE_BACKUP: administrator must reconcile")
            fingerprint = None if op == "stop" else runtime_fingerprint(slot)
            if (op in {"deploy", "promote"} and state["active"]
                    and state["active"]["runtime_fingerprint"] != fingerprint):
                raise Refused("RUNTIME_CONFIG_CHANGED: use a reviewed stop/configure/deploy maintenance procedure")
            record = None
            if op in {"deploy", "promote"}:
                tree = self.github.target_tree(branch, req["target_sha"])
                if op == "deploy":
                    record = {"target_sha": req["target_sha"], "build_sha": req["target_sha"],
                              "tree_sha": tree, "image": req.get("image", "")}
                else:
                    source_port = port_of(req["promote_from"], self.cfg["slots"])
                    source_state = self.load(source_port)
                    source = source_state.get("active")
                    if not source or source["deployment_id"] != req["source_deployment_id"]:
                        raise Refused("PROMOTION_SOURCE_CHANGED")
                    self.engine.verify(f"portapp-p{source_port}", source, source_port)
                    if not self.engine.healthy(source, self.cfg["slots"][req["promote_from"]]):
                        raise Refused("PROMOTION_SOURCE_UNHEALTHY")
                    if tree != source["tree_sha"]:
                        raise Refused("TREE_MISMATCH: target content differs from tested artifact")
                    record = {"target_sha": req["target_sha"], "build_sha": source["build_sha"],
                              "tree_sha": tree, "image": source["image"],
                              "promoted_from": source["deployment_id"]}
            elif op == "rollback":
                if not state["previous"]:
                    raise Refused("NO_PREVIOUS_RELEASE")
                previous = state["previous"]
                if previous["runtime_fingerprint"] != fingerprint:
                    raise Refused("CONFIG_OR_DATA_EPOCH_CHANGED: no automatic rollback")
                record = {k: previous[k] for k in ("target_sha", "build_sha", "tree_sha", "image")}
                record["restored_from"] = previous["deployment_id"]
            elif op == "stop":
                if not state["active"]:
                    raise Refused("ALREADY_STOPPED")
            if record:
                prefix = "ghcr.io/" + self.cfg["repository"].lower()
                if not re.fullmatch(re.escape(prefix) + r"@sha256:[0-9a-f]{64}", record["image"]):
                    raise Refused("INVALID_IMAGE: only an immutable digest from the approved package")
                self.engine.image(record["image"], record["build_sha"], record["tree_sha"])
                record.update({"deployment_id": f"gh-{context['run_id']}-{context['attempt']}-p{port}-g{state['generation']+1}",
                               "at": now(), "actor": context["actor"], "slot_branch": branch,
                               "runtime_fingerprint": fingerprint, "config_revision": slot["config_revision"],
                               "data_epoch": slot["data_epoch"], "run_url": context["run_url"],
                               "controller_sha": context["controller_sha"], "controller_version": VERSION})
                # Recheck immediately before the transaction after any slow image pull.
                if op in {"deploy", "promote"}:
                    self.github.target_tree(branch, req["target_sha"])
                dep_id = self.github.create_deployment(record, slot["environment"], op, context["run_url"])
                record["github_deployment_id"] = dep_id
            journal = {"schema": 1, "created_at": now(), "operation": op,
                       "old_state": old, "candidate": record, "backup_container": backup,
                       "phase": "prepared", "run_url": context["run_url"]}
            atomic_json(self.pending_path(port), journal)
            committed = False
            try:
                if state["active"]:
                    self.engine.stop(name)
                    self.engine.rename(name, backup)
                journal["phase"] = "old-stopped"
                atomic_json(self.pending_path(port), journal)
                if record:
                    # Ensure the config did not change while the request was being prepared.
                    if runtime_fingerprint(slot) != fingerprint:
                        raise Refused("CONFIG_CHANGED_DURING_DEPLOY")
                    self.engine.run(name, record, slot)
                    if not self.engine.healthy(record, slot):
                        raise Refused("HEALTHCHECK_FAILED")
                state.update({"generation": state["generation"] + 1, "active": record,
                              "previous": old["active"] or old["previous"],
                              "last_result": "STOPPED" if op == "stop" else "DEPLOYED"})
                atomic_json(self.state_path(port), state)
                committed = True
                self.append_audit(port, state, req, context)
                self.pending_path(port).unlink()
            except Exception as error:
                if committed:
                    # A healthy deployment was committed; never undo it because audit cleanup failed.
                    raise Refused("DEPLOYED_RECORDING_INCOMPLETE: status and administrator reconciliation required") from error
                restored = False
                try:
                    current = self.engine.inspect(name)
                    if current:
                        labels = current.get("Config", {}).get("Labels", {}) or {}
                        is_candidate = record and labels.get("portctl.deployment") == record["deployment_id"]
                        is_old = old["active"] and labels.get("portctl.deployment") == old["active"]["deployment_id"]
                        if is_candidate:
                            self.engine.remove(name)
                        elif not is_old:
                            raise Refused("UNEXPECTED_CONTAINER_DURING_RECOVERY")
                    if old["active"]:
                        if runtime_fingerprint(slot) != old["active"]["runtime_fingerprint"]:
                            raise Refused("RECOVERY_CONFIG_CHANGED: do not restart an incompatible old runtime")
                        if self.engine.inspect(backup):
                            self.engine.rename(backup, name)
                        self.engine.start(name)
                        restored = self.engine.healthy(old["active"], slot)
                    else:
                        restored = self.engine.inspect(name) is None
                    if restored:
                        old["generation"] += 1
                        old["last_result"] = "FAILED_RESTORED" if old["active"] else "FAILED_EMPTY"
                        atomic_json(self.state_path(port), old)
                        self.append_audit(port, old, req, context)
                        self.pending_path(port).unlink()
                except Exception:
                    restored = False
                if record:
                    with contextlib.suppress(Exception):
                        self.github.deployment_status(record["github_deployment_id"], "failure",
                                                      slot["environment"], context["run_url"], slot["url"])
                if not restored:
                    raise Refused("RECOVERY_REQUIRED: transaction journal retained; do not rerun blindly") from error
                raise Refused("FAILED_RESTORED: previous runtime restored; original failure: " + str(error)) from error
            # Cleanup is after commit. Its failure must not erase a working deployment.
            warning = None
            try:
                self.engine.remove(backup)
                if record:
                    self.github.deployment_status(record["github_deployment_id"], "success",
                                                  slot["environment"], context["run_url"], slot["url"])
                elif old["active"].get("github_deployment_id"):
                    self.github.deployment_status(old["active"]["github_deployment_id"], "inactive",
                                                  slot["environment"], context["run_url"], slot["url"])
            except Exception:
                warning = "Runtime changed; registry status or backup cleanup requires reconciliation"
            result = self.status(port, slot)
            if warning:
                result["warning"] = warning
            return result


def validate_host_config(cfg):
    if not REPO.fullmatch(cfg.get("repository", "")):
        raise Refused("INVALID_HOST_REPOSITORY")
    for branch, slot in cfg["slots"].items():
        port_of(branch, cfg["slots"])
        for key in ("bind_address", "health_address"):
            ip = ipaddress.ip_address(slot[key])
            if ip.version != 4:
                raise Refused("REFERENCE_SUPPORTS_IPV4_ONLY")
        if slot["bind_address"] == "0.0.0.0":
            raise Refused("ALL_INTERFACES_FORBIDDEN: configure a loopback or VPN address")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,60}", slot["network"]):
            raise Refused("INVALID_NETWORK_NAME")
        if not 0 < float(slot["cpus"]) <= 4:
            raise Refused("INVALID_CPU_LIMIT")
        if not re.fullmatch(r"[1-9][0-9]{1,4}[mg]", slot["memory"]):
            raise Refused("INVALID_MEMORY_LIMIT")
        for key in ("config_revision", "data_epoch"):
            if not re.fullmatch(r"[A-Za-z0-9_.-]{1,60}", slot[key]):
                raise Refused("INVALID_CONFIGURATION_REVISION")


def output_status(data):
    print(json.dumps(data, ensure_ascii=True, indent=2))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("\n## Observed slot state / stan slotu\n\n```json\n")
            f.write(json.dumps(data, ensure_ascii=True, indent=2))
            f.write("\n```\n\nThis is runtime evidence, not business acceptance.\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="/etc/port-releases/host.json")
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args()
    if args.version:
        print(VERSION)
        return 0
    cfg = json.loads(Path(args.config).read_text())
    validate_host_config(cfg)
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    expected_ref = f"{cfg['repository']}/.github/workflows/port-release.yml@refs/heads/main"
    if (repo != cfg["repository"] or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or os.environ.get("GITHUB_WORKFLOW_REF") != expected_ref):
        raise Refused("TRUSTED_WORKFLOW_REQUIRED: dispatch the main workflow")
    # Defense in depth only. A workflow with arbitrary host shell access can bypass these tests.
    context = {"actor": os.environ.get("GITHUB_TRIGGERING_ACTOR", os.environ.get("GITHUB_ACTOR", "")),
               "run_id": os.environ["GITHUB_RUN_ID"], "attempt": os.environ["GITHUB_RUN_ATTEMPT"],
               "controller_sha": os.environ["GITHUB_SHA"],
               "run_url": f"https://github.com/{repo}/actions/runs/{os.environ['GITHUB_RUN_ID']}"}
    for key in ("run_id", "attempt"):
        if not context[key].isdigit():
            raise Refused("INVALID_RUN_ID")
    req = {k: os.environ.get("PORTCTL_" + k.upper(), "") for k in (
        "operation", "slot_branch", "target_sha", "expected_generation", "promote_from",
        "source_deployment_id", "confirm", "reason", "image")}
    ctl = Controller(cfg, GitHub(repo, os.environ.get("GH_TOKEN", "")), Docker(repo))
    try:
        result = ctl.execute(req, context)
        output_status(result)
        return 2 if result.get("warning") else 0
    except Refused:
        with contextlib.suppress(Exception):
            port = port_of(req["slot_branch"], cfg["slots"])
            output_status(ctl.status(port, cfg["slots"][req["slot_branch"]]))
        raise


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Refused as error:
        print("REFUSED: " + str(error), file=sys.stderr)
        sys.exit(1)
    except Exception as error:
        print("UNEXPECTED_ERROR: " + type(error).__name__ + "; consult administrator", file=sys.stderr)
        sys.exit(1)
