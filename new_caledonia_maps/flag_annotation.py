from pathlib import Path

import pangocairocffi
from cairocffi import LINE_CAP_ROUND
from map_engraver.canvas import Canvas
from map_engraver.canvas.canvas_coordinate import CanvasCoordinate
from map_engraver.canvas.canvas_unit import CanvasUnit
from map_engraver.drawable.images.svg import Svg
from pangocffi import Alignment


def draw_annotation_with_flag(
    canvas: Canvas,
    annotation_point: CanvasCoordinate,
    direction: str,  # 'up', 'down', 'left', 'right'
    distance: CanvasUnit,
    label: str,
    label_alignment: Alignment,
    flag_svg_path: Path,
    show_annotation_point=True
):
    # Draw a line
    canvas.context.move_to(annotation_point.x.pt, annotation_point.y.pt)
    if direction == 'up':
        canvas.context.line_to(
            annotation_point.x.pt,
            annotation_point.y.pt - distance.pt
        )
    elif direction == 'down':
        canvas.context.line_to(
            annotation_point.x.pt,
            annotation_point.y.pt + distance.pt
        )
    elif direction == 'right':
        canvas.context.line_to(
            annotation_point.x.pt + distance.pt,
            annotation_point.y.pt
        )
    canvas.context.set_dash([])
    canvas.context.set_source_rgba(1, 1, 1)
    canvas.context.set_line_cap(LINE_CAP_ROUND)
    canvas.context.set_line_width(CanvasUnit.from_px(2).pt)
    canvas.context.stroke()

    # Draw a circle at the annotation point
    if show_annotation_point:
        canvas.context.arc(
            annotation_point.x.pt,
            annotation_point.y.pt,
            CanvasUnit.from_px(3).pt,
            0,
            2 * 3.1416
        )
        canvas.context.stroke()
        canvas.context.arc(
            annotation_point.x.pt,
            annotation_point.y.pt,
            CanvasUnit.from_px(2).pt,
            0,
            2 * 3.1416
        )
        canvas.context.set_source_rgba(0, 0, 0)
        canvas.context.fill()

    # Prepare the flag SVG
    svg_drawer = Svg(flag_svg_path)
    svg_size = svg_drawer.read_svg_size()

    # Draw text
    label = '<span ' \
            'face="SF Pro Rounded" ' \
            'weight="Medium" ' \
            'size="10pt" ' \
            'letter_spacing="-600"' \
            '>' + label + '</span>'
    canvas.context.save()
    text = pangocairocffi.create_layout(canvas.context)
    text.set_alignment(label_alignment)
    text.set_markup(label)
    text_width = CanvasUnit.from_pango(text.get_size()[0])
    text_height = CanvasUnit.from_pango(text.get_size()[1])
    horizontal_margins = CanvasUnit.from_px(-2)
    vertical_margins = CanvasUnit.from_px(2)
    text_x = annotation_point.x.pt + horizontal_margins.pt
    text_y = 0

    if (direction == 'up' or direction == 'down') and \
            label_alignment is Alignment.RIGHT:
        text_x = annotation_point.x.pt - text_width.pt - horizontal_margins.pt
    elif direction == 'right':
        text_x = annotation_point.x.pt + distance.pt + \
                 CanvasUnit.from_px(3).pt + CanvasUnit.from_px(6).pt + \
                 svg_size[0].pt + horizontal_margins.pt

    if direction == 'up':
        text_y = annotation_point.y.pt - distance.pt - text_height.pt - \
                 vertical_margins.pt
    elif direction == 'down':
        text_y = annotation_point.y.pt + distance.pt + vertical_margins.pt
    elif direction == 'right':
        text_y = annotation_point.y.pt - \
                 (text_height / text.get_line_count() / 2).pt

    canvas.context.translate(text_x, text_y)
    pangocairocffi.layout_path(canvas.context, text)
    canvas.context.set_source_rgba(1, 1, 1)
    canvas.context.fill()
    canvas.context.restore()

    # Draw the flag
    svg_drawer.position = CanvasCoordinate.from_pt(
        text_x - svg_size[0].pt - CanvasUnit.from_px(3).pt,
        text_y + CanvasUnit.from_px(3).pt
    )
    svg_drawer.draw(canvas)
