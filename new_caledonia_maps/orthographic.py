import math
from pathlib import Path
from typing import List

import cairocffi.constants
import click
import shapefile
from map_engraver.data.osm import Parser
from map_engraver.data.osm.filter import filter_elements
from map_engraver.data.osm_shapely.osm_to_shapely import OsmToShapely
from map_engraver.data.osm_shapely_ops.homogenize import geoms_to_multi_polygon
from map_engraver.drawable.geometry.line_drawer import LineDrawer
from map_engraver.drawable.geometry.stripe_filled_polygon_drawer import StripeFilledPolygonDrawer
from map_engraver.drawable.images.svg import Svg
from map_engraver.drawable.layout.background import Background
from shapely.geometry import shape, Point
from shapely.geometry.base import BaseGeometry

from pyproj import CRS
from shapely import ops

from map_engraver.canvas import CanvasBuilder
from map_engraver.canvas.canvas_coordinate import CanvasCoordinate
from map_engraver.canvas.canvas_unit import CanvasUnit as Cu
from map_engraver.data import geo_canvas_ops
from map_engraver.data.geo.geo_coordinate import GeoCoordinate
from map_engraver.data.osm_shapely_ops.transform import \
    transform_interpolated_euclidean
from map_engraver.data.proj import masks

from map_engraver.drawable.geometry.polygon_drawer import PolygonDrawer


