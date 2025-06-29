"""
Protein and ROI Data Loader
Handles loading and validation of protein sequences and ROI data from Excel files
"""

import pandas as pd
import os
import re
from typing import List, Dict, Tuple, Optional


class ProteinDataLoader:
    """Class for loading and managing protein sequence data"""
    
    @staticmethod
    def load_protein_excel(file_path: str, name_column: int = 0, sequence_column: int = 1, 
                          sheet_name: str = None) -> List[Dict]:
        """Load protein data from Excel file
        
        Args:
            file_path (str): Path to Excel file
            name_column (int): Column index for protein names
            sequence_column (int): Column index for protein sequences
            sheet_name (str, optional): Sheet name to read
            
        Returns:
            List[Dict]: List of protein dictionaries
            
        Raises:
            Exception: If file cannot be read or data is invalid
        """
        try:
            # Read Excel file
            if sheet_name:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            else:
                df = pd.read_excel(file_path)
            
            # Remove empty rows
            df = df.dropna(how='all')
            
            proteins = []
            for index, row in df.iterrows():
                try:
                    # Extract protein name and sequence
                    protein_name = str(row.iloc[name_column]).strip() if pd.notna(row.iloc[name_column]) else None
                    protein_seq = str(row.iloc[sequence_column]).strip() if pd.notna(row.iloc[sequence_column]) else None
                    
                    # Skip invalid entries
                    if not protein_name or not protein_seq or protein_name.lower() in ['nan', 'none', '']:
                        continue
                    
                    # Clean and validate protein sequence
                    cleaned_seq = ProteinDataLoader.clean_protein_sequence(protein_seq)
                    
                    if cleaned_seq and len(cleaned_seq) >= 10:  # Minimum length check
                        protein_data = {
                            'name': protein_name,
                            'sequence': cleaned_seq,
                            'length': len(cleaned_seq),
                            'original_length': len(protein_seq),
                            'row_index': index
                        }
                        
                        # Add validation info
                        validation = ProteinDataLoader.validate_protein_sequence(cleaned_seq)
                        protein_data.update(validation)
                        
                        proteins.append(protein_data)
                        
                except Exception as e:
                    print(f"Error processing row {index}: {e}")
                    continue
            
            return proteins
            
        except Exception as e:
            raise Exception(f"Error loading protein Excel file: {str(e)}")
    
    @staticmethod
    def clean_protein_sequence(sequence: str) -> str:
        """Clean protein sequence by removing invalid characters
        
        Args:
            sequence (str): Raw protein sequence
            
        Returns:
            str: Cleaned protein sequence
        """
        if not sequence:
            return ""
        
        # Remove whitespace and convert to uppercase
        cleaned = re.sub(r'\s+', '', sequence.upper())
        
        # Keep only valid amino acid letters
        valid_aa = set('ACDEFGHIKLMNPQRSTVWY')
        cleaned = ''.join(char for char in cleaned if char in valid_aa)
        
        return cleaned
    
    @staticmethod
    def validate_protein_sequence(sequence: str) -> Dict:
        """Validate protein sequence and return validation info
        
        Args:
            sequence (str): Protein sequence to validate
            
        Returns:
            Dict: Validation information
        """
        validation = {
            'is_valid': True,
            'warnings': [],
            'amino_acid_composition': {}
        }
        
        if not sequence:
            validation['is_valid'] = False
            validation['warnings'].append("Empty sequence")
            return validation
        
        # Check length
        if len(sequence) < 10:
            validation['warnings'].append(f"Very short sequence ({len(sequence)} AA)")
        elif len(sequence) > 5000:
            validation['warnings'].append(f"Very long sequence ({len(sequence)} AA)")
        
        # Check for invalid characters
        valid_aa = set('ACDEFGHIKLMNPQRSTVWY')
        invalid_chars = set(sequence) - valid_aa
        if invalid_chars:
            validation['warnings'].append(f"Invalid characters found: {invalid_chars}")
        
        # Calculate amino acid composition
        for aa in valid_aa:
            count = sequence.count(aa)
            if count > 0:
                validation['amino_acid_composition'][aa] = {
                    'count': count,
                    'percentage': round((count / len(sequence)) * 100, 2)
                }
        
        # Check for unusual composition
        if sequence.count('X') > len(sequence) * 0.1:
            validation['warnings'].append("High percentage of unknown amino acids (X)")
        
        return validation


