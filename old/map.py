from map_functions import ScriptFinder

finder=ScriptFinder()

# Generate and save JSON
json_str = finder.generate_json(r"C:\Users\cedwards\Documents\Funner\Elev8", output_file="structure.json")

# Or just get the JSON string
#json_str = mapper.generate_json(r"C:\your\path\here")