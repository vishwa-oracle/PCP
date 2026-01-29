#!/usr/bin/env python3
"""
pcp_layout.py - Analyze PCP archive logs with time-range named output directory
Usage:
    python3 pcp_layout.py [archive] [start_time] [end_time]
Example:
    python3 pcp_layout.py 20260122.15.xz "2026-01-22 12:00" "2026-01-22 12:10"
Author: Vishwanath Bombalekar
"""
import os
import sys
import subprocess
import re
from datetime import datetime

# Configuration file for some pmrep commands
CONFIG_FILE = "/etc/pcp/pmrep/ora_pmrep.conf"


def log_error(msg, error_log_path):
    print(msg, file=sys.stderr)
    try:
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except:
        pass


def run_command(cmd, output_file, error_log_path):
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
            log_error(f"Command failed (rc={result.returncode}): {cmd}", error_log_path)
            if result.stderr:
                log_error(f"stderr:\n{result.stderr.strip()}", error_log_path)
            return False
        return True
    except subprocess.TimeoutExpired:
        log_error(f"Command timed out after 300s: {cmd}", error_log_path)
        return False
    except Exception as e:
        log_error(f"Exception running: {cmd} → {type(e).__name__}: {e}", error_log_path)
        return False


def validate_time(timestr):
    return bool(re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?$", timestr))


def time_to_dir_format(timestr):
    """
    Convert '2026-01-26 12:05' → '260120261205'
    Format: DDMMYYYYHHMM
    """
    if not timestr:
        return "unknown"
    cleaned = re.sub(r"[- :]", "", timestr)
    year = cleaned[0:4]
    month = cleaned[4:6]
    day = cleaned[6:8]
    hour = cleaned[8:10]
    minute = cleaned[10:12]
    return f"{day}{month}{year}{hour}{minute}"


def main():
    if len(sys.argv) == 4:
        archive, start_time, end_time = sys.argv[1:4]
    else:
        print("\nFiles in current directory:")
        print("─" * 50)
        for fname in sorted(os.listdir(".")):
            if os.path.isfile(fname):
                print(f"  {fname}")
        print("─" * 50)

        archive = input("PCP archive basename (e.g. 20260122.15.xz): ").strip()

        print(f"\nReading archive metadata for: {archive}")
        print("─" * 60)
        cmd = f"pmdumplog -z -L '{archive}' 2>&1"
        try:
            proc = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            stdout, _ = proc.communicate(timeout=60)
            print(stdout.strip() or "(no output)")
        except Exception as e:
            print(f"Could not read archive label: {e}")
        print("─" * 60 + "\n")

        start_time = input("Start time (YYYY-MM-DD HH:MM): ").strip()
        end_time   = input("End   time (YYYY-MM-DD HH:MM): ").strip()

    # Validation
    if not archive or not os.path.isfile(archive):
        print(f"Error: Archive not found: {archive}", file=sys.stderr)
        sys.exit(1)

    if not validate_time(start_time) or not validate_time(end_time):
        print("Error: Time format should be YYYY-MM-DD HH:MM", file=sys.stderr)
        sys.exit(1)

    # Create time-range named output directory
    start_dir  = time_to_dir_format(start_time)
    end_dir    = time_to_dir_format(end_time)
    OUTPUT_DIR = f"pcp_analysis-{start_dir}-{end_dir}"

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    ERROR_LOG = os.path.join(OUTPUT_DIR, "errors")

    with open(ERROR_LOG, "w", encoding="utf-8") as f:
        f.write(f"Analysis started: {datetime.now().isoformat()}\n")
        f.write(f"Archive : {archive}\n")
        f.write(f"Period  : {start_time} → {end_time}\n\n")

    print(f"\nOutput directory : {OUTPUT_DIR}/")
    print(f"Archive          : {archive}")
    print(f"Time window      : {start_time} → {end_time}\n")

    # Reports with clean, prefixed filenames (no .log extension)
    reports = [
        ("archive-label",    f"pmdumplog -z -L '{archive}'",                    "pcp-archive-label"),
        ("load",             f"pmrep -z -a '{archive}' -p kernel.all.load -S '@{start_time}' -T '@{end_time}'", "pcp-load"),
        ("atop",             f"pcp -z -a '{archive}' --start '@{start_time}' --finish '@{end_time}' atop",      "pcp-atop"),
        ("mpstat",           f"pcp -z -a '{archive}' --start '@{start_time}' --finish '@{end_time}' mpstat",    "pcp-mpstat"),
        ("memory",           f"pmrep -z -a '{archive}' -c '{CONFIG_FILE}' :meminfo-1 -p -S '@{start_time}' -T '@{end_time}'", "pcp-memory"),
        ("iostat",           f"pcp -z -a '{archive}' --start '@{start_time}' --finish '@{end_time}' iostat -x 1", "pcp-iostat"),
        ("vmstat",           f"pmrep -z -a '{archive}' -p -S '@{start_time}' -T '@{end_time}' :vmstat",         "pcp-vmstat"),
        ("runq-blocked",     f"pmrep -z -a '{archive}' -p proc.runq.runnable proc.runq.blocked -S '@{start_time}' -T '@{end_time}'", "pcp-runq-blocked"),
        ("netstat",          f"pcp -z -a '{archive}' --start '@{start_time}' --finish '@{end_time}' netstat",   "pcp-netstat"),
        ("ps",               f"pcp -z -a '{archive}' --start '@{start_time}' --finish '@{end_time}' ps -u",     "pcp-ps"),
        ("pidstat",          f"pcp -z -a '{archive}' --start '@{start_time}' --finish '@{end_time}' pidstat -rl 1", "pcp-pidstat"),
        ("slabinfo",         f"pmrep -z -a '{archive}' -c '{CONFIG_FILE}' :slabinfo -p -S '@{start_time}' -T '@{end_time}'", "pcp-slabinfo"),
        ("numastat",         f"pmrep -z -a '{archive}' -c '{CONFIG_FILE}' :numastat-1 -u -p -S '@{start_time}' -T '@{end_time}'", "pcp-numastat"),
    ]

    success = 0
    for title, cmd, filename in reports:
        out_path = os.path.join(OUTPUT_DIR, filename)
        print(f"→ {title:.<20} ", end="", flush=True)
        if run_command(cmd, out_path, ERROR_LOG):
            print("OK")
            success += 1
        else:
            print("FAILED")

    print(f"\nDone. {success}/{len(reports)} sections completed.")
    print(f"Results in: ./{OUTPUT_DIR}/")
    print(f"Errors logged to: {ERROR_LOG}")

    if success < len(reports):
        print("Some commands failed → check errors file for details.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
