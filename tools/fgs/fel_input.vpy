import json
from pathlib import Path
from fel_reconstruct import create_graph

# vspipe --arg manifest=/absolute/path/reconstruct.json --container y4m ...
create_graph(json.loads(Path(manifest).read_text())).set_output()
