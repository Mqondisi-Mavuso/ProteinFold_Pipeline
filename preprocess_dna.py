"""
Enhanced sequence processing utilities for DNA and protein sequences
with bulk FASTA file processing and ROI extraction
"""
import re
import os
import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Tuple, Optional

class SequenceProcessor:
    """Class for processing DNA and protein sequences"""
    
    @staticmethod
    def find_roi_in_fasta(fasta_content, roi="CACCTG"):
        """Find the first line containing the Region of Interest in FASTA content
        
        Args:
            fasta_content (str): Content of a FASTA file
            roi (str): Region of Interest sequence to find (default: "CACCTG")
            
        Returns:
            str: Subsequence containing the ROI or None if not found
        """
        lines = fasta_content.strip().split('\n')
        
        # Skip header lines (start with >)
        sequence_lines = [line for line in lines if not line.startswith('>')]
        
        # Combine all sequence lines into one string for easier searching
        full_sequence = ''.join(sequence_lines)
        
        # Find the ROI
        roi_index = full_sequence.find(roi)
        if roi_index == -1:
            return None
        
        # Extract a subsequence containing the ROI (include some context around it)
        context_size = 30  # Nucleotides before and after ROI
        start = max(0, roi_index - context_size)
        end = min(len(full_sequence), roi_index + len(roi) + context_size)
        
        return full_sequence[start:end]
    
    @staticmethod
    def find_all_roi_in_sequence(sequence: str, roi: str = "CACCTG", context_size: int = 10) -> List[Dict]:
        """Find all occurrences of ROI in a sequence with context
        
        Args:
            sequence (str): DNA sequence to search in
            roi (str): Region of Interest sequence to find
            context_size (int): Number of bases before and after ROI to include
            
        Returns:
            List[Dict]: List of dictionaries containing ROI information
        """
        roi_occurrences = []
        start = 0
        
        while True:
            roi_index = sequence.find(roi, start)
            if roi_index == -1:
                break
                
            # Calculate start and end positions with context
            context_start = max(0, roi_index - context_size)
            context_end = min(len(sequence), roi_index + len(roi) + context_size)
            
            # Extract the sequence with context
            roi_with_context = sequence[context_start:context_end]
            
            # Create locus string (start_end format)
            roi_locus = f"{context_start}_{context_end-1}"
            
            roi_info = {
                'roi_sequence': roi_with_context,
                'roi_locus': roi_locus,
                'roi_start': roi_index,
                'roi_end': roi_index + len(roi) - 1,
                'context_start': context_start,
                'context_end': context_end - 1
            }
            
            roi_occurrences.append(roi_info)
            start = roi_index + 1  # Move past this occurrence
            
        return roi_occurrences
    
    @staticmethod
    def extract_sequence_from_fasta(fasta_content: str) -> str:
        """Extract the DNA sequence from FASTA content (removes headers)
        
        Args:
            fasta_content (str): Content of a FASTA file
            
        Returns:
            str: Clean DNA sequence
        """
        lines = fasta_content.strip().split('\n')
        sequence_lines = [line.strip() for line in lines if not line.startswith('>')]
        return ''.join(sequence_lines).upper()
    
    @staticmethod
    def parse_filename(filename: str) -> Tuple[str, str]:
        """Parse FASTA filename to extract accession number and gene name
        
        Args:
            filename (str): FASTA filename (e.g., "NM_001315501.2_full_SLC22A18.fasta")
            
        Returns:
            Tuple[str, str]: (accession_number, gene_name)
        """
        # Remove file extension
        base_name = Path(filename).stem
        
        # Split by underscore and extract parts
        parts = base_name.split('_')
        
        if len(parts) >= 3:
            # Format: accession_full_genename or accession_length_genename
            accession = parts[0]
            gene_name = '_'.join(parts[2:])  # In case gene name has underscores
        else:
            # Fallback: try to find pattern
            match = re.match(r'^([^_]+)_.*?([A-Za-z0-9]+)$', base_name)
            if match:
                accession = match.group(1)
                gene_name = match.group(2)
            else:
                accession = base_name
                gene_name = base_name
                
        return accession, gene_name
    
    @staticmethod
    def determine_status_from_json(gene_name: str, json_file_path: str) -> str:
        """Determine sequence status from JSON summary file
        
        Args:
            gene_name (str): Gene name to look up
            json_file_path (str): Path to JSON summary file
            
        Returns:
            str: Status ("MANE Select", "RefSeq", "Predicted", "Unknown")
        """
        try:
            with open(json_file_path, 'r') as f:
                data = json.load(f)
            
            # Look for the gene in successful results
            for result in data.get('successful_results', []):
                result_gene = result.get('gene_info', {}).get('gene_name', '')
                if result_gene.upper() == gene_name.upper():
                    search_result = result.get('search_result', {})
                    
                    if search_result.get('is_mane', False):
                        if search_result.get('is_refseq', False):
                            return "MANE Select+RefSeq"
                        else:
                            return "MANE Select"
                    elif search_result.get('is_refseq', False):
                        return "RefSeq"
                    elif search_result.get('is_predicted', False):
                        return "Predicted"
                    else:
                        return "Curated"
            
            return "Unknown"
            
        except Exception as e:
            print(f"Error reading JSON file {json_file_path}: {e}")
            return "Unknown"
    
    @staticmethod
    def process_fasta_directory(directory_path: str, roi: str = "CACCTG", 
                              progress_callback=None) -> pd.DataFrame:
        """Process all FASTA files in a directory and create summary DataFrame
        
        Args:
            directory_path (str): Path to directory containing FASTA files
            roi (str): Region of Interest sequence to find
            progress_callback: Optional callback function for progress updates
            
        Returns:
            pd.DataFrame: Summary DataFrame with columns:
                [gene_name, accession_number, species, status, found_roi, roi_locus, gene]
        """
        directory = Path(directory_path)
        fasta_files = list(directory.glob("*.fasta")) + list(directory.glob("*.fa"))
        
        if not fasta_files:
            raise ValueError(f"No FASTA files found in directory: {directory_path}")
        
        # Look for JSON summary file
        json_files = list(directory.glob("*.json"))
        json_file = json_files[0] if json_files else None
        
        results = []
        total_files = len(fasta_files)
        
        for idx, fasta_file in enumerate(fasta_files):
            if progress_callback:
                progress_callback(idx, total_files, f"Processing {fasta_file.name}")
            
            try:
                # Parse filename
                accession, gene_name = SequenceProcessor.parse_filename(fasta_file.name)
                
                # Determine status from JSON if available
                status = "Unknown"
                if json_file:
                    status = SequenceProcessor.determine_status_from_json(gene_name, str(json_file))
                
                # Read FASTA content
                with open(fasta_file, 'r') as f:
                    fasta_content = f.read()
                
                # Extract sequence
                sequence = SequenceProcessor.extract_sequence_from_fasta(fasta_content)
                
                # Find all ROI occurrences
                roi_occurrences = SequenceProcessor.find_all_roi_in_sequence(sequence, roi)
                
                if roi_occurrences:
                    # Add one row for each ROI occurrence
                    for roi_info in roi_occurrences:
                        results.append({
                            'gene_name': gene_name,
                            'accession_number': accession,
                            'species': 'homo sapiens',  # Default, could be extracted from FASTA header
                            'status': status,
                            'found_roi': True,
                            'roi_locus': roi_info['roi_locus'],
                            'gene': roi_info['roi_sequence']
                        })
                else:
                    # No ROI found, add single row with NA values
                    results.append({
                        'gene_name': gene_name,
                        'accession_number': accession,
                        'species': 'homo sapiens',
                        'status': status,
                        'found_roi': False,
                        'roi_locus': 'NA',
                        'gene': 'NA'
                    })
                    
            except Exception as e:
                print(f"Error processing file {fasta_file.name}: {e}")
                # Add error row
                results.append({
                    'gene_name': fasta_file.stem,
                    'accession_number': 'ERROR',
                    'species': 'NA',
                    'status': 'ERROR',
                    'found_roi': False,
                    'roi_locus': 'NA',
                    'gene': 'NA'
                })
        
        if progress_callback:
            progress_callback(total_files, total_files, "Processing complete!")
        
        # Create DataFrame
        df = pd.DataFrame(results)
        
        # Reorder columns to match specification
        column_order = ['gene_name', 'accession_number', 'species', 'status', 'found_roi', 'roi_locus', 'gene']
        df = df[column_order]
        
        return df
    
    @staticmethod
    def save_summary_to_excel(df: pd.DataFrame, output_path: str) -> str:
        """Save summary DataFrame to Excel file
        
        Args:
            df (pd.DataFrame): Summary DataFrame
            output_path (str): Path to save Excel file
            
        Returns:
            str: Full path to saved file
        """
        try:
            df.to_excel(output_path, index=False)
            return output_path
        except Exception as e:
            raise Exception(f"Error saving Excel file: {e}")
    
    @staticmethod
    def load_fasta_file(file_path):
        """Load a FASTA file and return its content
        
        Args:
            file_path (str): Path to the FASTA file
            
        Returns:
            str: Content of the FASTA file or None if error
        """
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            return content
        except Exception as e:
            print(f"Error loading FASTA file: {e}")
            return None
    
    @staticmethod
    def save_fasta(sequence, header, file_path):
        """Save a sequence as a FASTA file
        
        Args:
            sequence (str): Sequence to save
            header (str): FASTA header line (without '>')
            file_path (str): Path to save the file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(file_path, 'w') as f:
                f.write(f">{header}\n")
                
                # Write sequence in chunks of 60 characters per line
                for i in range(0, len(sequence), 60):
                    f.write(sequence[i:i+60] + "\n")
            return True
        except Exception as e:
            print(f"Error saving FASTA file: {e}")
            return False
    
    @staticmethod
    def extract_subsequence(sequence, start, end):
        """Extract a subsequence from a sequence
        
        Args:
            sequence (str): Full sequence
            start (int): Start position (0-based)
            end (int): End position (exclusive)
            
        Returns:
            str: Extracted subsequence
        """
        return sequence[start:end]
    
    @staticmethod
    def find_all_occurrences(sequence, pattern):
        """Find all occurrences of a pattern in a sequence
        
        Args:
            sequence (str): Sequence to search in
            pattern (str): Pattern to find
            
        Returns:
            list: List of starting positions of the pattern
        """
        positions = []
        start = 0
        
        while True:
            pos = sequence.find(pattern, start)
            if pos == -1:
                break
            positions.append(pos)
            start = pos + 1
            
        return positions
    
    @staticmethod
    def reverse_complement(dna_sequence):
        """Get the reverse complement of a DNA sequence
        
        Args:
            dna_sequence (str): DNA sequence
            
        Returns:
            str: Reverse complement of the DNA sequence
        """
        complement = {'A': 'T', 'C': 'G', 'G': 'C', 'T': 'A', 
                      'a': 't', 'c': 'g', 'g': 'c', 't': 'a',
                      'N': 'N', 'n': 'n'}
        
        # Create the complement
        complement_seq = ''.join(complement.get(base, base) for base in dna_sequence)
        
        # Reverse the complement
        reverse_complement_seq = complement_seq[::-1]
        
        return reverse_complement_seq
    
    @staticmethod
    def translate_dna(dna_sequence):
        """Translate a DNA sequence to protein
        
        Args:
            dna_sequence (str): DNA sequence
            
        Returns:
            str: Protein sequence
        """
        # Genetic code
        genetic_code = {
            'ATA': 'I', 'ATC': 'I', 'ATT': 'I', 'ATG': 'M',
            'ACA': 'T', 'ACC': 'T', 'ACG': 'T', 'ACT': 'T',
            'AAC': 'N', 'AAT': 'N', 'AAA': 'K', 'AAG': 'K',
            'AGC': 'S', 'AGT': 'S', 'AGA': 'R', 'AGG': 'R',
            'CTA': 'L', 'CTC': 'L', 'CTG': 'L', 'CTT': 'L',
            'CCA': 'P', 'CCC': 'P', 'CCG': 'P', 'CCT': 'P',
            'CAC': 'H', 'CAT': 'H', 'CAA': 'Q', 'CAG': 'Q',
            'CGA': 'R', 'CGC': 'R', 'CGG': 'R', 'CGT': 'R',
            'GTA': 'V', 'GTC': 'V', 'GTG': 'V', 'GTT': 'V',
            'GCA': 'A', 'GCC': 'A', 'GCG': 'A', 'GCT': 'A',
            'GAC': 'D', 'GAT': 'D', 'GAA': 'E', 'GAG': 'E',
            'GGA': 'G', 'GGC': 'G', 'GGG': 'G', 'GGT': 'G',
            'TCA': 'S', 'TCC': 'S', 'TCG': 'S', 'TCT': 'S',
            'TTC': 'F', 'TTT': 'F', 'TTA': 'L', 'TTG': 'L',
            'TAC': 'Y', 'TAT': 'Y', 'TAA': '*', 'TAG': '*',
            'TGC': 'C', 'TGT': 'C', 'TGA': '*', 'TGG': 'W',
        }
        
        # Make sequence uppercase
        dna_sequence = dna_sequence.upper()
        
        # Translate
        protein = ""
        for i in range(0, len(dna_sequence), 3):
            codon = dna_sequence[i:i+3]
            
            # Skip if the codon is incomplete
            if len(codon) < 3:
                continue
                
            # Translate the codon
            amino_acid = genetic_code.get(codon, 'X')  # 'X' for unknown codons
            protein += amino_acid
            
            # Stop at the first stop codon
            if amino_acid == '*':
                break
                
        return protein