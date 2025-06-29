from Bio import Entrez, SeqIO
import re
import os
import sys

class NCBISequenceFetcher:
    """Class for handling NCBI sequence searches and downloads"""
    
    def __init__(self, email):
        """Initialize with user email for NCBI API"""
        self.email = email
        Entrez.email = email
        
    def search_gene_mane_select(self, gene_name, organism="homo sapiens"):
        """Search specifically for MANE Select sequences"""
        try:
            # First, try direct MANE Select search
            mane_search_term = f'"{gene_name}"[Gene Name] AND "MANE Select"[Filter] AND "{organism}"[Organism]'
            print(f"Searching for MANE Select with: {mane_search_term}")
            
            handle = Entrez.esearch(db="nucleotide", term=mane_search_term, retmax=5)
            record = Entrez.read(handle)
            handle.close()
            
            if record["IdList"]:
                # Get summaries for MANE Select results
                handle = Entrez.esummary(db="nucleotide", id=",".join(record["IdList"]))
                summaries = Entrez.read(handle)
                handle.close()
                
                # Format MANE Select results
                mane_results = []
                for summary in summaries:
                    accession = summary.get("Caption", "Unknown")
                    title = summary.get("Title", "Unknown")
                    length = summary.get("Length", 0)
                    
                    # Verify this is actually MANE Select
                    is_mane = "MANE Select" in title or "MANE_Select" in title
                    is_refseq = re.match(r"NM_", accession) is not None
                    
                    if is_mane or (is_refseq and gene_name.upper() in title.upper()):
                        mane_results.append({
                            "id": summary["Id"],
                            "accession": accession,
                            "title": title,
                            "length": length,
                            "is_mane": True,
                            "is_refseq": is_refseq,
                            "relevance_score": 100
                        })
                        print(f"  Found MANE Select: {accession} - {title[:80]}...")
                
                if mane_results:
                    return mane_results
                    
        except Exception as e:
            print(f"MANE Select search failed: {e}")
        
        # If MANE Select search fails, return empty list
        return []
    
    def search_gene(self, organism, gene_name):
        """Search for gene sequences in NCBI with improved strategy"""
        all_results = []
        
        # Strategy 1: Try MANE Select first
        mane_results = self.search_gene_mane_select(gene_name, organism)
        all_results.extend(mane_results)
        
        # Strategy 2: Gene-specific search
        try:
            gene_search_term = f'"{gene_name}"[Gene Name] AND "{organism}"[Organism] AND "mRNA"[Filter]'
            print(f"Searching with gene-specific query: {gene_search_term}")
            
            handle = Entrez.esearch(db="nucleotide", term=gene_search_term, retmax=10)
            record = Entrez.read(handle)
            handle.close()
            
            if record["IdList"]:
                # Get summaries for gene results
                handle = Entrez.esummary(db="nucleotide", id=",".join(record["IdList"]))
                summaries = Entrez.read(handle)
                handle.close()
                
                # Process gene search results
                for summary in summaries:
                    accession = summary.get("Caption", "Unknown")
                    title = summary.get("Title", "Unknown")
                    length = summary.get("Length", 0)
                    
                    # Skip if we already have this sequence from MANE search
                    if any(result["accession"] == accession for result in all_results):
                        continue
                    
                    # Check if this is a MANE Select entry
                    is_mane = "MANE Select" in title or "MANE_Select" in title
                    is_refseq = re.match(r"NM_", accession) is not None
                    is_predicted = re.match(r"XM_", accession) is not None
                    
                    # Calculate relevance score
                    relevance_score = 0
                    gene_in_title = gene_name.upper() in title.upper()
                    
                    if is_mane:
                        relevance_score += 100
                    elif is_refseq and gene_in_title:
                        relevance_score += 80
                    elif is_refseq:
                        relevance_score += 50
                    elif is_predicted and gene_in_title:
                        relevance_score += 30
                    elif is_predicted:
                        relevance_score += 10
                    
                    # Only include if relevance is reasonable
                    if relevance_score >= 30:
                        all_results.append({
                            "id": summary["Id"],
                            "accession": accession,
                            "title": title,
                            "length": length,
                            "is_mane": is_mane,
                            "is_refseq": is_refseq,
                            "is_predicted": is_predicted,
                            "relevance_score": relevance_score
                        })
                        print(f"  Found: {accession} (score: {relevance_score}) - {title[:60]}...")
                        
        except Exception as e:
            print(f"Gene search failed: {e}")
        
        # Strategy 3: Fallback to broader search if nothing found
        if not all_results:
            try:
                broad_search_term = f"{organism} {gene_name} mRNA"
                print(f"Fallback broad search: {broad_search_term}")
                
                handle = Entrez.esearch(db="nucleotide", term=broad_search_term, retmax=5)
                record = Entrez.read(handle)
                handle.close()
                
                if record["IdList"]:
                    handle = Entrez.esummary(db="nucleotide", id=",".join(record["IdList"]))
                    summaries = Entrez.read(handle)
                    handle.close()
                    
                    for summary in summaries:
                        accession = summary.get("Caption", "Unknown")
                        title = summary.get("Title", "Unknown")
                        length = summary.get("Length", 0)
                        
                        is_mane = "MANE Select" in title
                        is_refseq = re.match(r"NM_", accession) is not None
                        
                        all_results.append({
                            "id": summary["Id"],
                            "accession": accession,
                            "title": title,
                            "length": length,
                            "is_mane": is_mane,
                            "is_refseq": is_refseq,
                            "is_predicted": re.match(r"XM_", accession) is not None,
                            "relevance_score": 20 if is_refseq else 10
                        })
                        
            except Exception as e:
                print(f"Broad search failed: {e}")
        
        # Sort results by relevance score (highest first)
        all_results.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        print(f"Total results found for {gene_name}: {len(all_results)}")
        return all_results
    
    def find_mane_select(self, organism, gene_name):
        """Find and return the best sequence for a gene (prioritizing MANE Select)"""
        results = self.search_gene(organism, gene_name)
        
        if not results:
            print(f"No results found for {gene_name}")
            return None
        
        # Results are already sorted by relevance_score
        best_result = results[0]
        
        # Log what we found for debugging
        result_type = "MANE Select" if best_result['is_mane'] else "RefSeq" if best_result['is_refseq'] else "Predicted"
        print(f"  Best result for {gene_name}: {best_result['accession']} ({result_type}, score: {best_result['relevance_score']})")
        
        return best_result
    
    def download_sequence(self, seq_id, seq_length=0, output_dir=".", gene_name=None):
        """Download sequence and save to file
        
        Args:
            seq_id: NCBI sequence ID
            seq_length: Number of bases to download (0 = full length)
            output_dir: Directory to save the file
            gene_name: Gene name to include in filename
            
        Returns:
            Path to the saved file or None if error
        """
        try:
            print(f"Downloading sequence ID: {seq_id}, length: {seq_length}")
            
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
            
            print(f"Using Entrez.efetch with params: {params}")
            
            # Fetch the sequence
            handle = Entrez.efetch(**params)
            sequence_data = handle.read()
            handle.close()
            
            # Debug: Check what we received
            print(f"Received data length: {len(sequence_data)} bytes")
            print(f"First 100 characters: {sequence_data[:100]}")
            
            if not sequence_data:
                print("No sequence data received")
                return None
            
            # Extract accession from the first line of the FASTA
            first_line = sequence_data.split('\n')[0]
            accession_match = re.search(r'>(\S+)', first_line)
            if accession_match:
                raw_accession = accession_match.group(1)
                # Clean the accession for safe file naming
                accession = re.sub(r'[\\/*?:"<>|]', '_', raw_accession)
                print(f"Extracted accession: {raw_accession}")
                print(f"Cleaned for filename: {accession}")
            else:
                accession = f"sequence_{seq_id}"
                print(f"Could not extract accession, using: {accession}")
            
            # Create a Windows-safe filename with gene name
            if gene_name:
                # Clean gene name for safe file naming
                safe_gene_name = re.sub(r'[\\/*?:"<>|]', '_', gene_name)
                if seq_length > 0:
                    filename = f"{accession}_{seq_length}bp_{safe_gene_name}.fasta"
                else:
                    filename = f"{accession}_full_{safe_gene_name}.fasta"
            else:
                # Fallback to original naming if no gene name provided
                if seq_length > 0:
                    filename = f"{accession}_{seq_length}bp.fasta"
                else:
                    filename = f"{accession}_full.fasta"
            
            # Create the full filepath
            filepath = os.path.join(output_dir, filename)
            print(f"Saving to: {filepath}")
            
            # Make sure the directory exists
            os.makedirs(output_dir, exist_ok=True)
            
            # Write the file with explicit binary mode
            with open(filepath, "wb") as outfile:
                outfile.write(sequence_data.encode('utf-8'))
            
            # Verify file was written correctly
            if os.path.getsize(filepath) == 0:
                print("Failed to write sequence data to file (file is empty)")
                return None
            else:
                filesize = os.path.getsize(filepath)
                print(f"File written successfully: {filesize} bytes")
                
            return filepath
                
        except Exception as e:
            print(f"Error downloading sequence: {str(e)}")
            import traceback
            traceback.print_exc()
            return None