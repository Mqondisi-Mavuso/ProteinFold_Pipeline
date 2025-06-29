from alphafold_crawler import AlphaFoldSubmitter

submitter = AlphaFoldSubmitter()
submitter.setup(
    email="fortunemavuso4@gmail.com", 
    password="",
    job_name="Test Job",
    dna_sequence="ACTG",
    protein_sequence="MSQA"
)

# Test just the login
submitter.init_browser()
success = submitter.login_to_alphafold()
print(f"Login success: {success}")