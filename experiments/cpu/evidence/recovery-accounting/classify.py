from pathlib import Path
import re
import difflib

root=Path(__file__).resolve().parent
for stage in range(4):
    patch=(root/f'stage-{stage}'/'transition.patch').read_text()
    for part in patch.split('diff --git ')[1:]:
        name=part.splitlines()[0].split('/')[-1]
        if name not in ('m68kcpu.h','m68k_in.c','m68k.h','m68kmake.c'): continue
        residual=[]
        for hunk in part.split('@@')[2::2]:
            old=[s[1:] for s in hunk.splitlines() if s.startswith('-')]
            new=[s[1:] for s in hunk.splitlines() if s.startswith('+')]
            def normalize(s):
                s=re.sub(r'\(m68ki_context \*ctx,?\s*','(',s)
                s=re.sub(r'\(m68ki_context \*,?\s*','(',s)
                s=re.sub(r'\(ctx,?\s*','(',s)
                s=s.replace('(void)', '()')
                return re.sub(r'\s+','',s)
            a,b=list(map(normalize,old)),list(map(normalize,new))
            for tag,i,j,k,l in difflib.SequenceMatcher(None,a,b,autojunk=False).get_opcodes():
                if tag!='equal': residual.extend('-'+s for s in old[i:j]); residual.extend('+'+s for s in new[k:l])
        print('STAGE',stage,name,'RESIDUAL',len(residual))
        print('\n'.join(residual))
