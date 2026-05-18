import os
import subprocess
import glob

def run_discrete_benchmarks():
    """
    Run all discrete benchmarking experiments sequentially.
    """
    # Define paths to discrete benchmark configurations
    discrete_fixed_path = "local_matrix_computation/runs/descrete_fixed_toplogies/"
    discrete_random_path = "local_matrix_computation/runs/descrete_random_toplogies/"

    # Collect all batch files
    batch_files = glob.glob(os.path.join(discrete_fixed_path, "*.json"))
    batch_files += glob.glob(os.path.join(discrete_random_path, "*.json"))

    if not batch_files:
        print("No discrete benchmark configurations found.")
        return

    # Create output directory for logs
    output_dir = "local_matrix_computation/discrete_benchmark_logs"
    os.makedirs(output_dir, exist_ok=True)

    # File to track completed batches
    completed_batches_file = os.path.join(output_dir, "completed_batches.txt")
    completed_batches = set()

    # Load completed batches if the file exists
    if os.path.exists(completed_batches_file):
        with open(completed_batches_file, "r") as f:
            completed_batches = set(line.strip() for line in f)

    # Initialize success and failure tracking
    success_batches = []
    failed_batches = []

    # Run each batch file
    for batch_file in batch_files:
        if batch_file in completed_batches:
            print(f"Skipping already completed batch: {batch_file}")
            continue

        print(f"Running benchmark batch: {batch_file}")
        try:
            result = subprocess.run(
                ["python", "local_matrix_computation/run_batch.py", batch_file, "--force"],
                check=True,
                capture_output=True,
                text=True
            )
            # Log success
            success_batches.append(batch_file)
            log_file_path = os.path.join(output_dir, f"{os.path.basename(batch_file)}.log")
            with open(log_file_path, "w") as log_file:
                log_file.write(result.stdout)
                log_file.write(result.stderr)

            # Mark batch as completed
            with open(completed_batches_file, "a") as f:
                f.write(batch_file + "\n")
        except subprocess.CalledProcessError as e:
            # Log failure
            failed_batches.append(batch_file)
            error_log_path = os.path.join(output_dir, f"{os.path.basename(batch_file)}.error.log")
            with open(error_log_path, "w") as error_log:
                error_log.write(e.stdout or "")
                error_log.write(e.stderr or "")
            print(f"Error running batch {batch_file}: {e}")

    # Write summary to file
    summary_file_path = os.path.join(output_dir, "summary.txt")
    with open(summary_file_path, "w") as summary_file:
        summary_file.write("Summary of Discrete Benchmark Runs:\n")
        summary_file.write(f"Successful batches ({len(success_batches)}):\n")
        for batch in success_batches:
            summary_file.write(f"  - {batch}\n")

        summary_file.write(f"Failed batches ({len(failed_batches)}):\n")
        for batch in failed_batches:
            summary_file.write(f"  - {batch}\n")

    print(f"Summary written to {summary_file_path}")

    # Exit with appropriate code
    if failed_batches:
        exit(1)

if __name__ == "__main__":
    run_discrete_benchmarks()