if [ ! -d "decompiled" ]; then
    echo "Creating decompiled directory..."
else
    rm -rf decompiled
fi

mkdir -p decompiled
cd decompiled
ilspycmd -p -o . -r ../Managed/ -lv CSharp12_0 ../Managed/Assembly-CSharp.dll

cd ..

python decompile_fix.py