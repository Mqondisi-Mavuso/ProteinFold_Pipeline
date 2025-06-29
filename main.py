"""
Main entry point for the NCBI Sequence Retriever & AlphaFold Submitter application
"""
import sys
from PyQt6.QtWidgets import QApplication
from ncbi_alphafold_gui_r import MainWindow

def main():
    """Main function to start the application"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
