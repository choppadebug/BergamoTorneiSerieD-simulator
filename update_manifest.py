"""Refresh the historical CSV list served by the static website."""
import json
from pathlib import Path

if __name__ == '__main__':
    directory = Path(__file__).parent / 'input'
    names = sorted(path.name for path in directory.glob('*.csv'))
    (directory / 'manifest.json').write_text(json.dumps(names, indent=2) + '\n', encoding='utf-8')
    print(f'Listed {len(names)} historical CSV files in input/manifest.json')
