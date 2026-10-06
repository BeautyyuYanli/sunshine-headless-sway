#!/bin/sh
# Run only from the private session. Existing GUI instances may retain their
# original display; refusing them avoids silently launching back onto KDE.
set -eu
case "${1:-}" in
    genshin) launcher=an-anime-game-launcher ;;
    zzz) launcher=sleepy-launcher ;;
    *) echo 'Usage: launch-game.sh genshin|zzz' >&2; exit 2 ;;
esac
if pgrep -u "$(id -u)" -f "^/usr/bin/$launcher([[:space:]]|$)" >/dev/null; then
    echo "Close the existing $launcher instance before launching from Moonlight." >&2
    exit 1
fi
export PATH="$HOME/.local/share/sunshine-headless/bin:$PATH"
if [ "$1" = zzz ] && [ ! -f /mnt/large/Games/ZenlessZoneZero/ZenlessZoneZero.exe ]; then
    exec /usr/bin/sleepy-launcher
fi
exec "/usr/bin/$launcher" --run-game
