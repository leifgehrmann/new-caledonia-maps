from pathlib import Path

import cairocffi
import click
from map_engraver.canvas import CanvasBuilder
from map_engraver.canvas.canvas_bbox import CanvasBbox
from map_engraver.canvas.canvas_coordinate import CanvasCoordinate
from map_engraver.canvas.canvas_unit import CanvasUnit as Cu
from map_engraver.data.canvas_geometry.rect import rect
from map_engraver.data.geo.geo_coordinate import GeoCoordinate
from map_engraver.data.geo_canvas_ops.geo_canvas_mask import canvas_mask
from map_engraver.data.geo_canvas_ops.geo_canvas_scale import GeoCanvasScale
from map_engraver.data.geo_canvas_ops.geo_canvas_transformers_builder import GeoCanvasTransformersBuilder
from map_engraver.data.osm import Parser
from map_engraver.data.osm.filter import filter_elements
from map_engraver.data.osm_shapely.osm_to_shapely import OsmToShapely
from map_engraver.drawable.geometry.line_drawer import LineDrawer
from map_engraver.drawable.geometry.polygon_drawer import PolygonDrawer
from pyproj import CRS
from shapely.geometry import MultiLineString
from shapely.ops import transform


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

    img_path = Path(__file__).parent.parent.joinpath('img')

    sea_color = (0 / 255, 101 / 255, 204 / 255)
    # sea_color = (200/255, 200/255, 200/255)
    land_color = (183 / 255, 218 / 255, 158 / 255)
    # land_color = (230/255, 230/255, 230/255)
    boat_path = (255 / 255, 255 / 255, 255 / 255)
    ship_side_path = img_path.joinpath('ship_side_light.svg')
    if dark:
        name = 'preview-dark.svg'
        sea_color = (0 / 255, 36 / 255, 125 / 255)
        land_color = (76 / 255, 141 / 255, 146 / 255)
        boat_path = (184 / 255, 204 / 255, 255 / 255)
        ship_side_path = img_path.joinpath('ship_side_dark.svg')

    data_path = Path(__file__).parent.parent.joinpath('data')
    nc_path = data_path.joinpath('new_caledonia.osm')

    # Read OSM data for New Caledonia
    osm_map = Parser.parse(nc_path)
    osm_to_shapely = OsmToShapely(osm_map)

    coastline_ways = filter_elements(
        osm_map,
        lambda _, way: (
                'natural' in way.tags and
                way.tags['natural'] == 'coastline'
        ),
        filter_nodes=False,
        filter_relations=False
    )
    coastline_wgs84 = list(map(
        lambda way: osm_to_shapely.way_to_line_string(way),
        list(coastline_ways.ways.values())
    ))

    # Build the canvas
    Path(__file__).parent.parent.joinpath('output/') \
        .mkdir(parents=True, exist_ok=True)
    path = Path(__file__).parent.parent.joinpath('output/%s' % name)
    path.unlink(missing_ok=True)
    canvas_builder = CanvasBuilder()
    canvas_builder.set_path(path)
    canvas_width = Cu.from_px(720)
    canvas_height = Cu.from_px(328)
    canvas_bbox = CanvasBbox(
        CanvasCoordinate.origin(),
        canvas_width,
        canvas_height
    )
    canvas_builder.set_size(canvas_width, canvas_height)
    canvas = canvas_builder.build()

    # Now let's sort out the projection system
    crs = CRS.from_proj4('+proj=utm +zone=17')
    wgs84_crs = CRS.from_epsg(4326)
    builder = GeoCanvasTransformersBuilder()
    builder.set_crs(crs)
    builder.set_data_crs(wgs84_crs)
    builder.set_origin_for_geo(GeoCoordinate(8.8401, -77.6389, wgs84_crs))
    builder.set_origin_for_canvas(CanvasCoordinate.from_px(
        canvas_width.px / 2,
        canvas_height.px / 2
    ))
    builder.set_scale(GeoCanvasScale(3000, Cu.from_px(100)))

    mask_canvas = canvas_mask(
        rect(canvas_bbox).buffer(Cu.from_px(10).pt),
        builder
    )

    # Generate the transformers
    wgs84_to_canvas = builder.build_crs_to_canvas_transformer()

    coastline_canvas = transform(
        wgs84_to_canvas, MultiLineString(coastline_wgs84)
    )
    coastline_canvas = coastline_canvas.simplify(1)

    # Finally, let's get to rendering stuff!
    polygon_drawer = PolygonDrawer()
    polygon_drawer.fill_color = sea_color
    polygon_drawer.geoms = [mask_canvas]
    polygon_drawer.draw(canvas)

    line_drawer = LineDrawer()
    line_drawer.geoms = [coastline_canvas]
    line_drawer.stroke_color = boat_path
    line_drawer.stroke_width = Cu.from_px(2)
    line_drawer.stroke_dashes = [Cu.from_px(2), Cu.from_px(3)], Cu.from_px(3)
    line_drawer.stroke_line_cap = cairocffi.constants.LINE_CAP_ROUND
    line_drawer.stroke_line_join = cairocffi.constants.LINE_CAP_ROUND
    line_drawer.draw(canvas)

    canvas.close()


if __name__ == '__main__':
    render()
