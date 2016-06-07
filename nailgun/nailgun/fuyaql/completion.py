class FuCompleter(object):
    def __init__(self, words):
        self.words = words
        self.prefix = None
        self.matches = None
        return

    def complete(self, text, index):
        if text != self.prefix:
            self.matches = [m for m in self.words if m.startswith(text)]
            self.prefix = text
        try:
            return self.matches[index]
        except IndexError:
            return None
