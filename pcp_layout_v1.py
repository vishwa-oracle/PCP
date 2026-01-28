#!/usr/bin/env python3
"""
pcp_layout.py - Analyze PCP (Performance Co-Pilot) archive logs
Usage:
    python3 pcp_layout.py [archive] [start_time] [end_time]
Example:
    python3 pcp_layout.py 20260122.15.xz "2026-01-22 12:00" "2026-01-22 12:01"
Author: Vishwanath B
"""
import os
import sys
import subprocess
import re
import shutil
from datetime import datetime

OUTPUT_DIR = "pcp_analysis"
CONFIG_FILE = "/etc/pcp/pmrep/ora_pmrep.conf"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Timestamp prefix for all files created in this run
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
ERROR_LOG = os.path.join(OUTPUT_DIR, f"errors_{TIMESTAMP}.log")

# Initialize error log
with open(ERROR_LOG, "w", encoding="utf-8") as f:
    f.write(f"Error log started: {datetime.now().isoformat()}\n\n")


def log_error(msg):
    print(msg, file=sys.stderr)
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")


def run_command(cmd, output_file):
    """
    Run shell command, save stdout → file, log errors.
    Uses universal_newlines=True → compatible with Python 3.6
    """
    try:
        with open(output_file, "w", encoding="utf-8") as out:
            result = subprocess.run(
                cmd,
                shell=True,
                stdout=out,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=300,
            )
        if result.returncode != 0:
            log_error(f"Command failed (rc={result.returncode}): {cmd}")
            if result.stderr:
                log_error("stderr:")
                log_error(result.stderr.strip())
            return False
        return True
    except subprocess.TimeoutExpired:
        log_error(f"Command timed out after 300s: {cmd}")
        return False
    except Exception as e:
        log_error(f"Exception running command: {cmd}")
        log_error(f"→ {type(e).__name__}: {str(e)}")
        return False


