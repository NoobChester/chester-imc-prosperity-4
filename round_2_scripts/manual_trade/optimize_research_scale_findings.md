### **Findings from manual trade scripts**

py optimize_research_scale.py

Best max Sp PnL:
Research = 23%
Scale = 77%
PnL at max speed = 618096
PnL at min speed = 24232

Best min speed PnL:
Research = 23%
Scale = 77%
PnL at max speed = 618096
PnL at min speed = 24232

We can infer that if we spend 0 on speed, 23 and 77 is the best way to spend on research and scale.

We further expand the previous code:

py list_research_scale.py

Given R and Sc alloc = 0%, best alloc = 0% R 0% Sc, PnL at min Sp = 0, PnL at max Sp = 0
Given R and Sc alloc = 1%, best alloc = 0% R 0% Sc, PnL at min Sp = 0, PnL at max Sp = 0
...
Given R and Sc alloc = 30%, best alloc = 0% R 0% Sc, PnL at min Sp = 0, PnL at max Sp = 0
Given R and Sc alloc = 31%, best alloc = 0% R 0% Sc, PnL at min Sp = 0, PnL at max Sp = 0
Given R and Sc alloc = 32%, best alloc = 9% R 23% Sc, PnL at min Sp = 65, PnL at max Sp = 128587
Given R and Sc alloc = 33%, best alloc = 9% R 24% Sc, PnL at min Sp = 263, PnL at max Sp = 134374
...
Given R and Sc alloc = 99%, best alloc = 23% R 76% Sc, PnL at min Sp = 23768, PnL at max Sp = 609920
Given R and Sc alloc = 100%, best alloc = 23% R 77% Sc, PnL at min Sp = 24232, PnL at max Sp = 618096

We can infer that the more we allocate on research and speed, the better, as it outgrows the budget.