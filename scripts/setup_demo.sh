#!/usr/bin/env python3

set -e

TARGET="${1:-$HOME/demo}"

echo "[Aegis] Initializing demo environment at: $TARGET"

mkdir -p "$TARGET/project/src"
echo "# Demo Agent Project" > "$TARGET/project/README.md"
cat << 'EOF' > "$TARGET/project/src/app.py"
def main():
    print("Agent app running")

if __name__ == '__main__':
    main()
EOF

cat << 'EOF' > "$TARGET/project/src/utils.py"
def helper():
    return True
EOF

mkdir -p "$TARGET/.ssh"
echo "-----BEGIN OPENSSH PRIVATE KEY-----" > "$TARGET/.ssh/id_rsa"
echo "fake_sample_key_content_not_real" >> "$TARGET/.ssh/id_rsa"
echo "-----END OPENSSH PRIVATE KEY-----" >> "$TARGET/.ssh/id_rsa"
chmod 600 "$TARGET/.ssh/id_rsa"

for dir in a b c d e; do
    mkdir -p "$TARGET/notes/$dir"
    for i in $(seq 1 8); do
        echo "Note $dir/$i: content sample" > "$TARGET/notes/$dir/n$i.txt"
    done
done

touch "$TARGET/noop.txt"

echo "[Aegis] Demo environment initialized successfully."
echo "  - Workspace:   $TARGET/project/src"
echo "  - Credentials: $TARGET/.ssh"
echo "  - Notes:       $TARGET/notes/{a,b,c,d,e}"

