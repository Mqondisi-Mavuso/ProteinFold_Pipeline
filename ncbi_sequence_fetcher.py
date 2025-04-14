from Bio import Entrez, SeqIO
import re
import os

class NCBISequenceFetcher:
    """Class for handling NCBI sequence searches and downloads"""
    
    def __init__(self, email):
        """Initialize with user email for NCBI API"""
        self.email = email
        Entrez.email = email
        
    def search_gene(self, organism, gene_name):
        """Search for gene sequences in NCBI"""
        search_term = f"{organism} {gene_name}"
        
        # Search the nucleotide database
        handle = Entrez.esearch(db="nucleotide", term=search_term, retmax=10)
        record = Entrez.read(handle)
        handle.close()
        
        if not record["IdList"]:
            return []
            
        # Get summaries for the results
        handle = Entrez.esummary(db="nucleotide", id=",".join(record["IdList"]))
        summaries = Entrez.read(handle)
        handle.close()
        
        # Format the results
        results = []
        for summary in summaries:
            accession = summary.get("Caption", "Unknown")
            title = summary.get("Title", "Unknown")
            length = summary.get("Length", 0)
            
            # Check if this is a MANE Select entry
            is_mane = "MANE Select" in title
            is_refseq = re.match(r"NM_|XM_", accession) is not None
            
            results.append({
                "id": summary["Id"],
                "accession": accession,
                "title": title,
                "length": length,
                "is_mane": is_mane,
                "is_refseq": is_refseq
            })
        
        return results
    
    def download_sequence(self, seq_id, seq_length=0, output_dir="."):
        """Download sequence and save to file
        
        Args:
            seq_id: NCBI sequence ID
            seq_length: Number of bases to download (0 = full length)
            output_dir: Directory to save the file
            
        Returns:
            Path to the saved file or None if error
        """
        try:
            # Create parameters for fetch
            params = {
                "db": "nucleotide",
                "id": seq_id,
                "rettype": "fasta",
                "retmode": "text"
            }
            
            # Add sequence length limits if specified
            if seq_length > 0:
                params["seq_start"] = 1
                params["seq_stop"] = seq_length
            
            # Fetch the sequence using the proven direct approach
            handle = Entrez.efetch(**params)
            sequence_data = handle.read()
            handle.close()
            
            if not sequence_data:
                print("No sequence data received")
                return None
            
            # Extract accession from the first line of the FASTA
            first_line = sequence_data.split('\n')[0]
            accession_match = re.search(r'>(\S+)', first_line)
            if accession_match:
                accession = accession_match.group(1)
            else:
                accession = f"sequence_{seq_id}"
            
            # Save to file
            filename = f"{accession}_seq.fasta"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, "w", encoding="utf-8") as outfile:
                outfile.write(sequence_data)
            
            # Verify file was written correctly
            if os.path.getsize(filepath) == 0:
                print("Failed to write sequence data to file (file is empty)")
                return None
                
            return filepath
            
        except Exception as e:
            print(f"Error downloading sequence: {str(e)}")
            return None
            
    def find_mane_select(self, organism, gene_name):
        """Find and return the MANE select or RefSeq entry for a gene"""
        results = self.search_gene(organism, gene_name)
        
        # First look for MANE Select
        for result in results:
            if result["is_mane"]:
                return result
        
        # Then look for RefSeq (NM_) entries
        for result in results:
            if result["is_refseq"]:
                return result
                
        # Return the first result if nothing else found
        if results:
            return results[0]
            
        return None
