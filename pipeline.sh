dotnet run \
    --project DllTranslation pipeline \
    --dir decompiled \
    --output translations \
    --literals-only \
    --paratranz-dir old \
    --new-paratranz-dir new \
    --replaced-output replaced \
    --paratranz-project-id 15832 \
    --paratranz-token f4a06da14ee3fe6bf5b43145418e07c7

{
    python asset_translator.py pipeline \
    --work-dir . \
    --input-asset ./data.unity3D \
    --dll-folder ./Managed \
    --unity-version 2019.4.16f1 \
    --tool-project-dir ./DllTranslation \
    --old-trans-dir ./old \
    --new-font-asset ./TMPfont/sharedassets0.assets \
    --font-config ./font_change_config.json \
    --new-font-dll-folder ./TMPfont/Managed \
    --output-asset ./output_assets/data.unity3D
}&

{
    cd replaced
    dotnet build -c "Release"
}&

wait

echo "Done"