import glob

import math
from pathlib import Path
from typing import List

import cairocffi.constants
import click
import shapefile
from map_engraver.canvas.canvas_bbox import CanvasBbox
from map_engraver.data.canvas_geometry.rect import rect
from map_engraver.data.geo_canvas_ops.geo_canvas_mask import \
    canvas_mask, canvas_wgs84_mask
from map_engraver.data.geo_canvas_ops.geo_canvas_transformers_builder import \
    GeoCanvasTransformersBuilder
from map_engraver.data.osm import Parser
from map_engraver.data.osm.filter import filter_elements
from map_engraver.data.osm_shapely.osm_to_shapely import OsmToShapely
from map_engraver.drawable.geometry.line_drawer import LineDrawer
from map_engraver.drawable.images.svg import Svg
from pangocffi import Alignment
from shapely.geometry import shape, MultiLineString, Point
from shapely.geometry.base import BaseGeometry

from pyproj import CRS
from shapely import ops

from map_engraver.canvas import CanvasBuilder
from map_engraver.canvas.canvas_coordinate import CanvasCoordinate
from map_engraver.canvas.canvas_unit import CanvasUnit as Cu
from map_engraver.data.geo.geo_coordinate import GeoCoordinate
from map_engraver.data.osm_shapely_ops.transform import \
    transform_interpolated_euclidean

from map_engraver.drawable.geometry.polygon_drawer import PolygonDrawer

from new_caledonia_maps.flag_annotation import draw_annotation_with_flag


