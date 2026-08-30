from cffi import FFI
from .region_trace import trace_widget_regions
from fabric.utils import get_relative_path
ffi = FFI()

ffi.cdef("""
    typedef struct BlurContext BlurContext;

    int          blur_supported(void *wl_display);
    BlurContext* blur_enable(void *wl_display, void *wl_surface);
    void         blur_set_region(BlurContext *ctx,
                                 int32_t x, int32_t y,
                                 int32_t width, int32_t height);
    void         blur_set_regions(BlurContext *ctx,
                                  const int32_t *xs, const int32_t *ys,
                                  const int32_t *widths, const int32_t *heights,
                                  int count);
    void         blur_disable(BlurContext *ctx);
    void         blur_free(BlurContext *ctx);
""")

ffi.cdef("""
    typedef struct _GtkWidget  GtkWidget;
    typedef struct _GdkWindow  GdkWindow;
    typedef struct _GdkDisplay GdkDisplay;

    GdkWindow*  gtk_widget_get_window(GtkWidget *widget);
    GdkDisplay* gtk_widget_get_display(GtkWidget *widget);

    void* gdk_wayland_display_get_wl_display(GdkDisplay *display);
    void* gdk_wayland_window_get_wl_surface(GdkWindow *window);
""")

import os
import subprocess

_blur_so_path = get_relative_path("./lib/libblur.so")
if not os.path.exists(_blur_so_path):
    _blur_makefile_dir = get_relative_path("./lib")
    if os.path.exists(os.path.join(_blur_makefile_dir, "Makefile")):
        try:
            subprocess.run(["make", "-C", _blur_makefile_dir], check=True, capture_output=True)
        except Exception:
            pass

libblur = ffi.dlopen(_blur_so_path)
libgtk  = ffi.dlopen("libgtk-3.so.0")
libgdk  = ffi.dlopen("libgdk-3.so.0")

def _get_wl_pointers(widget):
    ptr     = ffi.cast("GtkWidget*", hash(widget))
    gdk_win = libgtk.gtk_widget_get_window(ptr)
    gdk_dpy = libgtk.gtk_widget_get_display(ptr)

    if not gdk_win:
        raise RuntimeError(
            "Widget has no GDK window — is it realized? "
            "Connect to the 'realize' signal before calling blur functions."
        )

    wl_display = libgdk.gdk_wayland_display_get_wl_display(gdk_dpy)
    wl_surface = libgdk.gdk_wayland_window_get_wl_surface(gdk_win)

    return wl_display, wl_surface

def is_blur_supported(widget) -> bool:
    wl_display, _ = _get_wl_pointers(widget)
    return bool(libblur.blur_supported(wl_display))

def enable_blur(widget) -> "BlurContext | None":
    try:
        wl_display, wl_surface = _get_wl_pointers(widget)
        ctx = libblur.blur_enable(wl_display, wl_surface)

        if not ctx:
            print("enable_blur: compositor does not support ext_background_effect_manager_v1")
            return None

        return ctx
    except Exception as e:
        print(f"enable_blur failed: {e}")
        return None

def set_blur_region(ctx, x: int, y: int, width: int, height: int):
    libblur.blur_set_region(ctx, x, y, width, height)

def set_blur_regions(ctx, rects: list[tuple[int, int, int, int]]):
    count = len(rects)
    if count == 0:
        return

    xs      = ffi.new("int32_t[]", [r[0] for r in rects])
    ys      = ffi.new("int32_t[]", [r[1] for r in rects])
    widths  = ffi.new("int32_t[]", [r[2] for r in rects])
    heights = ffi.new("int32_t[]", [r[3] for r in rects])

    libblur.blur_set_regions(ctx, xs, ys, widths, heights, count)

def set_blur_regions_from_widget(ctx, widget, accuracy: int = 10,
                                 alpha_threshold: int = 10, erode=4):
    if not ctx or not widget:
        return
    if hasattr(widget, "get_realized") and not widget.get_realized():
        return
    rects = trace_widget_regions(widget, accuracy=accuracy,
                                 alpha_threshold=alpha_threshold, erode=erode)
    if rects:
        set_blur_regions(ctx, [(r.x, r.y, r.width, r.height) for r in rects])

def disable_blur(ctx):
    libblur.blur_disable(ctx)

def free_blur(ctx):
    libblur.blur_free(ctx)
