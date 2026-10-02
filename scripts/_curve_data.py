import json

d = json.load(open('run 7/ablation_selection.json', encoding='utf-8'))
rows = d['rows']
by = {(round(r['keep_ratio'], 2), r['select_mode']): r for r in rows}

def p(kr, mode):
    r = by.get((kr, mode))
    return None if r is None else round(r['word_recall_pct'], 2)

print('tokens per keep_ratio:')
for kr in (1.00, 0.75, 0.50, 0.35):
    key = (kr, 'router' if kr == 1.0 else 'random')
    r = by.get(key)
    print(' ', kr, r['visual_tokens'])

print('strat_negated:', [(kr, p(kr, 'stratified_negated')) for kr in (1.00, 0.75, 0.50, 0.35)])
print('random      :', [(kr, p(kr, 'random')) for kr in (1.00, 0.75, 0.50, 0.35)])
print('ink oracle  :', [(kr, p(kr, 'ink')) for kr in (1.00, 0.75, 0.50, 0.35)])
print('router(fwd) :', [(kr, p(kr, 'router')) for kr in (1.00, 0.75, 0.50, 0.35)])
print('strat(fwd)  :', [(kr, p(kr, 'stratified')) for kr in (1.00, 0.75, 0.50, 0.35)])

# tokens
toks = {kr: by[(kr, 'router' if kr == 1.0 else 'random')]['visual_tokens'] for kr in (1.00, 0.75, 0.50, 0.35)}
print('toks', toks)
