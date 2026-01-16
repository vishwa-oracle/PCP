# pcp_layout.py - Analyze PCP (Performance Co-Pilot) logs for system performance metrics
# Usage: python3 pcp_layout.py [logfile] [start_time] [end_time]
# Example: python3 pcp_layout.py 20260115.8.xz "2026-01-15 12:00" "2023-01-15 12:01"  [ Please use it for small iteration like a minute or two ]
# Author: vishwanath.bombalekar@oracle.com

import os
import sys
import subprocess
import re

OUTPUT_DIR = "pcp_analysis"
ERROR_LOG = os.path.join(OUTPUT_DIR, "errors.log")
CONFIG_FILE = "/etc/pcp/pmrep/ora_pmrep.conf"

os.makedirs(OUTPUT_DIR, exist_ok=True)
with open(ERROR_LOG, "w") as ef:
    pass  # Clear error log on each run

def log_error(msg):
    print(msg)
    with open(ERROR_LOG, "a") as ef:
        ef.write(msg + "\n")

def run_command(cmd, output_file):
    try:
        with open(output_file, "w") as out, open(ERROR_LOG, "a") as err:
            res = subprocess.run(cmd, shell=True, stdout=out, stderr=err)
        if res.returncode != 0:
            log_error(f"Error: Command '{cmd}' failed. See {ERROR_LOG} for details.")
    except Exception as e:
        log_error(f"Exception running '{cmd}': {e}")

def validate_time(timestr):
    return re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$", timestr) is not None

def main():
    if len(sys.argv) == 4:
        logname, stime, etime = sys.argv[1:4]
    else:
        print("List of files in current directory:")
        print("\n".join(os.listdir('.')))
        logname = input("Enter the log file name: ").strip()
        stime = input("Enter the Start time (YYYY-MM-DD HH:MM): ").strip()
        etime = input("Enter the End time (YYYY-MM-DD HH:MM): ").strip()

    # Validate inputs
    if not logname or not os.path.isfile(logname):
        log_error(f"Error: Log file '{logname}' not found")
        sys.exit(1)
    if not validate_time(stime):
        log_error("Error: Invalid start time format")
        sys.exit(1)
    if not validate_time(etime):
        log_error("Error: Invalid end time format")
        sys.exit(1)

    # Check if required PCP commands are present
    for tool in ["pmdumplog", "pmrep", "pcp"]:
        if not shutil.which(tool):
            log_error(f"Error: {tool} not found. Please install PCP tools.")
            sys.exit(1)

    if not os.path.isfile(CONFIG_FILE):
        log_error(f"Warning: Configuration file {CONFIG_FILE} not found. Some metrics may fail.")

    print(f"Analyzing PCP log file: {logname}")
    print(f"Time range: {stime} to {etime}")

    # Command definitions
    metrics = [
        ("PMDUMPLOG", f"pmdumplog -z -L '{logname}'", f"PMDUMPLOG_{logname.replace(' ', '_')}.txt"),
        ("Load", f"pmrep -z -a '{logname}' -p kernel.all.load -S '@{stime}' -T '@{etime}'", "Load.txt"),
        ("Atop", f"pcp -z -a '{logname}' --start '@{stime}' --finish '@{etime}' atop", "Atop.txt"),
        ("Mpstat", f"pcp -z -a '{logname}' --start '@{stime}' --finish '@{etime}' mpstat", "Mpstat.txt"),
        ("Memory", f"pmrep -z -a '{logname}' -c '{CONFIG_FILE}' :meminfo-1 -p -S '@{stime}' -T '@{etime}'", "Memory.txt"),
        ("Iostat", f"pcp -z -a '{logname}' --start '@{stime}' --finish '@{etime}' iostat -x t", "Iostat.txt"),
        ("Vmstat", f"pmrep -z -a '{logname}' -p -S '@{stime}' -T '@{etime}' :vmstat", "Vmstat.txt"),
        ("D_state_Blocked", f"pmrep -z -a '{logname}' -p proc.runq.runnable proc.runq.blocked -S '@{stime}' -T '@{etime}'", "D_state_Blocked.txt"),
        ("Netstat", f"pcp -z -a '{logname}' --start '@{stime}' --finish '@{etime}' netstat", "Netstat.txt"),
        ("PS", f"pcp -z -a '{logname}' --start '@{stime}' --finish '@{etime}' ps -u", "PS.txt"),
        ("PID_STAT", f"pcp -z -a '{logname}' --start '@{stime}' --finish '@{etime}' pidstat -rl", "PID_STAT.txt"),
        ("Slabinfo", f"pmrep -z -c '{CONFIG_FILE}' :slabinfo -a '{logname}' -p -S '@{stime}' -T '@{etime}'", "Slabinfo.txt"),
        ("Numastat", f"pmrep -z -a '{logname}' -c '{CONFIG_FILE}' :numastat-1 -u -p -S '@{stime}' -T '@{etime}'", "Numastat.txt")
    ]

    for section, cmd, out_file in metrics:
        out_path = os.path.join(OUTPUT_DIR, out_file)
        print(f"--- {section} ---")
        run_command(cmd, out_path)
        print(f"Output for {section} saved to {out_path}")

    print("\nAnalysis complete. Results saved to", OUTPUT_DIR)
    print("Check", ERROR_LOG, "for any errors encountered during execution.")

if __name__ == "__main__":
    import shutil
    main()
