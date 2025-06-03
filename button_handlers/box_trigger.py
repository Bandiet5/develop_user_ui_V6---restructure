from button_handlers.base import BaseButtonHandler

class BoxTriggerHandler(BaseButtonHandler):
    supported_versions = [1]

    def run_v1(self):
        """
        Box trigger logic is client-side only for now.
        This handler is just a placeholder to be compatible with the system.
        """
        print("[BoxTriggerHandler] Trigger box clicked. No server logic to run.")
        return {"status": "ok", "message": "Box trigger activated"}

    def run_current(self):
        return self.run_v1()
