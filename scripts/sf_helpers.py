#!/usr/bin/env python3
"""
sf_helpers.py — Salesforce Metadata API helper for prep-demo skill.

Handles:
  - Custom field XML generation and deployment
  - Page layout retrieval and field injection
  - Org branding (name, logo, app/tab renaming)

Usage (called by the prep-demo skill via Claude's Bash tool):
  python3 sf_helpers.py deploy-fields   --org <alias> --spec <fields.json>
  python3 sf_helpers.py update-branding --org <alias> --spec <branding.json>
  python3 sf_helpers.py rename-apps     --org <alias> --spec <apps.json>
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET


# ---------------------------------------------------------------------------
# SF CLI helpers
# ---------------------------------------------------------------------------

def sf(args: list[str], org: str | None = None) -> dict:
    cmd = ["sf"] + args + ["--json"]
    if org:
        cmd += ["--target-org", org]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"SF CLI error:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    if data.get("status", 0) != 0:
        print(f"SF CLI command failed: {json.dumps(data, indent=2)}", file=sys.stderr)
        sys.exit(1)
    return data


def get_user_id(sf_username: str, org: str) -> str:
    result = sf(
        ["data", "query", "--query",
         f"SELECT Id FROM User WHERE Username='{sf_username}' LIMIT 1"],
        org=org,
    )
    records = result.get("result", {}).get("records", [])
    if not records:
        raise ValueError(f"User not found in org: {sf_username}")
    return records[0]["Id"]


# ---------------------------------------------------------------------------
# Custom fields
# ---------------------------------------------------------------------------

FIELD_TYPE_MAP = {
    "Text": "Text",
    "Url": "Url",
    "Email": "Email",
    "Phone": "Phone",
    "Number": "Number",
    "Currency": "Currency",
    "Percent": "Percent",
    "Checkbox": "Checkbox",
    "Date": "Date",
    "DateTime": "DateTime",
    "Picklist": "Picklist",
    "MultiselectPicklist": "MultiselectPicklist",
    "LongTextArea": "LongTextArea",
    "TextArea": "TextArea",
}


def _build_custom_field_xml(field: dict) -> str:
    ftype = FIELD_TYPE_MAP.get(field["type"], "Text")
    label = field["label"]
    api_name = field["api_name"]  # must end with __c
    if not api_name.endswith("__c"):
        api_name += "__c"

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<CustomField xmlns="http://soap.sforce.com/2006/04/metadata">',
        f'    <fullName>{api_name}</fullName>',
        f'    <label>{label}</label>',
        f'    <type>{ftype}</type>',
    ]

    if ftype == "Text":
        lines.append(f'    <length>{field.get("length", 255)}</length>')
    elif ftype == "LongTextArea":
        lines.append(f'    <length>{field.get("length", 32768)}</length>')
        lines.append(f'    <visibleLines>{field.get("visibleLines", 5)}</visibleLines>')
    elif ftype in ("Number", "Currency", "Percent"):
        lines.append(f'    <precision>{field.get("precision", 18)}</precision>')
        lines.append(f'    <scale>{field.get("scale", 2)}</scale>')
    elif ftype in ("Picklist", "MultiselectPicklist"):
        lines.append("    <valueSet>")
        lines.append("        <valueSetDefinition>")
        for val in field.get("values", []):
            lines.append(f"            <value><fullName>{val}</fullName><default>false</default><label>{val}</label></value>")
        lines.append("        </valueSetDefinition>")
        lines.append("    </valueSet>")

    lines.append("</CustomField>")
    return "\n".join(lines)


def deploy_custom_fields(spec_path: str, org: str):
    with open(spec_path) as f:
        spec = json.load(f)

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        _write_sfdx_project(base)

        # package.xml
        package_members: dict[str, list[str]] = {}

        for obj_spec in spec:
            sobject = obj_spec["object"]
            fields_dir = base / "force-app" / "main" / "default" / "objects" / sobject / "fields"
            fields_dir.mkdir(parents=True, exist_ok=True)

            for field in obj_spec["fields"]:
                api_name = field["api_name"]
                if not api_name.endswith("__c"):
                    api_name += "__c"
                xml_content = _build_custom_field_xml(field)
                (fields_dir / f"{api_name}.field-meta.xml").write_text(xml_content)
                package_members.setdefault(f"CustomField", []).append(f"{sobject}.{api_name}")

        # Write package.xml
        pkg_dir = base / "force-app" / "main" / "default"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        _write_package_xml(base / "package.xml", package_members)

        print(f"Deploying custom fields to org: {org}")
        result = subprocess.run(
            ["sf", "project", "deploy", "start",
             "--source-dir", str(base / "force-app"),
             "--target-org", org, "--json"],
            capture_output=True, text=True, cwd=str(base)
        )
        print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
        print("Custom fields deployed successfully.")


def _write_package_xml(path: Path, members: dict[str, list[str]]):
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<Package xmlns="http://soap.sforce.com/2006/04/metadata">',
    ]
    for metadata_type, names in members.items():
        lines.append("    <types>")
        for name in names:
            lines.append(f"        <members>{name}</members>")
        lines.append(f"        <name>{metadata_type}</name>")
        lines.append("    </types>")
    lines += ["    <version>59.0</version>", "</Package>"]
    path.write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Org branding
# ---------------------------------------------------------------------------

def update_org_name(name: str, org: str):
    print(f"Updating org company name to: {name}")
    result = sf(
        ["data", "query", "--query", "SELECT Id FROM Organization LIMIT 1"],
        org=org,
    )
    org_id = result["result"]["records"][0]["Id"]
    sf(
        ["data", "update", "record",
         "--sobject", "Organization",
         "--record-id", org_id,
         "--values", f"Name='{name}'"],
        org=org,
    )
    print("Org name updated.")


def upload_logo(logo_url: str, org: str, tmpdir: str):
    """Download logo from URL and deploy as a LightningExperienceTheme static resource."""
    print(f"Downloading logo from: {logo_url}")
    base = Path(tmpdir)
    logo_path = base / "logo_download"
    try:
        urllib.request.urlretrieve(logo_url, str(logo_path))
    except Exception as e:
        print(f"Warning: Could not download logo ({e}). Skipping logo upload.", file=sys.stderr)
        return

    # Deploy as static resource
    static_dir = base / "force-app" / "main" / "default" / "staticresources"
    static_dir.mkdir(parents=True, exist_ok=True)
    _write_sfdx_project(base)

    import shutil
    shutil.copy(logo_path, static_dir / "DemoOrgLogo.png")

    meta = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<StaticResource xmlns="http://soap.sforce.com/2006/04/metadata">\n'
        '    <cacheControl>Public</cacheControl>\n'
        '    <contentType>image/png</contentType>\n'
        '</StaticResource>'
    )
    (static_dir / "DemoOrgLogo.resource-meta.xml").write_text(meta)

    result = subprocess.run(
        ["sf", "project", "deploy", "start",
         "--source-dir", str(base / "force-app"),
         "--target-org", org, "--json"],
        capture_output=True, text=True, cwd=str(base)
    )
    print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
    print("Logo static resource deployed. Apply it via Setup > Themes and Branding.")


def update_branding(spec_path: str, org: str):
    with open(spec_path) as f:
        spec = json.load(f)

    with tempfile.TemporaryDirectory() as tmpdir:
        if "org_name" in spec:
            update_org_name(spec["org_name"], org)

        if "logo_url" in spec:
            upload_logo(spec["logo_url"], org, tmpdir)

    print("Branding update complete.")


# ---------------------------------------------------------------------------
# App / tab renaming
# ---------------------------------------------------------------------------

def _write_sfdx_project(base: Path):
    (base / "sfdx-project.json").write_text(json.dumps({
        "packageDirectories": [{"path": "force-app", "default": True}],
        "sourceApiVersion": "59.0"
    }))


def rename_apps(spec_path: str, org: str):
    """
    Retrieve existing CustomApplication metadata, rename labels, redeploy.
    spec: [{"app_api_name": "standard__Sales", "new_label": "Revenue Hub"}, ...]
    """
    with open(spec_path) as f:
        spec = json.load(f)

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        _write_sfdx_project(base)
        (base / "force-app").mkdir(parents=True, exist_ok=True)

        for item in spec:
            app_name = item["app_api_name"]
            new_label = item["new_label"]

            print(f"Retrieving app metadata: {app_name}")
            result = subprocess.run(
                ["sf", "project", "retrieve", "start",
                 "--metadata", f"CustomApplication:{app_name}",
                 "--target-org", org, "--json"],
                capture_output=True, text=True, cwd=str(base)
            )
            data = json.loads(result.stdout) if result.stdout else {}
            if data.get("status", 1) != 0:
                print(f"Warning: retrieve failed for {app_name}: {data.get('message','')}", file=sys.stderr)
                continue

            app_files = list(base.rglob(f"{app_name}.app-meta.xml"))
            if not app_files:
                print(f"Warning: no file found for {app_name} after retrieve", file=sys.stderr)
                continue

            tree = ET.parse(app_files[0])
            root = tree.getroot()
            ns = {"sf": "http://soap.sforce.com/2006/04/metadata"}
            label_el = root.find("sf:label", ns)
            if label_el is not None:
                label_el.text = new_label
                tree.write(app_files[0], xml_declaration=True, encoding="UTF-8")
                print(f"Patched label '{app_name}' → '{new_label}'")

                deploy = subprocess.run(
                    ["sf", "project", "deploy", "start",
                     "--source-dir", str(app_files[0].parent.parent.parent.parent.parent),
                     "--metadata", f"CustomApplication:{app_name}",
                     "--target-org", org, "--json"],
                    capture_output=True, text=True, cwd=str(base)
                )
                deploy_data = json.loads(deploy.stdout) if deploy.stdout else {}
                if deploy_data.get("status", 1) == 0:
                    print(f"Deployed renamed app: {app_name}")
                else:
                    print(f"Deploy warning for {app_name}: {deploy_data.get('message','')}", file=sys.stderr)
            else:
                print(f"No <label> element found in {app_name}, skipping.", file=sys.stderr)

        print("App renaming complete.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Salesforce demo prep helpers")
    sub = parser.add_subparsers(dest="command")

    p_fields = sub.add_parser("deploy-fields", help="Deploy custom fields from a JSON spec")
    p_fields.add_argument("--org", required=True)
    p_fields.add_argument("--spec", required=True, help="Path to fields spec JSON")

    p_brand = sub.add_parser("update-branding", help="Update org name and logo")
    p_brand.add_argument("--org", required=True)
    p_brand.add_argument("--spec", required=True, help="Path to branding spec JSON")

    p_apps = sub.add_parser("rename-apps", help="Rename Lightning apps")
    p_apps.add_argument("--org", required=True)
    p_apps.add_argument("--spec", required=True, help="Path to apps rename spec JSON")

    p_user = sub.add_parser("get-user-id", help="Resolve a SF username to a record ID")
    p_user.add_argument("--org", required=True)
    p_user.add_argument("--username", required=True)

    args = parser.parse_args()

    if args.command == "deploy-fields":
        deploy_custom_fields(args.spec, args.org)
    elif args.command == "update-branding":
        update_branding(args.spec, args.org)
    elif args.command == "rename-apps":
        rename_apps(args.spec, args.org)
    elif args.command == "get-user-id":
        uid = get_user_id(args.username, args.org)
        print(uid)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
