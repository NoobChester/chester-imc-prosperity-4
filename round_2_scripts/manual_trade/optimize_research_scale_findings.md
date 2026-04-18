### **Findings from manual trade scripts**

py optimize_research_scale.py

Best max speed PnL:
research percentage = 23%
scale percentage = 77%
PnL at max speed = 618096
PnL at min speed = 24232

Best min speed PnL:
research percentage = 23%
scale percentage = 77%
PnL at max speed = 618096
PnL at min speed = 24232

We can infer that if we spend 0 on speed, 23 and 77 is the best way to spend on research and scale.

We further expand the previous code:

py list_research_scale.py

Given max = 0%, best alloc = 0% R 0% S, PnL at min speed = 0, PnL at max speed = 0

Given max = 1%, best alloc = 0% R 0% S, PnL at min speed = 0, PnL at max speed = 0

...

Given max = 30%, best alloc = 0% R 0% S, PnL at min speed = 0, PnL at max speed = 0

Given max = 31%, best alloc = 0% R 0% S, PnL at min speed = 0, PnL at max speed = 0

Given max = 32%, best alloc = 9% R 23% S, PnL at min speed = 65, PnL at max speed = 128587

Given max = 33%, best alloc = 9% R 24% S, PnL at min speed = 263, PnL at max speed = 134374

...

Given max = 99%, best alloc = 23% R 76% S, PnL at min speed = 23768, PnL at max speed = 609920

Given max = 100%, best alloc = 23% R 77% S, PnL at min speed = 24232, PnL at max speed = 618096

We can infer that the more we allocate on research and speed, the better, as it outgrows the budget.