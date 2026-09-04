import math
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

def compute_rounded_rect_regions(
    x: int,
    y: int,
    w: int,
    h: int,
    r: int,
    top_left: bool = True,
    top_right: bool = True,
    bottom_left: bool = True,
    bottom_right: bool = True,
) -> list[tuple[int, int, int, int]]:
    """Compute non-overlapping horizontal rectangle slices defining a rounded rectangle

    for Wayland wl_region background blur.
    """
    if r <= 0 or not (top_left or top_right or bottom_left or bottom_right):
        return [(int(x), int(y), int(w), int(h))]

    r = min(int(r), int(w) // 2, int(h) // 2)
    if r <= 0:
        return [(int(x), int(y), int(w), int(h))]

    rows = []
    # Top corner scanlines
    for dy in range(r):
        v = r - dy - 0.5
        h_dist = math.sqrt(max(0.0, r * r - v * v))
        dx = int(round(r - h_dist))
        left_dx = dx if top_left else 0
        right_dx = dx if top_right else 0
        row_x = x + left_dx
        row_w = w - left_dx - right_dx
        if row_w > 0:
            rows.append((row_x, y + dy, row_w, 1))

    # Middle section
    mid_y = y + r
    mid_h = h - 2 * r
    if mid_h > 0:
        rows.append((x, mid_y, w, mid_h))

    # Bottom corner scanlines
    for dy in range(r):
        v = dy + 0.5
        h_dist = math.sqrt(max(0.0, r * r - v * v))
        dx = int(round(r - h_dist))
        left_dx = dx if bottom_left else 0
        right_dx = dx if bottom_right else 0
        row_x = x + left_dx
        row_w = w - left_dx - right_dx
        if row_w > 0:
            rows.append((row_x, y + h - r + dy, row_w, 1))

    # Merge contiguous rows with identical x and w
    merged: list[tuple[int, int, int, int]] = []
    for rx, ry, rw, rh in rows:
        if merged and merged[-1][0] == rx and merged[-1][2] == rw and (merged[-1][1] + merged[-1][3] == ry):
            prev_x, prev_y, prev_w, prev_h = merged[-1]
            merged[-1] = (prev_x, prev_y, prev_w, prev_h + rh)
        else:
            merged.append((rx, ry, rw, rh))
    return merged
