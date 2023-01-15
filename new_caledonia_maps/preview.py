import glob

import math
from pathlib import Path

import cairocffi
import click
from map_engraver.canvas import CanvasBuilder
from map_engraver.canvas.canvas_coordinate import CanvasCoordinate
from map_engraver.canvas.canvas_unit import CanvasUnit as Cu
from map_engraver.data.canvas_geometry.rect import rect
from map_engraver.data.geo.geo_coordinate import GeoCoordinate
from map_engraver.data.geo_canvas_ops.geo_canvas_mask import canvas_mask
from map_engraver.data.geo_canvas_ops.geo_canvas_scale import GeoCanvasScale
from map_engraver.data.geo_canvas_ops.geo_canvas_transformers_builder import \
    GeoCanvasTransformersBuilder
from map_engraver.data.geotiff.canvas_transform import \
    build_geotiff_crs_within_canvas_matrix
from map_engraver.data.osm import Parser
from map_engraver.data.osm.filter import filter_elements
from map_engraver.data.osm_shapely.natural_coastline import \
    CoastlineOutputType, \
    natural_coastline_to_multi_polygon
from map_engraver.data.osm_shapely.osm_to_shapely import OsmToShapely
from map_engraver.drawable.geometry.line_drawer import LineDrawer
from map_engraver.drawable.geometry.polygon_drawer import PolygonDrawer
from map_engraver.drawable.images.bitmap import Bitmap
from map_engraver.drawable.images.svg import Svg
from pyproj import CRS
from shapely.geometry import Point
from shapely.ops import transform, unary_union


