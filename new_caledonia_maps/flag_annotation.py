from pathlib import Path
from typing import Tuple, Optional, Union

import pangocairocffi
from cairocffi import LINE_CAP_ROUND
from map_engraver.canvas import Canvas
from map_engraver.canvas.canvas_coordinate import CanvasCoordinate
from map_engraver.canvas.canvas_unit import CanvasUnit
from map_engraver.drawable.images.svg import Svg
from pangocffi import Alignment


def _draw_line(
    canvas: Canvas,
    annotation_point: CanvasCoordinate,
    direction: str,  # 'up', 'down', 'left', 'right'
    offset: Union[CanvasUnit, Tuple[CanvasUnit, CanvasUnit]],
    show_annotation_point: bool,
    curve_control_a: Optional[Tuple[CanvasUnit, CanvasUnit]],
    curve_control_b: Optional[Tuple[CanvasUnit, CanvasUnit]]
) -> CanvasCoordinate:
    """
    :param canvas:
    :param annotation_point:
    :param direction:
    :param offset:
    :param show_annotation_point:
    :param curve_control_a:
    :param curve_control_b:
    :return: The point at the end of the line.
    """
    # Draw a line
    canvas.context.move_to(annotation_point.x.pt, annotation_point.y.pt)

    if isinstance(offset, CanvasUnit):
        if direction == 'up':
            offset = [CanvasUnit.from_px(0), offset * -1]
        elif direction == 'down':
            offset = [CanvasUnit.from_px(0), offset]
        elif direction == 'right':
            offset = [offset, CanvasUnit.from_px(0)]
        else:
            offset = [offset * -1, CanvasUnit.from_px(0)]

    # Compute curve
    end_x = annotation_point.x.pt + offset[0].pt
    end_y = annotation_point.y.pt + offset[1].pt

    curve_control_a_x, curve_control_a_y = annotation_point.pt
    curve_control_b_x, curve_control_b_y = end_x, end_y

    if curve_control_a is not None:
        curve_control_a_x += curve_control_a[0].pt
        curve_control_a_y += curve_control_a[1].pt

    if curve_control_b is not None:
        curve_control_b_x += curve_control_b[0].pt
        curve_control_b_y += curve_control_b[1].pt

    canvas.context.curve_to(
        curve_control_a_x,
        curve_control_a_y,
        curve_control_b_x,
        curve_control_b_y,
        end_x,
        end_y
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

    return CanvasCoordinate.from_pt(end_x, end_y)


def _draw_label(
    canvas: Canvas,
    label_point: CanvasCoordinate,
    direction: str,  # 'up', 'down', 'left', 'right'
    label: str,
    label_alignment: Alignment,
    icon_size: Optional[Tuple[CanvasUnit, CanvasUnit]]
) -> CanvasCoordinate:
    # Draw text
    label = '<span ' \
            'face="SF Pro Rounded" ' \
            'weight="Medium" ' \
            'size="10pt" ' \
            'letter_spacing="-600"' \
            '>' + label + '</span>'
    canvas.context.save()
    text = pangocairocffi.create_layout(canvas.context)
    text.alignment = label_alignment
    text.apply_markup(label)
    text_width = CanvasUnit.from_pango(text.get_size()[0])
    text_height = CanvasUnit.from_pango(text.get_size()[1])
    horizontal_margins = CanvasUnit.from_px(-2)
    vertical_margins = CanvasUnit.from_px(2)
    text_x = label_point.x.pt + horizontal_margins.pt
    text_y = 0

    if (direction == 'up' or direction == 'down') and \
            label_alignment is Alignment.RIGHT:
        text_x = label_point.x.pt - text_width.pt - horizontal_margins.pt
    elif direction == 'right':
        text_x = label_point.x.pt + \
                 CanvasUnit.from_px(6).pt + \
                 horizontal_margins.pt
        if icon_size is not None:
            text_x += icon_size[0].pt + CanvasUnit.from_px(3).pt

    if direction == 'up':
        text_y = label_point.y.pt - text_height.pt - \
                 vertical_margins.pt
    elif direction == 'down':
        text_y = label_point.y.pt + vertical_margins.pt
    elif direction == 'right':
        text_y = label_point.y.pt - \
                 (text_height / text.get_line_count() / 2).pt

    canvas.context.translate(text_x, text_y)
    pangocairocffi.layout_path(canvas.context, text)
    canvas.context.set_source_rgba(1, 1, 1)
    canvas.context.fill()
    canvas.context.restore()

    return CanvasCoordinate.from_pt(text_x, text_y)


def draw_annotation(
    canvas: Canvas,
    annotation_point: CanvasCoordinate,
    direction: str,  # 'up', 'down', 'left', 'right'
    offset: Union[CanvasUnit, Tuple[CanvasUnit, CanvasUnit]],
    label: str,
    label_alignment: Alignment,
    show_annotation_point=True,
    curve_control_a: Optional[Tuple[CanvasUnit, CanvasUnit]] = None,
    curve_control_b: Optional[Tuple[CanvasUnit, CanvasUnit]] = None
):
    line_end_point = _draw_line(
        canvas,
        annotation_point,
        direction,
        offset,
        show_annotation_point,
        curve_control_a,
        curve_control_b
    )
    _draw_label(
        canvas,
        line_end_point,
        direction,
        label,
        label_alignment,
        None
    )


def draw_annotation_with_flag(
    canvas: Canvas,
    annotation_point: CanvasCoordinate,
    direction: str,  # 'up', 'down', 'left', 'right'
    offset: Union[CanvasUnit, Tuple[CanvasUnit, CanvasUnit]],
    label: str,
    label_alignment: Alignment,
    flag_svg_path: Path,
    show_annotation_point=True,
    curve_control_a: Optional[Tuple[CanvasUnit, CanvasUnit]] = None,
    curve_control_b: Optional[Tuple[CanvasUnit, CanvasUnit]] = None
):
    # Prepare the flag SVG
    svg_drawer = Svg(flag_svg_path)
    svg_size = svg_drawer.read_svg_size()

    line_end_point = _draw_line(
        canvas,
        annotation_point,
        direction,
        offset,
        show_annotation_point,
        curve_control_a,
        curve_control_b
    )
    label_point = _draw_label(
        canvas,
        line_end_point,
        direction,
        label,
        label_alignment,
        svg_size
    )

    # Draw the flag
    svg_drawer.position = CanvasCoordinate.from_pt(
        label_point.x.pt - svg_size[0].pt - CanvasUnit.from_px(3).pt,
        label_point.y.pt + CanvasUnit.from_px(3).pt
    )
    svg_drawer.draw(canvas)
