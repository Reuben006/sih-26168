"""Download verified IO-VNBD smartphone data using the committed inventory."""
import argparse,concurrent.futures,hashlib,json,shutil,urllib.parse,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--scope',choices=['expanded','all'],default='expanded')
 args=parser.parse_args()
 manifest=ROOT/'reports'/('expanded_split.json' if args.scope=='expanded' else 'repository_smartphone_inventory.json')
 entries=json.loads(manifest.read_text())['recordings']
 folder=ROOT/'app/datasets'/('expanded' if args.scope=='expanded' else 'repository-smartphone');folder.mkdir(parents=True,exist_ok=True)
 def download(entry):
  dst=folder/(entry['name'] if args.scope=='expanded' else entry['sha256']+'.csv')
  if dst.exists() and hashlib.sha256(dst.read_bytes()).hexdigest()==entry['sha256']:return dst
  url='https://media.githubusercontent.com/media/onyekpeu/IO-VNBD/master/'+urllib.parse.quote(entry['path'])
  with urllib.request.urlopen(url,timeout=120) as response:data=response.read()
  if len(data)!=entry['bytes'] or hashlib.sha256(data).hexdigest()!=entry['sha256']:raise ValueError('Checksum mismatch: '+entry['path'])
  temporary=dst.with_suffix('.part');temporary.write_bytes(data);temporary.replace(dst);return dst
 unique={e['sha256']:e for e in entries}
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  for i,path in enumerate(pool.map(download,unique.values()),1):print(f'{i}/{len(unique)} verified {path.name}',flush=True)
 if args.scope=='expanded':
  for name in ['S-M.csv','S-S1.csv','S-Vw4.csv','S-Vw1.csv']:
   destination=ROOT/'app/datasets'/name
   if not destination.exists():shutil.copyfile(folder/name,destination)
if __name__=='__main__':main()
