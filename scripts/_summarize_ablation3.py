import json

d = json.load(open('run 8/ablation_selection.json', encoding='utf-8'))
m = d['meta']
print('META:', {k: m[k] for k in m})
print()
rows = d['rows']
cols = ['config', 'keep_ratio', 'select_mode', 'visual_tokens', 'retained_ink',
        'mean_min_line_cov', 'word_recall_pct', 'character_accuracy_pct',
        'word_order_pct', 'mean_ned', 'len_ratio_pct', 'valid_json_pct', 'avg_latency_ms']
widths = [30, 5, 10, 5, 6, 7, 7, 7, 7, 6, 6, 5, 7]
print(''.join(str(c).ljust(w) for c, w in zip(cols, widths)))
for r in rows:
    vals = []
    for c, w in zip(cols, widths):
        v = r.get(c)
        if c in ('retained_ink', 'mean_min_line_cov') and v is None:
            s = '-'
        elif c == 'keep_ratio':
            s = f'{v:.2f}'
        elif c in ('word_recall_pct', 'character_accuracy_pct', 'word_order_pct'):
            s = f'{v:.2f}'
        elif c == 'mean_ned':
            s = f'{v:.3f}'
        elif c in ('len_ratio_pct', 'avg_latency_ms', 'valid_json_pct'):
            s = f'{v:.0f}'
        else:
            s = str(v)
        vals.append(str(s).ljust(w))
    print(''.join(vals))
print()
ctrl = rows[0]
print('CONTROL:', ctrl['config'], 'recall', round(ctrl['word_recall_pct'], 2),
      'charAcc', round(ctrl['character_accuracy_pct'], 2),
      'order', round(ctrl['word_order_pct'], 2), 'drift', round(m['control_drift_pts'], 2))
# Compare forward router vs strat_negated at each keep (the sign-fix test)
print('\nSign-fix test (forward router vs strat_negated):')
for kr in (1.00, 0.75, 0.50, 0.35):
    by = {r['select_mode']: r for r in rows if round(r['keep_ratio'], 2) == kr}
    rt = by.get('router')
    sn = by.get('stratified_negated')
    if rt and sn:
        print(f'  keep={kr}: router(forward)={rt["word_recall_pct"]:.2f}  strat_neg={sn["word_recall_pct"]:.2f}  '
              f'router-mincov={rt["mean_min_line_cov"]}  ink={rt["retained_ink"]:.3f}')
