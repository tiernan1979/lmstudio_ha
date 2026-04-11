from collections import defaultdict


class Memory:
    def __init__(self):
        self.store = defaultdict(list)

    def add(self, cid, role, content):
        self.store[cid].append({"role": role, "content": content})

    def get(self, cid, limit=20):
        return self.store[cid][-limit:]