# Thread: moving the job queue to a new broker

**Ann** (10:01): Morning! The staging broker is ready.
I copied the config from the old cluster
and left the retention at seven days.
**Bob** (10:04): Thanks. Did the consumers reconnect on their own?
**Ann** (10:06): Yes, all twelve of them.

**Bob** (10:09): Great, then let's switch production on Thursday.
Ping me if anything looks off.

**Eve** (10:15): Works for me. I will update `config/queue.yaml` before the switch.
