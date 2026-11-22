"""Rebuild the published checkpoints from local puzzle inputs and pinned public references."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('data',type=Path,help='Directory containing puzzles.csv')
    ap.add_argument('output',type=Path)
    ap.add_argument('--workers',type=int,default=4)
    ap.add_argument('--own-only',action='store_true',help='Use only programs generated from the puzzle inputs')
    args=ap.parse_args()
    here=Path(__file__).resolve().parent
    data=args.data.resolve()
    out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=True)
    puzzles=data/'puzzles.csv'
    if not puzzles.exists():ap.error(f'Missing {puzzles}')
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    workers=['--workers',str(args.workers)]
    def run(script,*params):
        subprocess.run([sys.executable,str(here/script),*map(str,params)],check=True,env=env)

    exe_suffix='.exe' if os.name=='nt' else ''
    graph_bin=out/('graph_search'+exe_suffix)
    dict_bin=out/('backward'+exe_suffix)
    for source,binary in [('graph_search.cpp',graph_bin),('backward.cpp',dict_bin)]:
        subprocess.run([os.environ.get('CXX','g++'),'-O3','-std=c++17',str(here/source),'-o',str(binary)],check=True)
    def output(name):return out/(name+'.csv')
    def improve(name,inputs,depth,schedule=False):
        flags=['--schedule'] if schedule else []
        run('run.py','improve',puzzles,output(name),'--sources',*inputs,'--cut-depth',str(depth),
            '--binary',graph_bin,*workers,*flags)
    def merge(name,inputs):
        run('run.py','merge',puzzles,output(name),'--sources',*inputs,*workers)

    radix=output('independent')
    dictionary=output('dictionary')
    run('run.py','construct',puzzles,radix,*workers)
    run('dictionary.py',puzzles,dictionary,'--binary',dict_bin,*workers)
    run('dictionary.py',puzzles,output('dict64'),'--binary',dict_bin,'--radix','64','--width','24',*workers)
    run('integer_search.py',puzzles,output('mip-own'),'--sources',dictionary,radix,'--nodes','16',*workers)
    run('integer_search.py',puzzles,output('multi-own'),'--sources',output('dict64'),output('mip-own'),dictionary,radix,'--nodes','16',*workers)
    improve('own-graph',[dictionary,radix],2,True)
    merge('standalone',[output('multi-own'),output('own-graph'),output('mip-own'),output('dict64'),dictionary,radix])
    if args.own_only:return
    run('fetch_references.py',data)
    public=[data/(name+'.csv') for name in ('portfolio','exp','xray','konbu','elias','peephole')]
    improve('graph',[*public,radix],0)
    improve('cut',[output('graph'),*public,radix],3)
    improve('deep',[output('cut'),output('graph'),*public,radix],4)
    improve('recombined',[output('cut'),output('graph'),*public,output('mip-own'),dictionary,radix],3,True)
    improve('fusion',[output('recombined'),output('cut'),*public,output('standalone'),output('dict64')],2,True)
    merge('submission',[output('deep'),output('fusion'),output('recombined'),output('cut'),output('standalone')])
    run('run.py','verify',puzzles,output('submission'))


if __name__=='__main__':
    main()
