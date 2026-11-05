"""Read-only SVG structure/appearance audit; old positional/--compare interface retained."""
import argparse
import json
from logo_core.audit import audit_svg

def inspect(path):
    return audit_svg(path)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('svg');parser.add_argument('--compare')
    args=parser.parse_args();result=inspect(args.svg)
    if args.compare:
        other=inspect(args.compare)
        result['comparison']={'file':other['file'],'same_geometry_signature':result['geometry_signature']==other['geometry_signature'],'same_appearance_signature':result['appearance_signature']==other['appearance_signature'],'other_status':other['status']}
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
