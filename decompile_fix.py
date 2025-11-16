from pathlib import Path
from dataclasses import dataclass

from const import VERSION

@dataclass
class FixRule:
    path: str
    fix_rules: list[tuple[str, str]]

FIXRULE = []

FIXRULE.append(
    FixRule(
        path="SaveLoadManager.cs",
        fix_rules=[
            ("ref string reference;", "ref string reference = ref array[0];"),
        ],
    )
)

if VERSION >= (0, 32, 0, 0):
    FIXRULE.append(
        FixRule(
            path="Assembly-CSharp.csproj",
            fix_rules=[
                ("<TargetFramework>net40</TargetFramework>", "<TargetFramework>netstandard2.1</TargetFramework>"),
            ],
        )
    )
    
    FIXRULE.append(
        FixRule(
            path="Assembly-CSharp.csproj",
            fix_rules=[
                ("<Reference Include=\"System.Core\" />", "")
            ]
        )
    )

def decompile_fix(directory: Path):
    
    for fix_rule in FIXRULE:
        target_file = directory / fix_rule.path

        with open(target_file, "r", encoding="utf-8") as f:
            text = f.read()

        for fix_rule in fix_rule.fix_rules:
            text = text.replace(*fix_rule)

        with open(target_file, "w", encoding="utf-8") as f:
            f.write(text)

if __name__ == "__main__":
    decompile_path = Path("./decompiled")
    decompile_fix(decompile_path)