@click.command()
@click.option(
    "--dark/--light",
    default=False,
    help='Disables anti-aliasing when rendering the image.'
)
def render(
        dark: bool,
):
    name = 'panama-light.svg'

    img_path = Path(__file__).parent.parent.joinpath('img')

    sea_color = (0/255, 101/255, 204/255)
    land_color = (183/255, 218/255, 158/255)
    boat_path_color = (255 / 255, 255 / 255, 255 / 255)
    ship_side_path = img_path.joinpath('ship_side_light.svg')
    panama_border_color = (0, 0, 0)
    if dark:
        name = 'panama-dark.svg'
        sea_color = (0 / 255, 36 / 255, 125 / 255)
        land_color = (76 / 255, 141 / 255, 146 / 255)
        boat_path_color = (184 / 255, 204 / 255, 255 / 255)
        ship_side_path = img_path.joinpath('ship_side_dark.svg')

    # Extract shapefile data into multi-polygons
    root_path = Path(__file__).parent.parent
    data_path = root_path.joinpath('data')
    land_shape_path = data_path.joinpath('ne_10m_land/ne_10m_land.shp')
    lake_shape_path = data_path.joinpath('ne_10m_lakes/ne_10m_lakes.shp')
    borders_path = data_path.joinpath('borders.osm')
    shade_glob = 'data/panama_shaded_relief_*.svg'

    # Read land/lake map shapefile data
    def parse_shapefile(shapefile_path: Path):
        shapefile_collection = shapefile.Reader(shapefile_path.as_posix())
        shapely_objects = []
        for shape_record in shapefile_collection.shapeRecords():
            shapely_objects.append(shape(shape_record.shape.__geo_interface__))
        return shapely_objects

    land_shapes = parse_shapefile(land_shape_path)
    lake_shapes = parse_shapefile(lake_shape_path)

    # Read borders data
    osm_map = Parser.parse(borders_path)
    osm_to_shapely = OsmToShapely(osm_map)
    panama_border_ways = filter_elements(
        osm_map,
        lambda _, way: (
                'barrier' in way.tags and
                way.tags['barrier'] == 'border_control' and
                'name' in way.tags and
                way.tags['name'] == 'Panama'
        ),
        filter_nodes=False,
        filter_relations=False
    )
    historic_water = filter_elements(
        osm_map,
        lambda _, way: (
                'natural' in way.tags and way.tags['natural'] == 'water'
        ),
        filter_nodes=False,
        filter_relations=False
    )
    historic_land = filter_elements(
        osm_map,
        lambda _, way: (
                'natural' in way.tags and way.tags['natural'] == 'land'
        ),
        filter_nodes=False,
        filter_relations=False
    )
    panama_border_wgs84 = list(map(
        lambda way: osm_to_shapely.way_to_line_string(way),
        list(panama_border_ways.ways.values())
    ))
    polygons_water = list(map(
        lambda way: osm_to_shapely.way_to_polygon(way),
        list(historic_water.ways.values())
    ))
    polygons_land = list(map(
        lambda way: osm_to_shapely.way_to_polygon(way),
        list(historic_land.ways.values())
    ))

    # Invert CRS for shapes, because shapefiles are store coordinates are
    # lon/lat, not according to the ISO-approved standard.
    def transform_geoms_to_invert(geoms: List[BaseGeometry]):
        return list(map(
            lambda geom: ops.transform(lambda x, y: (y, x), geom),
            geoms
        ))

    land_shapes = transform_geoms_to_invert(land_shapes)
    lake_shapes = transform_geoms_to_invert(lake_shapes)
    land_shapes = ops.unary_union(land_shapes + polygons_land)
    # Add ancient lakes
    lake_shapes = ops.unary_union(lake_shapes + polygons_water)
    # Removed modern lakes and reservoirs
    lake_shapes = lake_shapes.difference(ops.unary_union(polygons_land))

    # Read boat route.
    boat_way = filter_elements(
        osm_map, lambda _, way: (
            'name' in way.tags and way.tags['name'] == 'First Expedition'
        ),
        filter_nodes=False,
        filter_relations=False
    )
    boat_path_wgs84 = osm_to_shapely.way_to_line_string(
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
    canvas_height = Cu.from_px(500)
    canvas_builder.set_size(
        canvas_width,
        canvas_height
    )
    canvas = canvas_builder.build()

    # Now let's sort out the projection system
    crs = CRS.from_proj4('+proj=utm +zone=17')
    wgs84_crs = CRS.from_epsg(4326)
    builder = GeoCanvasTransformersBuilder()
    builder.set_scale_and_origin_from_coordinates_and_crs(
        crs,
        GeoCoordinate(9, -83.5, wgs84_crs),
        GeoCoordinate(9, -76.5, wgs84_crs),
        CanvasCoordinate.from_px(0, canvas_height.px / 2),
        CanvasCoordinate.from_px(canvas_width.px, canvas_height.px / 2)
    )
    builder.set_data_crs(wgs84_crs)

    # Generate the transformers
    wgs84_to_canvas = builder.build_crs_to_canvas_transformer()

    # Generate the masks to cull the data with.
    mask_canvas = canvas_mask(
        rect(CanvasBbox(
            CanvasCoordinate.origin(),
            canvas_width,
            canvas_height
        )).buffer(Cu.from_px(10).pt),
        builder
    )
    mask_wgs84 = canvas_wgs84_mask(
        rect(CanvasBbox(
            CanvasCoordinate.origin(),
            canvas_width,
            canvas_height
        )).buffer(Cu.from_px(10).pt),
        builder
    )

    # Cull away unnecessary geometries, and subtract lakes from land.
    land_shapes = land_shapes.intersection(mask_wgs84)
    lake_shapes = lake_shapes.intersection(mask_wgs84)
    land_shapes = land_shapes.difference(lake_shapes)

    # Finally, let's get to rendering stuff!
    polygon_drawer = PolygonDrawer()
    polygon_drawer.fill_color = sea_color
    polygon_drawer.geoms = [mask_canvas]
    polygon_drawer.draw(canvas)

    land_shapes_canvas = transform_interpolated_euclidean(
        wgs84_to_canvas,
        land_shapes
    )

    polygon_drawer = PolygonDrawer()
    polygon_drawer.fill_color = land_color
    polygon_drawer.geoms = [land_shapes_canvas]
    polygon_drawer.draw(canvas)

    for shade_path in glob.glob(shade_glob, root_dir=root_path):
        svg_drawer = Svg(Path(shade_path))
        svg_drawer.width = canvas_width
        svg_drawer.position = CanvasCoordinate.origin()
        svg_drawer.draw(canvas)

    boat_path_canvas = transform_interpolated_euclidean(
        wgs84_to_canvas, boat_path_wgs84
    )
    boat_path_canvas = boat_path_canvas.intersection(mask_canvas)
    line_drawer = LineDrawer()
    line_drawer.geoms = [boat_path_canvas]
    line_drawer.stroke_color = boat_path_color
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
        boat_line_string_length - svg_drawer.width.pt / 5
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

    # Draw the borders of Panama
    panama_border_canvas = transform_interpolated_euclidean(
        wgs84_to_canvas, MultiLineString(panama_border_wgs84)
    )
    panama_border_canvas = panama_border_canvas.simplify(1)
    line_drawer = LineDrawer()
    line_drawer.geoms = [panama_border_canvas]
    line_drawer.stroke_color = panama_border_color
    line_drawer.stroke_width = Cu.from_px(2)
    line_drawer.stroke_dashes = [Cu.from_px(2), Cu.from_px(3)], Cu.from_px(3)
    line_drawer.stroke_line_cap = cairocffi.constants.LINE_CAP_ROUND
    line_drawer.stroke_line_join = cairocffi.constants.LINE_CAP_ROUND
    line_drawer.draw(canvas)

    draw_annotation_with_flag(
        canvas,
        CanvasCoordinate.from_pt(*wgs84_to_canvas(
            *GeoCoordinate(8.834019, -77.631797, wgs84_crs).tuple
        )),
        'up',
        Cu.from_px(100),
        'New Caledonia\n<span size="80%">Est. 1698</span>',
        Alignment.RIGHT,
        img_path.joinpath('scotland.svg')
    )

    draw_annotation_with_flag(
        canvas,
        CanvasCoordinate.from_pt(*wgs84_to_canvas(
            *GeoCoordinate(9.582889, -79.470306, wgs84_crs).tuple
        )),
        'up',
        Cu.from_px(110),
        'Nombre de Dios\n<span size="80%">Est. 1510</span>',
        Alignment.LEFT,
        img_path.joinpath('spain.svg')
    )

    draw_annotation_with_flag(
        canvas,
        CanvasCoordinate.from_pt(*wgs84_to_canvas(
            *GeoCoordinate(8.983333, -79.516667, wgs84_crs).tuple
        )),
        'down',
        Cu.from_px(100),
        'Panama City\n<span size="80%">Est. 1519</span>',
        Alignment.LEFT,
        img_path.joinpath('spain.svg')
    )

    draw_annotation_with_flag(
        canvas,
        CanvasCoordinate.from_pt(*wgs84_to_canvas(
            *GeoCoordinate(9.554444, -79.655, wgs84_crs).tuple
        )),
        'up',
        Cu.from_px(80),
        'Portobelo\n<span size="80%">Est. 1597</span>',
        Alignment.RIGHT,
        img_path.joinpath('spain.svg')
    )

    draw_annotation_with_flag(
        canvas,
        CanvasCoordinate.from_pt(*wgs84_to_canvas(
            *GeoCoordinate(8.433333, -82.433333, wgs84_crs).tuple
        )),
        'down',
        Cu.from_px(100),
        'David\n<span size="80%">Est. 1602</span>',
        Alignment.LEFT,
        img_path.joinpath('spain.svg')
    )

    draw_annotation_with_flag(
        canvas,
        CanvasCoordinate.from_pt(*wgs84_to_canvas(
            *GeoCoordinate(9.5683, -82.5643, wgs84_crs).tuple
        )),
        'up',
        Cu.from_px(50),
        'Panama today',
        Alignment.LEFT,
        img_path.joinpath('panama.svg'),
        show_annotation_point=False
    )

    canvas.close()


if __name__ == '__main__':
    render()