@click.command()
@click.option(
    "--dark/--light",
    default=False,
    help='Disables anti-aliasing when rendering the image.'
)
def render(
        dark: bool,
):
    name = 'orthographic-light.svg'

    img_path = Path(__file__).parent.parent.joinpath('img')

    bg_color = (1, 1, 1)
    sea_color = (0/255, 101/255, 204/255)
    land_color = (183/255, 218/255, 158/255)
    scotland = (255 / 255, 255 / 255, 255 / 255)
    england = (255 / 255, 170 / 255, 180 / 255)
    france = (126 / 255, 222 / 255, 255 / 255)
    netherlands = (255 / 255, 184 / 255, 105 / 255)
    spain = (247 / 255, 255 / 255, 136 / 255)
    portugal = (113 / 255, 255 / 255, 110 / 255)
    boat_path = (255 / 255, 255 / 255, 255 / 255)
    ship_side_path = img_path.joinpath('ship_side_light.svg')
    if dark:
        name = 'orthographic-dark.svg'
        bg_color = (0, 0, 0)
        sea_color = (0 / 255, 36 / 255, 125 / 255)
        land_color = (76 / 255, 141 / 255, 146 / 255)
        scotland = (255 / 255, 255 / 255, 255 / 255)
        england = (186 / 255, 90 / 255, 106 / 255)
        france = (40 / 255, 160 / 255, 190 / 255)
        netherlands = (151 / 255, 118 / 255, 55 / 255)
        spain = (171 / 255, 203 / 255, 98 / 255)
        portugal = (31 / 255, 179 / 255, 56 / 255)
        boat_path = (184 / 255, 204 / 255, 255 / 255)
        ship_side_path = img_path.joinpath('ship_side_dark.svg')

    # Extract shapefile data into multi-polygons
    data_path = Path(__file__).parent.parent.joinpath('data')
    land_shape_path = data_path.joinpath('ne_50m_land/ne_50m_land.shp')
    lake_shape_path = data_path.joinpath('ne_50m_lakes/ne_50m_lakes.shp')
    borders_path = data_path.joinpath('borders.osm')

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
    historic_water = filter_elements(osm_map, lambda _, way: 'natural' in way.tags and way.tags['natural'] == 'water', filter_nodes=False, filter_relations=False)
    historic_land = filter_elements(osm_map, lambda _, way: 'natural' in way.tags and way.tags['natural'] == 'land', filter_nodes=False, filter_relations=False)
    borders_sc = filter_elements(osm_map, lambda _, relation: relation.tags['country'] == 'scotland', filter_nodes=False, filter_ways=False)
    borders_en = filter_elements(osm_map, lambda _, relation: relation.tags['country'] == 'england', filter_nodes=False, filter_ways=False)
    borders_es = filter_elements(osm_map, lambda _, relation: relation.tags['country'] == 'spain', filter_nodes=False, filter_ways=False)
    borders_fr = filter_elements(osm_map, lambda _, relation: relation.tags['country'] == 'france', filter_nodes=False, filter_ways=False)
    borders_pt = filter_elements(osm_map, lambda _, relation: relation.tags['country'] == 'portugal', filter_nodes=False, filter_ways=False)
    borders_nl = filter_elements(osm_map, lambda _, relation: relation.tags['country'] == 'netherlands', filter_nodes=False, filter_ways=False)
    borders_xx = filter_elements(osm_map, lambda _, relation: relation.tags['country'] == 'england/france', filter_nodes=False, filter_ways=False)
    polygons_water = list(map(lambda way: osm_to_shapely.way_to_polygon(way), list(historic_water.ways.values())))
    polygons_land = list(map(lambda way: osm_to_shapely.way_to_polygon(way), list(historic_land.ways.values())))
    multi_polygon_sc = osm_to_shapely.relation_to_multi_polygon(list(borders_sc.relations.values())[0])
    multi_polygon_en = osm_to_shapely.relation_to_multi_polygon(list(borders_en.relations.values())[0])
    multi_polygon_es = osm_to_shapely.relation_to_multi_polygon(list(borders_es.relations.values())[0])
    multi_polygon_fr = osm_to_shapely.relation_to_multi_polygon(list(borders_fr.relations.values())[0])
    multi_polygon_pt = osm_to_shapely.relation_to_multi_polygon(list(borders_pt.relations.values())[0])
    multi_polygon_nl = osm_to_shapely.relation_to_multi_polygon(list(borders_nl.relations.values())[0])
    multi_polygon_xx = osm_to_shapely.relation_to_multi_polygon(list(borders_xx.relations.values())[0])

    # Invert CRS for shapes, because shapefiles are store coordinates are lon/lat,
    # not according to the ISO-approved standard.
    def transform_geoms_to_invert(geoms: List[BaseGeometry]):
        return list(map(
            lambda geom: ops.transform(lambda x, y: (y, x), geom),
            geoms
        ))

    land_shapes = transform_geoms_to_invert(land_shapes)
    lake_shapes = transform_geoms_to_invert(lake_shapes)
    land_shapes = ops.unary_union(land_shapes)
    # Add ancient lakes
    lake_shapes = ops.unary_union(lake_shapes + polygons_water)
    # Removed modern lakes and reservoirs
    lake_shapes = lake_shapes.difference(ops.unary_union(polygons_land))

    # Read boat route.
    boat_way = filter_elements(osm_map, lambda _, way: 'name' in way.tags and way.tags['name'] == 'First Expedition', filter_nodes=False, filter_relations=False)
    boat_linestring = osm_to_shapely.way_to_line_string(list(boat_way.ways.values())[0])

    # Build the canvas
    Path(__file__).parent.parent.joinpath('output/') \
        .mkdir(parents=True, exist_ok=True)
    path = Path(__file__).parent.parent.joinpath('output/%s' % name)
    path.unlink(missing_ok=True)
    canvas_builder = CanvasBuilder()
    canvas_builder.set_path(path)
    globe_px = 720
    margin_px = 0
    canvas_builder.set_size(
        Cu.from_px(margin_px * 2 + globe_px),
        Cu.from_px(margin_px * 2 + globe_px)
    )
    canvas = canvas_builder.build()

    # Now let's sort out the projection system
    crs = CRS.from_proj4('+proj=ortho +lat_0=20 +lon_0=-50')
    azimuthal_mask_ortho = masks.azimuthal_mask(crs)
    azimuthal_mask_wgs84 = masks.azimuthal_mask_wgs84(crs)
    geo_to_canvas_scale = geo_canvas_ops.GeoCanvasScale(
        azimuthal_mask_ortho.bounds[2] - azimuthal_mask_ortho.bounds[0],
        Cu.from_px(globe_px)
    )
    origin_for_geo = GeoCoordinate(0, 0, crs)
    origin_x = Cu.from_px(margin_px + globe_px / 2)
    origin_y = Cu.from_px(margin_px + globe_px / 2)
    origin_for_canvas = CanvasCoordinate(origin_x, origin_y)
    proj_to_canvas = geo_canvas_ops.build_transformer(
        crs=crs,
        data_crs=crs,
        scale=geo_to_canvas_scale,
        origin_for_geo=origin_for_geo,
        origin_for_canvas=origin_for_canvas
    )
    wgs84_crs = CRS.from_epsg(4326)
    wgs84_to_canvas = geo_canvas_ops.build_transformer(
        crs=crs,
        data_crs=wgs84_crs,
        scale=geo_to_canvas_scale,
        origin_for_geo=origin_for_geo,
        origin_for_canvas=origin_for_canvas
    )

    # Cull away unnecessary geometries, and subtract lakes from land.
    land_shapes = land_shapes.intersection(azimuthal_mask_wgs84)
    lake_shapes = lake_shapes.intersection(azimuthal_mask_wgs84)
    multi_polygon_sc = multi_polygon_sc.intersection(azimuthal_mask_wgs84)
    multi_polygon_en = multi_polygon_en.intersection(azimuthal_mask_wgs84)
    multi_polygon_es = multi_polygon_es.intersection(azimuthal_mask_wgs84)
    multi_polygon_fr = multi_polygon_fr.intersection(azimuthal_mask_wgs84)
    multi_polygon_pt = multi_polygon_pt.intersection(azimuthal_mask_wgs84)
    multi_polygon_nl = multi_polygon_nl.intersection(azimuthal_mask_wgs84)
    multi_polygon_xx = multi_polygon_xx.intersection(azimuthal_mask_wgs84)
    land_shapes = land_shapes.difference(lake_shapes)
    multi_polygon_sc = multi_polygon_sc.intersection(land_shapes)
    multi_polygon_en = multi_polygon_en.intersection(land_shapes)
    multi_polygon_es = multi_polygon_es.intersection(land_shapes)
    multi_polygon_fr = multi_polygon_fr.intersection(land_shapes)
    multi_polygon_pt = multi_polygon_pt.intersection(land_shapes)
    multi_polygon_nl = multi_polygon_nl.intersection(land_shapes)
    multi_polygon_xx = multi_polygon_xx.intersection(land_shapes)
    land_shapes = geoms_to_multi_polygon(
        land_shapes.difference(ops.unary_union([
            multi_polygon_sc,
            multi_polygon_en,
            multi_polygon_es,
            multi_polygon_fr,
            multi_polygon_pt,
            multi_polygon_nl,
            multi_polygon_xx
        ]))
    )

    # Finally, let's get to rendering stuff!
    background = Background()
    background.color = bg_color
    background.draw(canvas)

    mask_canvas = ops.transform(proj_to_canvas, azimuthal_mask_ortho)
    polygon_drawer = PolygonDrawer()
    polygon_drawer.fill_color = sea_color
    polygon_drawer.geoms = [mask_canvas]
    polygon_drawer.draw(canvas)

    land_shapes_canvas = transform_interpolated_euclidean(
        wgs84_to_canvas,
        land_shapes
    )
    multi_polygon_sc_canvas = transform_interpolated_euclidean(wgs84_to_canvas, multi_polygon_sc)
    multi_polygon_en_canvas = transform_interpolated_euclidean(wgs84_to_canvas, multi_polygon_en)
    multi_polygon_es_canvas = transform_interpolated_euclidean(wgs84_to_canvas, multi_polygon_es)
    multi_polygon_fr_canvas = transform_interpolated_euclidean(wgs84_to_canvas, multi_polygon_fr)
    multi_polygon_pt_canvas = transform_interpolated_euclidean(wgs84_to_canvas, multi_polygon_pt)
    multi_polygon_nl_canvas = transform_interpolated_euclidean(wgs84_to_canvas, multi_polygon_nl)
    multi_polygon_xx_canvas = transform_interpolated_euclidean(wgs84_to_canvas, multi_polygon_xx)

    polygon_drawer = PolygonDrawer()
    polygon_drawer.fill_color = land_color
    polygon_drawer.geoms = [land_shapes_canvas]
    polygon_drawer.draw(canvas)

    polygon_drawer = PolygonDrawer()
    polygon_drawer.fill_color = scotland
    polygon_drawer.geoms = [multi_polygon_sc_canvas]
    polygon_drawer.draw(canvas)
    polygon_drawer.fill_color = england
    polygon_drawer.geoms = [multi_polygon_en_canvas]
    polygon_drawer.draw(canvas)
    polygon_drawer.fill_color = spain
    polygon_drawer.geoms = [multi_polygon_es_canvas]
    polygon_drawer.draw(canvas)
    polygon_drawer.fill_color = france
    polygon_drawer.geoms = [multi_polygon_fr_canvas]
    polygon_drawer.draw(canvas)
    polygon_drawer.fill_color = portugal
    polygon_drawer.geoms = [multi_polygon_pt_canvas]
    polygon_drawer.draw(canvas)
    polygon_drawer.fill_color = netherlands
    polygon_drawer.geoms = [multi_polygon_nl_canvas]
    polygon_drawer.draw(canvas)

    stripe_polygon_drawer = StripeFilledPolygonDrawer()
    stripe_polygon_drawer.geoms = [multi_polygon_xx_canvas]
    stripe_polygon_drawer.stripe_angle = math.pi / 8
    stripe_polygon_drawer.stripe_widths = [Cu.from_px(2), Cu.from_px(2)]
    stripe_polygon_drawer.stripe_colors = [england, france]
    stripe_polygon_drawer.draw(canvas)

    boat_line_string_canvas = transform_interpolated_euclidean(wgs84_to_canvas, boat_linestring)
    line_drawer = LineDrawer()
    line_drawer.geoms = [boat_line_string_canvas]
    line_drawer.stroke_color = boat_path
    line_drawer.stroke_width = Cu.from_px(2)
    line_drawer.stroke_dashes = [Cu.from_px(2), Cu.from_px(3)], Cu.from_px(3)
    line_drawer.stroke_line_cap = cairocffi.constants.LINE_CAP_ROUND
    line_drawer.draw(canvas)

    svg_drawer = Svg(ship_side_path)
    svg_drawer.width = Cu.from_px(50)
    svg_drawer.height = Cu.from_px(35)
    boat_position_perc = 0.6
    boat_line_string_length = boat_line_string_canvas.length
    boat_position: Point = boat_line_string_canvas.interpolate(
        boat_line_string_length * boat_position_perc
    )
    boat_position_left: Point = boat_line_string_canvas.interpolate(
        boat_line_string_length * boat_position_perc + svg_drawer.width.pt / 3
    )
    boat_position_right: Point = boat_line_string_canvas.interpolate(
        boat_line_string_length * boat_position_perc - svg_drawer.width.pt / 3
    )
    svg_drawer.position = CanvasCoordinate.from_pt(
        boat_position.x,
        boat_position.y
    )
    svg_drawer.svg_origin = CanvasCoordinate(
        svg_drawer.width / 2,
        svg_drawer.height + line_drawer.stroke_width * 1.5,
    )
    svg_drawer.rotation = math.atan2(
        boat_position_right.y - boat_position_left.y,
        boat_position_right.x - boat_position_left.x
    )
    svg_drawer.draw(canvas)

    canvas.close()


if __name__ == '__main__':
    render()
