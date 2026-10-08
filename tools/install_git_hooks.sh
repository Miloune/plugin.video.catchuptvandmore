#!/bin/sh
# Installe le hook Git pre-commit de ce dépôt (audit Python 2.7 avant chaque
# commit). Le hook réel est versionné dans tools/hooks/pre-commit ; le fichier
# .git/hooks/pre-commit n'est qu'un wrapper, donc les mises à jour du dépôt
# sont prises en compte sans réinstaller.
set -eu
ROOT="$(git rev-parse --show-toplevel)"
mkdir -p "$ROOT/.git/hooks"
cat > "$ROOT/.git/hooks/pre-commit" <<'EOF'
#!/bin/sh
# Wrapper généré par tools/install_git_hooks.sh — exécute le hook versionné.
exec sh "$(git rev-parse --show-toplevel)/tools/hooks/pre-commit"
EOF
chmod +x "$ROOT/.git/hooks/pre-commit"
chmod +x "$ROOT/tools/hooks/pre-commit" 2>/dev/null || true
echo "Hook installé : .git/hooks/pre-commit (audit Python 2.7)"
