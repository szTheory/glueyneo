"""MIT: fail-closed compiled declaration coverage; reviewed dispositions are data."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

SOURCES = ["experiments/cpu/cpu_adapter.c", "experiments/cpu/cpu_adapter.h",
           "third_party/musashi/m68kcpu.h", "third_party/musashi/m68kcpu.c",
           "third_party/musashi/m68kops.c", "third_party/musashi/m68kops.h",
           "third_party/musashi/m68k.h", "third_party/musashi/m68kconf.h"]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def declarations(root):
    result = {}
    compiler = os.environ.get("CC", "cc")
    for source in (SOURCES[0], SOURCES[3], SOURCES[4]):
        command = [compiler, "-std=c17", "-Ithird_party/musashi", "-Iexperiments/cpu",
                   "-Xclang", "-ast-dump=json", "-fsyntax-only", source]
        process = subprocess.run(command, cwd=root, text=True, capture_output=True, timeout=60)
        if process.returncode:
            raise ValueError("compiled inventory extraction failed: " + process.stderr)
        tree = json.loads(process.stdout)
        def walk(node, depth=0):
            children = node.get("inner", [])
            fields = [v for v in children if v.get("kind") == "FieldDecl"]
            names = {v.get("name") for v in fields}
            group = node.get("name") if node.get("name") in {"m68ki_context", "cpu_instance"} else None
            if "dar_save" in names:
                group = "m68ki_cpu_core"
            if names == {"userdata", "allocate", "release"}:
                group = "cpu_allocator"
            if group:
                for field in fields:
                    result[group + "." + field["name"]] = field["type"]["qualType"]
            if node.get("kind") == "VarDecl" and (depth == 1 or node.get("storageClass") == "static"):
                if node.get("storageClass") != "extern":
                    result["global." + node["name"]] = node["type"]["qualType"]
            for child in children:
                walk(child, depth + 1)
        walk(tree)
    return result

def verify(root):
    inventory = json.loads((root / "experiments/cpu/state-inventory.json").read_text())
    for path in SOURCES:
        if inventory["source_hashes"].get(path) != digest(root / path):
            raise ValueError("stale state inventory source: " + path)
    compiled = declarations(root)
    rows = inventory["objects"]
    reviewed = {r["name"]: r["type"] for r in rows}
    if len(reviewed) != len(rows) or reviewed != compiled:
        raise ValueError("unclassified or stale compiled declaration: " + str(sorted(set(compiled) ^ set(reviewed))))
    for row in rows:
        for key in ("source", "owner", "mutation_sites", "callback_access", "class", "restore"):
            if not row.get(key):
                raise ValueError("missing state disposition: " + row["name"] + "." + key)
        if row["name"].startswith("global.") and row["class"] != "immutable":
            raise ValueError("shared mutable declaration: " + row["name"])
    return {"status": "pass", "compiled_objects": len(rows), "shared_immutable": sum(r["class"] == "immutable" for r in rows),
            "inventory_sha256": digest(root / "experiments/cpu/state-inventory.json")}
