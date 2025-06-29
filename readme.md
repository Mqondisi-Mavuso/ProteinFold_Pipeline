# NCBI Sequence Retriever & AlphaFold Submitter

A GUI application that allows you to search for gene sequences from NCBI, download them, preprocess them to find regions of interest, and submit them to AlphaFold 3 for protein-DNA complex prediction.

## Features

- Search for gene sequences from NCBI using gene name and organism
- Download sequences in FASTA format
- Find regions of interest (ROI) in DNA sequences
- Process DNA sequences for AlphaFold 3 submission
- Submit protein-DNA complex prediction jobs to AlphaFold 3
- Track job status and download results

## Installation

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the application:
   ```
   python main.py
   ```

## Requirements

- Python 3.8 or higher
- PyQt6
- Biopython
- Selenium
- BeautifulSoup4
- Requests
- Chrome WebDriver (for Selenium)

## File Structure

- `main.py` - Entry point for the application
- `ncbi_alphafold_gui_r.py` - Main GUI implementation
- `ncbi_sequence_fetcher.py` - Handles NCBI sequence searches and downloads
- `ncbi_threads.py` - Thread classes for non-blocking NCBI operations
-