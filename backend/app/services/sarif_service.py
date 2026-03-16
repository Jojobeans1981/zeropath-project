import re


def severity_to_level(severity: str) -> str:
    if severity in ("critical", "high"):
        return "error"
    elif severity == "medium":
        return "warning"
    return "note"


def slugify(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def generate_sarif(scan, findings: list) -> dict:
    # Build unique rules
    rules = {}
    for f in findings:
        rule_id = slugify(f.vulnerability_type)
        if rule_id not in rules:
            rules[rule_id] = {
                "id": rule_id,
                "name": f.vulnerability_type,
                "shortDescription": {"text": f.vulnerability_type},
                "defaultConfiguration": {"level": severity_to_level(f.severity)},
            }

    # Build results
    results = []
    for f in findings:
        results.append({
            "ruleId": slugify(f.vulnerability_type),
            "level": severity_to_level(f.severity),
            "message": {"text": f.description},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": f.file_path},
                    "region": {"startLine": f.line_number},
                }
            }],
            "properties": {
                "explanation": f.explanation,
                "severity": f.severity,
                "identityHash": f.identity_hash,
            },
        })

    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "ZeroPath Security Scanner",
                    "version": "1.0.0",
                    "informationUri": "https://github.com/Jojobeans1981/zeropath-project",
                    "rules": list(rules.values()),
                }
            },
            "results": results,
        }],
    }
