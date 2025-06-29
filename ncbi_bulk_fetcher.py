"""
NCBI Bulk Sequence Fetcher
Handles bulk sequence retrieval from Excel spreadsheets
"""
import pandas as pd
import os
import time
import json
from datetime import datetime
from ncbi_sequence_fetcher import NCBISequenceFetcher

class NCBIBulkFetcher:
    """Class for handling bulk NCBI sequence downloads from Excel files"""
    
    def __init__(self, email):
        """Initialize with user email for NCBI API"""
        self.email = email
        self.fetcher = NCBISequenceFetcher(email)
        self.results = []
        self.failed_genes = []
        self.progress_callback = None
        self.should_stop = False
        
    def set_progress_callback(self, callback):
        """Set callback function for progress updates
        
        Args:
            callback: Function that takes (current, total, message) parameters
        """
        self.progress_callback = callback
    
    def stop_processing(self):
        """Signal to stop the bulk processing"""
        self.should_stop = True
    
    def load_gene_list_from_excel(self, excel_path, gene_column=0, organism_column=None, 
                                  status_column=None, sheet_name=None):
        """Load gene list from Excel file
        
        Args:
            excel_path (str): Path to Excel file
            gene_column (int or str): Column index or name containing gene names
            organism_column (int or str, optional): Column index or name containing organism names
            status_column (int or str, optional): Column index or name containing status info
            sheet_name (str, optional): Sheet name to read (default: first sheet)
            
        Returns:
            list: List of dictionaries with gene information
        """
        try:
            # Read Excel file
            if sheet_name:
                df = pd.read_excel(excel_path, sheet_name=sheet_name)
            else:
                df = pd.read_excel(excel_path)
            
            # Remove completely empty rows
            df = df.dropna(how='all')
            
            # Get column names if they're strings, otherwise use positional indexing
            if isinstance(gene_column, str):
                gene_col_name = gene_column
            else:
                gene_col_name = df.columns[gene_column]
            
            organism_col_name = None
            if organism_column is not None:
                if isinstance(organism_column, str):
                    organism_col_name = organism_column
                else:
                    organism_col_name = df.columns[organism_column]
            
            status_col_name = None
            if status_column is not None:
                if isinstance(status_column, str):
                    status_col_name = status_column
                else:
                    status_col_name = df.columns[status_column]
            
            # Extract gene information
            gene_list = []
            for index, row in df.iterrows():
                gene_name = str(row[gene_col_name]).strip() if pd.notna(row[gene_col_name]) else None
                
                # Skip empty gene names
                if not gene_name or gene_name.lower() in ['', 'nan', 'none']:
                    continue
                
                gene_info = {
                    'gene_name': gene_name,
                    'organism': 'homo sapiens',  # Default organism
                    'status': None,
                    'row_index': index
                }
                
                # Add organism if specified
                if organism_col_name and organism_col_name in df.columns:
                    organism = str(row[organism_col_name]).strip() if pd.notna(row[organism_col_name]) else None
                    if organism and organism.lower() not in ['', 'nan', 'none']:
                        gene_info['organism'] = organism
                
                # Add status if specified
                if status_col_name and status_col_name in df.columns:
                    status = str(row[status_col_name]).strip() if pd.notna(row[status_col_name]) else None
                    if status and status.lower() not in ['', 'nan', 'none']:
                        gene_info['status'] = status
                
                gene_list.append(gene_info)
            
            print(f"Loaded {len(gene_list)} genes from Excel file")
            return gene_list
            
        except Exception as e:
            print(f"Error loading Excel file: {e}")
            raise e
    
    def search_and_download_bulk(self, gene_list, output_dir, seq_length=0, 
                                delay_between_requests=1.0, max_retries=3):
        """Search and download sequences for multiple genes
        
        Args:
            gene_list (list): List of gene dictionaries from load_gene_list_from_excel
            output_dir (str): Directory to save sequences
            seq_length (int): Number of bases to download (0 = full length)
            delay_between_requests (float): Delay in seconds between NCBI requests
            max_retries (int): Maximum number of retries for failed downloads
            
        Returns:
            dict: Summary of results with successful and failed downloads
        """
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Initialize results tracking
        self.results = []
        self.failed_genes = []
        successful_downloads = 0
        
        total_genes = len(gene_list)
        
        # Create a summary file
        summary_file = os.path.join(output_dir, f"bulk_download_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        
        for i, gene_info in enumerate(gene_list):
            if self.should_stop:
                print("Bulk processing stopped by user")
                break
                
            gene_name = gene_info['gene_name']
            organism = gene_info['organism']
            
            # Update progress
            if self.progress_callback:
                self.progress_callback(i + 1, total_genes, f"Processing {gene_name}")
            
            print(f"Processing {i+1}/{total_genes}: {gene_name} ({organism})")
            
            try:
                # Search for the gene
                search_results = self.fetcher.search_gene(organism, gene_name)
                
                if not search_results:
                    print(f"  No results found for {gene_name}")
                    self.failed_genes.append({
                        'gene_info': gene_info,
                        'error': 'No search results found',
                        'retry_count': 0
                    })
                    continue
                
                # Find the best result (MANE Select or RefSeq)
                best_result = self.fetcher.find_mane_select(organism, gene_name)
                
                if not best_result:
                    best_result = search_results[0]  # Fallback to first result
                
                print(f"  Found: {best_result['accession']} - {best_result['title'][:50]}...")
                
                # Download the sequence with retries
                download_success = False
                retry_count = 0
                
                while retry_count < max_retries and not download_success:
                    try:
                        filepath = self.fetcher.download_sequence(
                            best_result['id'], 
                            seq_length, 
                            output_dir
                        )
                        
                        if filepath:
                            print(f"  Downloaded to: {filepath}")
                            
                            # Record successful download
                            result_info = {
                                'gene_info': gene_info,
                                'search_result': best_result,
                                'filepath': filepath,
                                'download_time': datetime.now().isoformat(),
                                'seq_length_requested': seq_length
                            }
                            
                            self.results.append(result_info)
                            successful_downloads += 1
                            download_success = True
                            
                        else:
                            retry_count += 1
                            print(f"  Download failed, retry {retry_count}/{max_retries}")
                            
                    except Exception as download_error:
                        retry_count += 1
                        print(f"  Download error (retry {retry_count}/{max_retries}): {download_error}")
                        
                        if retry_count >= max_retries:
                            self.failed_genes.append({
                                'gene_info': gene_info,
                                'search_result': best_result,
                                'error': str(download_error),
                                'retry_count': retry_count
                            })
                
                if not download_success:
                    print(f"  Failed to download {gene_name} after {max_retries} attempts")
                    if not any(f['gene_info']['gene_name'] == gene_name for f in self.failed_genes):
                        self.failed_genes.append({
                            'gene_info': gene_info,
                            'search_result': best_result,
                            'error': 'Download failed after retries',
                            'retry_count': max_retries
                        })
                
            except Exception as e:
                print(f"  Error processing {gene_name}: {e}")
                self.failed_genes.append({
                    'gene_info': gene_info,
                    'error': str(e),
                    'retry_count': 0
                })
            
            # Add delay between requests to be respectful to NCBI
            if i < total_genes - 1:  # Don't delay after the last request
                time.sleep(delay_between_requests)
        
        # Save summary
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_genes': total_genes,
            'successful_downloads': successful_downloads,
            'failed_downloads': len(self.failed_genes),
            'output_directory': output_dir,
            'seq_length_requested': seq_length,
            'successful_results': self.results,
            'failed_genes': self.failed_genes
        }
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\nBulk download completed!")
        print(f"Successful downloads: {successful_downloads}")
        print(f"Failed downloads: {len(self.failed_genes)}")
        print(f"Summary saved to: {summary_file}")
        
        return summary
    
    def retry_failed_downloads(self, summary_file, output_dir, max_retries=3):
        """Retry downloading sequences that failed in a previous run
        
        Args:
            summary_file (str): Path to the summary JSON file from previous run
            output_dir (str): Directory to save sequences
            max_retries (int): Maximum number of retries
            
        Returns:
            dict: Updated summary with retry results
        """
        try:
            # Load previous summary
            with open(summary_file, 'r') as f:
                previous_summary = json.load(f)
            
            failed_genes = previous_summary.get('failed_genes', [])
            
            if not failed_genes:
                print("No failed genes to retry")
                return previous_summary
            
            print(f"Retrying {len(failed_genes)} failed downloads...")
            
            # Retry failed downloads
            retry_results = []
            still_failed = []
            
            for i, failed_gene in enumerate(failed_genes):
                if self.should_stop:
                    break
                    
                gene_info = failed_gene['gene_info']
                gene_name = gene_info['gene_name']
                organism = gene_info['organism']
                
                if self.progress_callback:
                    self.progress_callback(i + 1, len(failed_genes), f"Retrying {gene_name}")
                
                print(f"Retrying {i+1}/{len(failed_genes)}: {gene_name}")
                
                try:
                    # Search again
                    search_results = self.fetcher.search_gene(organism, gene_name)
                    
                    if search_results:
                        best_result = self.fetcher.find_mane_select(organism, gene_name)
                        if not best_result:
                            best_result = search_results[0]
                        
                        # Try download
                        filepath = self.fetcher.download_sequence(
                            best_result['id'], 
                            previous_summary.get('seq_length_requested', 0), 
                            output_dir
                        )
                        
                        if filepath:
                            print(f"  Retry successful: {filepath}")
                            retry_results.append({
                                'gene_info': gene_info,
                                'search_result': best_result,
                                'filepath': filepath,
                                'download_time': datetime.now().isoformat(),
                                'retry_attempt': True
                            })
                        else:
                            still_failed.append(failed_gene)
                    else:
                        still_failed.append(failed_gene)
                        
                except Exception as e:
                    print(f"  Retry failed: {e}")
                    failed_gene['retry_error'] = str(e)
                    still_failed.append(failed_gene)
                
                time.sleep(1.0)  # Delay between retry requests
            
            # Update summary
            updated_summary = previous_summary.copy()
            updated_summary['retry_timestamp'] = datetime.now().isoformat()
            updated_summary['retry_successful'] = len(retry_results)
            updated_summary['still_failed'] = len(still_failed)
            updated_summary['successful_results'].extend(retry_results)
            updated_summary['failed_genes'] = still_failed
            updated_summary['successful_downloads'] += len(retry_results)
            updated_summary['failed_downloads'] = len(still_failed)
            
            # Save updated summary
            with open(summary_file, 'w') as f:
                json.dump(updated_summary, f, indent=2)
            
            print(f"Retry completed! {len(retry_results)} additional successful downloads")
            return updated_summary
            
        except Exception as e:
            print(f"Error during retry: {e}")
            raise e
    
    def get_results_summary(self):
        """Get a summary of the current results
        
        Returns:
            dict: Summary information
        """
        return {
            'total_processed': len(self.results) + len(self.failed_genes),
            'successful': len(self.results),
            'failed': len(self.failed_genes),
            'success_rate': len(self.results) / max(1, len(self.results) + len(self.failed_genes)) * 100
        }
