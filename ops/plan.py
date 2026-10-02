#!/usr/bin/env python3
"""Validate manual inputs on a GitHub-hosted runner before any host job is scheduled."""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent / "host"))
from portctl import GitHub, Refused, port_of, validate_request


def main():
    cfg = json.loads(Path("ops/slots.json").read_text())
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise Refused("Choose main in the Run workflow branch selector")
    if os.environ.get("GITHUB_REPOSITORY") != cfg["repository"]:
        raise Refused("Configure ops/slots.json for this repository")
    actor = os.environ.get("GITHUB_TRIGGERING_ACTOR", os.environ.get("GITHUB_ACTOR", ""))
    if actor not in cfg["operators"]:
        raise Refused("Actor is not an approved deployment operator")
    req = {k: os.environ.get("PORTCTL_" + k.upper(), "") for k in (
        "operation", "slot_branch", "target_sha", "expected_generation", "promote_from",
        "source_deployment_id", "confirm", "reason")}
    validate_request(req, cfg)
    if req["operation"] != "status" and not cfg.get("application_ready"):
        raise Refused("Application contract and project-ci.sh must be configured first")
    port = port_of(req["slot_branch"], cfg["slots"])
    tree = ""
    if req["operation"] in {"deploy", "promote"}:
        tree = GitHub(cfg["repository"], os.environ["GH_TOKEN"]).target_tree(
            req["slot_branch"], req["target_sha"])
    values = {"port": str(port), "target_sha": req["target_sha"], "tree_sha": tree,
              "environment": cfg["slots"][req["slot_branch"]]["environment"],
              "image_repository": "ghcr.io/" + cfg["repository"].lower()}
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        for key, value in values.items():
            if "\n" in value or "\r" in value:
                raise Refused("Invalid output")
            f.write(f"{key}={value}\n")
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
        f.write("# Deployment plan / plan wdrozenia\n\n")
        f.write(f"Operation: `{req['operation']}` | slot: `{req['slot_branch']}` | port: `{port}`\n\n")
        f.write(f"Target SHA: `{req['target_sha'] or '(runtime state)'}`\n\n")
        f.write("This plan is NOT proof that the application was deployed.\n")

if __name__ == "__main__":
    try:
        main()
    except (Refused, KeyError, ValueError) as e:
        print("PLAN_REFUSED: " + str(e), file=sys.stderr)
        sys.exit(1)
