from pathlib import Path
from typing import List

import click
import shapefile
from map_engraver.drawable.layout.background import Background
from shapely.geometry import shape
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
    england = (255, 18, 44)
    france = (245, 245, 0)
    netherlands = (255, 139, 7)
    spain = (46, 194, 244)
    portugal = (0, 201, 0)

    bg_color = (1, 1, 1)
    sea_color = (0/255, 101/255, 204/255)
    land_color = (183/255, 218/255, 158/255)
    if dark:
        name = 'orthographic-dark.svg'
        bg_color = (0, 0, 0)
        sea_color = (0 / 255, 36 / 255, 125 / 255)
        land_color = (76 / 255, 141 / 255, 146 / 255)

    # Extract shapefile data into multi-polygons
    data_path = Path(__file__).parent.parent.joinpath('data')
    land_shape_path = data_path.joinpath('ne_10m_land/ne_10m_land.shp')
    lake_shape_path = data_path.joinpath('ne_10m_lakes/ne_10m_lakes.shp')

    # Read world map shapefile
    def parse_shapefile(shapefile_path: Path):
        shapefile_collection = shapefile.Reader(shapefile_path.as_posix())
        shapely_objects = []
        for shape_record in shapefile_collection.shapeRecords():
            shapely_objects.append(shape(shape_record.shape.__geo_interface__))
        return shapely_objects

    land_shapes = parse_shapefile(land_shape_path)
    lake_shapes = parse_shapefile(lake_shape_path)

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
    lake_shapes = ops.unary_union(lake_shapes)

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
    crs = CRS.from_proj4('+proj=ortho +lat_0=30 +lon_0=-40')
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
    land_shapes = land_shapes.difference(lake_shapes)

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

    polygon_drawer = PolygonDrawer()
    polygon_drawer.fill_color = land_color
    polygon_drawer.geoms = [land_shapes_canvas]
    polygon_drawer.draw(canvas)

    canvas.close()


if __name__ == '__main__':
    render()