class ROIDataLoader:
    """Class for loading and managing ROI (Region of Interest) data"""
    
    @staticmethod
    def load_roi_excel(file_path: str, sheet_name: str = 'ROI_Analysis') -> List[Dict]:
        """Load ROI data from Excel file
        
        Args:
            file_path (str): Path to Excel file
            sheet_name (str): Sheet name containing ROI data
            
        Returns:
            List[Dict]: List of ROI dictionaries
            
        Raises:
            Exception: If file cannot be read or required columns are missing
        """
        try:
            # Read Excel file
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            # Check required columns
            required_columns = ['gene_name', 'gene', 'roi_locus', 'found_roi']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                raise Exception(f"Missing required columns: {missing_columns}")
            
            # Filter for rows where ROI was found
            roi_df = df[df['found_roi'] == True].copy()
            
            if roi_df.empty:
                raise Exception("No ROI sequences found in the data")
            
            roi_data = []
            for index, row in roi_df.iterrows():
                try:
                    # Extract ROI information
                    gene_name = str(row['gene_name']).strip()
                    roi_sequence = str(row['gene']).strip()
                    roi_locus = str(row['roi_locus']).strip()
                    
                    # Skip invalid entries
                    if pd.isna(row['gene']) or pd.isna(row['gene_name']) or pd.isna(row['roi_locus']):
                        continue
                    
                    # Clean and validate DNA sequence
                    cleaned_seq = ROIDataLoader.clean_dna_sequence(roi_sequence)
                    
                    if cleaned_seq and len(cleaned_seq) >= 10:  # Minimum length check
                        roi_entry = {
                            'gene_name': gene_name,
                            'roi_sequence': cleaned_seq,
                            'roi_locus': roi_locus,
                            'accession': str(row.get('accession_number', 'Unknown')),
                            'species': str(row.get('species', 'homo sapiens')),
                            'status': str(row.get('status', 'Unknown')),
                            'original_length': len(roi_sequence),
                            'cleaned_length': len(cleaned_seq),
                            'row_index': index
                        }
                        
                        # Add validation info
                        validation = ROIDataLoader.validate_dna_sequence(cleaned_seq)
                        roi_entry.update(validation)
                        
                        roi_data.append(roi_entry)
                        
                except Exception as e:
                    print(f"Error processing ROI row {index}: {e}")
                    continue
            
            return roi_data
            
        except Exception as e:
            raise Exception(f"Error loading ROI Excel file: {str(e)}")
    
    @staticmethod
    def clean_dna_sequence(sequence: str) -> str:
        """Clean DNA sequence by removing invalid characters
        
        Args:
            sequence (str): Raw DNA sequence
            
        Returns:
            str: Cleaned DNA sequence
        """
        if not sequence:
            return ""
        
        # Remove whitespace and convert to uppercase
        cleaned = re.sub(r'\s+', '', sequence.upper())
        
        # Keep only valid DNA nucleotides
        valid_nucleotides = set('ATCG')
        cleaned = ''.join(char for char in cleaned if char in valid_nucleotides)
        
        return cleaned
    
    @staticmethod
    def validate_dna_sequence(sequence: str) -> Dict:
        """Validate DNA sequence and return validation info
        
        Args:
            sequence (str): DNA sequence to validate
            
        Returns:
            Dict: Validation information
        """
        validation = {
            'is_valid': True,
            'warnings': [],
            'nucleotide_composition': {}
        }
        
        if not sequence:
            validation['is_valid'] = False
            validation['warnings'].append("Empty sequence")
            return validation
        
        # Check length
        if len(sequence) < 10:
            validation['warnings'].append(f"Very short sequence ({len(sequence)} bp)")
        elif len(sequence) > 1000:
            validation['warnings'].append(f"Very long sequence ({len(sequence)} bp)")
        
        # Check for invalid characters
        valid_nucleotides = set('ATCG')
        invalid_chars = set(sequence) - valid_nucleotides
        if invalid_chars:
            validation['warnings'].append(f"Invalid characters found: {invalid_chars}")
        
        # Calculate nucleotide composition
        for nucleotide in valid_nucleotides:
            count = sequence.count(nucleotide)
            if count > 0:
                validation['nucleotide_composition'][nucleotide] = {
                    'count': count,
                    'percentage': round((count / len(sequence)) * 100, 2)
                }
        
        # Check GC content
        gc_count = sequence.count('G') + sequence.count('C')
        gc_content = (gc_count / len(sequence)) * 100 if len(sequence) > 0 else 0
        validation['gc_content'] = round(gc_content, 2)
        
        if gc_content < 20 or gc_content > 80:
            validation['warnings'].append(f"Unusual GC content: {gc_content:.1f}%")
        
        return validation


