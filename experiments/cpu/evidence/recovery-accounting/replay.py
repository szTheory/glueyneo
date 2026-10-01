"""Replay historical edits offline using preserved recipes and Git evidence."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

evidence = Path(__file__).resolve().parent
repo = Path(sys.argv[1]).resolve()
history = json.loads((evidence/'history.json').read_text())
receipt = json.loads((repo/'experiments/cpu/evidence/attempt-1/receipt.json').read_text())

def git(*args, cwd=repo):
    return subprocess.check_output(['git', *args], cwd=cwd)

def churn(a, b):
    result=subprocess.run(['git','diff','--no-index','--numstat',str(a),str(b)],capture_output=True,text=True)
    assert result.returncode in (0,1),result.stderr
    return sum(map(int,result.stdout.split()[:2])) if result.stdout else 0

with tempfile.TemporaryDirectory(prefix='cpu-history-') as temp:
    scratch=Path(temp)
    pristine=scratch/'pristine'
    pristine.mkdir()
    for row in receipt['inputs']:
        name=Path(row['file']).name
        (pristine/name).write_bytes(git('show',history['halted_commit']+':'+row['file']))
    # The admitted historical diff restores exact pristine bytes without download.
    result=subprocess.run(['git','apply','--reverse',str(repo/'experiments/cpu/evidence/attempt-1/source.patch')],cwd=pristine,capture_output=True)
    assert result.returncode==0,result.stderr.decode()
    for row in receipt['inputs']:
        assert hashlib.sha256((pristine/Path(row['file']).name).read_bytes()).hexdigest()==row['pristine_sha256']
    previous=pristine
    upstream=recipe_total=0
    for row in history['stages']:
        number=row['stage']
        source=evidence/f'stage-{number}'
        target=scratch/f'stage-{number}'
        result=subprocess.run([sys.executable,str(source/'adapt.py'),str(pristine),str(target)],capture_output=True)
        assert result.returncode==0,result.stderr.decode()
        for name,count in row['input_churn'].items():
            assert churn(previous/name,target/name)==count
            assert hashlib.sha256((target/name).read_bytes()).hexdigest()==history['source_identities'][f'stage-{number}/{name}']
        assert hashlib.sha256((source/'adapt.py').read_bytes()).hexdigest()==history['source_identities'][f'stage-{number}/adapt.py']
        actual_recipe=len((source/'adapt.py').read_text().splitlines()) if number==0 else churn(evidence/f'stage-{number-1}'/'adapt.py',source/'adapt.py')
        assert actual_recipe==row['recipe_churn']
        upstream+=sum(row['input_churn'].values())
        recipe_total+=actual_recipe
        previous=target
    for row in receipt['inputs']:
        assert hashlib.sha256((previous/Path(row['file']).name).read_bytes()).hexdigest()==row['adapted_sha256']
    assert upstream==history['upstream_cumulative']==1771
    assert recipe_total==history['support']['recipe_cumulative']==110
    assert sum(history['support'].values())==history['helper_cumulative_conservative']==302
    assert upstream+sum(history['support'].values())==history['handwritten_cumulative_conservative']==2073
    assert sum(history['semantic_charges'].values())==history['semantic_upper_bound']==471
print(json.dumps({'status':'pass','upstream':upstream,'helpers':302,'total':2073,'semantic_upper_bound':471,'all_four_source_stages_replayed':True}))
