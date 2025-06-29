"""
AlphaFold Crawler - Main module
This script integrates login, job submission, and results download
"""
import os
import sys
import time
import datetime
import argparse
from alphafold_login import AlphaFoldLogin
from alphafold_upload import AlphaFoldUploader
from alphafold_download import AlphaFoldDownloader

def parse_arguments():
    """Parse command line arguments
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description='AlphaFold Crawler')
    
    # Add command to run
    parser.add_argument('command', choices=['login', 'submit', 'status', 'download', 'all'],
                        help='Command to run (login, submit, status, download, or all)')
    
    # Add login parameters
    parser.add_argument('-e', '--email', help='Gmail email address for login')
    parser.add_argument('-p', '--password', help='Gmail password for login')
    
    # Add job submission parameters
    parser.add_argument('-j', '--job-name', help='Name for the AlphaFold job')
    parser.add_argument('-pf', '--protein-file', help='File containing protein sequence in FASTA format')
    parser.add_argument('-ps', '--protein-sequence', help='Protein sequence')
    parser.add_argument('-df', '--dna-file', help='File containing DNA sequence in FASTA format')
    parser.add_argument('-ds', '--dna-sequence', help='DNA sequence')
    parser.add_argument('-m', '--multimer', action='store_true', help='Use multimer model')
    parser.add_argument('-a', '--all-models', action='store_true', help='Save all 5 models')
    
    # Add job status and download parameters
    parser.add_argument('-i', '--job-id', help='AlphaFold job ID')
    parser.add_argument('-o', '--output-dir', default='results', help='Directory to save results')
    
    return parser.parse_args()

def read_sequence_file(file_path):
    """Read sequence from a FASTA file
    
    Args:
        file_path (str): Path to FASTA file
        
    Returns:
        str: Sequence
    """
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return None
        
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        # Skip header lines (those starting with >)
        sequence = ''
        for line in lines:
            if not line.startswith('>'):
                sequence += line.strip()
        
        return sequence
    except Exception as e:
        print(f"Error reading sequence file: {e}")
        return None

def login(args):
    """Login to AlphaFold
    
    Args:
        args: Command line arguments
        
    Returns:
        tuple: (login_handler, success)
    """
    # Create login handler
    login_handler = AlphaFoldLogin()
    
    # Set up with credentials if provided
    if args.email and args.password:
        login_handler.setup(args.email, args.password)
    
    # Try to login
    success = login_handler.login()
    
    return login_handler, success

def submit_job(args, login_handler):
    """Submit a job to AlphaFold
    
    Args:
        args: Command line arguments
        login_handler: AlphaFoldLogin instance
        
    Returns:
        tuple: (job_id, success)
    """
    # Get protein sequence
    protein_sequence = None
    if args.protein_sequence:
        protein_sequence = args.protein_sequence
    elif args.protein_file:
        protein_sequence = read_sequence_file(args.protein_file)
    
    if not protein_sequence:
        print("Protein sequence is required. Provide with -ps or -pf.")
        return None, False
    
    # Get DNA sequence if provided
    dna_sequence = None
    if args.dna_sequence:
        dna_sequence = args.dna_sequence
    elif args.dna_file:
        dna_sequence = read_sequence_file(args.dna_file)
    
    # Generate job name if not provided
    job_name = args.job_name
    if not job_name:
        job_name = f"AlphaFold_Job_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Create uploader
    uploader = AlphaFoldUploader(login_handler.get_driver())
    
    # Set up job parameters
    uploader.setup(
        job_name=job_name,
        protein_sequence=protein_sequence,
        dna_sequence=dna_sequence,
        use_multimer=args.multimer,
        save_all_models=args.all_models
    )
    
    # Submit the job
    success = uploader.submit_job()
    
    if success:
        job_id = uploader.get_job_id()
        print(f"Job submitted successfully with ID: {job_id}")
        print(f"Results URL: {uploader.get_results_url()}")
        return job_id, True
    else:
        print("Failed to submit job")
        return None, False

def check_job_status(args, login_handler):
    """Check job status
    
    Args:
        args: Command line arguments
        login_handler: AlphaFoldLogin instance
        
    Returns:
        tuple: (job_status, success)
    """
    # Create downloader
    downloader = AlphaFoldDownloader(login_handler.get_driver())
    
    # Set job ID if provided
    if args.job_id:
        downloader.set_job_id(args.job_id)
    
    # Check status
    status = downloader.check_job_status()
    
    if status != "Unknown":
        return status, True
    else:
        print("Failed to check job status")
        return status, False

def download_results(args, login_handler):
    """Download job results
    
    Args:
        args: Command line arguments
        login_handler: AlphaFoldLogin instance
        
    Returns:
        bool: Success
    """
    # Create downloader
    downloader = AlphaFoldDownloader(login_handler.get_driver())
    
    # Set job ID if provided
    if args.job_id:
        downloader.set_job_id(args.job_id)
    
    # Create output directory
    output_dir = args.output_dir
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Download results
    success = downloader.download_results(output_dir)
    
    if success:
        print(f"Results downloaded to {output_dir}")
        return True
    else:
        print("Failed to download results")
        return False

def run_all(args):
    """Run login, submit, check status, and download
    
    Args:
        args: Command line arguments
        
    Returns:
        bool: Success
    """
    # Login
    login_handler, login_success = login(args)
    if not login_success:
        return False
    
    # Submit job
    job_id, submit_success = submit_job(args, login_handler)
    if not submit_success:
        login_handler.cleanup()
        return False
    
    # Update args with job ID
    args.job_id = job_id
    
    # Check status in a loop until completed or failed
    print("Checking job status...")
    while True:
        status, status_success = check_job_status(args, login_handler)
        
        if status == "Completed":
            print("Job completed!")
            break
        elif status == "Failed":
            print("Job failed!")
            login_handler.cleanup()
            return False
        elif status == "Queued" or status == "Running":
            print(f"Job is {status}. Checking again in 60 seconds...")
            time.sleep(60)
        else:
            print(f"Unknown status: {status}. Checking again in 60 seconds...")
            time.sleep(60)
    
    # Download results
    download_success = download_results(args, login_handler)
    
    # Clean up
    login_handler.cleanup()
    
    return download_success

def main():
    """Main function"""
    # Parse arguments
    args = parse_arguments()
    
    # Run the specified command
    if args.command == 'login':
        login_handler, success = login(args)
        if success:
            print("Login successful")
            # Keep browser open for inspection
            input("Press Enter to close the browser...")
            login_handler.cleanup()
        else:
            print("Login failed")
        return success
        
    elif args.command == 'submit':
        login_handler, login_success = login(args)
        if not login_success:
            return False
            
        job_id, submit_success = submit_job(args, login_handler)
        
        # Clean up
        login_handler.cleanup()
        
        return submit_success
        
    elif args.command == 'status':
        login_handler, login_success = login(args)
        if not login_success:
            return False
            
        status, status_success = check_job_status(args, login_handler)
        
        # Clean up
        login_handler.cleanup()
        
        return status_success
        
    elif args.command == 'download':
        login_handler, login_success = login(args)
        if not login_success:
            return False
            
        download_success = download_results(args, login_handler)
        
        # Clean up
        login_handler.cleanup()
        
        return download_success
        
    elif args.command == 'all':
        return run_all(args)
    
    return False

if __name__ == "__main__":
    # Run main function
    success = main()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)
