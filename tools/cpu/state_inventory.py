"""MIT: fail-closed compiled declaration coverage; reviewed dispositions are data."""
import hashlib
import json
import os
import re
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
            if {"dar_save", "cpu_type"} <= names:
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
    adapter = (root / SOURCES[0]).read_text()
    header = (root / SOURCES[1]).read_text()
    scalar_text = header.split("#define CPU_GUEST_SCALARS(F)", 1)[1].split("typedef struct", 1)[0]
    scalars = set(re.findall(r"F\((\w+)\)", scalar_text))
    if "CPU_GUEST_SCALARS(CPU_CAPTURE_FIELD)" not in adapter or "CPU_GUEST_SCALARS(CPU_RESTORE_FIELD)" not in adapter:
        raise ValueError("missing codec scalar application")
    for row in rows:
        if row["class"] != "guest":
            continue
        name = row["name"].split(".")[-1]
        expected = "cpu_guest_state." + name
        if row.get("codec") != expected:
            raise ValueError("missing codec field mapping: " + row["name"])
        if row["name"].startswith("m68ki_cpu_core.") and name in scalars:
            continue
        member = ("cpu." if row["name"].startswith("m68ki_cpu_core.") else "") + name
        index = r"\[i\]" if name in {"dar", "dar_save", "sp"} else ""
        if not (re.search(r"s\."+name+index+r"=c->backend\."+member+index, adapter) and
                re.search(r"c->backend\."+member+index+r"=s\."+name+index, adapter)):
            raise ValueError("missing explicit capture/apply: " + row["name"])
    return {"status": "pass", "compiled_objects": len(rows), "shared_immutable": sum(r["class"] == "immutable" for r in rows),
            "inventory_sha256": digest(root / "experiments/cpu/state-inventory.json")}
