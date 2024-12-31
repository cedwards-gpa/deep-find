import os
import json
from pathlib import Path

class ScriptFinder:
    def __init__(self):
        self.target_extensions = {'.py', '.python', '.js', '.jsx'}

    def find_scripts(self, path):
        """Find Python and JavaScript files and return minimal info"""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")
        
        scripts = []
        
        for root, _, files in os.walk(path):
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() in self.target_extensions:
                    scripts.append({
                        'f': file,  # filename
                        'p': str(file_path.relative_to(path))  # relative path
                    })
        
        return sorted(scripts, key=lambda x: x['p'])

    def generate_json(self, path, output_file=None):
        """Generate minimal JSON output"""
        try:
            result = {
                'b': str(Path(path).absolute()),  # base path
                's': self.find_scripts(path)  # scripts
            }
            
            json_str = json.dumps(result, separators=(',', ':'))
            
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(json_str)
            
            return json_str
            
        except Exception as e:
            print(f"Error: {str(e)}")
            return None

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Find scripts')
    parser.add_argument('path', help='Directory to search')
    parser.add_argument('-o', '--output', help='Output file')
    
    args = parser.parse_args()
    
    finder = ScriptFinder()
    json_output = finder.generate_json(args.path, args.output)
    
    if json_output and not args.output:
        print(json_output)