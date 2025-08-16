set -e

dotnet run \
    --project DllTranslation pipeline \
    --dir decompiled \
    --output translations \
    --paratranz-dir old \
    --new-paratranz-dir new \
    --replaced-output replaced \
    --paratranz-project-id 15832 \
    --paratranz-token "$PARATRANZ_TOKEN" \

cd replaced
rm -f decompiled.sln
dotnet build -c "Release"