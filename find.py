from jesus import DependencyAnalyzer, ScriptFinder
import json
import os

finder=ScriptFinder()

# Generate and save JSON
json_str = finder.generate_json(r"C:\Users\cedwards\Documents\Funner\Elev8", output_file="structure.json")


# Initialize analyzer
analyzer = DependencyAnalyzer(
    base_path=r"C:\Users\cedwards\Documents\Funner\Elev8",
    connection_string="DRIVER={SQL Server};SERVER=localhost;DATABASE=MES;UID=sa;PWD=GPAsvr230"
)

# Try database analysis first
analyzer.analyze_database()

# Then load structure and analyze files
with open('structure.json', 'r') as f:
    structure = json.load(f)

for file_info in structure['s']:
    if file_info['f'].endswith('.py'):
        analyzer.analyze_file(file_info['p'])

# Generate outputs
analyzer.generate_tree_report('dependency_tree.json')
with open('dependency_tree.txt', 'w', encoding='utf-8') as f:
    analyzer.print_tree(f)