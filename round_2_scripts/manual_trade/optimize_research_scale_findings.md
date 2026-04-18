# Findings from Manual Trade Scripts

## 1. Baseline optimization

Command:

```bash
py optimize_research_scale.py
```

Best result (both max-speed and min-speed objective runs produced the same allocation):

- Research: 23%
- Scale: 77%
- PnL at max speed: 618096
- PnL at min speed: 24232

Conclusion:

- If speed allocation is 0%, the best split between research and scale is 23% / 77%.

## 2. Sweep over total (Research + Scale) allocation

Command:

```bash
py list_research_scale.py
```

Selected points from the output:

- Total alloc 0%: best = 0% R, 0% Sc, min speed PnL = 0, max speed PnL = 0
- Total alloc 1%: best = 0% R, 0% Sc, min speed PnL = 0, max speed PnL = 0
- ...
- Total alloc 30%: best = 9% R 21% Sc, PnL at min Sp = -331, PnL at max Sp = 117014
- Total alloc 31%: best = 9% R, 22% Sc, min speed PnL = -133, max speed PnL = 122801
- Total alloc 32%: best = 9% R, 23% Sc, min speed PnL = 65, max speed PnL = 128587
- Total alloc 33%: best = 9% R, 24% Sc, min speed PnL = 263, max speed PnL = 134374
- ...
- Total alloc 99%: best = 23% R, 76% Sc, min speed PnL = 23768, max speed PnL = 609920
- Total alloc 100%: best = 23% R, 77% Sc, min speed PnL = 24232, max speed PnL = 618096

Observed trend:

- Increasing total allocation to research+scale improves PnL in this model.
- Results suggest little value in allocating more than about 68% to speed under these assumptions.

## 3. Worst-case variant

Assumption:

- Spend all remaining budget and still receive min speed.

```bash
py list_research_scale_worst_case.py
```

Selected points:

- Total alloc 32%: best = 9% R, 23% Sc, min speed PnL = -33934
- Total alloc 33%: best = 9% R, 24% Sc, min speed PnL = -33236
- ...
- Total alloc 72%: best = 18% R, 54% Sc, min speed PnL = -1767
- Total alloc 73%: best = 18% R, 55% Sc, min speed PnL = -874
- Total alloc 74%: best = 18% R, 56% Sc, min speed PnL = 19
- Total alloc 75%: best = 18% R, 57% Sc, min speed PnL = 912
- Total alloc 99%: best = 23% R, 76% Sc, min speed PnL = 23268
- Total alloc 100%: best = 23% R, 77% Sc, min speed PnL = 24232

Conclusion:

- If speed spend exceeds about 26% (so research+scale is below about 74%), min-speed PnL can become negative.
- This does not prove speed spend is always bad, because speed spend can improve rank and therefore increase speed multiplier.

## 4. Game Theory Analysis

```bash
> python pnl.py 85 0.9
Best R alloc = 5%, best Sc alloc = 10%, PnL = -1082
```
```bash
> python pnl.py 84 0.9
Best R alloc = 5%, best Sc alloc = 11%, PnL = 3809
```


- It can be seen that anything above 85% allocation on speed results in negative gain, the only reason for doing this would be to sabotage other teams, it can be assumed that a small amount of teams would be doing this.
- It can be assumed that many teams would try and get a guaranteed profit by investing very little on speed.

Conclusion:
- Based on this analysis, there is likely more teams who place below 50% than above 50%, some teams would also use this strategy and try to invest 51% to beat the rest.
- Therefore I will invest 52% on speed.

## 4. Solution
```bash
> python pnl.py 52 0.5
Best R alloc = 13%, best Sc alloc = 35%, PnL = 90097
```