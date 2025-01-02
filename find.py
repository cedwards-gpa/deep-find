from jesus import DependencyAnalyzer, ScriptFinder
from dotenv import load_dotenv
import json
import os

load_dotenv()

finder = ScriptFinder()
json_str = finder.generate_json(os.getenv('BASE_PATH'), "structure.json")

analyzer = DependencyAnalyzer(
    base_path=os.getenv('BASE_PATH'),
    connection_string = (
    f"DRIVER={{{os.getenv('DB_DRIVER')}}};"
    f"SERVER={os.getenv('DB_SERVER')};"
    f"DATABASE={os.getenv('DB_NAME')};"
    f"UID={os.getenv('DB_USER')};"
    f"PWD={os.getenv('DB_PASSWORD')}"
)
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

print('Done!')