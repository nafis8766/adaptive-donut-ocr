import json

d = json.load(open('run 7/ablation_selection.json', encoding='utf-8'))
m = d['meta']
print('META:', {k: m[k] for k in m})
print()
rows = d['rows']
cols = ['config', 'keep_ratio', 'select_mode', 'visual_tokens', 'retained_ink',
        'mean_min_line_cov', 'word_recall_pct', 'character_accuracy_pct',
        'word_order_pct', 'mean_ned', 'len_ratio_pct', 'hit_max_length_pct',
        'valid_json_pct', 'avg_latency_ms']
widths = [30, 5, 10, 5, 6, 7, 7, 7, 7, 6, 6, 5, 5, 7]
hdr = ''.join(str(c).ljust(w) for c, w in zip(cols, widths))
print(hdr)
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
        elif c in ('len_ratio_pct', 'avg_latency_ms'):
            s = f'{v:.0f}'
        elif c == 'hit_max_length_pct':
            s = f'{v:.0f}'
        elif c == 'valid_json_pct':
            s = f'{v:.1f}'
        else:
            s = str(v)
        vals.append(str(s).ljust(w))
    print(''.join(vals))
print()
print('n rows:', len(rows))
# control check
ctrl = rows[0]
print('CONTROL row:', ctrl['config'], 'recall', round(ctrl['word_recall_pct'], 2),
      'charAcc', round(ctrl['character_accuracy_pct'], 2),
      'order', round(ctrl['word_order_pct'], 2))
print('control_drift_pts:', m.get('control_drift_pts'))
