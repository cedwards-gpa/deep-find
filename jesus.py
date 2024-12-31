import re
import json
import pyodbc
from pathlib import Path
from collections import defaultdict
import os

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

class DependencyAnalyzer:
    def __init__(self, base_path, connection_string):
        self.base_path = Path(base_path)
        self.conn_str = connection_string
        self.dependencies = {
            'stored_procedures': set(),
            'functions': {},
            'sp_to_tables': {},
            'function_to_sp': {}
        }

    def _analyze_function_content(self, content):
        """Analyze function content for stored procedure calls"""
        sp_patterns = [
            # Original stp patterns
            r'system\.db\.runStoredProcedure\(["\'](?:stp\.|stp_)(\w+)',
            r'system\.db\.runPrepStmt\(["\']EXEC\s+(?:stp\.|stp_)(\w+)',
            r'system\.db\.runQuery\(["\']EXEC\s+(?:stp\.|stp_)(\w+)',
            r'EXEC\s+(?:stp\.|stp_)(\w+)',
            r'["\'](?:stp\.|stp_)(\w+)["\']',
            
            # createSProcCall pattern
            r'system\.db\.createSProcCall\(["\'](?:[\w.]+\.)?(\w+)',  # Will match oee.stp_getGroupOEE_AQP
            
            # Mes module patterns
            r'mes\.[\w.]+\.sp\.(\w+)\(',  # matches mes.oee.sp.getPeriodAllLinesOEE_AQP
            r'mes\.[\w.]+\.stp\.(\w+)\(',  # variation with stp
            r'mes\.[\w.]+\.sproc\.(\w+)\(',  # variation with sproc
            
            # Direct sp/stp calls
            r'sp\.(\w+)\(',
            r'stp\.(\w+)\(',
            r'sproc\.(\w+)\(',
            
            # System db patterns
            r'system\.db\.runProcedure\(["\'](\w+)',
            r'system\.db\.runStoredProcedure\(["\'](\w+)',
            
            # Additional Ignition patterns
            r'\.callProcedure\(["\'](\w+)',
            r'\.storedProcedure\(["\'](\w+)'
        ]
        
        found_sps = set()
        for pattern in sp_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                sp_name = match.group(1)
                # Handle cases where the schema (e.g., 'oee.') is part of the name
                if '.' in sp_name:
                    sp_name = sp_name.split('.')[-1]
                
                # If it doesn't start with stp_ and isn't a fully qualified name, add the prefix
                if not sp_name.startswith(('stp_', 'stp.')):
                    sp_name = f"stp_{sp_name}"
                    
                found_sps.add(sp_name)
        
        return list(found_sps)

    def _extract_functions_with_content(self, file_content):
        """Extract both function names and their content"""
        functions = {}
        current_function = None
        current_content = []
        indent_level = 0
        
        lines = file_content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Check for function definition
            if stripped.startswith('def '):
                # If we were tracking a previous function, save it
                if current_function:
                    functions[current_function] = '\n'.join(current_content)
                
                # Start new function
                func_match = re.match(r'\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)', line)
                if func_match:
                    current_function = func_match.group(1)
                    current_content = [line]
                    indent_level = len(line) - len(line.lstrip())
                    
                    # Include docstring if present
                    i += 1
                    while i < len(lines) and (not lines[i].strip() or lines[i].lstrip().startswith('"""')):
                        current_content.append(lines[i])
                        if lines[i].lstrip().startswith('"""'):
                            # Skip until end of docstring
                            if not lines[i].strip().endswith('"""'):
                                i += 1
                                while i < len(lines) and '"""' not in lines[i]:
                                    current_content.append(lines[i])
                                    i += 1
                                if i < len(lines):
                                    current_content.append(lines[i])
                        i += 1
                    i -= 1  # Adjust for outer loop increment
                    
            # Add content to current function
            elif current_function and line:
                line_indent = len(line) - len(line.lstrip())
                if not stripped or line_indent > indent_level:
                    current_content.append(line)
                else:
                    # End of function reached
                    functions[current_function] = '\n'.join(current_content)
                    current_function = None
                    current_content = []
            
            i += 1
        
        # Save last function if exists
        if current_function:
            functions[current_function] = '\n'.join(current_content)
        
        return functions

    def analyze_file(self, file_path):
        """Analyze a single Python file for functions and SP references"""
        full_path = self.base_path / file_path
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract functions and their content
            functions = self._extract_functions_with_content(content)
            if functions:
                self.dependencies['functions'][file_path] = functions
            
            # Find SP references in each function
            for func_name, func_content in functions.items():
                stored_procs = self._analyze_function_content(func_content)
                if stored_procs:
                    if file_path not in self.dependencies['function_to_sp']:
                        self.dependencies['function_to_sp'][file_path] = {}
                    self.dependencies['function_to_sp'][file_path][func_name] = stored_procs
                    self.dependencies['stored_procedures'].update(stored_procs)
        
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")

    def analyze_database(self):
        """Connect to SQL Server and analyze stored procedures"""
        try:
            with pyodbc.connect(self.conn_str) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        OBJECT_NAME(object_id) as proc_name,
                        OBJECT_DEFINITION(object_id) as proc_definition
                    FROM sys.procedures
                    WHERE OBJECT_NAME(object_id) LIKE 'stp[_.]%'
                """)
                
                for row in cursor.fetchall():
                    proc_name = row.proc_name
                    proc_def = row.proc_definition
                    
                    self.dependencies['stored_procedures'].add(proc_name)
                    tables = self._find_table_references(proc_def)
                    if tables:
                        self.dependencies['sp_to_tables'][proc_name] = list(tables)
        
        except Exception as e:
            print(f"Database connection error: {str(e)}")

    def _find_table_references(self, sql_text):
        """Extract table references from SQL text"""
        tables = set()
        
        # Pattern for direct table references (excluding temp tables)
        permanent_table_patterns = [
            r'FROM\s+([^\s\(\)#]+)',  # FROM clause
            r'JOIN\s+([^\s\(\)#]+)',  # JOIN clause
            r'INTO\s+([^\s\(\)#]+(?<!#))',  # INTO clause (not ending in #)
            r'UPDATE\s+([^\s\(\)#]+)',  # UPDATE clause
            r'INSERT\s+INTO\s+([^\s\(\)#]+)'  # INSERT INTO clause
        ]
        
        # Exclude list for common false positives
        exclude_list = {
            'dbo', 'INTO', 'FROM', 'JOIN', 'UPDATE', 'INSERT',
            'WHERE', 'AND', 'OR', 'NULL', 'NOT', 'AS', 'ON',
            'WITH', 'THE', 'A', 'AN', 'IS', 'IN'
        }
        
        # Find permanent tables
        for pattern in permanent_table_patterns:
            matches = re.finditer(pattern, sql_text, re.IGNORECASE)
            for match in matches:
                table_ref = match.group(1).strip()
                # Handle schema.table format
                if '.' in table_ref:
                    parts = table_ref.split('.')
                    table_name = parts[-1]  # Get the last part after schema
                    if table_name.lower() not in exclude_list:
                        tables.add(table_name)
                else:
                    if table_ref.lower() not in exclude_list:
                        tables.add(table_ref)
        
        # Find temporary tables (preserving the # prefix)
        temp_pattern = r'(#\w+)'
        for create_pattern in [
            r'CREATE\s+TABLE\s+(#\w+)',  # CREATE TABLE
            r'INTO\s+(#\w+)',            # INTO
            r'FROM\s+(#\w+)',            # FROM
            r'JOIN\s+(#\w+)',            # JOIN
            r'UPDATE\s+(#\w+)',          # UPDATE
            r'INSERT\s+INTO\s+(#\w+)'    # INSERT INTO
        ]:
            matches = re.finditer(create_pattern, sql_text, re.IGNORECASE)
            for match in matches:
                temp_table = match.group(1)
                tables.add(temp_table)  # Add with # prefix
        
        return sorted(tables)  # Sort for consistent output


    def load_existing_sp_data(self, filename):
        """Load existing stored procedure data from file"""
        try:
            with open(filename, 'r') as f:
                existing_deps = json.load(f)
                
            sp_to_tables = {
                k if k.startswith(('stp.', 'stp_')) else f"stp_{k}": v 
                for k, v in existing_deps.get('sp_to_tables', {}).items()
            }
            self.dependencies['sp_to_tables'].update(sp_to_tables)
        except Exception as e:
            print(f"Error loading existing SP data: {str(e)}")

    def generate_tree_report(self, output_file=None):
        """Generate a hierarchical tree report of dependencies"""
        tree = {}
        
        for file_path, functions in self.dependencies['functions'].items():
            file_node = {
                'type': 'file',
                'functions': {}
            }
            
            for func_name, func_content in functions.items():
                function_node = {
                    'type': 'function',
                    'stored_procedures': {}
                }
                
                if (file_path in self.dependencies['function_to_sp'] and 
                    func_name in self.dependencies['function_to_sp'][file_path]):
                    
                    for sp_name in self.dependencies['function_to_sp'][file_path][func_name]:
                        sp_node = {
                            'type': 'stored_procedure',
                            'tables': sorted(self.dependencies['sp_to_tables'].get(sp_name, []))  # Sort tables
                        }
                        function_node['stored_procedures'][sp_name] = sp_node
                
                file_node['functions'][func_name] = function_node
            
            tree[file_path] = file_node
        
        report = {
            'type': 'dependency_tree',
            'files': tree
        }
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2)
        
        return report

    def print_tree(self, output_file=None):
        """Print a human-readable tree visualization"""
        tree = self.generate_tree_report()
        output_lines = []
        
        def write_line(line):
            if output_file:
                print(line, file=output_file)
            output_lines.append(line)
        
        write_line("Dependency Tree:")
        write_line("================")
        
        for file_path, file_data in tree['files'].items():
            write_line(f"\n📄 {file_path}")
            
            for func_name, func_data in file_data['functions'].items():
                write_line(f"  ├─📊 Function: {func_name}")
                
                if func_data['stored_procedures']:
                    for sp_name, sp_data in func_data['stored_procedures'].items():
                        write_line(f"  │  ├─💾 SP: {sp_name}")
                        
                        if sp_data['tables']:
                            for i, table in enumerate(sp_data['tables'], 1):
                                is_last = i == len(sp_data['tables'])
                                prefix = "  │  │  └─" if is_last else "  │  │  ├─"
                                # Keep # prefix for temp tables in output
                                write_line(f"{prefix}🗃️ Table: {table}")
                        else:
                            write_line("  │  │  └─(No tables found)")
                else:
                    write_line("  │  └─(No stored procedures found)")
        
        return "\n".join(output_lines)