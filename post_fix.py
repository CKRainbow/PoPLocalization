from pathlib import Path
from dataclasses import dataclass

@dataclass
class FixRule:
    path: str
    fix_rules: list[tuple[str, str]]

FIXRULE = []

FIXRULE.append(
    FixRule(
        path="OverWorldController.cs",
        fix_rules=[
            ("if (randomNonHazardousValidTile.worldObject == OWTile.WorldObject.None)", 
             "if (randomNonHazardousValidTile is not null && randomNonHazardousValidTile.worldObject == OWTile.WorldObject.None)")
        ],
    )
)

def post_fix(directory: Path):
    
    for fix_rule in FIXRULE:
        target_file = directory / fix_rule.path

        with open(target_file, "r", encoding="utf-8") as f:
            text = f.read()

        for fix_rule in fix_rule.fix_rules:
            text = text.replace(*fix_rule)

        with open(target_file, "w", encoding="utf-8") as f:
            f.write(text)

if __name__ == "__main__":
    replaced_path = Path("./replaced")
    post_fix(replaced_path)