import gpxpy
import gpxpy.gpx
import math
from datetime import timedelta
import matplotlib.pyplot as plt
import json
import csv

# Helper function to calculate distance between 2 lat/lon points
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # Radius of Earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# Load the GPX file
gpx_file = open('COURSE_172695633.gpx', 'r')
gpx = gpxpy.parse(gpx_file)

# Initialize metrics
total_distance = 0.0
total_elevation_gain = 0.0
total_elevation_loss = 0.0
elevations = []
times = []
distances = [0.0]
grades = []
coords = []
cumulative_gain = []
current_gain = 0.0

for track in gpx.tracks:
    for segment in track.segments:
        prev_point = None
        for point in segment.points:
            if prev_point:
                dist = haversine(prev_point.latitude, prev_point.longitude, point.latitude, point.longitude)
                total_distance += dist
                distances.append(total_distance / 1000.0)
                elev_diff = point.elevation - prev_point.elevation
                if elev_diff > 0:
                    total_elevation_gain += elev_diff
                    current_gain += elev_diff
                else:
                    total_elevation_loss -= elev_diff
                if dist > 0:
                    grade = (elev_diff / dist) * 100
                    grades.append(grade)
                cumulative_gain.append(current_gain)
            else:
                grades.append(0.0)
                cumulative_gain.append(0.0)
            elevations.append(point.elevation)
            times.append(point.time)
            coords.append((point.latitude, point.longitude))
            prev_point = point

# Derived metrics
max_elev = max(elevations)
min_elev = min(elevations)
duration = (times[-1] - times[0]) if times[0] and times[-1] else None
km_effort = total_distance/1000 + total_elevation_gain/100.0

# Output summary
print(f"Total distance: {total_distance/1000:.2f} km")
print(f"Elevation gain: {total_elevation_gain:.0f} m")
print(f"Elevation loss: {total_elevation_loss:.0f} m")
print(f"Max elevation: {max_elev:.1f} m")
print(f"Min elevation: {min_elev:.1f} m")
print(f"Km-effort: {km_effort:.1f}")
if duration:
    print(f"Total duration: {duration}")

# Save metrics to a JSON file
metrics = {
    "total_distance_km": round(total_distance / 1000, 2),
    "elevation_gain_m": round(total_elevation_gain),
    "elevation_loss_m": round(total_elevation_loss),
    "max_elevation_m": round(max_elev, 1),
    "min_elevation_m": round(min_elev, 1),
    "km_effort": round(km_effort, 1),
    "duration": str(duration) if duration else None
}

with open('dirfys_metrics.json', 'w') as f:
    json.dump(metrics, f, indent=4)

# Save route data for further analysis
with open('dirfys_route_data.csv', 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['Distance_km', 'Elevation_m', 'Grade_percent', 'Cumulative_Elevation_Gain_m', 'Latitude', 'Longitude'])
    for i in range(len(elevations)):
        writer.writerow([distances[i], elevations[i], grades[i], cumulative_gain[i], coords[i][0], coords[i][1]])

# Elevation profile
plt.figure(figsize=(12, 4))
plt.plot(distances, elevations)
plt.xlabel('Distance (km)')
plt.ylabel('Elevation (m)')
plt.title('Elevation Profile')
plt.grid(True)
plt.tight_layout()
plt.savefig('elevation_profile.png')
plt.show()

# Grade distribution histogram
plt.figure(figsize=(8, 4))
plt.hist(grades, bins=40, color='orange', edgecolor='black')
plt.xlabel('Grade (%)')
plt.ylabel('Frequency')
plt.title('Grade Distribution')
plt.grid(True)
plt.tight_layout()
plt.savefig('grade_distribution.png')
plt.show()

# Cumulative elevation gain plot
plt.figure(figsize=(12, 4))
plt.plot(distances, cumulative_gain, color='green')
plt.xlabel('Distance (km)')
plt.ylabel('Cumulative Elevation Gain (m)')
plt.title('Cumulative Elevation Gain')
plt.grid(True)
plt.tight_layout()
plt.savefig('cumulative_gain.png')
plt.show()

# Route map (2D path)
latitudes, longitudes = zip(*coords)
plt.figure(figsize=(8, 8))
plt.plot(longitudes, latitudes, color='blue')
plt.xlabel('Longitude')
plt.ylabel('Latitude')
plt.title('Route Map')
plt.grid(True)
plt.tight_layout()
plt.savefig('route_map.png')
plt.show()
