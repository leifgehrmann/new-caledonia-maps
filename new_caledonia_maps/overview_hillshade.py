import glob
import subprocess
from pathlib import Path

from PIL import Image
from map_engraver.canvas.canvas_bbox import CanvasBbox
from map_engraver.canvas.canvas_coordinate import CanvasCoordinate
from map_engraver.canvas.canvas_unit import CanvasUnit as Cu
from map_engraver.data.canvas_geometry.rect import rect
from map_engraver.data.geo.geo_coordinate import GeoCoordinate
from map_engraver.data.geo_canvas_ops.geo_canvas_scale import GeoCanvasScale
from map_engraver.data.geo_canvas_ops.geo_canvas_transformers_builder import \
    GeoCanvasTransformersBuilder
from map_engraver.data.geotiff.canvas_transform import \
    transform_geotiff_to_crs_within_canvas
from osgeo import gdal
from pyproj import CRS


def docker_run(command: str):
    result = subprocess.call(
        'docker run '
        '--rm '
        '-t '
        '-v `pwd`:/root/mydata/ '
        '-w /root/mydata/ '
        'new-caledonia-maps-potrace '
        '/bin/sh -c '
        + "'" + command + "'",
        shell=True,
        cwd=Path(__file__).parent.parent.as_posix()
    )
    if result != 0:
        raise Exception('Failed to execute docker command')


srtm_height_tif_filename = 'data/N08W078.hgt'
overview_filepath = 'data/overview_shaded_relief/'
overview_height_tif_filename = overview_filepath + 'projected_height.tif'
overview_tif_filename = overview_filepath + 'projected.tif'
overview_pnm_filename = overview_filepath + 'projected.pnm'
overview_relief_light_tif_filename = overview_filepath + 'light_relief.tif'
overview_relief_light_png_filename = overview_filepath + 'light_relief.png'
overview_relief_dark_tif_filename = overview_filepath + 'dark_relief.tif'
overview_relief_dark_png_filename = overview_filepath + 'dark_relief.png'
overview_relief_light_map_filename = 'data/color-relief-light.txt'
overview_relief_dark_map_filename = 'data/color-relief-dark.txt'
overview_svg_filename_match = overview_filepath + '*.svg'
overview_highlight_svg_filename = overview_filepath + '%s_highlight_%.2f.svg'
overview_shadow_svg_filename = overview_filepath + '%s_shadow_%.2f.svg'
# In the SRTM hillshade tif, flat slopes are this shade of gray.
threshold_midpoint = 181 / 255

root_path = Path(__file__).parent.parent
srtm_height_tif_path = root_path.joinpath(srtm_height_tif_filename)
overview_output_path = root_path.joinpath(overview_filepath)
overview_height_tif_path = root_path.joinpath(overview_height_tif_filename)
overview_tif_path = root_path.joinpath(overview_tif_filename)
overview_pnm_path = root_path.joinpath(overview_pnm_filename)
overview_relief_light_tif_path = root_path.joinpath(
    overview_relief_light_tif_filename
)
overview_relief_light_png_path = root_path.joinpath(
    overview_relief_light_png_filename
)
overview_relief_dark_tif_path = root_path.joinpath(
    overview_relief_dark_tif_filename
)
overview_relief_dark_png_path = root_path.joinpath(
    overview_relief_dark_png_filename
)
overview_relief_light_map_path = root_path.joinpath(
    overview_relief_light_map_filename
)
overview_relief_dark_map_path = root_path.joinpath(
    overview_relief_dark_map_filename
)

# Generate the output directory if it doesn't exist.
overview_output_path.mkdir(parents=True, exist_ok=True)

# Reproject the SRTM height map from Natural Earth to a map of New Caledonia.
if not overview_height_tif_path.exists():
    canvas_width = Cu.from_px(720)
    canvas_height = Cu.from_px(720)
    canvas_bbox = CanvasBbox(
        CanvasCoordinate.origin(),
        CanvasCoordinate(canvas_width, canvas_height)
    )
    canvas_rect = rect(canvas_bbox)
    crs = CRS.from_proj4('+proj=utm +zone=17')
    wgs84_crs = CRS.from_epsg(4326)
    builder = GeoCanvasTransformersBuilder()
    builder.set_crs(crs)
    builder.set_data_crs(wgs84_crs)
    builder.set_origin_for_geo(GeoCoordinate(8.8401, -77.6389, wgs84_crs))
    builder.set_origin_for_canvas(CanvasCoordinate.from_px(
        canvas_width.px / 2,
        canvas_height.px / 3 * 2
    ))
    builder.set_scale(GeoCanvasScale(2000, Cu.from_px(100)))

    transform_geotiff_to_crs_within_canvas(
        srtm_height_tif_path,
        # Add padding to avoid hill-shade edges appearing on map
        canvas_rect.buffer(Cu.from_px(10).pt),
        builder,
        overview_height_tif_path
    )

