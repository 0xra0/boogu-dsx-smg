#!/bin/sh
# Capture what the game is actually doing while it is FROZEN.
#
#   run this WHILE the game is hung, before the 120s watchdog kills it
#   ./capture_freeze.sh
#
# It writes a report to /mnt/sata/weapon_mod/freeze_report.txt containing:
#   1. per-thread CPU and run state   (no debugger needed, always works)
#   2. per-thread stack backtraces    (needs ptrace permission, see below)
#
# (1) alone answers the biggest question: a thread pinned at 100% means an
# infinite loop in game logic; every thread idle means a deadlock or a load that
# never returns.  Those have completely different causes.
#
# If the backtraces come out empty, ptrace is blocked.  Allow it once with:
#   echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope
# (resets to 1 on reboot; or run this script under sudo instead)

OUT=/mnt/sata/weapon_mod/freeze_report.txt

PID=$(pgrep -f 'Cyberpunk2077\.exe' 2>/dev/null | while read p; do
        # skip our own shell and any grep/pgrep that merely mentions the name
        [ "$p" = "$$" ] && continue
        rss=$(awk '{print $24}' /proc/$p/stat 2>/dev/null)
        [ -n "$rss" ] && [ "$rss" -gt 100000 ] && echo "$p"
      done | head -1)

if [ -z "$PID" ]; then
  echo "No running Cyberpunk2077.exe found (>400MB RSS)." >&2
  echo "Run this while the game is open and frozen." >&2
  exit 1
fi

{
  echo "=============================================================="
  echo "freeze capture  $(date '+%F %H:%M:%S')   pid=$PID"
  echo "=============================================================="
  echo
  echo "--- process ---"
  awk '{print "state="$3"  utime="$14"  stime="$15"  threads="$20"  rss_pages="$24}' \
      /proc/$PID/stat
  echo

  echo "--- sample 1: per-thread cpu ticks (utime+stime) ---"
  for t in /proc/$PID/task/*; do
    [ -r "$t/stat" ] || continue
    awk '{u=$14+$15; gsub(/[()]/,"",$2); print u"\t"$3"\t"$1"\t"$2}' "$t/stat"
  done | sort -rn > /tmp/.fz1
  head -20 /tmp/.fz1
  echo

  echo "(sampling again in 3s to see which threads are actually advancing)"
  sleep 3
  echo "--- sample 2: threads that ADVANCED between samples ---"
  for t in /proc/$PID/task/*; do
    [ -r "$t/stat" ] || continue
    awk '{u=$14+$15; gsub(/[()]/,"",$2); print u"\t"$3"\t"$1"\t"$2}' "$t/stat"
  done | sort -rn > /tmp/.fz2
  join -1 3 -2 3 -o 0,1.1,2.1,2.2,2.4 \
       <(sort -k3,3 /tmp/.fz1) <(sort -k3,3 /tmp/.fz2) 2>/dev/null \
    | awk '$3>$2 {printf "tid=%s  +%d ticks  state=%s  %s\n", $1, $3-$2, $4, $5}' \
    | sort -t+ -k2 -rn | head -20
  echo "(nothing listed above = every thread is idle -> blocked, not looping)"
  echo

  echo "--- kernel wait channels (what each thread is blocked in) ---"
  for t in /proc/$PID/task/*; do
    tid=${t##*/}
    w=$(cat "$t/wchan" 2>/dev/null)
    st=$(awk '{print $3}' "$t/stat" 2>/dev/null)
    [ -n "$w" ] && echo "tid=$tid state=$st wchan=$w"
  done | sort -t= -k3 | uniq -c -f2 | sort -rn | head -20
  echo

  echo "--- backtraces (all threads) ---"
  if command -v eu-stack >/dev/null 2>&1; then
    eu-stack -p "$PID" 2>&1 | head -400
  else
    echo "(eu-stack not installed)"
  fi
  echo
  echo "--- gdb backtrace (fallback / richer symbols) ---"
  if command -v gdb >/dev/null 2>&1; then
    timeout 60 gdb -p "$PID" -batch \
      -ex 'set pagination off' \
      -ex 'thread apply all bt 25' 2>&1 | head -400
  else
    echo "(gdb not installed)"
  fi
} > "$OUT" 2>&1

echo "wrote $OUT  ($(wc -l < "$OUT") lines)"
grep -q 'Thread' "$OUT" && echo "backtraces: CAPTURED" \
  || echo "backtraces: EMPTY -> run: echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope"
