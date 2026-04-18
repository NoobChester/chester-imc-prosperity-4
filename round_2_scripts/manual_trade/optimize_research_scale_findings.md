## **Findings from manual trade scripts**

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

### We can infer that if we spend 0 on speed, 23 and 77 is the best way to spend on research and scale.

### We further expand the previous code:

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

### We can infer that the more we allocate on research and speed, the better, as it outgrows the budget.

### We can also infer that it is never worth it to spend any more than 68% on speed.

### However let's assume the worst case, we spend all the rest of our budget and still get min speed:

Given R and Sc alloc = 32%, best alloc = 9% R 23% Sc, PnL at min Sp = -33934

Given R and Sc alloc = 33%, best alloc = 9% R 24% Sc, PnL at min Sp = -33236

...

Given R and Sc alloc = 72%, best alloc = 18% R 54% Sc, PnL at min Sp = -1767

Given R and Sc alloc = 73%, best alloc = 18% R 55% Sc, PnL at min Sp = -874

Given R and Sc alloc = 74%, best alloc = 18% R 56% Sc, PnL at min Sp = 19

Given R and Sc alloc = 75%, best alloc = 18% R 57% Sc, PnL at min Sp = 912

Given R and Sc alloc = 99%, best alloc = 23% R 76% Sc, PnL at min Sp = 23268

Given R and Sc alloc = 100%, best alloc = 23% R 77% Sc, PnL at min Sp = 24232

### If we spend more than 26% on speed, we risk getting negative PnL.

### However that does not mean we it is never worth it, we have not considered the increase in speed.