# Convert height map to hillshade
if not overview_relief_light_tif_path.exists() or \
        not overview_relief_dark_tif_path.exists():
    gdal.UseExceptions()
    gdal.DEMProcessing(
        overview_relief_light_tif_path.as_posix(),
        overview_height_tif_path.as_posix(),
        'color-relief',
        options=gdal.DEMProcessingOptions(
            colorFilename=overview_relief_light_map_path.as_posix(),
            band=1,
            addAlpha=True,
            colorSelection='linear_interpolation'
        )
    )
    gdal.DEMProcessing(
        overview_relief_dark_tif_path.as_posix(),
        overview_height_tif_path.as_posix(),
        'color-relief',
        options=gdal.DEMProcessingOptions(
            colorFilename=overview_relief_dark_map_path.as_posix(),
            band=1,
            addAlpha=True,
            colorSelection='linear_interpolation'
        )
    )

    image = Image.open(overview_relief_light_tif_path)
    image.save(overview_relief_light_png_path)
    image = Image.open(overview_relief_dark_tif_path)
    image.save(overview_relief_dark_png_path)

# Convert height map to hillshade
if not overview_tif_path.exists():
    gdal.UseExceptions()
    gdal.DEMProcessing(
        overview_tif_path.as_posix(),
        overview_height_tif_path.as_posix(),
        'hillshade',
        options=gdal.DEMProcessingOptions(
            format='GTiff',
            band=1,
            zFactor=1,
            scale=1,
            azimuth=312,
            altitude=45
        )
    )

# Convert the TIFF to PNM.
if not overview_pnm_path.exists():
    docker_run(
        'tifftopnm %s > %s' % (overview_tif_filename, overview_pnm_filename)
    )

# Generate the **shadow** specs of the TIFF as an SVG at different brightness
# thresholds. We duplicate them, so we can have dark and light themes later.
for threshold_delta in [0.05, 0.10, 0.15]:
    threshold = threshold_midpoint + threshold_delta
    docker_run(
        'potrace %s -o %s -b svg -k %f -i' % (
            overview_pnm_filename,
            overview_highlight_svg_filename % ('dark', threshold),
            threshold
        )
    )
    docker_run(
        'cp %s %s' % (
            overview_highlight_svg_filename % ('dark', threshold),
            overview_highlight_svg_filename % ('light', threshold)
        )
    )

# Generate the **highlight** specs of the TIFF as an SVG at different
# brightness thresholds. We duplicate them, so we can have dark and light
# themes later.
for threshold_delta in [0.05, 0.10, 0.15, 0.25, 0.40]:
    threshold = threshold_midpoint - threshold_delta
    docker_run(
        'potrace %s -o %s -b svg -k %f' % (
            overview_pnm_filename,
            overview_shadow_svg_filename % ('dark', threshold),
            threshold
        )
    )
    docker_run(
        'cp %s %s' % (
            overview_shadow_svg_filename % ('dark', threshold),
            overview_shadow_svg_filename % ('light', threshold)
        )
    )

# Update the colors of the SVGs according to the theme and colors.
for path in glob.glob(overview_svg_filename_match, root_dir=root_path):
    color = None
    opacity = None
    if 'dark' in path:
        if 'shadow' in path:
            color = '#000'
            opacity = 0.05
        elif 'highlight' in path:
            color = '#FFF'
            opacity = 0.05
    else:
        if 'shadow' in path:
            color = '#000'
            opacity = 0.05
        elif 'highlight' in path:
            color = '#FFF'
            opacity = 0.1

    docker_run(
        'sed -i -e "s/fill=\\"#000000\\"/fill=\\"%s\\" opacity=\\"%f\\"/" %s'
        % (
            color, opacity, path
        )
    )
    docker_run(
        'sed -i -e "s/pt\\"/px\\"/g" %s' % path
    )
