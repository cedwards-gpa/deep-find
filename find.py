# Save this as run_analysis.py
from jesus import DependencyAnalyzer
import json

# Initialize analyzer
analyzer = DependencyAnalyzer(
    base_path=r"C:\Users\cedwards\Documents\Funner\Elev8",
    connection_string="DRIVER={SQL Server};"
                     "SERVER=localhost;"
                     "DATABASE=MES;"
                     "UID=sa;"
                     "PWD=GPAsvr230"
)

# Load existing SP data (if you have it)
analyzer.load_existing_sp_data('dependency_report.json')

# Load and analyze files
with open('structure.json', 'r') as f:
    structure = json.load(f)

for file_info in structure['s']:
    if file_info['f'].endswith('.py'):
        analyzer.analyze_file(file_info['p'])

# Analyze database
analyzer.analyze_database()

# Generate reports
analyzer.generate_tree_report('dependency_tree.json')

# Create text visualization
with open('dependency_tree.txt', 'w', encoding='utf-8') as f:
    analyzer.print_tree(f)

print("Analysis complete! Check dependency_tree.txt and dependency_tree.json")