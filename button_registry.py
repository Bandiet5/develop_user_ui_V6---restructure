# button_registry.py

from button_handlers.ai_chat import AiChatHandler
from button_handlers.mini_analytics import MiniAnalyticsHandler
from button_handlers.form import FormHandler
from button_handlers.download import DownloadHandler
from button_handlers.upload import UploadHandler
from button_handlers.smart_table import SmartTableHandler
from button_handlers.multi_upload import MultiUploadHandler
from button_handlers.box_trigger import BoxTriggerHandler


# Map button types to their handler classes
BUTTON_TYPES = {
    "ai_chat": AiChatHandler,
    "mini_analytics": MiniAnalyticsHandler,
    "form": FormHandler,
    "download": DownloadHandler,
    "upload": UploadHandler,
    "smart_table": SmartTableHandler,
    "multi_upload": MultiUploadHandler,
    "box_trigger": BoxTriggerHandler,

}

def get_handler(button_type):
    """
    Return the handler class for a given button type, or None if unsupported.
    """
    return BUTTON_TYPES.get(button_type)