class JobPairGenerator:
    """Class for generating protein-ROI job pairs"""
    
    @staticmethod
    def create_all_combinations(proteins: List[Dict], roi_data: List[Dict]) -> List[Dict]:
        """Create all possible protein-ROI combinations for AlphaFold jobs
        
        Args:
            proteins (List[Dict]): List of protein data
            roi_data (List[Dict]): List of ROI data
            
        Returns:
            List[Dict]: List of job dictionaries
        """
        jobs = []
        
        for protein in proteins:
            for roi in roi_data:
                job = JobPairGenerator.create_job_pair(protein, roi)
                jobs.append(job)
        
        return jobs
    
    @staticmethod
    def create_job_pair(protein: Dict, roi: Dict) -> Dict:
        """Create a single protein-ROI job pair
        
        Args:
            protein (Dict): Protein data
            roi (Dict): ROI data
            
        Returns:
            Dict: Job dictionary
        """
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M")
        
        # Generate job name according to specification
        job_name = f"Protein-DNA_{protein['name']}_{roi['gene_name']}_{roi['roi_locus']}_{timestamp}"
        
        return {
            'job_name': job_name,
            'protein_name': protein['name'],
            'protein_sequence': protein['sequence'],
            'protein_length': protein['length'],
            'dna_sequence': roi['roi_sequence'],
            'gene_name': roi['gene_name'],
            'roi_locus': roi['roi_locus'],
            'accession': roi['accession'],
            'species': roi['species'],
            'created_time': datetime.now().isoformat(),
            'estimated_complexity': JobPairGenerator.estimate_job_complexity(protein, roi)
        }
    
    @staticmethod
    def estimate_job_complexity(protein: Dict, roi: Dict) -> str:
        """Estimate the computational complexity of a protein-ROI job
        
        Args:
            protein (Dict): Protein data
            roi (Dict): ROI data
            
        Returns:
            str: Complexity estimate ('Low', 'Medium', 'High')
        """
        protein_length = protein['length']
        roi_length = len(roi['roi_sequence'])
        
        total_residues = protein_length + (roi_length // 3)  # Approximate amino acids from DNA
        
        if total_residues < 200:
            return 'Low'
        elif total_residues < 500:
            return 'Medium'
        else:
            return 'High'
    
    @staticmethod
    def filter_jobs_by_criteria(jobs: List[Dict], max_protein_length: int = None, 
                               max_roi_length: int = None, complexity_limit: str = None) -> List[Dict]:
        """Filter jobs based on specified criteria
        
        Args:
            jobs (List[Dict]): List of job dictionaries
            max_protein_length (int, optional): Maximum protein length
            max_roi_length (int, optional): Maximum ROI length
            complexity_limit (str, optional): Maximum complexity level
            
        Returns:
            List[Dict]: Filtered job list
        """
        filtered_jobs = []
        
        complexity_order = {'Low': 1, 'Medium': 2, 'High': 3}
        max_complexity_level = complexity_order.get(complexity_limit, 3)
        
        for job in jobs:
            # Check protein length
            if max_protein_length and job['protein_length'] > max_protein_length:
                continue
            
            # Check ROI length
            if max_roi_length and len(job['dna_sequence']) > max_roi_length:
                continue
            
            # Check complexity
            job_complexity_level = complexity_order.get(job['estimated_complexity'], 3)
            if job_complexity_level > max_complexity_level:
                continue
            
            filtered_jobs.append(job)
        
        return filtered_jobs


class DataValidator:
    """Class for validating protein and ROI data before job submission"""
    
    @staticmethod
    def validate_protein_data(proteins: List[Dict]) -> Tuple[List[Dict], List[str]]:
        """Validate protein data and return valid proteins with warnings
        
        Args:
            proteins (List[Dict]): List of protein dictionaries
            
        Returns:
            Tuple[List[Dict], List[str]]: (valid_proteins, validation_warnings)
        """
        valid_proteins = []
        warnings = []
        
        for i, protein in enumerate(proteins):
            protein_warnings = []
            
            # Check name
            if not protein.get('name') or len(protein['name'].strip()) == 0:
                protein_warnings.append(f"Protein {i+1}: Missing or empty name")
                continue
            
            # Check sequence
            if not protein.get('sequence') or len(protein['sequence']) == 0:
                protein_warnings.append(f"Protein {protein['name']}: Missing or empty sequence")
                continue
            
            # Check sequence length
            if len(protein['sequence']) < 10:
                protein_warnings.append(f"Protein {protein['name']}: Sequence too short ({len(protein['sequence'])} AA)")
                continue
            
            if len(protein['sequence']) > 2000:
                protein_warnings.append(f"Protein {protein['name']}: Very long sequence ({len(protein['sequence'])} AA) - may take longer to process")
            
            # Check for duplicate names
            duplicate_names = [p['name'] for p in valid_proteins if p['name'] == protein['name']]
            if duplicate_names:
                protein_warnings.append(f"Protein {protein['name']}: Duplicate name found")
            
            # Add validation warnings from sequence validation
            if protein.get('warnings'):
                for warning in protein['warnings']:
                    protein_warnings.append(f"Protein {protein['name']}: {warning}")
            
            # If no critical errors, add to valid list
            if not any('Missing or empty' in w or 'too short' in w for w in protein_warnings):
                valid_proteins.append(protein)
            
            warnings.extend(protein_warnings)
        
        return valid_proteins, warnings
    
    @staticmethod
    def validate_roi_data(roi_data: List[Dict]) -> Tuple[List[Dict], List[str]]:
        """Validate ROI data and return valid ROIs with warnings
        
        Args:
            roi_data (List[Dict]): List of ROI dictionaries
            
        Returns:
            Tuple[List[Dict], List[str]]: (valid_rois, validation_warnings)
        """
        valid_rois = []
        warnings = []
        
        for i, roi in enumerate(roi_data):
            roi_warnings = []
            
            # Check gene name
            if not roi.get('gene_name') or len(roi['gene_name'].strip()) == 0:
                roi_warnings.append(f"ROI {i+1}: Missing or empty gene name")
                continue
            
            # Check sequence
            if not roi.get('roi_sequence') or len(roi['roi_sequence']) == 0:
                roi_warnings.append(f"ROI {roi['gene_name']}: Missing or empty sequence")
                continue
            
            # Check sequence length
            if len(roi['roi_sequence']) < 10:
                roi_warnings.append(f"ROI {roi['gene_name']}: Sequence too short ({len(roi['roi_sequence'])} bp)")
                continue
            
            if len(roi['roi_sequence']) > 500:
                roi_warnings.append(f"ROI {roi['gene_name']}: Very long sequence ({len(roi['roi_sequence'])} bp)")
            
            # Check for duplicate gene names with same locus
            duplicate_key = f"{roi['gene_name']}_{roi.get('roi_locus', '')}"
            existing_keys = [f"{r['gene_name']}_{r.get('roi_locus', '')}" for r in valid_rois]
            if duplicate_key in existing_keys:
                roi_warnings.append(f"ROI {roi['gene_name']}: Duplicate gene name and locus found")
            
            # Add validation warnings from sequence validation
            if roi.get('warnings'):
                for warning in roi['warnings']:
                    roi_warnings.append(f"ROI {roi['gene_name']}: {warning}")
            
            # If no critical errors, add to valid list
            if not any('Missing or empty' in w or 'too short' in w for w in roi_warnings):
                valid_rois.append(roi)
            
            warnings.extend(roi_warnings)
        
        return valid_rois, warnings
    
    @staticmethod
    def validate_job_batch(jobs: List[Dict], max_jobs: int = 30) -> Tuple[List[Dict], List[str]]:
        """Validate a batch of jobs before submission
        
        Args:
            jobs (List[Dict]): List of job dictionaries
            max_jobs (int): Maximum number of jobs allowed
            
        Returns:
            Tuple[List[Dict], List[str]]: (valid_jobs, validation_warnings)
        """
        warnings = []
        
        # Check job count
        if len(jobs) > max_jobs:
            warnings.append(f"Job count ({len(jobs)}) exceeds maximum allowed ({max_jobs})")
            jobs = jobs[:max_jobs]
            warnings.append(f"Truncated to first {max_jobs} jobs")
        
        # Check for duplicate job names
        job_names = [job['job_name'] for job in jobs]
        duplicate_names = set([name for name in job_names if job_names.count(name) > 1])
        if duplicate_names:
            warnings.append(f"Duplicate job names found: {duplicate_names}")
        
        # Estimate total processing time
        total_complexity_score = sum([
            1 if job['estimated_complexity'] == 'Low' else 
            2 if job['estimated_complexity'] == 'Medium' else 3 
            for job in jobs
        ])
        
        estimated_hours = total_complexity_score * 0.5  # Rough estimate: 0.5 hours per complexity point
        if estimated_hours > 24:
            warnings.append(f"Estimated processing time: {estimated_hours:.1f} hours - consider splitting into multiple batches")
        
        return jobs, warnings


class DataExporter:
    """Class for exporting protein and ROI data analysis"""
    
    @staticmethod
    def export_protein_summary(proteins: List[Dict], output_path: str):
        """Export protein data summary to Excel
        
        Args:
            proteins (List[Dict]): List of protein dictionaries
            output_path (str): Path to save Excel file
        """
        try:
            import pandas as pd
            
            # Prepare data for export
            export_data = []
            for protein in proteins:
                export_data.append({
                    'Protein Name': protein['name'],
                    'Sequence Length (AA)': protein['length'],
                    'Valid Sequence': protein.get('is_valid', True),
                    'Warnings': '; '.join(protein.get('warnings', [])) if protein.get('warnings') else 'None',
                    'Row Index': protein.get('row_index', 'Unknown')
                })
            
            df = pd.DataFrame(export_data)
            df.to_excel(output_path, index=False, sheet_name='Protein Summary')
            
        except Exception as e:
            raise Exception(f"Error exporting protein summary: {str(e)}")
    
    @staticmethod
    def export_roi_summary(roi_data: List[Dict], output_path: str):
        """Export ROI data summary to Excel
        
        Args:
            roi_data (List[Dict]): List of ROI dictionaries
            output_path (str): Path to save Excel file
        """
        try:
            import pandas as pd
            
            # Prepare data for export
            export_data = []
            for roi in roi_data:
                export_data.append({
                    'Gene Name': roi['gene_name'],
                    'ROI Locus': roi['roi_locus'],
                    'Sequence Length (bp)': len(roi['roi_sequence']),
                    'GC Content (%)': roi.get('gc_content', 'Unknown'),
                    'Accession': roi['accession'],
                    'Species': roi['species'],
                    'Status': roi['status'],
                    'Valid Sequence': roi.get('is_valid', True),
                    'Warnings': '; '.join(roi.get('warnings', [])) if roi.get('warnings') else 'None',
                    'Row Index': roi.get('row_index', 'Unknown')
                })
            
            df = pd.DataFrame(export_data)
            df.to_excel(output_path, index=False, sheet_name='ROI Summary')
            
        except Exception as e:
            raise Exception(f"Error exporting ROI summary: {str(e)}")
    
    @staticmethod
    def export_job_plan(jobs: List[Dict], output_path: str):
        """Export job execution plan to Excel
        
        Args:
            jobs (List[Dict]): List of job dictionaries
            output_path (str): Path to save Excel file
        """
        try:
            import pandas as pd
            
            # Prepare data for export
            export_data = []
            for i, job in enumerate(jobs, 1):
                export_data.append({
                    'Job Number': i,
                    'Job Name': job['job_name'],
                    'Protein Name': job['protein_name'],
                    'Protein Length (AA)': job['protein_length'],
                    'Gene Name': job['gene_name'],
                    'ROI Locus': job['roi_locus'],
                    'DNA Length (bp)': len(job['dna_sequence']),
                    'Estimated Complexity': job['estimated_complexity'],
                    'Accession': job['accession'],
                    'Species': job['species']
                })
            
            df = pd.DataFrame(export_data)
            
            # Create summary statistics
            summary_data = {
                'Metric': [
                    'Total Jobs',
                    'Low Complexity Jobs',
                    'Medium Complexity Jobs', 
                    'High Complexity Jobs',
                    'Average Protein Length',
                    'Average DNA Length',
                    'Unique Proteins',
                    'Unique Genes'
                ],
                'Value': [
                    len(jobs),
                    len([j for j in jobs if j['estimated_complexity'] == 'Low']),
                    len([j for j in jobs if j['estimated_complexity'] == 'Medium']),
                    len([j for j in jobs if j['estimated_complexity'] == 'High']),
                    round(sum([j['protein_length'] for j in jobs]) / len(jobs), 1) if jobs else 0,
                    round(sum([len(j['dna_sequence']) for j in jobs]) / len(jobs), 1) if jobs else 0,
                    len(set([j['protein_name'] for j in jobs])),
                    len(set([j['gene_name'] for j in jobs]))
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            
            # Write to Excel with multiple sheets
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Job Plan', index=False)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
        except Exception as e:
            raise Exception(f"Error exporting job plan: {str(e)}")


# Helper functions for integration with existing code
def load_and_validate_protein_data(excel_path: str, name_col: int = 0, seq_col: int = 1) -> Tuple[List[Dict], List[str]]:
    """Load and validate protein data from Excel file
    
    Args:
        excel_path (str): Path to protein Excel file
        name_col (int): Column index for protein names
        seq_col (int): Column index for protein sequences
        
    Returns:
        Tuple[List[Dict], List[str]]: (valid_proteins, warnings)
    """
    # Load protein data
    proteins = ProteinDataLoader.load_protein_excel(excel_path, name_col, seq_col)
    
    # Validate protein data
    valid_proteins, warnings = DataValidator.validate_protein_data(proteins)
    
    return valid_proteins, warnings


def load_and_validate_roi_data(excel_path: str, sheet_name: str = 'ROI_Analysis') -> Tuple[List[Dict], List[str]]:
    """Load and validate ROI data from Excel file
    
    Args:
        excel_path (str): Path to ROI Excel file
        sheet_name (str): Sheet name containing ROI data
        
    Returns:
        Tuple[List[Dict], List[str]]: (valid_rois, warnings)
    """
    # Load ROI data
    roi_data = ROIDataLoader.load_roi_excel(excel_path, sheet_name)
    
    # Validate ROI data
    valid_rois, warnings = DataValidator.validate_roi_data(roi_data)
    
    return valid_rois, warnings


def create_job_batch(proteins: List[Dict], roi_data: List[Dict], 
                    selected_protein_index: int = 0, max_jobs: int = 30) -> Tuple[List[Dict], List[str]]:
    """Create a batch of jobs for a selected protein against all ROI data
    
    Args:
        proteins (List[Dict]): List of protein dictionaries
        roi_data (List[Dict]): List of ROI dictionaries
        selected_protein_index (int): Index of selected protein
        max_jobs (int): Maximum number of jobs to create
        
    Returns:
        Tuple[List[Dict], List[str]]: (job_batch, warnings)
    """
    if selected_protein_index >= len(proteins):
        raise ValueError(f"Selected protein index {selected_protein_index} out of range")
    
    selected_protein = proteins[selected_protein_index]
    
    # Create jobs for selected protein against all ROI data
    jobs = []
    for roi in roi_data:
        job = JobPairGenerator.create_job_pair(selected_protein, roi)
        jobs.append(job)
    
    # Validate job batch
    valid_jobs, warnings = DataValidator.validate_job_batch(jobs, max_jobs)
    
    return valid_jobs, warnings