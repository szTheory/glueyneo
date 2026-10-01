"""Identify exact context-only pairs in the historical core C patch."""
import difflib
import json
from pathlib import Path
import re

root=Path(__file__).resolve().parent
patch=(root/'stage-0'/'transition.patch').read_text()
part=next(p for p in patch.split('diff --git ')[1:] if p.splitlines()[0].endswith('/m68kcpu.c'))
def normalize(s):
    s=re.sub(r'\(m68ki_context \*ctx,?\s*','(',s)
    s=re.sub(r'\(m68ki_context \*,?\s*','(',s)
    s=re.sub(r'\(ctx,?\s*','(',s)
    s=s.replace('(void)', '()')
    return re.sub(r'\s+','',s)

matched=[]
residual=[]
for hunk in re.split(r'(?m)^@@ ',part)[1:]:
    header,*lines=hunk.splitlines()
    m=re.match(r'-(\d+)(?:,\d+)? \+(\d+)',header)
    a,b=map(int,m.groups())
    old=[]
    new=[]
    for line in lines:
        if line.startswith('-'):
            old.append({'line':a,'text':line[1:]}); a+=1
        elif line.startswith('+'):
            new.append({'line':b,'text':line[1:]}); b+=1
        elif line.startswith(' '): a+=1; b+=1
    for tag,i,j,k,l in difflib.SequenceMatcher(None,[normalize(s['text']) for s in old],[normalize(s['text']) for s in new],autojunk=False).get_opcodes():
        if tag=='equal':
            matched.extend({'pristine':o,'adapted':n} for o,n in zip(old[i:j],new[k:l]))
        else:
            residual.extend({'operation':'delete',**s} for s in old[i:j])
            residual.extend({'operation':'add',**s} for s in new[k:l])
assert len(matched)*2+len(residual)==188
report={'file':'third_party/musashi/m68kcpu.c','historical_stage':0,'total_added_deleted':188,'context_only_pairs':len(matched),'context_only_added_deleted':len(matched)*2,'conservative_semantic_charge':len(residual),'pairs':matched,'charged_residual':residual,'rationale':'Excluded pairs differ only in first explicit context parameters/arguments, void-to-context signatures, or whitespace. All remaining lines stay charged, including imports, removed singleton storage, callback data elimination, initialization change and instruction counter. Handwritten and helper totals remain unchanged.','revised_attempt1_semantic_upper_bound':471-188+len(residual)}
(root/'core-semantic-refinement.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('pairs','charged_residual')}))
