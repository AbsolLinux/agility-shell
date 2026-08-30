import cairo
from dataclasses import dataclass

@dataclass
class Rect:
    x: int
    y: int
    width: int
    height: int

def trace_widget_regions(widget, accuracy=2, alpha_threshold=20, erode=4):
    if not hasattr(widget, "get_realized") or not widget.get_realized():
        return []
    alloc = widget.get_allocation()
    w, h = alloc.width, alloc.height
    if w <= 0 or h <= 0:
        return []

    try:
        surface = cairo.ImageSurface(cairo.Format.ARGB32, w, h)
        cr = cairo.Context(surface)
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        widget.draw(cr)
    except Exception:
        return []

    data   = surface.get_data()
    stride = surface.get_stride()

    raw = []
    for y in range(0, h, accuracy):
        step_h = min(accuracy, h - y)
        x = 0
        while x < w:
            if data[y * stride + x * 4 + 3] > alpha_threshold:
                start_x = x
                while x < w and data[y * stride + x * 4 + 3] > alpha_threshold:
                    x += 1
                raw.append(Rect(start_x, y, x - start_x, step_h))
            else:
                x += 1

    active: dict[tuple, Rect] = {}
    merged: list[Rect] = []
    for rect in raw:
        key = (rect.x, rect.width)
        if key in active:
            m = active[key]
            if m.y + m.height == rect.y:
                m.height += rect.height
                continue
            else:
                merged.append(active.pop(key))
        active[key] = Rect(rect.x, rect.y, rect.width, rect.height)

    merged.extend(active.values())
    if erode <= 0:
        return merged

    if not merged:
        return merged

    min_y = min(r.y for r in merged)
    max_y = max(r.y + r.height for r in merged)

    result = []
    for r in merged:
        new_x = r.x + erode
        new_w = r.width - (erode * 2)
        
        base_y = max(r.y, min_y + erode)
        
        new_y = base_y - 2 
        
        base_bottom = min(r.y + r.height, max_y - erode)
        new_h = base_bottom - base_y
        
        if new_w > 0 and new_h > 0:
            result.append(Rect(new_x, new_y, new_w, new_h))
    return result
def trace_widget_regions_as_dicts(widget, accuracy=10, alpha_threshold=10, erode=0):
    return [
        {"x": r.x, "y": r.y, "width": r.width, "height": r.height}
        for r in trace_widget_regions(widget, accuracy, alpha_threshold, erode)
    ]