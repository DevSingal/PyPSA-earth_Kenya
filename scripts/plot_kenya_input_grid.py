"""Build an interactive map of the Kenya input transmission grid.

The map uses the processed OSM/base-network GeoJSON files produced before
PyPSA clustering and optimisation, so it shows the grid available to the model.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd


DEFAULT_RESOURCES = Path("resources/Kenya_test_runs")
DEFAULT_OUTPUT = Path("analysis/outputs/input_grid_kenya_osm.html")


VOLTAGE_COLORS = {
    66000: "#8c8c8c",
    132000: "#2b8cbe",
    220000: "#41ab5d",
    230000: "#41ab5d",
    300000: "#feb24c",
    400000: "#f03b20",
    500000: "#bd0026",
}


def read_geojson(path: Path) -> gpd.GeoDataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    return gpd.read_file(path).to_crs("EPSG:4326")


def voltage_color(voltage: object) -> str:
    try:
        return VOLTAGE_COLORS.get(int(float(voltage)), "#636363")
    except (TypeError, ValueError):
        return "#636363"


def voltage_label(voltage: object) -> str:
    try:
        return f"{int(float(voltage)) / 1000:.0f} kV"
    except (TypeError, ValueError):
        return "unknown"


def line_style(feature: dict) -> dict:
    voltage = feature.get("properties", {}).get("voltage")
    is_dc = bool(feature.get("properties", {}).get("dc"))
    return {
        "color": "#6a51a3" if is_dc else voltage_color(voltage),
        "weight": 4 if is_dc else 3,
        "opacity": 0.8,
    }


def thin_line_style(color: str) -> dict:
    return {"color": color, "weight": 2, "opacity": 0.65}


def add_geojson_layer(
    fmap: folium.Map,
    gdf: gpd.GeoDataFrame,
    name: str,
    fields: list[str],
    aliases: list[str],
    style_function,
    show: bool = True,
) -> None:
    if gdf.empty:
        return

    available_fields = [field for field in fields if field in gdf.columns]
    available_aliases = [
        alias for field, alias in zip(fields, aliases, strict=False) if field in gdf.columns
    ]

    folium.GeoJson(
        gdf,
        name=name,
        show=show,
        style_function=style_function,
        tooltip=folium.GeoJsonTooltip(fields=available_fields, aliases=available_aliases),
        popup=folium.GeoJsonPopup(fields=available_fields, aliases=available_aliases),
    ).add_to(fmap)


def add_bus_layer(fmap: folium.Map, buses: gpd.GeoDataFrame) -> None:
    if buses.empty:
        return

    group = folium.FeatureGroup(name="Base-network substations / buses", show=True)

    for _, row in buses.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue
        voltage = row.get("voltage")
        tooltip = (
            f"Bus {row.get('bus_id', '')} | station {row.get('station_id', '')} | "
            f"{voltage_label(voltage)}"
        )
        popup = folium.Popup(
            f"""
            <table>
              <tr><th align="left">Bus</th><td>{row.get("bus_id", "")}</td></tr>
              <tr><th align="left">Station</th><td>{row.get("station_id", "")}</td></tr>
              <tr><th align="left">Voltage</th><td>{voltage_label(voltage)}</td></tr>
              <tr><th align="left">Substation</th><td>{row.get("tag_substation", "")}</td></tr>
              <tr><th align="left">Under construction</th><td>{row.get("under_construction", "")}</td></tr>
            </table>
            """,
            max_width=280,
        )
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=4.5,
            color="#111111",
            weight=1,
            fill=True,
            fill_color=voltage_color(voltage),
            fill_opacity=0.9,
            tooltip=tooltip,
            popup=popup,
        ).add_to(group)

    group.add_to(fmap)


def add_legend(fmap: folium.Map) -> None:
    rows = "\n".join(
        f"""
        <div style="display:flex;align-items:center;gap:7px;margin:3px 0;">
          <span style="display:inline-block;width:24px;height:4px;background:{color};"></span>
          <span>{int(voltage / 1000)} kV</span>
        </div>
        """
        for voltage, color in sorted(VOLTAGE_COLORS.items())
    )
    html = f"""
    <div style="
      position: fixed;
      bottom: 24px;
      left: 24px;
      z-index: 9999;
      background: white;
      border: 1px solid #999;
      border-radius: 6px;
      padding: 10px 12px;
      font-family: Arial, sans-serif;
      font-size: 12px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.18);
    ">
      <div style="font-weight: 700; margin-bottom: 5px;">Input grid voltage</div>
      {rows}
      <div style="display:flex;align-items:center;gap:7px;margin:3px 0;">
        <span style="display:inline-block;width:24px;height:4px;background:#6a51a3;"></span>
        <span>DC / converter</span>
      </div>
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(html))


