import os
import shutil

def seed_user_environment():
    user_dir = os.path.expanduser("~/.config/agility-shell")
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(user_dir, exist_ok=True)

    for item in ["config", "themes", "style", "wallpapers", "icons", "svgs", "sounds"]:
        src = os.path.join(repo_dir, item)
        dst = os.path.join(user_dir, item)
        if not os.path.exists(src):
            continue
        if not os.path.exists(dst):
            try:
                shutil.copytree(src, dst)
            except Exception:
                pass
        elif os.path.isdir(src) and os.path.isdir(dst):
            for root, _, files in os.walk(src):
                rel = os.path.relpath(root, src)
                target_subdir = os.path.join(dst, rel) if rel != "." else dst
                os.makedirs(target_subdir, exist_ok=True)
                for f in files:
                    src_file = os.path.join(root, f)
                    dst_file = os.path.join(target_subdir, f)
                    if not os.path.exists(dst_file):
                        try:
                            shutil.copy2(src_file, dst_file)
                        except Exception:
                            pass

seed_user_environment()

import bar
import services.singletons as singletons
from setproctitle import setproctitle
from fabric import Application
from services.wallpaper import WallpaperService
from services.style import StyleService
from utils.sounds import play_sound
setproctitle("agility-shell")

app = Application("agility-shell")

singletons.style_service = StyleService(app)

singletons.style_service.reload()

bar_manager = bar.initialise_bars()
singletons.bar_manager = bar_manager

wallpaper_service = WallpaperService.get_instance()
# wallpaper_service.set_bar_manager(bar_manager)

play_sound("session-start")
app.run()