def validate_time(timestr):
    return bool(re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?$", timestr))


def main():
    if len(sys.argv) == 4:
        # Command-line mode
        archive, start_time, end_time = sys.argv[1:4]
    else:
        # Interactive mode
        print("\nFiles in current directory:")
        print("─" * 50)
        for fname in sorted(os.listdir(".")):
            if os.path.isfile(fname):
                print(f"  {fname}")
        print("─" * 50)

        archive = input("PCP archive basename (e.g. 20260122.15.xz): ").strip()

        # ────────────────────────────────────────────────────────────────
        # Show archive label & metadata BEFORE asking for time range
        # ────────────────────────────────────────────────────────────────
        print(f"\nReading archive metadata for: {archive}")
        print("───────────────────────────────────────────────────────────────")

        cmd = f"pmdumplog -z -L '{archive}' 2>&1"

        try:
            # Python 3.6 compatible way (no capture_output)
            proc = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # merge stderr into stdout
                universal_newlines=True
            )
            stdout, _ = proc.communicate(timeout=60)

            if proc.returncode == 0:
                print(stdout.strip())
            else:
                print(f"pmdumplog returned non-zero exit code {proc.returncode}")
                print(stdout.strip())
                log_error(f"pmdumplog -L failed (rc={proc.returncode}): {stdout.strip()[:500]}...")

        except subprocess.TimeoutExpired:
            print("Timeout while reading archive metadata")
            log_error("pmdumplog -L timed out")
        except Exception as e:
            print(f"Failed to run pmdumplog -L: {e}")
            log_error(f"Exception in pmdumplog -L: {type(e).__name__}: {e}")

        print("───────────────────────────────────────────────────────────────\n")

        # Now ask for time range
        start_time = input("Start time (YYYY-MM-DD HH:MM): ").strip()
        end_time   = input("End   time (YYYY-MM-DD HH:MM): ").strip()

    # ── Validation ───────────────────────────────────────────────────────
    if not archive or not os.path.isfile(archive):
        log_error(f"Archive not found: {archive}")
        sys.exit(1)

    if not validate_time(start_time) or not validate_time(end_time):
        log_error("Invalid time format. Use: YYYY-MM-DD HH:MM or YYYY-MM-DD HH:MM:SS")
        sys.exit(1)

    # Check required PCP tools
    required = ["pmdumplog", "pmrep", "pcp"]
    missing = [t for t in required if shutil.which(t) is None]
    if missing:
        log_error("Missing required tools: " + ", ".join(missing))
        log_error("Install package: pcp / pcp-manager / etc.")
        sys.exit(1)

    if not os.path.isfile(CONFIG_FILE):
        log_error(f"Note: {CONFIG_FILE} not found → some pmrep sections may fail")

    print(f"\nAnalyzing archive : {archive}")
    print(f"Time window       : {start_time} → {end_time}")
    print(f"Output goes to    : {OUTPUT_DIR}/")
    print(f"Run timestamp     : {TIMESTAMP}\n")

    # ── Reports list ─────────────────────────────────────────────────────
    reports = [
        ("Archive label & metadata", f"pmdumplog -z -L '{archive}'", f"00_pmdumplog_{TIMESTAMP}.log"),
        ("System load avg", f"pmrep -z -a '{archive}' -p kernel.all.load -S '@{start_time}' -T '@{end_time}'", f"01_load_{TIMESTAMP}.log"),
        ("atop", f"pcp -z -a '{archive}' --start '@{start_time}' --finish '@{end_time}' atop", f"02_atop_{TIMESTAMP}.log"),
        ("mpstat", f"pcp -z -a '{archive}' --start '@{start_time}' --finish '@{end_time}' mpstat", f"03_mpstat_{TIMESTAMP}.log"),
        ("Memory detailed", f"pmrep -z -a '{archive}' -c '{CONFIG_FILE}' :meminfo-1 -p -S '@{start_time}' -T '@{end_time}'", f"04_memory_{TIMESTAMP}.log"),
        ("iostat extended", f"pcp -z -a '{archive}' --start '@{start_time}' --finish '@{end_time}' iostat -x 1", f"05_iostat_{TIMESTAMP}.log"),
        ("vmstat style", f"pmrep -z -a '{archive}' -p -S '@{start_time}' -T '@{end_time}' :vmstat", f"06_vmstat_{TIMESTAMP}.log"),
        ("Run queue + blocked", f"pmrep -z -a '{archive}' -p proc.runq.runnable proc.runq.blocked -S '@{start_time}' -T '@{end_time}'", f"07_runq_blocked_{TIMESTAMP}.log"),
        ("netstat", f"pcp -z -a '{archive}' --start '@{start_time}' --finish '@{end_time}' netstat", f"08_netstat_{TIMESTAMP}.log"),
        ("ps -u", f"pcp -z -a '{archive}' --start '@{start_time}' --finish '@{end_time}' ps -u", f"09_ps_{TIMESTAMP}.log"),
        ("pidstat -rl", f"pcp -z -a '{archive}' --start '@{start_time}' --finish '@{end_time}' pidstat -rl 1", f"10_pidstat_{TIMESTAMP}.log"),
        ("Slab allocator", f"pmrep -z -a '{archive}' -c '{CONFIG_FILE}' :slabinfo -p -S '@{start_time}' -T '@{end_time}'", f"11_slabinfo_{TIMESTAMP}.log"),
        ("Numa statistics", f"pmrep -z -a '{archive}' -c '{CONFIG_FILE}' :numastat-1 -u -p -S '@{start_time}' -T '@{end_time}'", f"12_numastat_{TIMESTAMP}.log"),
    ]

    success = 0
    for title, cmd, fname_template in reports:
        out_path = os.path.join(OUTPUT_DIR, fname_template.format(TIMESTAMP=TIMESTAMP))
        print(f"→ {title:.<35} ", end="", flush=True)
        if run_command(cmd, out_path):
            print("OK")
            success += 1
        else:
            print("FAILED")

    print(f"\nFinished. {success}/{len(reports)} sections completed successfully.")
    print(f"Results → {OUTPUT_DIR}/")
    print(f"Errors → {os.path.basename(ERROR_LOG)}")
    if success < len(reports):
        print("\nSome commands failed → see error log for details.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
