from .base import BaseButton
from icons import BluetoothIcon
 
class BluetoothButton(BaseButton):
    VARIANTS = []
    def __init__(self, monitor_id, vertical, variant=None, **kwargs):
        super().__init__(icon=BluetoothIcon(16), variant=variant or "icon", **kwargs)
 