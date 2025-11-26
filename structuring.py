import os
import glob
import xml.etree.ElementTree as ET
from datetime import datetime

# ----------------- PATHS -----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

INPUT_DIR = os.path.join(BASE_DIR, "gpx_files", "unstructured")
OUTPUT_DIR = os.path.join(BASE_DIR, "gpx_files", "gpx_garmin")

# ----------------- NAMESPACES -----------------
NS_GPX = "http://www.topografix.com/GPX/1/1"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"

# Register only safe prefixes (no ns2/ns3 to avoid the error)
ET.register_namespace("", NS_GPX)
ET.register_namespace("xsi", NS_XSI)


# ----------------- HELPERS -----------------
def extract_metadata_time(original_root):
    """
    Get one timestamp for <metadata><time>.
    Prefer metadata/time, otherwise use first trkpt time,
    otherwise use current UTC time.
    """
    # 1) <metadata><time>
    for meta in original_root.findall(".//{*}metadata"):
        t_el = meta.find(".//{*}time")
        if t_el is not None and t_el.text:
            return t_el.text.strip()

    # 2) first trkpt time
    for trkpt in original_root.findall(".//{*}trkpt"):
        t_el = trkpt.find(".//{*}time")
        if t_el is not None and t_el.text:
            return t_el.text.strip()

    # 3) fallback: now
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")


def extract_track_name(original_root, default_name="Activity"):
    """
    Try to get <trk><name>. If none exists, use default_name.
    """
    for trk in original_root.findall(".//{*}trk"):
        name_el = trk.find(".//{*}name")
        if name_el is not None and name_el.text:
            return name_el.text.strip()
    return default_name


# ----------------- CORE CONVERTER -----------------
def convert_gpx_to_garmin_minimal(
    input_path: str,
    output_path: str,
    default_type: str = "trail_running",
    round_coords: bool = True,
    coord_decimals: int = 8,
):
    """
    Convert a GPX file to a Garmin-style GPX, keeping ONLY:
        <trkpt lat="..." lon="..."><ele>...</ele></trkpt>

    - Reads tracks if present.
    - If no tracks, converts routes to a single track.
    - Ignores time, HR, cadence, all extensions, waypoints, etc.
    """
    tree = ET.parse(input_path)
    original_root = tree.getroot()

    # ---------- New <gpx> root ----------
    gpx_attrib = {
        "creator": "Garmin Connect",
        "version": "1.1",
        f"{{{NS_XSI}}}schemaLocation": (
            "http://www.topografix.com/GPX/1/1 "
            "http://www.topografix.com/GPX/11.xsd"
        ),
    }
    new_root = ET.Element(f"{{{NS_GPX}}}gpx", gpx_attrib)

    # ---------- <metadata> ----------
    metadata_el = ET.SubElement(new_root, f"{{{NS_GPX}}}metadata")
    link_el = ET.SubElement(metadata_el, f"{{{NS_GPX}}}link", {"href": "connect.garmin.com"})
    text_el = ET.SubElement(link_el, f"{{{NS_GPX}}}text")
    text_el.text = "Garmin Connect"

    meta_time_el = ET.SubElement(metadata_el, f"{{{NS_GPX}}}time")
    meta_time_el.text = extract_metadata_time(original_root)

    # ---------- Source: tracks or routes ----------
    original_tracks = original_root.findall(".//{*}trk")
    original_routes = original_root.findall(".//{*}rte")

    if original_tracks:
        sources = original_tracks
        use_routes = False
    elif original_routes:
        sources = original_routes
        use_routes = True
    else:
        print(f"[SKIP] No <trk> or <rte> in {os.path.basename(input_path)}")
        return

    # ---------- Build <trk> / <trkseg> / <trkpt> ----------
    for idx, src in enumerate(sources):
        trk_el = ET.SubElement(new_root, f"{{{NS_GPX}}}trk")

        # Track name & type
        trk_name = extract_track_name(original_root, default_name=f"Activity {idx + 1}")
        name_el = ET.SubElement(trk_el, f"{{{NS_GPX}}}name")
        name_el.text = trk_name

        type_el = ET.SubElement(trk_el, f"{{{NS_GPX}}}type")
        type_el.text = default_type

        if use_routes:
            # Make one segment from route points
            seg_el = ET.SubElement(trk_el, f"{{{NS_GPX}}}trkseg")
            for rtept in src.findall(".//{*}rtept"):
                lat = rtept.attrib.get("lat")
                lon = rtept.attrib.get("lon")
                if lat is None or lon is None:
                    continue

                if round_coords:
                    lat = f"{round(float(lat), coord_decimals):.{coord_decimals}f}"
                    lon = f"{round(float(lon), coord_decimals):.{coord_decimals}f}"

                trkpt_el = ET.SubElement(
                    seg_el,
                    f"{{{NS_GPX}}}trkpt",
                    {"lat": lat, "lon": lon},
                )

                ele = rtept.find(".//{*}ele")
                if ele is not None and ele.text:
                    ele_el = ET.SubElement(trkpt_el, f"{{{NS_GPX}}}ele")
                    ele_el.text = ele.text.strip()
        else:
            # Use existing track segments / points
            for orig_seg in src.findall(".//{*}trkseg"):
                seg_el = ET.SubElement(trk_el, f"{{{NS_GPX}}}trkseg")

                for orig_pt in orig_seg.findall(".//{*}trkpt"):
                    lat = orig_pt.attrib.get("lat")
                    lon = orig_pt.attrib.get("lon")
                    if lat is None or lon is None:
                        continue

                    if round_coords:
                        lat = f"{round(float(lat), coord_decimals):.{coord_decimals}f}"
                        lon = f"{round(float(lon), coord_decimals):.{coord_decimals}f}"

                    trkpt_el = ET.SubElement(
                        seg_el,
                        f"{{{NS_GPX}}}trkpt",
                        {"lat": lat, "lon": lon},
                    )

                    ele = orig_pt.find(".//{*}ele")
                    if ele is not None and ele.text:
                        ele_el = ET.SubElement(trkpt_el, f"{{{NS_GPX}}}ele")
                        ele_el.text = ele.text.strip()

    # ---------- Save ----------
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    new_tree = ET.ElementTree(new_root)
    new_tree.write(output_path, encoding="UTF-8", xml_declaration=True)

    print(f"[OK] {os.path.basename(input_path)} → {os.path.relpath(output_path, BASE_DIR)}")


# ----------------- BATCH RUNNER -----------------
def convert_folder():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    gpx_files = glob.glob(os.path.join(INPUT_DIR, "*.gpx"))

    if not gpx_files:
        print(f"No .gpx files found in {INPUT_DIR}")
        return

    print(f"Found {len(gpx_files)} file(s) in {INPUT_DIR}")
    for inp in gpx_files:
        base = os.path.splitext(os.path.basename(inp))[0]
        out = os.path.join(OUTPUT_DIR, f"{base}_garmin.gpx")
        try:
            convert_gpx_to_garmin_minimal(inp, out)
        except Exception as e:
            print(f"[ERROR] {os.path.basename(inp)}: {e}")


if __name__ == "__main__":
    convert_folder()
