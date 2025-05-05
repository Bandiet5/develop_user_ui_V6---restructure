# button_registry.py

from button_handlers.ai_chat import AiChatHandler
from button_handlers.mini_analytics import MiniAnalyticsHandler
from button_handlers.form import FormHandler
from button_handlers.download import DownloadHandler
from button_handlers.upload import UploadHandler


# Map button types to their handler classes
BUTTON_TYPES = {
    "ai_chat": AiChatHandler,
    "mini_analytics": MiniAnalyticsHandler,
    "form": FormHandler,
    "download": DownloadHandler,
    "upload": UploadHandler,
}

def get_handler(button_type):
    """
    Return the handler class for a given button type, or None if unsupported.
    """
    return BUTTON_TYPES.get(button_type)
