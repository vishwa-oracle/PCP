#!/usr/bin/env python3
"""
pcp_layout.py - Analyze PCP archive logs with time-range named output directory
Usage:
    python3 pcp_layout.py -a ARCHIVE [start_time] [end_time]
    - start_time and end_time accept either "YYYY-MM-DD HH:MM" or just "HH:MM".
      If only "HH:MM" is given, today's date will be prepended automatically.
    - You may also run interactively if no arguments are provided.

Examples:
    python3 pcp_layout.py -a 20260122.15.xz "2026-01-22 12:00" "2026-01-22 12:10"
    python3 pcp_layout.py -a 20260122.15.xz 12:00 12:10

Author: Vishwanath Bombalekar
Contributors:
    - Sagar Sagar - https://github.com/orasagar
"""
import os
import sys
import subprocess
import re
import argparse
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
        # Write the command to the top of the file first
        with open(output_file, "w", encoding="utf-8") as out:
            out.write(f"# Command ran:\n#   {cmd}\n\n")
        # Then run the command and append output
        with open(output_file, "a", encoding="utf-8") as out:
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
    # Accept formats: 'YYYY-MM-DD HH:MM' or 'HH:MM'
    return (
        bool(re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?$", timestr))
        or bool(re.match(r"^\d{2}:\d{2}(:\d{2})?$", timestr))
    )


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


def with_today_if_timeonly(timestr):
    """If timestr is 'HH:MM' or 'HH:MM:SS', prepend today's date."""
    if re.match(r"^\d{2}:\d{2}(:\d{2})?$", timestr):
        return datetime.now().strftime("%Y-%m-%d") + f" {timestr}"
    return timestr

def main():
    parser = argparse.ArgumentParser(description="Analyze PCP archive logs with time-range named output directory")
    parser.add_argument("-a", "--archive", type=str, help="PCP archive basename (e.g. 20260122.15.xz)")
    parser.add_argument("start_time", type=str, nargs="?", help="Start time ('YYYY-MM-DD HH:MM' or 'HH:MM')")
    parser.add_argument("end_time", type=str, nargs="?", help="End time ('YYYY-MM-DD HH:MM' or 'HH:MM')")
    args = parser.parse_args()

    if args.archive and args.start_time and args.end_time:
        archive = args.archive
        start_time = with_today_if_timeonly(args.start_time)
        end_time = with_today_if_timeonly(args.end_time)
    else:
        # Interactive fallback if any of the args are missing
        print("\nFiles in current directory:")
        print("─" * 50)
        for fname in sorted(os.listdir(".")):
            if os.path.isfile(fname):
                print(f"  {fname}")
        print("─" * 50)

        archive = args.archive or input("PCP archive basename (e.g. 20260122.15.xz): ").strip()

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

        start_time = args.start_time or input("Start time (YYYY-MM-DD HH:MM or HH:MM): ").strip()
        end_time   = args.end_time or input("End   time (YYYY-MM-DD HH:MM or HH:MM): ").strip()

        start_time = with_today_if_timeonly(start_time)
        end_time = with_today_if_timeonly(end_time)

    # Validation
    if not archive or not os.path.isfile(archive):
        print(f"Error: Archive not found: {archive}", file=sys.stderr)
        sys.exit(1)

    if not validate_time(start_time) or not validate_time(end_time):
        print("Error: Time format should be 'YYYY-MM-DD HH:MM' or 'HH:MM'", file=sys.stderr)
        sys.exit(1)

    # Create time-range named output directory
    start_dir  = time_to_dir_format(start_time)
    end_dir    = time_to_dir_format(end_time)
    OUTPUT_DIR_local = f"pcp_analysis-{start_dir}-{end_dir}"
    os.makedirs(OUTPUT_DIR_local, exist_ok=True)

    ERROR_LOG_local = os.path.join(OUTPUT_DIR_local, "errors")

    with open(ERROR_LOG_local, "w", encoding="utf-8") as f:
        f.write(f"Analysis started: {datetime.now().isoformat()}\n")
        f.write(f"Archive : {archive}\n")
        f.write(f"Period  : {start_time} → {end_time}\n\n")

    print(f"\nOutput directory : {OUTPUT_DIR_local}/")
    print(f"Archive          : {archive}")
    print(f"Time window      : {start_time} → {end_time}\n")

    # Reports with clean, prefixed filenames (no .log extension)
    reports = [
        ("archive-label",    f"pmdumplog -z -L '{archive}'",                    "pcp-archive-label"),
        ("cpu-architecture", f"pmrep -X cpu -a '{archive}' hinv.cpu -S '@{start_time}' -T '@{end_time}' -u -p",  "pcp-cpu-architecture"),
        ("iostat",           f"pmiostat -x dm -x t -a '{archive}' -S '@{start_time}' -T '@{end_time}'",              "pcp-iostat"),
        ("mpstat",           f"pcp -z -a '{archive}' --start '@{start_time}' --finish '@{end_time}' mpstat",    "pcp-mpstat"),
        ("slabinfo",         f"pcp -z -S '@{start_time}' -T '@{end_time}' slabinfo -a '{archive}' ", "pcp-slabinfo"),
        ("vmstat",           f"pmstat -z -a '{archive}' -S '@{start_time}' -T '@{end_time}'",         "pcp-vmstat"),
        ("zoneinfo",         f"pcp -z -S '@{start_time}' -T '@{end_time}' -a '{archive}' zoneinfo", "pcp-zoneinfo"),
        ("buddyinfo",         f"pcp -z -S '@{start_time}' -T '@{end_time}' -a '{archive}' buddyinfo", "pcp-buddyinfo"),
        ("netstat",          f"pcp -z -a '{archive}' --start '@{start_time}' --finish '@{end_time}' netstat",   "pcp-netstat"),        
        ("memory",           f"pcp -z -a '{archive}' meminfo -S '@{start_time}' -T '@{end_time}'", "pcp-memory"),
        ("pidstat",          f"pcp -z -a '{archive}' --start '@{start_time}' --finish '@{end_time}' pidstat -rl 1", "pcp-pidstat"),
        ("ps",               f"pcp -z -a '{archive}' --start '@{start_time}' --finish '@{end_time}' ps -u",     "pcp-ps"),
        ("numastat",         f"pcp -z -S '@{start_time}' -T '@{end_time}' -a '{archive}' numastat -nm", "pcp-numastat"),
        ("atop",             f"pcp -z -a '{archive}' --start '@{start_time}' --finish '@{end_time}' atop",      "pcp-atop"),
    ]

    # Optionally run extra reports based on user choice (interactive mode)
    extra_reports = [
        ("load", f"pmrep -z -a '{archive}' -p kernel.all.load -S '@{start_time}' -T '@{end_time}'", "pcp-load"),
        ("runq-blocked", f"pmrep -z -a '{archive}' -p proc.runq.runnable proc.runq.blocked -S '@{start_time}' -T '@{end_time}'", "pcp-runq-blocked"),
    ]
    # If this is interactive (i.e., not all args provided on CLI)
    if not (args.archive and args.start_time and args.end_time):
        print("\nOptional reports available:")
        print("  [1] Load (kernel.all.load)")
        print("  [2] Runq-blocked (proc.runq.runnable & proc.runq.blocked)")
        print("  [3] Both")
        print("  [n] Neither\n")
        choice = input("Add extra reports? [1/2/3/n]: ").strip().lower()
        if choice == "1":
            reports += [extra_reports[0]]
        elif choice == "2":
            reports += [extra_reports[1]]
        elif choice == "3":
            reports += extra_reports
        # Anything else or 'n' skips both

    import multiprocessing

    # Assign local values to globals so report_task can access them in Pool workers
    globals()["OUTPUT_DIR"] = OUTPUT_DIR_local
    globals()["ERROR_LOG"] = ERROR_LOG_local

    with multiprocessing.Pool(4) as pool:
        results = pool.map(report_task, reports)

    success = sum(1 for ok in results if ok)

    print(f"\nDone. {success}/{len(reports)} sections completed.")
    print(f"Results in: ./{OUTPUT_DIR_local}/")
    print(f"Errors logged to: {ERROR_LOG_local}")

    if success < len(reports):
        print("Some commands failed → check errors file for details.")


# Multiprocessing-safe print lock for output cleanliness
from multiprocessing import Lock as MpLock

print_lock = MpLock()
OUTPUT_DIR = None
ERROR_LOG = None

def report_task(args):
    title, cmd, filename = args
    out_path = os.path.join(OUTPUT_DIR, filename)
    ok = run_command(cmd, out_path, ERROR_LOG)
    with print_lock:
        print(f"→ {title:.<20} {'OK' if ok else 'FAILED'}")
    return ok

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
