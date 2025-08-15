from pathlib import Path

def decompile_fix(directory: Path):

    target_file = directory / "SaveLoadManager.cs"

    with open(target_file, "r", encoding="utf-8") as f:
        text = f.read()

    text = text.replace("ref string reference;", "ref string reference = ref array[0];")

    with open(target_file, "w", encoding="utf-8") as f:
        f.write(text)

if __name__ == "__main__":
    decompile_path = Path("./decompiled")
    decompile_fix(decompile_path)