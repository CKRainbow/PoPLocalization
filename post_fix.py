from pathlib import Path
from dataclasses import dataclass

from const import VERSION

@dataclass
class FixRule:
    path: str
    fix_rules: list[tuple[str, str]]

FIXRULE = []


if VERSION < (0, 32, 0, 0):
    FIXRULE.append(
        FixRule(
            path="OverWorldController.cs",
            fix_rules=[
                ("if (randomNonHazardousValidTile.worldObject == OWTile.WorldObject.None)", 
                "if (randomNonHazardousValidTile is not null && randomNonHazardousValidTile.worldObject == OWTile.WorldObject.None)")
            ],
        )
    )

    FIXRULE.append(
        FixRule(
            path="QuickCharacterManager.cs",
            fix_rules=[
                ("room2.brothelCharacters.Add(new Brothel.BrothelCharacter(character, 0));", "room2.brothelCharacters.Add(new Brothel.BrothelCharacter(character, room2.roomID));"),
                ("room3.brothelCharacters.Add(new Brothel.BrothelCharacter(character, 0));", "room3.brothelCharacters.Add(new Brothel.BrothelCharacter(character, room3.roomID));"),
                ("room4.brothelCharacters.Add(new Brothel.BrothelCharacter(character, 0));", "room4.brothelCharacters.Add(new Brothel.BrothelCharacter(character, room4.roomID));"),
                ("currentRoom.brothelCharacters.Add(new Brothel.BrothelCharacter(character, 0));", "currentRoom.brothelCharacters.Add(new Brothel.BrothelCharacter(character, currentRoom.roomID));")
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