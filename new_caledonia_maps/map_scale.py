from typing import Tuple, List

from map_engraver.canvas import Canvas
from map_engraver.canvas.canvas_bbox import CanvasBbox
from map_engraver.canvas.canvas_coordinate import CanvasCoordinate
from map_engraver.canvas.canvas_unit import CanvasUnit
from map_engraver.data.geo_canvas_ops.geo_canvas_transformers_builder import \
    GeoCanvasTransformersBuilder
from map_engraver.data.pango.layout import Layout
from map_engraver.drawable.geometry.polygon_drawer import PolygonDrawer
from map_engraver.drawable.text.pango_drawer import PangoDrawer
from pangocffi import Alignment
from shapely import ops
from shapely.geometry import Point, Polygon


def draw_map_scale(
    canvas: Canvas,
    canvas_bbox: CanvasBbox,
    transformers_builder: GeoCanvasTransformersBuilder,
    width_in_geo_units: float,
    segments: int,
    labels: List[Tuple[float, str]]  # array of geographic units and names
):
    """
    This implementation adds a map scale to the top-right of the map.

    :param canvas:
    :param canvas_bbox:
    :param transformers_builder:
    :param width_in_geo_units:
    :param segments:
    :param labels:
    :return:
    """
    margin = CanvasUnit.from_px(50)
    line_thickness = CanvasUnit.from_px(2)
    scale_thickness = line_thickness * 4

    width_in_canvas_units = transformers_builder.scale.canvas_units / \
        transformers_builder.scale.geo_units * \
        width_in_geo_units

    # Construct a pill-shaped polygon that looks similar to this:
    # ╭─────────╮
    # ╰─────────╯
    radius = scale_thickness.pt / 2
    start_circle = Point(radius, 0).buffer(radius)
    end_circle = Point(width_in_canvas_units.pt - radius, 0).buffer(radius)
    middle_rect = Polygon([
        (radius, -radius),
        (width_in_canvas_units.pt - radius, -radius),
        (width_in_canvas_units.pt - radius, radius),
        (radius, radius),
    ])
    scale_polygon = ops.unary_union([start_circle, middle_rect, end_circle])

    # We represent a tick by cutting a black piece in the scale.
    tick_polygon: Polygon = scale_polygon.buffer(-line_thickness.pt)
    for segment in range(1, segments, 2):
        sub_polygon = Polygon([
            (segment * width_in_canvas_units.pt / segments, -radius),
            ((segment + 1) * width_in_canvas_units.pt / segments, -radius),
            ((segment + 1) * width_in_canvas_units.pt / segments, radius),
            (segment * width_in_canvas_units.pt / segments, radius)
        ])
        tick_polygon = tick_polygon.difference(sub_polygon)

    # We need to calculate the total bbox of all the items, so let's start with
    # the bounds of the scale polygon
    bounds_min_x = scale_polygon.bounds[0]
    bounds_min_y = scale_polygon.bounds[1]
    bounds_max_x = scale_polygon.bounds[2]
    bounds_max_y = scale_polygon.bounds[3]

    # Calculate the width of the labels we'll display above the scale.
    labels_text: List[Layout] = []
    for label in labels:
        text = '<span ' \
                'face="SF Pro Rounded" ' \
                'weight="Medium" ' \
                'size="10pt" ' \
                'letter_spacing="-600"' \
                '>' + label[1] + '</span>'
        layout = Layout(canvas)
        layout.apply_markup(text)
        layout.alignment = Alignment.CENTER
        layout_bbox = layout.logical_extents

        text_scale_x = transformers_builder.scale.canvas_units / \
            transformers_builder.scale.geo_units * \
            label[0]

        text_position = CanvasCoordinate(
            text_scale_x - layout_bbox.width / 2,
            -(scale_thickness / 2 + line_thickness + layout_bbox.height)
        )

        layout.position = text_position
        layout.color = (1, 1, 1)

        labels_text.append(layout)

        # Now calculate the total bbox of all the items
        bounds_min_x = min(bounds_min_x, layout.logical_extents.min_pos.x.pt)
        bounds_min_y = min(bounds_min_y, layout.logical_extents.min_pos.y.pt)
        bounds_max_x = max(bounds_max_x, layout.logical_extents.max_pos.x.pt)
        bounds_max_y = max(bounds_max_y, layout.logical_extents.max_pos.y.pt)

    scale_bbox = CanvasBbox(
        CanvasCoordinate.from_pt(bounds_min_x, bounds_min_y),
        CanvasCoordinate.from_pt(bounds_max_x, bounds_max_y),
    )

    canvas_top_right_margin = CanvasCoordinate(
        canvas_bbox.max_pos.x - margin,
        canvas_bbox.min_pos.y + margin
    )
    canvas.context.save()
    canvas.context.translate(
        (canvas_top_right_margin.x - scale_bbox.width).pt,
        (canvas_top_right_margin.y - scale_bbox.min_pos.y).pt
    )

    polygon_drawer = PolygonDrawer()
    polygon_drawer.fill_color = (1, 1, 1, 1)
    polygon_drawer.geoms = [scale_polygon]
    polygon_drawer.draw(canvas)

    polygon_drawer = PolygonDrawer()
    polygon_drawer.fill_color = (0, 0, 0, 1)
    polygon_drawer.geoms = [tick_polygon]
    polygon_drawer.draw(canvas)

    label_drawer = PangoDrawer()
    label_drawer.pango_objects = labels_text
    label_drawer.draw(canvas)

    canvas.context.restore()
