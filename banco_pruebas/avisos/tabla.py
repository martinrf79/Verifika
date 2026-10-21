import json,sys
def tab(v):
    d={}
    for l in open(f'corridas_{v}.jsonl'):
        x=json.loads(l)
        if x['rep']==0: d[(x['charla'],x['turno'],x['forma'])]=x['bien']
    return d
b={}
for l in open('/home/user/Verifika/banco_pruebas/traduccion58_corridas.jsonl'):
    r=json.loads(l)
    if r.get('modelo','gemini')=='gemini' and r['rep']==0: b[(r['charla'],r['turno'],r['forma'])]=r['bien']
vs={v:tab(v) for v in sys.argv[1:]}
ks=sorted(vs[sys.argv[1]])
print('forma      prod '+' '.join(f'{v:>4}' for v in vs))
for fo in ('original','whatsapp','coloquial','TOTAL'):
    kk=[k for k in ks if fo=='TOTAL' or k[2]==fo]
    print(f'{fo:10} {sum(b[k] for k in kk):4} '+' '.join(f'{sum(vs[v].get(k,False) for k in kk):4}' for v in vs), 'de', len(kk))
if '--turnos' in sys.argv[0:]: pass
print('\nturno     prod '+' '.join(f'{v:>4}' for v in vs))
for t in sorted({(k[0],k[1]) for k in ks}):
    kk=[k for k in ks if (k[0],k[1])==t]
    print(f'{t[0]} T{t[1]:<3} {sum(b[k] for k in kk):4} '+' '.join(f'{sum(vs[v].get(k,False) for k in kk):4}' for v in vs))