def add_title(fmap: folium.Map) -> None:
    html = """
    <div style="
      position: fixed;
      top: 14px;
      left: 50px;
      z-index: 9999;
      background: rgba(255,255,255,0.94);
      border: 1px solid #999;
      border-radius: 6px;
      padding: 9px 12px;
      font-family: Arial, sans-serif;
      font-size: 14px;
      font-weight: 700;
      box-shadow: 0 2px 8px rgba(0,0,0,0.16);
    ">
      Kenya input transmission grid from processed OSM/base-network files
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(html))


def build_map(resources_dir: Path, output: Path) -> None:
    base_network = resources_dir / "base_network"
    osm_clean = resources_dir / "osm" / "clean"
    shapes = resources_dir / "shapes"

    lines = read_geojson(base_network / "all_lines_build_network.geojson")
    buses = read_geojson(base_network / "all_buses_build_network.geojson")
    transformers = read_geojson(base_network / "all_transformers_build_network.geojson")
    converters = read_geojson(base_network / "all_converters_build_network.geojson")
    clean_lines = read_geojson(osm_clean / "all_clean_lines.geojson")
    clean_substations = read_geojson(osm_clean / "all_clean_substations.geojson")
    country = read_geojson(shapes / "country_shapes.geojson")

    bounds_source = pd.concat(
        [gdf[["geometry"]] for gdf in [lines, buses, country] if not gdf.empty],
        ignore_index=True,
    )
    if bounds_source.empty:
        raise FileNotFoundError(f"No map geometry found under {resources_dir}")

    bounds = bounds_source.total_bounds
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
    fmap = folium.Map(location=center, zoom_start=6, tiles="OpenStreetMap")

    add_geojson_layer(
        fmap,
        country,
        "Kenya boundary",
        ["name", "country"],
        ["Name", "Country"],
        lambda _: {"color": "#222222", "weight": 1, "fillOpacity": 0.02},
        show=True,
    )
    add_geojson_layer(
        fmap,
        clean_lines,
        "Clean OSM lines before PyPSA build",
        ["voltage", "frequency", "circuits", "dc"],
        ["Voltage", "Frequency", "Circuits", "DC"],
        lambda _: thin_line_style("#9ecae1"),
        show=False,
    )
    add_geojson_layer(
        fmap,
        lines,
        "Base-network lines",
        ["line_id", "voltage", "circuits", "bus0", "bus1", "length", "dc"],
        ["Line", "Voltage", "Circuits", "Bus 0", "Bus 1", "Length m", "DC"],
        line_style,
        show=True,
    )
    add_geojson_layer(
        fmap,
        transformers,
        "Base-network transformers",
        ["line_id", "bus0", "bus1"],
        ["Transformer", "Bus 0", "Bus 1"],
        lambda _: thin_line_style("#fb6a4a"),
        show=True,
    )
    add_geojson_layer(
        fmap,
        converters,
        "Base-network converters",
        ["converter_id", "bus0", "bus1"],
        ["Converter", "Bus 0", "Bus 1"],
        lambda _: thin_line_style("#6a51a3"),
        show=True,
    )
    add_bus_layer(fmap, buses)
    add_geojson_layer(
        fmap,
        clean_substations,
        "Clean OSM substations before PyPSA build",
        ["voltage", "symbol", "tag_substation"],
        ["Voltage", "Symbol", "Substation tag"],
        lambda _: {"color": "#525252", "weight": 1, "fillOpacity": 0.45},
        show=False,
    )

    fmap.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
    folium.LayerControl(collapsed=False).add_to(fmap)
    add_title(fmap)
    add_legend(fmap)

    output.parent.mkdir(parents=True, exist_ok=True)
    fmap.save(output)
    print(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--resources-dir",
        type=Path,
        default=DEFAULT_RESOURCES,
        help=f"Processed resource directory. Default: {DEFAULT_RESOURCES}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output HTML path. Default: {DEFAULT_OUTPUT}",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_map(args.resources_dir, args.output)


if __name__ == "__main__":
    main()
