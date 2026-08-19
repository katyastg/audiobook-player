#!/bin/zsh
# Double-click this file to watch the encoding progress live in a Terminal
# window. It just re-runs encode_progress.py every few seconds; it does not
# affect the encoding itself, so closing the window is always safe.

cd "$(dirname "$0")/.."

while true; do
  clear
  echo "Перекодирование аудиокниг — окно можно закрыть в любой момент"
  echo
  python3 tools/encode_progress.py
  echo
  echo "обновляется каждые 5 секунд"
  if python3 tools/encode_progress.py | grep -q "100.0%"; then
    echo
    echo "Готово."
    break
  fi
  sleep 5
done