@click.command()
@click.option(
    "--dark/--light",
    default=False,
    help='Disables anti-aliasing when rendering the image.'
)
def render(
        dark: bool,
):
    name = 'preview-light.svg'

    root_path = Path(__file__).parent.parent
    data_path = root_path.joinpath('data')
    img_path = root_path.joinpath('img')

    sea_color = (0 / 255, 101 / 255, 204 / 255)
    # sea_color = (200/255, 200/255, 200/255)
    land_color = (183 / 255, 218 / 255, 158 / 255)
    # land_color = (230/255, 230/255, 230/255)
    beach_color = (255 / 255, 245 / 255, 208 / 255)
    boat_path = (255 / 255, 255 / 255, 255 / 255)
    ship_side_path = img_path.joinpath('ship_side_light.svg')
    hillshade_glob = 'data/preview_shaded_relief/light_*.svg'
    height_path = data_path.joinpath('preview_shaded_relief/light_relief.png')
    if dark:
        name = 'preview-dark.svg'
        sea_color = (0 / 255, 36 / 255, 125 / 255)
        land_color = (76 / 255, 141 / 255, 146 / 255)
        beach_color = (176 / 255, 176 / 255, 104 / 255)
        boat_path = (184 / 255, 204 / 255, 255 / 255)
        ship_side_path = img_path.joinpath('ship_side_dark.svg')
        hillshade_glob = 'data/preview_shaded_relief/dark_*.svg'
        height_path = data_path.joinpath('preview_shaded_relief/dark_relief.png')

    nc_path = data_path.joinpath('new_caledonia.osm')
    osm_preview_path = data_path.joinpath('preview.osm')
    shade_tiff = data_path.joinpath('preview_shaded_relief/projected.tif')

    # Read OSM data for New Caledonia
    osm_map = Parser.parse(nc_path)
    osm_to_shapely = OsmToShapely(osm_map)

    water_wgs84 = natural_coastline_to_multi_polygon(
        osm_map,
        (8.780, -77.80, 8.888, -77.5),
        CoastlineOutputType.WATER
    )
    beaches_relations = filter_elements(
        osm_map,
        lambda _, relation: (
                'natural' in relation.tags and
                relation.tags['natural'] == 'beach'
        ),
        filter_ways=False,
        filter_nodes=False,
    )
    beaches_wgs84 = unary_union(list(map(
        lambda relation: osm_to_shapely.relation_to_multi_polygon(relation),
        list(beaches_relations.relations.values())
    )))

    # Read custom data for the preview map
    osm_preview_map = Parser.parse(osm_preview_path)
    osm_preview_to_shapely = OsmToShapely(osm_preview_map)

    boat_way = filter_elements(
        osm_preview_map, lambda _, way: (
                'name' in way.tags and way.tags['name'] == 'First Expedition'
        ),
        filter_nodes=False,
        filter_relations=False
    )
    boat_path_wgs84 = osm_preview_to_shapely.way_to_line_string(
        list(boat_way.ways.values())[0]
    )

    # Build the canvas
    Path(__file__).parent.parent.joinpath('output/') \
        .mkdir(parents=True, exist_ok=True)
    path = Path(__file__).parent.parent.joinpath('output/%s' % name)
    path.unlink(missing_ok=True)
    canvas_builder = CanvasBuilder()
    canvas_builder.set_path(path)
    canvas_width = Cu.from_px(720)
    canvas_height = Cu.from_px(328)
    canvas_builder.set_size(canvas_width, canvas_height)
    canvas = canvas_builder.build()
    canvas_bbox = canvas_builder.build_bbox()

    # Now let's sort out the projection system
    crs = CRS.from_proj4('+proj=utm +zone=17')
    wgs84_crs = CRS.from_epsg(4326)
    builder = GeoCanvasTransformersBuilder()
    builder.set_crs(crs)
    builder.set_data_crs(wgs84_crs)
    builder.set_rotation(-0.2)
    builder.set_origin_for_geo(GeoCoordinate(8.8401, -77.6389, wgs84_crs))
    builder.set_origin_for_canvas(CanvasCoordinate.from_px(
        canvas_width.px / 2,
        canvas_height.px / 2
    ))
    builder.set_scale(GeoCanvasScale(2000, Cu.from_px(100)))

    mask_canvas = canvas_mask(
        rect(canvas_bbox).buffer(Cu.from_px(10).pt),
        builder
    )

    # Generate the transformers
    wgs84_to_canvas = builder.build_crs_to_canvas_transformer()

    water_canvas = transform(wgs84_to_canvas, water_wgs84)
    beaches_canvas = transform(wgs84_to_canvas, beaches_wgs84)
    boat_path_canvas = transform(wgs84_to_canvas, boat_path_wgs84)

    # Finally, let's get to rendering stuff!
    polygon_drawer = PolygonDrawer()
    polygon_drawer.fill_color = land_color
    polygon_drawer.geoms = [mask_canvas]
    polygon_drawer.draw(canvas)

    polygon_drawer = PolygonDrawer()
    polygon_drawer.fill_color = beach_color
    polygon_drawer.geoms = [beaches_canvas]
    polygon_drawer.draw(canvas)

    shade_matrix = build_geotiff_crs_within_canvas_matrix(
            # Add padding to avoid hill-shade edges appearing on map
            rect(canvas_bbox).buffer(Cu.from_px(10).pt),
            builder,
            shade_tiff
        )
    canvas.context.save()
    canvas.context.transform(shade_matrix)

    bitmap = Bitmap(height_path)
    bitmap.draw(canvas)

    for shade_path in glob.glob(hillshade_glob, root_dir=root_path):
        svg_drawer = Svg(Path(shade_path))
        svg_drawer.draw(canvas)

    canvas.context.restore()

    polygon_drawer = PolygonDrawer()
    polygon_drawer.fill_color = sea_color
    polygon_drawer.geoms = [water_canvas]
    polygon_drawer.draw(canvas)

    line_drawer = LineDrawer()
    line_drawer.geoms = [boat_path_canvas]
    line_drawer.stroke_color = boat_path
    line_drawer.stroke_width = Cu.from_px(2)
    line_drawer.stroke_dashes = [Cu.from_px(2), Cu.from_px(3)], Cu.from_px(3)
    line_drawer.stroke_line_cap = cairocffi.constants.LINE_CAP_ROUND
    line_drawer.stroke_line_join = cairocffi.constants.LINE_CAP_ROUND
    line_drawer.draw(canvas)

    svg_drawer = Svg(ship_side_path)
    svg_actual_width = Cu.from_px(50)
    svg_actual_height = Cu.from_px(35)
    svg_drawer.width = Cu.from_px(50)
    svg_drawer.height = Cu.from_px(35)
    boat_line_string_length = boat_path_canvas.length
    boat_position: Point = boat_path_canvas.interpolate(
        boat_line_string_length - svg_drawer.width.pt / 6
    )
    boat_position_left: Point = boat_path_canvas.interpolate(
        boat_line_string_length
    )
    svg_drawer.position = CanvasCoordinate.from_pt(
        boat_position.x,
        boat_position.y
    )
    svg_drawer.svg_origin = CanvasCoordinate(
        svg_actual_width / 2,
        svg_actual_height - line_drawer.stroke_width * 0.5,
    )
    svg_drawer.rotation = math.atan2(
        boat_position.y - boat_position_left.y,
        boat_position.x - boat_position_left.x
    )
    svg_drawer.draw(canvas)

    canvas.close()


if __name__ == '__main__':
    render()
