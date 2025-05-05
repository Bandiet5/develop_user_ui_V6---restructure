class BaseButtonHandler:
    supported_versions = [1]  # list of integers this handler supports

    def __init__(self, version, config):
        self.version = version or 1  # default to 1 if missing
        self.config = config or {}

    def run(self):
        if self.version in self.supported_versions:
            return self.run_current()
        else:
            print(f"[WARNING] Unsupported version {self.version}. Falling back.")
            return self.run_fallback()

    def run_current(self):
        raise NotImplementedError("run_current() must be implemented.")

    def run_fallback(self):
        if 1 in self.supported_versions:
            return self.run_v1()
        raise Exception("No fallback version available.")

    def run_v1(self):
        raise NotImplementedError("run_v1() must be implemented.")
