"""
Sequence processing utilities for DNA and protein sequences
"""
import re
import os

class SequenceProcessor:
    """Class for processing DNA and protein sequences"""
    
    @staticmethod
    def find_roi_in_fasta(fasta_content, roi="CACCTGA"):
        """Find the first line containing the Region of Interest in FASTA content
        
        Args:
            fasta_content (str): Content of a FASTA file
            roi (str): Region of Interest sequence to find (default: "CACCTGA")
            
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